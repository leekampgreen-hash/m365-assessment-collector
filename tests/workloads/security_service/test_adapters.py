"""Offline unit tests for the G07-B security / governance / service-health
workload adapters.

These tests must:

  * run with no Microsoft Graph traffic and no token acquisition;
  * never persist or assert on bearer / authorization strings;
  * assert behaviour for all 9 assigned endpoints;
  * cover event-source separation between G01-005 and G01-006;
  * cover current / snapshot generation for G01-011 / G01-013 / G01-015;
  * cover current / versioned-history generation for G01-016 / G01-017;
  * assert deterministic, stable ``version_identity`` behaviour;
  * assert null / missing-field handling;
  * assert deterministic output across repeated invocations.
"""
from __future__ import annotations

import copy
import unittest
from typing import Any, Dict, List, Mapping, Optional

from collectors.workloads.security_service import (
    DEFAULT_LINEAGE,
    ENDPOINT_TABLE_MAP,
    EVENT_SOURCE_DIRECTORY_AUDIT,
    EVENT_SOURCE_SIGN_IN,
    Lineage,
    adapt_directory_audit_logs,
    adapt_named_locations,
    adapt_risk_detections,
    adapt_risky_users,
    adapt_service_health_issues,
    adapt_service_health_overview,
    adapt_service_update_messages,
    adapt_sign_in_logs,
    compute_version_identity,
    conditional_access_policies,
    fallback_version_identity,
    lineage_from_mapping,
    named_locations,
    normalize_lineage,
    primary_version_identity,
    risky_users,
    service_health_issues,
    service_health_overview,
    service_update_messages,
)


SENSITIVE_TOKENS = (
    "secret-token-DO-NOT-LEAK",
    "Bearer abc.def.ghi",
    "Authorization: Bearer abc.def.ghi",
)


# ---------------------------------------------------------------------------
# Reusable fixtures
# ---------------------------------------------------------------------------


def make_lineage(**overrides: Any) -> Lineage:
    base: Dict[str, Any] = dict(
        tenant_id=42,
        collection_run_id=1001,
        endpoint_run_id=2002,
        collected_at="2026-08-20T12:00:00Z",
        retention_class="STANDARD",
    )
    base.update(overrides)
    return Lineage(**base)


# ---------------------------------------------------------------------------
# Package-level tests
# ---------------------------------------------------------------------------


class PackageSurfaceTests(unittest.TestCase):
    """The package exposes a stable surface and does not import
    credential-bearing modules."""

    def test_endpoint_table_map_covers_all_assigned_endpoints(self):
        expected = {
            "G01-005",
            "G01-006",
            "G01-011",
            "G01-012",
            "G01-013",
            "G01-014",
            "G01-015",
            "G01-016",
            "G01-017",
        }
        self.assertEqual(set(ENDPOINT_TABLE_MAP.keys()), expected)

    def test_endpoint_table_map_declares_event_source_for_audit_endpoints(self):
        self.assertEqual(
            ENDPOINT_TABLE_MAP["G01-005"]["event_source"],
            EVENT_SOURCE_DIRECTORY_AUDIT,
        )
        self.assertEqual(
            ENDPOINT_TABLE_MAP["G01-006"]["event_source"],
            EVENT_SOURCE_SIGN_IN,
        )
        self.assertEqual(
            ENDPOINT_TABLE_MAP["G01-005"]["current_table"],
            ENDPOINT_TABLE_MAP["G01-006"]["current_table"],
        )

    def test_endpoint_table_map_snapshot_history_targets(self):
        # G01-011 / G01-013 / G01-015 -> snapshot table only
        for endpoint_id in ("G01-011", "G01-013", "G01-015"):
            entry = ENDPOINT_TABLE_MAP[endpoint_id]
            self.assertTrue(entry["snapshot_table"].endswith("_snapshot"), entry)
            self.assertIsNone(entry["history_table"])
        # G01-016 / G01-017 -> history table only
        for endpoint_id in ("G01-016", "G01-017"):
            entry = ENDPOINT_TABLE_MAP[endpoint_id]
            self.assertTrue(entry["history_table"].endswith("_history"), entry)
            self.assertIsNone(entry["snapshot_table"])
        # G01-005 / G01-006 / G01-014 -> neither
        for endpoint_id in ("G01-005", "G01-006", "G01-014"):
            entry = ENDPOINT_TABLE_MAP[endpoint_id]
            self.assertIsNone(entry["snapshot_table"])
            self.assertIsNone(entry["history_table"])
        # G01-012 -> neither
        entry = ENDPOINT_TABLE_MAP["G01-012"]
        self.assertIsNone(entry["snapshot_table"])
        self.assertIsNone(entry["history_table"])


# ---------------------------------------------------------------------------
# Lineage tests
# ---------------------------------------------------------------------------


class LineageTests(unittest.TestCase):
    def test_default_lineage_is_none_safe(self):
        lineage = normalize_lineage(None)
        self.assertIs(lineage, DEFAULT_LINEAGE)
        self.assertEqual(lineage.as_dict(), DEFAULT_LINEAGE.as_dict())

    def test_normalize_lineage_accepts_lineage_instance(self):
        original = Lineage(tenant_id=1, collection_run_id=2)
        self.assertIs(normalize_lineage(original), original)

    def test_normalize_lineage_accepts_mapping(self):
        lineage = normalize_lineage({"tenant_id": 7, "collected_at": "x"})
        self.assertEqual(lineage.tenant_id, 7)
        self.assertEqual(lineage.collected_at, "x")
        self.assertIsNone(lineage.collection_run_id)

    def test_normalize_lineage_rejects_non_mapping(self):
        with self.assertRaises(TypeError):
            normalize_lineage("not a lineage")
        with self.assertRaises(TypeError):
            normalize_lineage(123)

    def test_lineage_from_mapping_alias(self):
        lineage = lineage_from_mapping({"tenant_id": 9})
        self.assertEqual(lineage.tenant_id, 9)
        self.assertIsNone(lineage.collection_run_id)


