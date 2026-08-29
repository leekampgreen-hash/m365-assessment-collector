from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

from collectors.core.auth import (
    AUTH_ERROR_INVALID_CLIENT,
    CollectorAuthConfig,
    CollectorTokenProvider,
    AuthError,
)
from collectors.sharepoint_audit import collect_and_persist_sharepoint_audit
from collectors.workloads.security_service.adapters import adapt_sharepoint_audit_logs

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

class Cursor:
    def __init__(self):
        self.executions = []
        self.rowcount = 1

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        self.executions.append((sql, params))
        return self

    def fetchone(self):
        return None

class Connection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.cursor_obj = Cursor()

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

class SharePointAuditProductionPathTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)
        self.records = [
            {"Id": "invite_guest", "CreationTime": "2026-08-29T10:00:00Z", "Workload": "SharePoint", "Operation": "SharingInvitationCreated", "TargetUserOrGroupType": "Guest"},
            {"Id": "invite_internal", "CreationTime": "2026-08-29T10:01:00Z", "Workload": "SharePoint", "Operation": "SharingInvitationCreated", "TargetUserOrGroupType": "Member"},
            {"Id": "anon_created", "CreationTime": "2026-08-29T10:02:00Z", "Workload": "SharePoint", "Operation": "AnonymousLinkCreated"},
            {"Id": "anon_removed", "CreationTime": "2026-08-29T10:03:00Z", "Workload": "SharePoint", "Operation": "AnonymousLinkRemoved"},
            {"Id": "revoked", "CreationTime": "2026-08-29T10:04:00Z", "Workload": "SharePoint", "Operation": "SharingRevoked"},
            {"Id": "onedrive", "CreationTime": "2026-08-29T10:05:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"},
            {"Id": "other", "CreationTime": "2026-08-29T10:06:00Z", "Workload": "SharePoint", "Operation": "FileAccessed"},
        ]

    def test_adapter_filter_and_normalization(self):
        lineage = {"tenant_id": 2, "collected_at": self.now.isoformat(), "retention_class": "LONG"}
        rows = adapt_sharepoint_audit_logs(self.records, lineage)
        self.assertEqual(len(rows), 5)  # 5 sharepoint records, skipping onedrive and other
        ids = [r["audit_record_id"] for r in rows]
        expected = ["invite_guest", "invite_internal", "anon_created", "anon_removed", "revoked"]
        self.assertEqual(ids, expected)
        # Check flags
        self.assertTrue(rows[0]["external_flag"])   # Guest
        self.assertFalse(rows[0]["anonymous_flag"])
        self.assertFalse(rows[1]["external_flag"])  # Member
        self.assertFalse(rows[1]["anonymous_flag"])
        self.assertTrue(rows[2]["anonymous_flag"])
        self.assertTrue(rows[2]["external_flag"])
        self.assertTrue(rows[3]["anonymous_flag"])
        self.assertTrue(rows[3]["external_flag"])
        self.assertTrue(rows[4]["external_flag"])   # Revoked marked external
        self.assertFalse(rows[4]["anonymous_flag"])

    def test_fake_management_source_reaches_real_orchestration_and_duplicate_idempotent(self):
        calls = []
        def opener(request: Request, timeout=None):
            calls.append(request.full_url)
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
            if "/subscriptions/content?" in request.full_url:
                return Response([{"contentId": "content-1", "contentUri": "https://manage.office.com/blob"}])
            return Response(self.records)
        connection = Connection()
        result = collect_and_persist_sharepoint_audit(
            tenant_id=2, auth_config=CollectorAuthConfig("tenant", "app", "secret"), connection=connection,
            url_open=opener, start=self.now.replace(hour=9), end=self.now, collected_at=self.now.isoformat(),
            collection_run_id=11, endpoint_run_id=12,
        )
        self.assertEqual(result["normalized"], 5)
        self.assertEqual(result["persisted"], 5)
        self.assertEqual(result["duplicates"], 0)
        self.assertEqual(result["checkpoint_advanced"], "YES")
        self.assertEqual(connection.commits, 2)
        sql = "\n".join(statement for statement, _ in connection.cursor_obj.executions)
        self.assertIn("core.sharepoint_high_value_audit_event", sql)
        self.assertIn("collector_id", sql)
        self.assertNotIn(" source =", sql)
        self.assertTrue(any("manage.office.com" in url for url in calls))

    def test_duplicate_metrics_use_persistence_rowcount(self):
        connection = Connection()
        connection.cursor_obj.rowcount = 0

        def opener(request: Request, timeout=None):
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
            if "/subscriptions/content?" in request.full_url:
                return Response([{"contentId": "content-1", "contentUri": "https://manage.office.com/blob"}])
            return Response([self.records[0]])

        result = collect_and_persist_sharepoint_audit(
            tenant_id=2, auth_config=CollectorAuthConfig("tenant", "app", "secret"), connection=connection,
            url_open=opener, start=self.now.replace(hour=9), end=self.now, collected_at=self.now.isoformat(),
            collection_run_id=11, endpoint_run_id=12,
        )
        self.assertEqual(result["persisted"], 0)
        self.assertEqual(result["duplicates"], 1)

    def test_auth_resource_and_negative_permission_gate(self):
        seen = []
        def opener(request, timeout=None):
            seen.append(parse_qs(request.data.decode()))
            return Response({"access_token": "opaque", "expires_in": 3600})
        provider = CollectorTokenProvider(CollectorAuthConfig("tenant", "app", "secret"), http_open=opener, resource="https://manage.office.com")
        self.assertEqual(provider.resource, "https://manage.office.com")
        provider.get_token()
        self.assertEqual(seen[0]["scope"], ["https://manage.office.com/.default"])
        self.assertIn("ActivityFeed.Read", ["ActivityFeed.Read"])
        def denied(request, timeout=None):
            return Response({"error": "invalid_scope"}, status=400)
        with self.assertRaises(AuthError) as error:
            CollectorTokenProvider(CollectorAuthConfig("tenant", "app", "secret"), http_open=denied, resource="https://manage.office.com").get_token()
        self.assertEqual(error.exception.classification, AUTH_ERROR_INVALID_CLIENT)

if __name__ == "__main__":
    unittest.main()