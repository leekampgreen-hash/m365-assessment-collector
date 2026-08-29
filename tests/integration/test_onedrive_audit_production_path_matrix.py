"""OD-P07 OneDrive high-value audit PRODUCTION-PATH negative matrix (integration).

This suite validates the complete OneDrive high-value audit production path
against a bounded positive/negative matrix, using:

- FAKE Management Activity source (fake ``url_open``)
- REAL production orchestration ``collect_and_persist_onedrive_audit``
- REAL parser/filter/normalizer ``normalize_onedrive_audit_record``
- REAL ``CollectionWriter`` lifecycle (collection/endpoint runs)
- REAL PostgreSQL (authoritative ``graph_agent`` database)
- REAL ``control.collector_checkpoint``
- REAL ``core.onedrive_high_value_audit_event`` persistence

The matrix is data-driven. Synthetic tenant fixtures are used so the live
tenant's legitimate production rows are never touched. All synthetic rows and
tenant fixtures are removed in module teardown (SYNTHETIC_RESIDUE = NONE).

No production source is changed by this suite.
"""
from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request

from collectors.core.auth import CollectorAuthConfig
from collectors.core.errors import CLASSIFICATIONS
from collectors.core.models import CollectionResult
from collectors.onedrive_audit import (
    AuditTransportError,
    ManagementActivityTransport,
    collect_and_persist_onedrive_audit,
    normalize_onedrive_audit_record,
)
from collectors.persistence import (
    CollectionWriter,
    dispatch_persistence,
    get_onedrive_audit_checkpoint,
    persist_onedrive_high_value_audit_batch,
)

# --- Synthetic tenant fixtures (never collide with live tenant id=2) ------
SYN_TENANT_A = 555001
SYN_TENANT_B = 555002
SYN_TENANTS = (SYN_TENANT_A, SYN_TENANT_B)
COLLECTOR = "onedrive_audit"
OD_SPEC_ENDPOINT = "OD-AUDIT"

AUTH = CollectorAuthConfig("2ac16e52-2259-4c0f-b02b-c6a04e5246d6", "app", "secret")

OD_SPEC = None  # populated below via simple namespace


class _Spec:
    endpoint_id = OD_SPEC_ENDPOINT
    name = "OneDrive Audit.SharePoint"


OD_SPEC = _Spec()


def _runtime_password() -> str:
    p = Path("/run/secrets/graph_agent_runtime_password")
    if not p.exists():
        raise unittest.SkipTest("production database credentials are unavailable")
    return p.read_text(encoding="utf-8").strip()


def _connect(user: str, password: str):
    import psycopg
    return psycopg.connect(
        host=os.environ.get("PGHOST", "postgres"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "graph_agent"),
        user=user,
        password=password,
    )


def _bootstrap_password() -> str:
    # Host-side secret read via sudo is performed by the test driver; the
    # suite receives it through an environment variable so the container
    # (runtime role, no DELETE) does not need the bootstrap secret.
    value = os.environ.get("OD_P07_BOOTSTRAP_PASSWORD", "")
    if not value:
        raise unittest.SkipTest("OD_P07_BOOTSTRAP_PASSWORD unavailable")
    return value


class Response:
    status = 200

    def __init__(self, payload, status=200):
        self.status = status
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def classify_exception(exc) -> str:
    if isinstance(exc, AuditTransportError):
        return exc.classification
    from collectors.core.auth import AuthError
    if isinstance(exc, AuthError):
        return exc.classification
    from collectors.persistence import PersistenceError
    if isinstance(exc, PersistenceError):
        return "PERSISTENCE_ERROR"
    return "UNKNOWN"


def _default_opener(records, *, subscription="enabled", content=None, blob_status=200):
    """Return a Management Activity fake opener that returns the given records."""
    content = content if content is not None else [{
        "contentId": "content-1", "contentUri": "https://manage.office.com/blob-1",
    }]
    calls = []

    def opener(request: Request, timeout=None):
        calls.append(request.full_url)
        url = request.full_url
        if url.endswith("/token"):
            return Response({"access_token": "opaque", "expires_in": 3600})
        if url.endswith("/subscriptions/list"):
            return Response([{"contentType": "Audit.SharePoint", "status": subscription}])
        if "/subscriptions/content?" in url:
            return Response(content)
        if url.endswith("/blob-1"):
            if blob_status != 200:
                return Response([], status=blob_status)
            return Response(records)
        return Response([])
    opener.calls = calls
    return opener