# ---------------------------------------------------------------------------
# Versioning tests
# ---------------------------------------------------------------------------


class VersioningTests(unittest.TestCase):
    def test_primary_version_identity_is_deterministic(self):
        v1 = primary_version_identity(
            tenant_id=1, source_object_id="abc", last_modified_date_time="2026-08-20T00:00:00Z"
        )
        v2 = primary_version_identity(
            tenant_id=1, source_object_id="abc", last_modified_date_time="2026-08-20T00:00:00Z"
        )
        self.assertEqual(v1, v2)

    def test_primary_version_identity_changes_on_last_modified_change(self):
        v1 = primary_version_identity(
            tenant_id=1, source_object_id="abc", last_modified_date_time="2026-08-20T00:00:00Z"
        )
        v2 = primary_version_identity(
            tenant_id=1, source_object_id="abc", last_modified_date_time="2026-08-21T00:00:00Z"
        )
        self.assertNotEqual(v1, v2)

    def test_fallback_version_identity_changes_on_lifecycle_change(self):
        base = {
            "status": "investigating",
            "is_resolved": False,
            "start_date_time": "2026-08-19T00:00:00Z",
            "end_date_time": None,
        }
        v1 = fallback_version_identity(
            tenant_id=1, source_object_id="abc", lifecycle_fields=base
        )
        v2 = fallback_version_identity(
            tenant_id=1,
            source_object_id="abc",
            lifecycle_fields={**base, "status": "restored"},
        )
        self.assertNotEqual(v1, v2)

    def test_fallback_version_identity_is_stable_for_same_inputs(self):
        fields = {
            "category": "PlanForChange",
            "severity": "high",
            "is_major_change": True,
            "start_date_time": "2026-08-19T00:00:00Z",
            "end_date_time": None,
            "action_required_by_date_time": "2026-09-01T00:00:00Z",
        }
        v1 = fallback_version_identity(tenant_id=1, source_object_id="m1", lifecycle_fields=fields)
        v2 = fallback_version_identity(tenant_id=1, source_object_id="m1", lifecycle_fields=dict(fields))
        self.assertEqual(v1, v2)

    def test_compute_version_identity_uses_primary_when_lmdt_present(self):
        record_with_lmdt = {
            "lastModifiedDateTime": "2026-08-20T00:00:00Z",
            "status": "restored",
            "isResolved": True,
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": None,
        }
        v = compute_version_identity(
            "G01-016", tenant_id=1, source_object_id="i1", record=record_with_lmdt
        )
        expected = primary_version_identity(
            tenant_id=1,
            source_object_id="i1",
            last_modified_date_time="2026-08-20T00:00:00Z",
        )
        self.assertEqual(v, expected)

    def test_compute_version_identity_uses_fallback_when_lmdt_missing(self):
        record = {
            "status": "investigating",
            "isResolved": False,
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": None,
        }
        v = compute_version_identity(
            "G01-016", tenant_id=1, source_object_id="i1", record=record
        )
        expected = fallback_version_identity(
            tenant_id=1,
            source_object_id="i1",
            lifecycle_fields={
                "status": "investigating",
                "is_resolved": False,
                "start_date_time": "2026-08-19T00:00:00Z",
                "end_date_time": None,
            },
        )
        self.assertEqual(v, expected)

    def test_compute_version_identity_uses_fallback_when_lmdt_blank_string(self):
        record = {
            "lastModifiedDateTime": "",
            "status": "restored",
            "isResolved": True,
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": "2026-08-20T00:00:00Z",
        }
        v = compute_version_identity(
            "G01-016", tenant_id=1, source_object_id="i1", record=record
        )
        expected = fallback_version_identity(
            tenant_id=1,
            source_object_id="i1",
            lifecycle_fields={
                "status": "restored",
                "is_resolved": True,
                "start_date_time": "2026-08-19T00:00:00Z",
                "end_date_time": "2026-08-20T00:00:00Z",
            },
        )
        self.assertEqual(v, expected)

    def test_compute_version_identity_stable_for_g01_017(self):
        record = {
            "lastModifiedDateTime": "2026-08-20T00:00:00Z",
            "category": "PlanForChange",
            "severity": "high",
            "isMajorChange": True,
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": None,
            "actionRequiredByDateTime": "2026-09-01T00:00:00Z",
        }
        v1 = compute_version_identity(
            "G01-017", tenant_id=1, source_object_id="m1", record=record
        )
        v2 = compute_version_identity(
            "G01-017", tenant_id=1, source_object_id="m1", record=copy.deepcopy(record)
        )
        self.assertEqual(v1, v2)

    def test_compute_version_identity_changes_on_lmdt_for_g01_017(self):
        r1 = {
            "lastModifiedDateTime": "2026-08-20T00:00:00Z",
            "category": "PlanForChange",
            "severity": "high",
            "isMajorChange": True,
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": None,
            "actionRequiredByDateTime": "2026-09-01T00:00:00Z",
        }
        r2 = dict(r1, lastModifiedDateTime="2026-08-21T00:00:00Z")
        v1 = compute_version_identity("G01-017", tenant_id=1, source_object_id="m1", record=r1)
        v2 = compute_version_identity("G01-017", tenant_id=1, source_object_id="m1", record=r2)
        self.assertNotEqual(v1, v2)

    def test_compute_version_identity_changes_on_lifecycle_change_for_g01_017_fallback(self):
        r1 = {
            "category": "PlanForChange",
            "severity": "high",
            "isMajorChange": True,
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": None,
            "actionRequiredByDateTime": "2026-09-01T00:00:00Z",
        }
        r2 = dict(r1, severity="medium")
        v1 = compute_version_identity("G01-017", tenant_id=1, source_object_id="m1", record=r1)
        v2 = compute_version_identity("G01-017", tenant_id=1, source_object_id="m1", record=r2)
        self.assertNotEqual(v1, v2)

    def test_compute_version_identity_rejects_unsupported_endpoint(self):
        with self.assertRaises(ValueError):
            compute_version_identity(
                "G01-005", tenant_id=1, source_object_id="x", record={"lastModifiedDateTime": "z"}
            )


# ---------------------------------------------------------------------------
# G01-005 Directory Audit Logs
# ---------------------------------------------------------------------------


class DirectoryAuditLogsAdapterTests(unittest.TestCase):
    def test_emits_audit_event_rows_with_directory_audit_event_source(self):
        records = [
            {
                "id": "audit-1",
                "activityDateTime": "2026-08-20T10:00:00Z",
                "activityDisplayName": "Add member to group",
                "category": "GroupManagement",
                "result": "success",
                "loggedByService": "Entra",
            }
        ]
        rows = adapt_directory_audit_logs(records, make_lineage())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["event_source"], EVENT_SOURCE_DIRECTORY_AUDIT)
        self.assertEqual(row["source_object_id"], "audit-1")
        self.assertEqual(row["tenant_id"], 42)
        self.assertEqual(row["collection_run_id"], 1001)
        self.assertEqual(row["endpoint_run_id"], 2002)
        self.assertEqual(row["collected_at"], "2026-08-20T12:00:00Z")
        self.assertEqual(row["event_at"], "2026-08-20T10:00:00Z")
        self.assertEqual(row["activity"], "Add member to group")
        self.assertEqual(row["category"], "GroupManagement")
        self.assertEqual(row["result"], "success")
        self.assertEqual(row["actor_user_id"], "Entra")

    def test_event_at_separate_from_collected_at(self):
        records = [
            {
                "id": "audit-1",
                "activityDateTime": "2026-08-20T10:00:00Z",
            }
        ]
        rows = adapt_directory_audit_logs(records, make_lineage())
        self.assertEqual(rows[0]["event_at"], "2026-08-20T10:00:00Z")
        self.assertEqual(rows[0]["collected_at"], "2026-08-20T12:00:00Z")
        self.assertNotEqual(rows[0]["event_at"], rows[0]["collected_at"])

    def test_optional_fields_become_null(self):
        records = [{"id": "audit-2"}]
        rows = adapt_directory_audit_logs(records, make_lineage())
        row = rows[0]
        self.assertIsNone(row["activity"])
        self.assertIsNone(row["category"])
        self.assertIsNone(row["result"])
        self.assertIsNone(row["event_at"])
        self.assertIsNone(row["actor_user_id"])

    def test_records_missing_id_rejected(self):
        with self.assertRaises(ValueError):
            adapt_directory_audit_logs([{"activityDateTime": "x"}], make_lineage())
        with self.assertRaises(ValueError):
            adapt_directory_audit_logs([{"id": ""}], make_lineage())

    def test_deterministic_output(self):
        records = [
            {
                "id": "audit-3",
                "activityDateTime": "2026-08-20T10:00:00Z",
                "activityDisplayName": "X",
                "category": "Y",
                "result": "success",
                "loggedByService": "Entra",
            }
        ]
        a = adapt_directory_audit_logs(records, make_lineage())
        b = adapt_directory_audit_logs(records, make_lineage())
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# G01-006 Sign-in Logs
# ---------------------------------------------------------------------------


class SignInLogsAdapterTests(unittest.TestCase):
    def test_emits_audit_event_rows_with_sign_in_event_source(self):
        records = [
            {
                "id": "sign-1",
                "createdDateTime": "2026-08-20T10:00:00Z",
                "userId": "user-1",
                "appId": "app-1",
                "status": {"errorCode": 0, "failureReason": None},
                "clientAppUsed": "Browser",
                "isInteractive": True,
            }
        ]
        rows = adapt_sign_in_logs(records, make_lineage())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["event_source"], EVENT_SOURCE_SIGN_IN)
        self.assertEqual(row["source_object_id"], "sign-1")
        self.assertEqual(row["tenant_id"], 42)
        self.assertEqual(row["actor_user_id"], "user-1")
        self.assertEqual(row["actor_app_id"], "app-1")
        self.assertEqual(row["activity"], "Browser")
        self.assertEqual(row["is_interactive"], True)

    def test_event_source_separation_g01_005_vs_g01_006(self):
        # Same Graph ``id`` should yield two distinct rows on two distinct
        # tables thanks to the event_source discriminator.
        audit_record = {"id": "shared-id", "activityDateTime": "2026-08-20T10:00:00Z"}
        signin_record = {"id": "shared-id", "createdDateTime": "2026-08-20T10:00:00Z"}
        lineage = make_lineage()
        audit_rows = adapt_directory_audit_logs([audit_record], lineage)
        signin_rows = adapt_sign_in_logs([signin_record], lineage)
        self.assertEqual(audit_rows[0]["event_source"], EVENT_SOURCE_DIRECTORY_AUDIT)
        self.assertEqual(signin_rows[0]["event_source"], EVENT_SOURCE_SIGN_IN)
        self.assertNotEqual(audit_rows[0]["event_source"], signin_rows[0]["event_source"])

    def test_sign_in_event_at_from_created_date_time(self):
        records = [
            {
                "id": "sign-2",
                "createdDateTime": "2026-08-20T10:00:00Z",
            }
        ]
        rows = adapt_sign_in_logs(records, make_lineage())
        self.assertEqual(rows[0]["event_at"], "2026-08-20T10:00:00Z")
        self.assertEqual(rows[0]["collected_at"], "2026-08-20T12:00:00Z")

    def test_optional_fields_become_null(self):
        records = [{"id": "sign-3"}]
        rows = adapt_sign_in_logs(records, make_lineage())
        self.assertIsNone(rows[0]["actor_user_id"])
        self.assertIsNone(rows[0]["actor_app_id"])
        self.assertIsNone(rows[0]["activity"])
        self.assertIsNone(rows[0]["category"])
        self.assertIsNone(rows[0]["result"])
        self.assertIsNone(rows[0]["is_interactive"])

    def test_non_mapping_status_does_not_break(self):
        records = [{"id": "sign-4", "status": "weird"}]
        rows = adapt_sign_in_logs(records, make_lineage())
        self.assertIsNone(rows[0]["category"])
        self.assertIsNone(rows[0]["result"])

    def test_nested_status_maps_failure_then_additional_details_fallback(self):
        rows = adapt_sign_in_logs([
            {"id": "sign-5", "status": {
                "errorCode": 501,
                "failureReason": "Invalid credentials",
                "additionalDetails": "Provider detail",
            }},
            {"id": "sign-6", "status": {
                "errorCode": 0,
                "failureReason": None,
                "additionalDetails": "No additional detail",
            }},
        ], make_lineage())
        self.assertEqual(rows[0]["category"], "501")
        self.assertEqual(rows[0]["result"], "Invalid credentials")
        self.assertEqual(rows[1]["category"], "0")
        self.assertEqual(rows[1]["result"], "No additional detail")

    def test_projects_only_approved_sign_in_fields(self):
        row = adapt_sign_in_logs([{
            "id": "sign-7",
            "createdDateTime": "2026-08-20T10:00:00Z",
            "userId": "user-7",
            "appId": "app-7",
            "status": {"errorCode": 0},
            "clientAppUsed": "Browser",
            "isInteractive": False,
            "ipAddress": "192.0.2.1",
            "location": {"city": "Hidden"},
            "userAgent": "Hidden agent",
            "correlationId": "hidden-correlation",
            "token": "secret-token-DO-NOT-LEAK",
            "credential": "secret-token-DO-NOT-LEAK",
        }], make_lineage())[0]
        self.assertEqual(set(row), {
            "tenant_id", "event_source", "source_object_id", "event_at",
            "collected_at", "collection_run_id", "endpoint_run_id",
            "actor_user_id", "actor_app_id", "activity", "category", "result",
            "is_interactive", "retention_class",
        })
        self.assertNotIn("192.0.2.1", repr(row))
        self.assertNotIn("secret-token-DO-NOT-LEAK", repr(row))