class OneDriveAuditProductionPathMatrixTests(unittest.TestCase):
    """Data-driven production-path negative matrix against real PostgreSQL."""

    @classmethod
    def setUpClass(cls):
        cls.bootstrap = _connect("graph_agent_bootstrap", _bootstrap_password())
        cls.runtime = _connect("graph_agent_runtime", _runtime_password())
        cls.bootstrap.autocommit = True
        cls.runtime.autocommit = False
        cur = cls.bootstrap.cursor()
        for tid in SYN_TENANTS:
            cur.execute(
                "INSERT INTO core.tenant (tenant_id, entra_tenant_id, display_label, enabled, retention_class) "
                "VALUES (%s, %s, %s, TRUE, 'REFERENCE') "
                "ON CONFLICT (tenant_id) DO NOTHING",
                (tid, "synthetic-{:06d}".format(tid), "OD-P07 synthetic tenant {}".format(tid)),
            )
        # baseline row counts for synthetic tenants (must be zero)
        cls.baseline = {}
        for tid in SYN_TENANTS:
            cur.execute("SELECT count(*) FROM core.onedrive_high_value_audit_event WHERE tenant_id=%s", (tid,))
            cls.baseline[tid] = cur.fetchone()[0]

    @classmethod
    def tearDownClass(cls):
        cur = cls.bootstrap.cursor()
        cur.execute(
            "DELETE FROM core.onedrive_high_value_audit_event WHERE tenant_id = ANY(%s)",
            (list(SYN_TENANTS),),
        )
        cur.execute(
            "DELETE FROM control.collector_checkpoint WHERE tenant_id = ANY(%s)",
            (list(SYN_TENANTS),),
        )
        # endpoint_run cascades on collection_run delete
        cur.execute(
            "DELETE FROM control.collection_run WHERE tenant_id = ANY(%s)",
            (list(SYN_TENANTS),),
        )
        cur.execute("DELETE FROM core.tenant WHERE tenant_id = ANY(%s)", (list(SYN_TENANTS),))
        cls.bootstrap.close()
        cls.runtime.close()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _runtime_conn(self):
        return _connect("graph_agent_runtime", _runtime_password())

    def _bootstrap_conn(self):
        return _connect("graph_agent_bootstrap", _bootstrap_password())

    def _orchestrate(self, tenant_id, opener, *, start=None, end=None, collected_at=None,
                     dry_run=False, connection=None, expect_raise=False, fake_conn=None):
        """Drive the REAL production lifecycle end to end.

        Returns a dict with metrics, run ids, captured classification and
        exception, and the connection used.
        """
        end = end or datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        start = start or (end.replace(hour=8))
        collected_at = collected_at or end.isoformat()
        conn = fake_conn if fake_conn is not None else (connection or self._runtime_conn())
        writer = CollectionWriter(conn, dispatch_persistence)
        collection_run_id = writer.begin_collection_run(tenant_id=tenant_id, endpoint_ids=[OD_SPEC_ENDPOINT])
        endpoint_run_id = writer.begin_endpoint_run(collection_run_id=collection_run_id, tenant_id=tenant_id, spec=OD_SPEC)
        classification = None
        exc = None
        metrics = None
        try:
            metrics = collect_and_persist_onedrive_audit(
                tenant_id=tenant_id, auth_config=AUTH, connection=conn,
                url_open=opener, start=start, end=end, collected_at=collected_at,
                collection_run_id=collection_run_id, endpoint_run_id=endpoint_run_id,
                dry_run=dry_run,
            )
            result = CollectionResult(
                endpoint_id=OD_SPEC_ENDPOINT, status="PASS",
                rows=metrics["normalized"], persisted_rows=metrics["persisted"],
            )
        except Exception as e:
            exc = e
            classification = classify_exception(e)
            record_cls = classification if classification in CLASSIFICATIONS else "API_ERROR"
            result = CollectionResult(
                endpoint_id=OD_SPEC_ENDPOINT, status="ERROR", error_classification=record_cls,
            )
        finally:
            writer.complete_endpoint_run(endpoint_run_id=endpoint_run_id, result=result)
            writer.complete_collection_run(collection_run_id=collection_run_id, results=[result])
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                if fake_conn is not None:
                    fake_conn._inner.close()
                elif connection is None:
                    conn.close()
            except Exception:
                pass
        return {
            "metrics": metrics,
            "collection_run_id": collection_run_id,
            "endpoint_run_id": endpoint_run_id,
            "classification": classification,
            "exc": exc,
            "conn": conn,
        }

    def _count_business(self, tenant_id, bootstrap=None):
        cur = (bootstrap or self._bootstrap_conn()).cursor()
        cur.execute("SELECT count(*) FROM core.onedrive_high_value_audit_event WHERE tenant_id=%s", (tenant_id,))
        return cur.fetchone()[0]

    def _query_business(self, tenant_id, audit_id, bootstrap=None):
        cur = (bootstrap or self._bootstrap_conn()).cursor()
        cur.execute(
            "SELECT audit_record_id, operation, event_category, external_flag, anonymous_flag, "
            "collection_run_id, endpoint_run_id, tenant_id "
            "FROM core.onedrive_high_value_audit_event WHERE tenant_id=%s AND audit_record_id=%s",
            (tenant_id, audit_id),
        )
        return cur.fetchall()

    def _checkpoint(self, tenant_id, conn=None):
        conn = conn or self._bootstrap_conn()
        return get_onedrive_audit_checkpoint(conn, tenant_id=tenant_id)

    # ------------------------------------------------------------------ #
    # 2. POSITIVE MATRIX
    # ------------------------------------------------------------------ #
    def test_positive_matrix_anonymous_guest_malware(self):
        records = [
            {"Id": "OD-ANON", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"},
            {"Id": "OD-GUEST", "CreationTime": "2026-09-01T10:01:00Z", "Workload": "OneDrive", "Operation": "SharingInvitationCreated", "TargetUserOrGroupType": "Guest", "TargetUserOrGroupName": "g@external.invalid"},
            {"Id": "OD-MALWARE", "CreationTime": "2026-09-01T10:02:00Z", "Workload": "OneDrive", "Operation": "FileMalwareDetected", "SourceFileName": "bad.exe"},
        ]
        opener = _default_opener(records)
        before = self._count_business(SYN_TENANT_A)
        out = self._orchestrate(SYN_TENANT_A, opener)
        self.assertIsNone(out["classification"], "positive run must not fail")
        m = out["metrics"]
        self.assertEqual(m["onedrive_records"], 3)
        self.assertEqual(m["high_value_candidates"], 3)
        self.assertEqual(m["normalized"], 3)
        self.assertEqual(m["persisted"], 3)
        self.assertEqual(m["duplicates"], 0)
        self.assertEqual(m["checkpoint_advanced"], "YES")

        boot = self._bootstrap_conn()
        anon = self._query_business(SYN_TENANT_A, "OD-ANON", boot)
        self.assertEqual(len(anon), 1)
        self.assertEqual(anon[0][2], "EXTERNAL_SHARING")
        self.assertEqual(anon[0][3], True)   # external
        self.assertEqual(anon[0][4], True)   # anonymous
        guest = self._query_business(SYN_TENANT_A, "OD-GUEST", boot)
        self.assertEqual(len(guest), 1)
        self.assertEqual(guest[0][2], "EXTERNAL_SHARING")
        self.assertEqual(guest[0][3], True)
        self.assertEqual(guest[0][4], False)  # not anonymous
        mal = self._query_business(SYN_TENANT_A, "OD-MALWARE", boot)
        self.assertEqual(len(mal), 1)
        self.assertEqual(mal[0][2], "MALWARE_DETECTED")
        self.assertEqual(mal[0][3], False)
        self.assertEqual(mal[0][4], False)
        # lineage populated
        for row in (anon[0], guest[0], mal[0]):
            self.assertIsNotNone(row[5])
            self.assertIsNotNone(row[6])
            self.assertEqual(row[7], SYN_TENANT_A)
        # exactly one business row each, tenant correct
        self.assertEqual(self._count_business(SYN_TENANT_A, boot), before + 3)

    # ------------------------------------------------------------------ #
    # 3. SAFE-DROP MATRIX
    # ------------------------------------------------------------------ #
    def test_safe_drop_matrix(self):
        cases = {
            "sharepoint_external": {
                "Id": "SP-ANON", "CreationTime": "2026-09-01T10:00:00Z",
                "Workload": "SharePoint", "Operation": "AnonymousLinkCreated",
            },
            "internal_member": {
                "Id": "OD-MEMBER", "CreationTime": "2026-09-01T10:01:00Z",
                "Workload": "OneDrive", "Operation": "SharingInvitationCreated",
                "TargetUserOrGroupType": "Member",
            },
            "ambiguous_sharing": {
                "Id": "OD-AMBIG", "CreationTime": "2026-09-01T10:02:00Z",
                "Workload": "OneDrive", "Operation": "SharingSet",
                "TargetUserOrGroupType": None,
            },
            "secure_link_alone": {
                "Id": "OD-SECURE", "CreationTime": "2026-09-01T10:03:00Z",
                "Workload": "OneDrive", "Operation": "SecureLinkCreated",
            },
            "unrelated_onedrive": {
                "Id": "OD-UNREL", "CreationTime": "2026-09-01T10:04:00Z",
                "Workload": "OneDrive", "Operation": "FileModified",
            },
            "generic_activity": {
                "Id": "OD-GENERIC", "CreationTime": "2026-09-01T10:05:00Z",
                "Workload": "OneDrive", "Operation": "FileDownloaded",
            },
        }
        records = list(cases.values())
        opener = _default_opener(records)
        before = self._count_business(SYN_TENANT_A)
        out = self._orchestrate(SYN_TENANT_A, opener)
        self.assertIsNone(out["classification"], "safe-drop run must succeed")
        m = out["metrics"]
        # --- BUSINESS OUTCOME (the safe-drop contract): all six must NOT persist ---
        self.assertEqual(m["onedrive_records"], 5)  # 5 OneDrive workload records
        self.assertEqual(m["high_value_candidates"], 0)
        self.assertEqual(m["normalized"], 0)
        self.assertEqual(m["persisted"], 0)
        self.assertEqual(self._count_business(SYN_TENANT_A), before)  # no business persistence
        self.assertEqual(m["checkpoint_advanced"], "YES")  # successful source processing advances

        # --- OBSERVABILITY / CLASSIFICATION CONTRACT (OD-P07 section 3): ---
        # These six are intentionally DROPPED as out-of-scope and must NOT be
        # counted as malformed. Current production counts Member + ambiguous
        # sharing (OneDrive operations in the locked set that fail the Guest
        # proof) as `malformed_records` instead of `records_dropped_out_of_scope`.
        # This assertion FAILS on current production and is the reproduction of
        # a REAL DEFECT (see evidence OD-P07). Expected-by-contract values:
        self.assertEqual(m["records_dropped_out_of_scope"], 6)
        self.assertEqual(m["malformed_records"], 0)

    # ------------------------------------------------------------------ #
    # 4. MALFORMED LOCKED-CANDIDATE MATRIX
    # ------------------------------------------------------------------ #
    def test_malformed_locked_candidate_matrix(self):
        base = {"Id": "OD-X", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        # Records that ARE deterministically high-value candidates (Workload=OneDrive,
        # Operation in locked set) but are missing authoritative required fields.
        malformed_cases = {
            "missing_id": {**base, "Id": None, "Operation": "AnonymousLinkCreated"},
            "missing_time": {**base, "CreationTime": None, "Operation": "AnonymousLinkCreated"},
            "invalid_candidate": {**base, "Id": "", "CreationTime": "not-a-date", "Operation": "SharingInvitationCreated", "TargetUserOrGroupType": "Guest"},
        }
        before = self._count_business(SYN_TENANT_A)
        # Normalizer level: locked candidates missing authoritative fields raise SCHEMA_CONTRACT_FAILURE
        for name, record in malformed_cases.items():
            with self.subTest(case=name):
                self.assertIn(record["Operation"], {"AnonymousLinkCreated", "SharingInvitationCreated"})
                try:
                    normalize_onedrive_audit_record(record, SYN_TENANT_A, "2026-09-01T12:00:00Z")
                    self.fail("malformed locked candidate must not normalize silently: " + name)
                except AuditTransportError as e:
                    self.assertEqual(e.classification, "SCHEMA_CONTRACT_FAILURE")
                except Exception:
                    self.fail("unexpected exception type for " + name)
        # Orchestration level: each malformed candidate as the sole source record
        for name, record in malformed_cases.items():
            with self.subTest(orchestration=name):
                cp_before = self._checkpoint(SYN_TENANT_A)
                opener = _default_opener([record])
                out = self._orchestrate(SYN_TENANT_A, opener, expect_raise=True)
                self.assertEqual(out["classification"], "SCHEMA_CONTRACT_FAILURE")
                # no invalid business row
                self.assertEqual(self._count_business(SYN_TENANT_A), before)
                # checkpoint unchanged (no persistence, no advance)
                self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before)

        # Missing Workload: locked OD-P03 fail-closed rule EXCLUDES the record
        # (no heuristic routing), so it is safely dropped out of scope, NOT
        # persisted, and the run still advances checkpoint as a safe-drop run.
        missing_workload = {**base, "Workload": None, "Operation": "AnonymousLinkCreated"}
        self.assertIsNone(normalize_onedrive_audit_record(missing_workload, SYN_TENANT_A, "2026-09-01T12:00:00Z"))
        opener = _default_opener([missing_workload])
        out = self._orchestrate(SYN_TENANT_A, opener)
        self.assertIsNone(out["classification"], "missing-workload is a safe drop, not a failure")
        self.assertEqual(out["metrics"]["persisted"], 0)
        self.assertEqual(out["metrics"]["records_dropped_out_of_scope"], 1)
        self.assertEqual(self._count_business(SYN_TENANT_A), before)
        self.assertEqual(out["metrics"]["checkpoint_advanced"], "YES")

    # ------------------------------------------------------------------ #
    # 5. AUTH FAILURE
    # ------------------------------------------------------------------ #
    def test_auth_failure(self):
        def denied(request, timeout=None):
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([], status=403)
            return Response([])
        before = self._count_business(SYN_TENANT_A)
        cp_before = self._checkpoint(SYN_TENANT_A)
        out = self._orchestrate(SYN_TENANT_A, denied)
        self.assertEqual(out["classification"], "PERMISSION_REQUIRED")
        # no business persistence
        self.assertEqual(self._count_business(SYN_TENANT_A), before)
        # checkpoint unchanged
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before)
        # lifecycle reflects failure
        self._assert_run_state(out["collection_run_id"], out["endpoint_run_id"], "FAILED", "ERROR")

    # ------------------------------------------------------------------ #
    # 6. SUBSCRIPTION FAILURE
    # ------------------------------------------------------------------ #
    def test_subscription_failure(self):
        opener = _default_opener([], subscription="disabled")
        before = self._count_business(SYN_TENANT_A)
        cp_before = self._checkpoint(SYN_TENANT_A)
        out = self._orchestrate(SYN_TENANT_A, opener)
        self.assertEqual(out["classification"], "SUBSCRIPTION_UNAVAILABLE")
        self.assertEqual(self._count_business(SYN_TENANT_A), before)
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before)
        # lifecycle reflects failure (control recorded via API_ERROR workaround;
        # true classification proven at orchestration boundary)
        self._assert_run_state(out["collection_run_id"], out["endpoint_run_id"], "FAILED", "ERROR")

    # ------------------------------------------------------------------ #
    # 7. SOURCE / TRANSPORT FAILURE (one representative per class)
    # ------------------------------------------------------------------ #
    def test_source_failure_retry_exhaustion(self):
        # repeated 5xx -> RETRY_EXHAUSTED before complete processing
        class Blob503:
            status = 503
            def read(self):
                return b"[]"
        def fail_after_attempts(attempt):
            state = {"n": 0}
            def opener(request, timeout=None):
                if request.full_url.endswith("/token"):
                    return Response({"access_token": "opaque", "expires_in": 3600})
                if request.full_url.endswith("/subscriptions/list"):
                    return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
                if "/subscriptions/content?" in request.full_url:
                    return Response([{"contentId": "content-1", "contentUri": "https://manage.office.com/blob-1"}])
                if request.full_url.endswith("/blob-1"):
                    state["n"] += 1
                    if state["n"] <= attempt:
                        return Response([], status=503)
                    return Response([{"Id": "OD-LATE", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}])
                return Response([])
            return opener
        # exhaustion: blob always 503
        opener = fail_after_attempts(999)
        before = self._count_business(SYN_TENANT_A)
        cp_before = self._checkpoint(SYN_TENANT_A)
        out = self._orchestrate(SYN_TENANT_A, opener)
        self.assertEqual(out["classification"], "RETRY_EXHAUSTED")
        self.assertEqual(self._count_business(SYN_TENANT_A), before)
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before)
        self._assert_run_state(out["collection_run_id"], out["endpoint_run_id"], "FAILED", "ERROR")

    def test_source_failure_malformed_content_blob(self):
        # blob is not an array -> SCHEMA_CONTRACT_FAILURE
        def malformed(request, timeout=None):
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
            if "/subscriptions/content?" in request.full_url:
                return Response([{"contentId": "content-1", "contentUri": "https://manage.office.com/blob-1"}])
            if request.full_url.endswith("/blob-1"):
                return Response({"not": "an array"})
            return Response([])
        before = self._count_business(SYN_TENANT_A)
        cp_before = self._checkpoint(SYN_TENANT_A)
        out = self._orchestrate(SYN_TENANT_A, malformed)
        self.assertEqual(out["classification"], "SCHEMA_CONTRACT_FAILURE")
        self.assertEqual(self._count_business(SYN_TENANT_A), before)
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before)

    def test_source_failure_before_complete_processing(self):
        # content listing contains two blobs; first is healthy, second 503 forever
        def partial(request, timeout=None):
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
            if "/subscriptions/content?" in request.full_url:
                return Response([
                    {"contentId": "content-1", "contentUri": "https://manage.office.com/blob-1"},
                    {"contentId": "content-2", "contentUri": "https://manage.office.com/blob-2"},
                ])
            if request.full_url.endswith("/blob-1"):
                return Response([{"Id": "OD-PART", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}])
            if request.full_url.endswith("/blob-2"):
                return Response([], status=503)
            return Response([])
        before = self._count_business(SYN_TENANT_A)
        cp_before = self._checkpoint(SYN_TENANT_A)
        out = self._orchestrate(SYN_TENANT_A, partial)
        self.assertEqual(out["classification"], "RETRY_EXHAUSTED")
        # no false SUCCESS, no over-advance
        self.assertEqual(self._count_business(SYN_TENANT_A), before)
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before)
        # already legitimate committed rows remain replay-safe (none inserted here)

    # ------------------------------------------------------------------ #
    # 8. PERSISTENCE FAILURE
    # ------------------------------------------------------------------ #
    def test_persistence_failure(self):
        records = [
            {"Id": "OD-PERSIST", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"},
        ]
        opener = _default_opener(records)
        before = self._count_business(SYN_TENANT_A)
        cp_before = self._checkpoint(SYN_TENANT_A)
        # wrap runtime connection with deterministic batch-INSERT fault injection
        runtime = self._runtime_conn()
        out = self._orchestrate(SYN_TENANT_A, opener, fake_conn=_FailBatchConnection(runtime))
        self.assertEqual(out["classification"], "PERSISTENCE_ERROR")
        # no partial invalid business transaction committed
        self.assertEqual(self._count_business(SYN_TENANT_A), before)
        # checkpoint unchanged
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before)
        self._assert_run_state(out["collection_run_id"], out["endpoint_run_id"], "FAILED", "ERROR")

    # ------------------------------------------------------------------ #
    # 9. DUPLICATE / REPLAY MATRIX
    # ------------------------------------------------------------------ #
    def test_duplicate_replay_matrix(self):
        anon = {"Id": "OD-DUP", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        # A. same audit Id twice in same blob -> one row
        opener = _default_opener([anon, dict(anon)])
        out = self._orchestrate(SYN_TENANT_A, opener)
        self.assertEqual(out["metrics"]["normalized"], 2)
        self.assertEqual(out["metrics"]["persisted"], 1)
        self.assertEqual(out["metrics"]["duplicates"], 1)
        # exactly one business row for this audit id despite two occurrences
        self._assert_business_count_for(SYN_TENANT_A, "OD-DUP", 1)

    def test_duplicate_replay_cross_blob_and_overlap(self):
        anon = {"Id": "OD-DUP2", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        # B. same audit Id across two blobs
        def two_blobs(request, timeout=None):
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
            if "/subscriptions/content?" in request.full_url:
                return Response([
                    {"contentId": "content-1", "contentUri": "https://manage.office.com/blob-1"},
                    {"contentId": "content-2", "contentUri": "https://manage.office.com/blob-2"},
                ])
            if request.full_url.endswith("/blob-1"):
                return Response([anon])
            if request.full_url.endswith("/blob-2"):
                return Response([dict(anon)])
            return Response([])
        out = self._orchestrate(SYN_TENANT_A, two_blobs)
        self.assertEqual(out["metrics"]["persisted"], 1)
        self.assertEqual(out["metrics"]["duplicates"], 1)
        self._assert_business_count_for(SYN_TENANT_A, "OD-DUP2", 1)

    def test_duplicate_replay_overlap_runs(self):
        anon = {"Id": "OD-DUP3", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        # first run inserts
        out1 = self._orchestrate(SYN_TENANT_A, _default_opener([anon]), end=datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(out1["metrics"]["persisted"], 1)
        # second overlapping run with checkpoint overlap re-delivers same id -> duplicate skip
        out2 = self._orchestrate(SYN_TENANT_A, _default_opener([dict(anon)]), end=datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(out2["metrics"]["persisted"], 0)
        self.assertEqual(out2["metrics"]["duplicates"], 1)
        self._assert_business_count_for(SYN_TENANT_A, "OD-DUP3", 1)

    def test_distinct_ids_same_timestamp(self):
        # D. same timestamp/object but different audit IDs -> two events
        base = {"CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        opener = _default_opener([{**base, "Id": "OD-DA"}, {**base, "Id": "OD-DB"}])
        out = self._orchestrate(SYN_TENANT_A, opener)
        self.assertEqual(out["metrics"]["persisted"], 2)
        # two independent business events despite same timestamp/object
        self._assert_business_count_for(SYN_TENANT_A, "OD-DA", 1)
        self._assert_business_count_for(SYN_TENANT_A, "OD-DB", 1)

    def test_late_arrival_during_overlap(self):
        # E. unseen older event during overlap -> INSERT
        old = {"Id": "OD-OLD", "CreationTime": "2026-08-31T22:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        new = {"Id": "OD-NEW", "CreationTime": "2026-09-01T10:30:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        # establish checkpoint at 12:00 with a run
        opener = _default_opener([new], content=[{"contentId": "c1", "contentUri": "https://manage.office.com/blob-1"}])
        out1 = self._orchestrate(SYN_TENANT_A, opener, end=datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(out1["metrics"]["persisted"], 1)
        # overlapping next run (checkpoint - 2h overlap) delivers the older unseen id
        opener2 = _default_opener([old], content=[{"contentId": "c2", "contentUri": "https://manage.office.com/blob-1"}])
        out2 = self._orchestrate(SYN_TENANT_A, opener2, end=datetime(2026, 9, 1, 13, tzinfo=timezone.utc))
        self.assertEqual(out2["metrics"]["persisted"], 1)
        self._assert_business_count_for(SYN_TENANT_A, "OD-OLD", 1)

    # ------------------------------------------------------------------ #
    # 10. TENANT ISOLATION
    # ------------------------------------------------------------------ #
    def test_tenant_isolation(self):
        anon_a = {"Id": "OD-SAME-ID", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        # same audit_record_id inserted for two different tenants
        out_a = self._orchestrate(SYN_TENANT_A, _default_opener([dict(anon_a)]), end=datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
        out_b = self._orchestrate(SYN_TENANT_B, _default_opener([dict(anon_a)]), end=datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(out_a["metrics"]["persisted"], 1)
        self.assertEqual(out_b["metrics"]["persisted"], 1)
        boot = self._bootstrap_conn()
        rows_a = self._query_business(SYN_TENANT_A, "OD-SAME-ID", boot)
        rows_b = self._query_business(SYN_TENANT_B, "OD-SAME-ID", boot)
        self.assertEqual(len(rows_a), 1)
        self.assertEqual(len(rows_b), 1)
        # tenant-scoped lineage
        self.assertEqual(rows_a[0][7], SYN_TENANT_A)
        self.assertEqual(rows_b[0][7], SYN_TENANT_B)
        # one tenant's checkpoint cannot regress/advance another's
        self._set_checkpoint(SYN_TENANT_A, datetime(2026, 9, 1, 11, tzinfo=timezone.utc))
        cp_a = self._checkpoint(SYN_TENANT_A)
        cp_b_before = self._checkpoint(SYN_TENANT_B)
        # advance tenant B beyond A; A must remain unchanged
        self._set_checkpoint(SYN_TENANT_B, datetime(2026, 9, 1, 13, tzinfo=timezone.utc))
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_a)
        self.assertNotEqual(self._checkpoint(SYN_TENANT_B), cp_b_before)

    def _set_checkpoint(self, tenant_id, dt):
        from collectors.persistence import advance_onedrive_audit_checkpoint
        conn = self._bootstrap_conn()
        advance_onedrive_audit_checkpoint(conn, tenant_id=tenant_id, checkpoint_at=dt)
        conn.close()

    # ------------------------------------------------------------------ #
    # 11. RUN LIFECYCLE + 12. CHECKPOINT MATRIX
    # ------------------------------------------------------------------ #
    def _assert_run_state(self, collection_run_id, endpoint_run_id, col_status, ep_status):
        boot = self._bootstrap_conn()
        cur = boot.cursor()
        cur.execute("SELECT status FROM control.collection_run WHERE collection_run_id=%s", (collection_run_id,))
        self.assertEqual(cur.fetchone()[0], col_status)
        cur.execute("SELECT status, error_classification FROM control.endpoint_run WHERE endpoint_run_id=%s", (endpoint_run_id,))
        row = cur.fetchone()
        self.assertEqual(row[0], ep_status)
        return row[1]

    def test_run_lifecycle_and_checkpoint_matrix(self):
        # Use a dedicated fresh tenant so the checkpoint matrix starts clean
        # (SYN_TENANT_B checkpoint is None at this point in the run order).
        tid = SYN_TENANT_B
        anon = {"Id": "OD-LIFE", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        end = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
        # --- SUCCESS run advances checkpoint (None -> 12:00) ---
        cp_before = self._checkpoint(tid)
        self.assertIsNone(cp_before, "expected fresh checkpoint for checkpoint matrix tenant")
        out = self._orchestrate(tid, _default_opener([dict(anon)]), end=end)
        self.assertIsNone(out["classification"])
        self._assert_run_state(out["collection_run_id"], out["endpoint_run_id"], "SUCCESS", "PASS")
        self.assertIsNotNone(self._checkpoint(tid))
        self.assertEqual(self._checkpoint(tid), end)

        # --- out-of-scope-only run advances checkpoint (12:00 -> 12:00 next run) ---
        cp_before = self._checkpoint(tid)
        out = self._orchestrate(tid, _default_opener([{"Id": "SP-1", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "SharePoint", "Operation": "AnonymousLinkCreated"}]), end=end)
        self.assertIsNone(out["classification"])
        self._assert_run_state(out["collection_run_id"], out["endpoint_run_id"], "SUCCESS", "PASS")
        self.assertEqual(out["metrics"]["checkpoint_advanced"], "YES")
        self.assertEqual(self._checkpoint(tid), end)

        # --- duplicate-only run advances checkpoint ---
        out = self._orchestrate(tid, _default_opener([dict(anon)]), end=end)
        self.assertIsNone(out["classification"])
        self.assertEqual(out["metrics"]["persisted"], 0)
        self.assertEqual(out["metrics"]["duplicates"], 1)
        self.assertEqual(out["metrics"]["checkpoint_advanced"], "YES")

    def test_checkpoint_no_advance_on_failures(self):
        anon = {"Id": "OD-CP", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"}
        end = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)

        def denied(request, timeout=None):
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([], status=403)
            return Response([])

        scenarios = {
            "auth_failure": denied,
            "subscription_failure": _default_opener([], subscription="disabled"),
            "schema_failure": _default_opener([{**anon, "Id": None}]),
            "source_failure": _default_opener([dict(anon)]),  # handled below via 503
            "persistence_failure": None,  # handled below via fault injection
        }
        for name, opener in scenarios.items():
            with self.subTest(name=name):
                self._checkpoint_for_no_advance(name, opener, end, anon)

    def _checkpoint_for_no_advance(self, name, opener, end, anon):
        if name == "source_failure":
            def source503(request, timeout=None):
                if request.full_url.endswith("/token"):
                    return Response({"access_token": "opaque", "expires_in": 3600})
                if request.full_url.endswith("/subscriptions/list"):
                    return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
                if "/subscriptions/content?" in request.full_url:
                    return Response([{"contentId": "c", "contentUri": "https://manage.office.com/blob-1"}])
                if request.full_url.endswith("/blob-1"):
                    return Response([], status=503)
                return Response([])
            opener = source503
        cp_before = self._checkpoint(SYN_TENANT_A)
        before = self._count_business(SYN_TENANT_A)
        if name == "persistence_failure":
            runtime = self._runtime_conn()
            out = self._orchestrate(SYN_TENANT_A, _default_opener([dict(anon)]), fake_conn=_FailBatchConnection(runtime), end=end)
        else:
            out = self._orchestrate(SYN_TENANT_A, opener, end=end)
        self.assertIsNotNone(out["classification"], name)
        # checkpoint unchanged
        self.assertEqual(self._checkpoint(SYN_TENANT_A), cp_before, name)
        # no business rows added
        self.assertEqual(self._count_business(SYN_TENANT_A), before, name)

    # ------------------------------------------------------------------ #
    # 13. OBSERVABILITY SANITY
    # ------------------------------------------------------------------ #
    def test_observability_distinguishes_counts(self):
        records = [
            {"Id": "OD-A", "CreationTime": "2026-09-01T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"},
            {"Id": "OD-B", "CreationTime": "2026-09-01T10:01:00Z", "Workload": "OneDrive", "Operation": "SharingInvitationCreated", "TargetUserOrGroupType": "Guest"},
            {"Id": "SP-1", "CreationTime": "2026-09-01T10:02:00Z", "Workload": "SharePoint", "Operation": "AnonymousLinkCreated"},
            {"Id": "OD-GEN", "CreationTime": "2026-09-01T10:03:00Z", "Workload": "OneDrive", "Operation": "FileAccessed"},
        ]
        out = self._orchestrate(SYN_TENANT_A, _default_opener(records))
        m = out["metrics"]
        self.assertEqual(m["records_parsed"], 4)
        self.assertEqual(m["onedrive_records"], 3)
        self.assertEqual(m["high_value_candidates"], 2)
        self.assertEqual(m["normalized"], 2)
        self.assertEqual(m["persisted"], 2)
        self.assertEqual(m["duplicates"], 0)
        self.assertEqual(m["records_dropped_out_of_scope"], 2)
        self.assertEqual(m["malformed_records"], 0)
        self.assertIsNotNone(m["checkpoint_before"])
        self.assertIsNotNone(m["checkpoint_after"])
        self.assertEqual(m["checkpoint_advanced"], "YES")
        self.assertIn("retries", m)

    # ------------------------------------------------------------------ #
    # helpers for assertions
    # ------------------------------------------------------------------ #
    def _assert_business_count_for(self, tenant_id, audit_id, expected, bootstrap=None):
        rows = self._query_business(tenant_id, audit_id, bootstrap)
        self.assertEqual(len(rows), expected, "expected {} business rows for {} tenant {}".format(expected, audit_id, tenant_id))


class _FailBatchConnection:
    """Deterministic fault injection at the production batch INSERT boundary."""

    def __init__(self, inner):
        self._inner = inner

    def cursor(self):
        return _FailBatchCursor(self._inner.cursor())

    def commit(self):
        self._inner.commit()

    def rollback(self):
        self._inner.rollback()


class _FailBatchCursor:
    def __init__(self, inner):
        self._inner = inner

    @property
    def rowcount(self):
        return self._inner.rowcount

    def execute(self, sql, params=None):
        if "INSERT INTO core.onedrive_high_value_audit_event" in sql:
            raise RuntimeError("injected batch persistence failure")
        return self._inner.execute(sql, params)

    def fetchone(self):
        return self._inner.fetchone()

    def fetchall(self):
        return self._inner.fetchall()


if __name__ == "__main__":
    unittest.main()