# ---------------------------------------------------------------------------
# G01-014 Risk Detections
# ---------------------------------------------------------------------------


class RiskDetectionsAdapterTests(unittest.TestCase):
    def test_emits_risk_detection_rows(self):
        records = [
            {
                "id": "rd-1",
                "detectedDateTime": "2026-08-20T11:00:00Z",
                "activityDateTime": "2026-08-20T10:30:00Z",
                "riskEventType": "anonymizedIPAddress",
                "riskLevel": "high",
                "riskState": "atRisk",
                "riskDetail": "anonymizedIpAddress",
                "detectionTimingType": "realtime",
                "activity": "signin",
            }
        ]
        rows = adapt_risk_detections(records, make_lineage())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["source_object_id"], "rd-1")
        self.assertEqual(row["tenant_id"], 42)
        self.assertEqual(row["detected_at"], "2026-08-20T11:00:00Z")
        self.assertEqual(row["activity_at"], "2026-08-20T10:30:00Z")
        self.assertEqual(row["risk_event_type"], "anonymizedIPAddress")
        self.assertEqual(row["risk_level"], "high")
        self.assertEqual(row["risk_state"], "atRisk")
        self.assertEqual(row["detection_timing_type"], "realtime")
        self.assertEqual(row["activity"], "signin")
        self.assertEqual(row["collected_at"], "2026-08-20T12:00:00Z")

    def test_optional_fields_become_null(self):
        records = [{"id": "rd-2"}]
        rows = adapt_risk_detections(records, make_lineage())
        self.assertIsNone(rows[0]["risk_event_type"])
        self.assertIsNone(rows[0]["risk_level"])
        self.assertIsNone(rows[0]["risk_state"])
        self.assertIsNone(rows[0]["activity_at"])

    def test_deterministic_output(self):
        records = [
            {
                "id": "rd-3",
                "detectedDateTime": "2026-08-20T11:00:00Z",
                "riskEventType": "x",
                "riskLevel": "high",
                "riskState": "atRisk",
            }
        ]
        a = adapt_risk_detections(records, make_lineage())
        b = adapt_risk_detections(records, make_lineage())
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# G01-011 Conditional Access Policies (current + snapshot)
# ---------------------------------------------------------------------------


class ConditionalAccessPoliciesAdapterTests(unittest.TestCase):
    def test_emits_current_and_snapshot_rows(self):
        records = [
            {
                "id": "cap-1",
                "displayName": "Require MFA",
                "state": "enabled",
                "createdDateTime": "2026-08-19T00:00:00Z",
                "modifiedDateTime": "2026-08-20T00:00:00Z",
                "conditions": {"clientAppTypes": ["exchangeActiveSync", "other"]},
                "grantControls": {"builtInControls": ["block"]},
            }
        ]
        rows = conditional_access_policies(records, make_lineage())
        self.assertEqual(len(rows), 2)
        current = rows[0]
        snapshot = rows[1]
        self.assertEqual(current["source_object_id"], "cap-1")
        self.assertEqual(current["tenant_id"], 42)
        self.assertEqual(current["display_name"], "Require MFA")
        self.assertEqual(current["state"], "enabled")
        self.assertEqual(current["created_date_time"], "2026-08-19T00:00:00Z")
        self.assertEqual(current["modified_date_time"], "2026-08-20T00:00:00Z")
        self.assertEqual(current["client_app_types"], ["exchangeActiveSync", "other"])
        self.assertEqual(current["grant_built_in_controls"], ["block"])
        self.assertTrue(current["security_evidence_complete"])
        self.assertEqual(current["last_observed_at"], "2026-08-20T12:00:00Z")
        # Snapshot row carries run-scoped fields
        self.assertEqual(snapshot["source_object_id"], "cap-1")
        self.assertEqual(snapshot["tenant_id"], 42)
        self.assertEqual(snapshot["display_name"], "Require MFA")
        self.assertEqual(snapshot["state"], "enabled")
        self.assertEqual(snapshot["client_app_types"], ["exchangeActiveSync", "other"])
        self.assertEqual(snapshot["grant_built_in_controls"], ["block"])
        self.assertTrue(snapshot["security_evidence_complete"])
        self.assertEqual(snapshot["snapshot_at"], "2026-08-20T12:00:00Z")
        # Snapshot rows do not have last_observed_at
        self.assertNotIn("last_observed_at", snapshot)

    def test_snapshot_keys_match_current_keys(self):
        records = [{"id": "cap-2", "displayName": "X", "state": "enabled"}]
        rows = conditional_access_policies(records, make_lineage())
        current_keys = set(rows[0].keys())
        snapshot_keys = set(rows[1].keys())
        # Drop ``last_observed_at`` from current and ``snapshot_at`` from snapshot,
        # then compare
        current_only = {k for k in current_keys if k != "last_observed_at"}
        snapshot_only = {k for k in snapshot_keys if k != "snapshot_at"}
        self.assertEqual(current_only, snapshot_only)

    def test_optional_fields_become_null(self):
        rows = conditional_access_policies([{"id": "cap-3"}], make_lineage())
        for row in rows:
            self.assertIsNone(row["display_name"])
            self.assertIsNone(row["state"])
            self.assertIsNone(row["created_date_time"])
            self.assertIsNone(row["modified_date_time"])

    def test_security_evidence_values_and_completeness(self):
        cases = [
            (["browser", "mobileAppsAndDesktopClients"], ["mfa"], True),
            (["easSupported"], [], True),
            (["easUnsupported"], [], True),
        ]
        for client_types, controls, complete in cases:
            rows = conditional_access_policies([{
                "id": "cap-security", "conditions": {"clientAppTypes": client_types},
                "grantControls": {"builtInControls": controls},
            }], make_lineage())
            self.assertEqual(rows[0]["client_app_types"], client_types)
            self.assertEqual(rows[0]["grant_built_in_controls"], controls)
            self.assertEqual(rows[0]["security_evidence_complete"], complete)

    def test_absent_grant_controls_is_valid_no_controls_evidence(self):
        rows = conditional_access_policies([{
            "id": "cap-no-grant", "conditions": {"clientAppTypes": ["browser"]},
        }], make_lineage())
        self.assertEqual(rows[0]["grant_built_in_controls"], [])
        self.assertTrue(rows[0]["security_evidence_complete"])

    def test_malformed_security_evidence_is_incomplete_not_empty(self):
        rows = conditional_access_policies([{
            "id": "cap-bad-client", "conditions": {"clientAppTypes": "browser"},
            "grantControls": {"builtInControls": ["block"]},
        }, {
            "id": "cap-bad-control", "conditions": {"clientAppTypes": ["browser"]},
            "grantControls": {"builtInControls": "block"},
        }], make_lineage())
        self.assertFalse(rows[0]["security_evidence_complete"])
        self.assertIsNone(rows[0]["client_app_types"])
        self.assertFalse(rows[2]["security_evidence_complete"])
        self.assertIsNone(rows[2]["grant_built_in_controls"])

    def test_missing_id_and_malformed_records_fail_closed(self):
        with self.assertRaises(ValueError):
            conditional_access_policies([{"displayName": "missing"}], make_lineage())
        with self.assertRaises(TypeError):
            conditional_access_policies(["not-a-policy"], make_lineage())

    def test_only_approved_policy_metadata_is_normalized(self):
        record = {
            "id": "cap-4",
            "displayName": "Metadata only",
            "state": "enabled",
            "createdDateTime": "2026-08-19T00:00:00Z",
            "modifiedDateTime": "2026-08-20T00:00:00Z",
            "conditions": {"users": {"includeUsers": ["all"]}},
            "grantControls": {"builtInControls": ["mfa"]},
            "sessionControls": {"signInFrequency": {"value": 1}},
            "access_token": "must-not-copy",
            "unknownField": "must-not-copy",
        }
        rows = conditional_access_policies([record], make_lineage(retention_class="REFERENCE"))
        approved = {
            "tenant_id", "collection_run_id", "endpoint_run_id", "collected_at",
            "retention_class", "source_object_id", "display_name", "state",
            "created_date_time", "modified_date_time",
            "client_app_types", "grant_built_in_controls", "security_evidence_complete",
        }
        for row in rows:
            self.assertTrue(set(row).issubset(approved | {"last_observed_at", "snapshot_at"}))
            rendered = str(row)
            for excluded in ("conditions", "grantControls", "sessionControls", "access_token", "unknownField"):
                self.assertNotIn(excluded, rendered)
            self.assertEqual(row["retention_class"], "REFERENCE")


# ---------------------------------------------------------------------------
# G01-012 Named Locations
# ---------------------------------------------------------------------------


class NamedLocationsAdapterTests(unittest.TestCase):
    def test_emits_current_state_rows_only(self):
        records = [
            {
                "id": "loc-1",
                "displayName": "HQ",
                "createdDateTime": "2026-08-19T00:00:00Z",
                "modifiedDateTime": "2026-08-20T00:00:00Z",
            }
        ]
        rows = named_locations(records, make_lineage())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["source_object_id"], "loc-1")
        self.assertEqual(row["tenant_id"], 42)
        self.assertEqual(row["display_name"], "HQ")
        self.assertEqual(row["last_observed_at"], "2026-08-20T12:00:00Z")

    def test_optional_fields_become_null(self):
        rows = named_locations([{"id": "loc-2"}], make_lineage())
        self.assertIsNone(rows[0]["display_name"])
        self.assertIsNone(rows[0]["created_date_time"])
        self.assertIsNone(rows[0]["modified_date_time"])

    def test_no_snapshot_rows(self):
        rows = named_locations(
            [
                {"id": "loc-3", "displayName": "A"},
                {"id": "loc-4", "displayName": "B"},
            ],
            make_lineage(),
        )
        # 2 records -> 2 rows (current-only).
        self.assertEqual(len(rows), 2)

    def test_only_approved_fields_are_retained(self):
        record = {
            "id": "loc-secure",
            "displayName": "HQ",
            "createdDateTime": "2026-08-19T00:00:00Z",
            "modifiedDateTime": "2026-08-20T00:00:00Z",
            "ipRanges": [{"cidrAddress": "10.0.0.0/8"}],
            "countriesAndRegions": ["US"],
            "unknownField": "drop",
            "passwordCredentials": [{"secretText": "drop"}],
            "access_token": "drop",
            "authorization": "drop",
        }
        row = named_locations([record], make_lineage(retention_class="REFERENCE"))[0]
        self.assertEqual(
            set(row),
            {
                "tenant_id", "collection_run_id", "endpoint_run_id",
                "collected_at", "retention_class", "source_object_id",
                "display_name", "created_date_time", "modified_date_time",
                "last_observed_at",
            },
        )
        self.assertEqual(row["retention_class"], "REFERENCE")
        rendered = str(row)
        for excluded in (
            "ipRanges", "countriesAndRegions", "unknownField",
            "passwordCredentials", "access_token", "authorization",
        ):
            self.assertNotIn(excluded, rendered)

    def test_missing_id_and_malformed_records_fail_closed(self):
        with self.assertRaises(ValueError):
            named_locations([{"displayName": "Missing ID"}], make_lineage())
        with self.assertRaises(TypeError):
            named_locations(["not-a-location"], make_lineage())


# ---------------------------------------------------------------------------
# G01-013 Risky Users (current + snapshot)
# ---------------------------------------------------------------------------


class RiskyUsersAdapterTests(unittest.TestCase):
    def test_emits_current_and_snapshot_rows(self):
        records = [
            {
                "id": "ru-1",
                "riskLevel": "high",
                "riskState": "atRisk",
                "riskDetail": "leakedCredentials",
                "isDeleted": False,
                "isProcessing": False,
                "riskLastUpdatedDateTime": "2026-08-20T00:00:00Z",
            }
        ]
        rows = risky_users(records, make_lineage())
        self.assertEqual(len(rows), 2)
        current = rows[0]
        snapshot = rows[1]
        self.assertEqual(current["source_object_id"], "ru-1")
        self.assertEqual(current["tenant_id"], 42)
        self.assertEqual(current["risk_level"], "high")
        self.assertEqual(current["risk_state"], "atRisk")
        self.assertEqual(current["risk_detail"], "leakedCredentials")
        self.assertEqual(current["is_deleted"], False)
        self.assertEqual(current["is_processing"], False)
        self.assertEqual(current["risk_last_updated_at"], "2026-08-20T00:00:00Z")
        self.assertEqual(current["last_observed_at"], "2026-08-20T12:00:00Z")
        self.assertEqual(snapshot["source_object_id"], "ru-1")
        self.assertEqual(snapshot["snapshot_at"], "2026-08-20T12:00:00Z")
        self.assertNotIn("last_observed_at", snapshot)

    def test_optional_fields_become_null(self):
        rows = risky_users([{"id": "ru-2"}], make_lineage())
        for row in rows:
            self.assertIsNone(row["risk_level"])
            self.assertIsNone(row["risk_state"])
            self.assertIsNone(row["risk_detail"])
            self.assertIsNone(row["is_deleted"])
            self.assertIsNone(row["is_processing"])
            self.assertIsNone(row["risk_last_updated_at"])


# ---------------------------------------------------------------------------
# G01-015 Service Health Overview (current + snapshot)
# ---------------------------------------------------------------------------


class ServiceHealthOverviewAdapterTests(unittest.TestCase):
    def test_emits_current_and_snapshot_rows(self):
        records = [
            {"id": "sho-1", "service": "Exchange Online", "status": "good"}
        ]
        rows = service_health_overview(records, make_lineage())
        self.assertEqual(len(rows), 2)
        current = rows[0]
        snapshot = rows[1]
        self.assertEqual(current["source_object_id"], "sho-1")
        self.assertEqual(current["tenant_id"], 42)
        self.assertEqual(current["service"], "Exchange Online")
        self.assertEqual(current["status"], "good")
        self.assertEqual(current["last_observed_at"], "2026-08-20T12:00:00Z")
        self.assertEqual(snapshot["source_object_id"], "sho-1")
        self.assertEqual(snapshot["snapshot_at"], "2026-08-20T12:00:00Z")
        self.assertNotIn("last_observed_at", snapshot)

    def test_optional_fields_become_null(self):
        rows = service_health_overview([{"id": "sho-2"}], make_lineage())
        for row in rows:
            self.assertIsNone(row["service"])
            self.assertIsNone(row["status"])


# ---------------------------------------------------------------------------
# G01-016 Service Health Issues (current + versioned history)
# ---------------------------------------------------------------------------


class ServiceHealthIssuesAdapterTests(unittest.TestCase):
    BASE_RECORD = {
        "id": "shi-1",
        "service": "Exchange Online",
        "status": "investigating",
        "classification": "incident",
        "startDateTime": "2026-08-19T00:00:00Z",
        "endDateTime": None,
        "lastModifiedDateTime": "2026-08-20T00:00:00Z",
        "isResolved": False,
    }

    def test_emits_current_and_history_rows(self):
        rows = service_health_issues([self.BASE_RECORD], make_lineage())
        self.assertEqual(len(rows), 2)
        current = rows[0]
        history = rows[1]
        self.assertEqual(current["source_object_id"], "shi-1")
        self.assertEqual(current["tenant_id"], 42)
        self.assertEqual(current["service"], "Exchange Online")
        self.assertEqual(current["status"], "investigating")
        self.assertEqual(current["classification"], "incident")
        self.assertEqual(current["start_date_time"], "2026-08-19T00:00:00Z")
        self.assertEqual(current["end_date_time"], None)
        self.assertEqual(current["last_modified_date_time"], "2026-08-20T00:00:00Z")
        self.assertEqual(current["is_resolved"], False)
        self.assertEqual(current["last_observed_at"], "2026-08-20T12:00:00Z")
        # History row
        self.assertEqual(history["source_object_id"], "shi-1")
        self.assertEqual(history["tenant_id"], 42)
        self.assertEqual(history["observed_at"], "2026-08-20T12:00:00Z")
        self.assertEqual(history["collected_at"], "2026-08-20T12:00:00Z")
        self.assertIsInstance(history["version_identity"], bytes)
        self.assertEqual(len(history["version_identity"]), 32)  # SHA-256

    def test_version_identity_stable_for_same_record(self):
        rows_a = service_health_issues([self.BASE_RECORD], make_lineage())
        rows_b = service_health_issues([copy.deepcopy(self.BASE_RECORD)], make_lineage())
        history_a = [r for r in rows_a if "version_identity" in r][0]
        history_b = [r for r in rows_b if "version_identity" in r][0]
        self.assertEqual(history_a["version_identity"], history_b["version_identity"])

    def test_version_identity_changes_on_lmdt_change(self):
        r1 = dict(self.BASE_RECORD)
        r2 = dict(self.BASE_RECORD, lastModifiedDateTime="2026-08-21T00:00:00Z")
        rows_a = service_health_issues([r1], make_lineage())
        rows_b = service_health_issues([r2], make_lineage())
        self.assertNotEqual(rows_a[1]["version_identity"], rows_b[1]["version_identity"])

    def test_version_identity_changes_on_lifecycle_when_lmdt_missing(self):
        r1 = {
            "id": "shi-2",
            "service": "Exchange",
            "status": "investigating",
            "classification": "incident",
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": None,
            "isResolved": False,
        }
        r2 = dict(r1, status="restored", isResolved=True)
        rows_a = service_health_issues([r1], make_lineage())
        rows_b = service_health_issues([r2], make_lineage())
        self.assertNotEqual(rows_a[1]["version_identity"], rows_b[1]["version_identity"])

    def test_optional_fields_become_null(self):
        rows = service_health_issues([{"id": "shi-3"}], make_lineage())
        current = rows[0]
        self.assertIsNone(current["service"])
        self.assertIsNone(current["status"])
        self.assertIsNone(current["classification"])
        self.assertIsNone(current["start_date_time"])
        self.assertIsNone(current["end_date_time"])
        self.assertIsNone(current["last_modified_date_time"])
        self.assertIsNone(current["is_resolved"])

    def test_history_keys_match_current(self):
        rows = service_health_issues([self.BASE_RECORD], make_lineage())
        current = rows[0]
        history = rows[1]
        current_keys = set(current.keys())
        history_keys = set(history.keys())
        # Drop the timeline column that's unique to each
        current_keys.discard("last_observed_at")
        history_keys.discard("observed_at")
        history_keys.discard("version_identity")
        # ``collected_at`` is a per-run lineage column that appears on
        # both rows; drop it from both sides.
        current_keys.discard("collected_at")
        history_keys.discard("collected_at")
        self.assertEqual(current_keys, history_keys)


# ---------------------------------------------------------------------------
# G01-017 Service Update Messages (current + versioned history)
# ---------------------------------------------------------------------------


class ServiceUpdateMessagesAdapterTests(unittest.TestCase):
    BASE_RECORD = {
        "id": "sum-1",
        "category": "PlanForChange",
        "severity": "high",
        "startDateTime": "2026-08-19T00:00:00Z",
        "endDateTime": None,
        "lastModifiedDateTime": "2026-08-20T00:00:00Z",
        "isMajorChange": True,
        "actionRequiredByDateTime": "2026-09-01T00:00:00Z",
        "services": ["Exchange Online", "SharePoint"],
    }

    def test_emits_current_and_history_rows(self):
        rows = service_update_messages([self.BASE_RECORD], make_lineage())
        self.assertEqual(len(rows), 2)
        current = rows[0]
        history = rows[1]
        self.assertEqual(current["source_object_id"], "sum-1")
        self.assertEqual(current["category"], "PlanForChange")
        self.assertEqual(current["severity"], "high")
        self.assertEqual(current["start_date_time"], "2026-08-19T00:00:00Z")
        self.assertEqual(current["last_modified_date_time"], "2026-08-20T00:00:00Z")
        self.assertEqual(current["is_major_change"], True)
        self.assertEqual(current["action_required_by_date_time"], "2026-09-01T00:00:00Z")
        self.assertEqual(current["services"], ["Exchange Online", "SharePoint"])
        self.assertEqual(current["last_observed_at"], "2026-08-20T12:00:00Z")
        self.assertEqual(history["source_object_id"], "sum-1")
        self.assertEqual(history["observed_at"], "2026-08-20T12:00:00Z")
        self.assertIsInstance(history["version_identity"], bytes)
        self.assertEqual(len(history["version_identity"]), 32)

    def test_version_identity_stable_for_same_record(self):
        rows_a = service_update_messages([self.BASE_RECORD], make_lineage())
        rows_b = service_update_messages([copy.deepcopy(self.BASE_RECORD)], make_lineage())
        self.assertEqual(
            [r for r in rows_a if "version_identity" in r][0]["version_identity"],
            [r for r in rows_b if "version_identity" in r][0]["version_identity"],
        )

    def test_version_identity_changes_on_lmdt(self):
        r2 = dict(self.BASE_RECORD, lastModifiedDateTime="2026-08-21T00:00:00Z")
        rows_a = service_update_messages([self.BASE_RECORD], make_lineage())
        rows_b = service_update_messages([r2], make_lineage())
        self.assertNotEqual(rows_a[1]["version_identity"], rows_b[1]["version_identity"])

    def test_version_identity_changes_on_severity_when_lmdt_missing(self):
        r1 = {
            "id": "sum-2",
            "category": "PlanForChange",
            "severity": "high",
            "isMajorChange": True,
            "startDateTime": "2026-08-19T00:00:00Z",
            "endDateTime": None,
            "actionRequiredByDateTime": "2026-09-01T00:00:00Z",
        }
        r2 = dict(r1, severity="medium")
        rows_a = service_update_messages([r1], make_lineage())
        rows_b = service_update_messages([r2], make_lineage())
        self.assertNotEqual(rows_a[1]["version_identity"], rows_b[1]["version_identity"])

    def test_optional_fields_become_null(self):
        rows = service_update_messages([{"id": "sum-3"}], make_lineage())
        current = rows[0]
        self.assertIsNone(current["category"])
        self.assertIsNone(current["severity"])
        self.assertIsNone(current["start_date_time"])
        self.assertIsNone(current["end_date_time"])
        self.assertIsNone(current["last_modified_date_time"])
        self.assertIsNone(current["is_major_change"])
        self.assertIsNone(current["action_required_by_date_time"])
        self.assertIsNone(current["services"])

    def test_services_non_list_become_null(self):
        rows = service_update_messages([{"id": "sum-4", "services": "not-a-list"}], make_lineage())
        self.assertIsNone(rows[0]["services"])


# ---------------------------------------------------------------------------
# Security / lineage / determinism
# ---------------------------------------------------------------------------


class SecurityTests(unittest.TestCase):
    """Adapters must not propagate tokens, bearer headers, or client secrets."""

    def test_no_credential_substrings_in_any_produced_row(self):
        lineage = make_lineage()
        record_sets = {
            "G01-005": [{"id": "audit-1", "activityDateTime": "2026-08-20T00:00:00Z"}],
            "G01-006": [{"id": "sign-1", "createdDateTime": "2026-08-20T00:00:00Z"}],
            "G01-011": [{"id": "p-1", "displayName": "X"}],
            "G01-012": [{"id": "n-1"}],
            "G01-013": [{"id": "r-1"}],
            "G01-014": [{"id": "d-1"}],
            "G01-015": [{"id": "h-1"}],
            "G01-016": [{"id": "i-1"}],
            "G01-017": [{"id": "m-1"}],
        }
        adapters = {
            "G01-005": adapt_directory_audit_logs,
            "G01-006": adapt_sign_in_logs,
            "G01-011": conditional_access_policies,
            "G01-012": named_locations,
            "G01-013": risky_users,
            "G01-014": adapt_risk_detections,
            "G01-015": service_health_overview,
            "G01-016": service_health_issues,
            "G01-017": service_update_messages,
        }
        for endpoint_id, records in record_sets.items():
            with self.subTest(endpoint=endpoint_id):
                rows = adapters[endpoint_id](records, lineage)
                for row in rows:
                    self.assertNotIn("Authorization", row)
                    self.assertNotIn("authorization", row)
                    self.assertNotIn("Bearer", row)
                    self.assertNotIn("client_secret", row)
                    for token in SENSITIVE_TOKENS:
                        self.assertNotIn(token, repr(row))

    def test_no_token_in_lineage_pass_through(self):
        lineage_with_token = {
            "tenant_id": 1,
            "collection_run_id": 2,
            "endpoint_run_id": 3,
            "collected_at": "2026-08-20T00:00:00Z",
            "token": SENSITIVE_TOKENS[0],  # type: ignore[dict-item]
        }
        # The lineage helper itself does not store arbitrary keys,
        # but even if a caller adds one, the adapters must not echo
        # it onto produced rows.
        rows = adapt_directory_audit_logs(
            [{"id": "x", "activityDateTime": "2026-08-20T00:00:00Z"}],
            lineage_with_token,
        )
        self.assertNotIn("token", rows[0])
        for token in SENSITIVE_TOKENS:
            self.assertNotIn(token, repr(rows[0]))

    def test_deterministic_output_across_repeated_runs(self):
        records = [
            {"id": "x", "activityDateTime": "2026-08-20T00:00:00Z"},
            {"id": "y", "createdDateTime": "2026-08-20T00:00:00Z"},
            {"id": "z", "lastModifiedDateTime": "2026-08-20T00:00:00Z", "status": "open"},
        ]
        first = {
            "audit": adapt_directory_audit_logs([records[0]], make_lineage()),
            "signin": adapt_sign_in_logs([records[1]], make_lineage()),
            "issue": service_health_issues([records[2]], make_lineage()),
        }
        second = {
            "audit": adapt_directory_audit_logs([records[0]], make_lineage()),
            "signin": adapt_sign_in_logs([records[1]], make_lineage()),
            "issue": service_health_issues([records[2]], make_lineage()),
        }
        self.assertEqual(first, second)


# ---------------------------------------------------------------------------
# No live Graph calls
# ---------------------------------------------------------------------------


class NoLiveGraphCallTests(unittest.TestCase):
    """Adapters must not reach out to Graph, import transport, or accept a
    transport handle.  This is a structural assertion."""

    def test_adapters_do_not_import_graph_transport(self):
        import collectors.workloads.security_service as pkg

        # The package surface does NOT expose GraphTransport or anything
        # that could fetch from the network.
        for name in dir(pkg):
            if name.startswith("_"):
                continue
            self.assertNotIn(name, ("GraphTransport", "Paginator", "BaseCollector"))
        # Structural check: importing the package does not pull in the
        # transport module (transport is only a dependency of G05 core).
        # The following attribute access proves the package's own
        # namespace does not re-export a transport.
        self.assertFalse(hasattr(pkg, "GraphTransport"))

    def test_adapters_do_not_require_network_state(self):
        # ``normalize_lineage(None)`` should be the only state required
        # by any adapter.
        for fn in (
            adapt_directory_audit_logs,
            adapt_sign_in_logs,
            adapt_risk_detections,
            conditional_access_policies,
            named_locations,
            risky_users,
            service_health_overview,
            service_health_issues,
            service_update_messages,
        ):
            rows = fn([{"id": "x"}], None)
            self.assertEqual(len(rows) > 0, True)


if __name__ == "__main__":
    unittest.main()
