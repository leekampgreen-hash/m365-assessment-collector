"""Offline integration tests for the G07-C workload dispatch layer.

These tests prove the dispatch contract end-to-end:

* every representative persistence mode dispatches a single record
  through ``normalize_record`` into the correct envelope shape;
* batch dispatch preserves source order and handles empty input;
* unsupported endpoint ids raise a controlled
  :class:`WorkloadDispatchError`;
* input records and lineage mappings are never mutated;
* the G01-005 / G01-006 ``event_source`` discriminator is preserved
  through the dispatcher;
* G01-016 / G01-017 produce stable ``version_identity`` for identical
  input;
* the envelope never contains a credential / token / Authorization
  substring, and the dispatcher never accepts or copies such fields.

No live Microsoft Graph calls are made.
"""
from __future__ import annotations

import copy
import unittest

from collectors.workloads import (
    EXPECTED_ENDPOINT_IDS,
    LineageContext,
    NormalizedWorkloadRecord,
    PERSISTENCE_CURRENT,
    PERSISTENCE_CURRENT_WITH_HISTORY,
    PERSISTENCE_CURRENT_WITH_SNAPSHOT,
    PERSISTENCE_EVENT,
    PERSISTENCE_REFERENCE,
    PersistenceMode,
    REGISTRY,
    WorkloadDispatchError,
    get_entry,
    normalize_record,
    normalize_records,
)


SENSITIVE_SUBSTRINGS = (
    "Bearer",
    "Authorization",
    "secret",
    "password",
    "access_token",
    "refresh_token",
    "client_secret",
)


# ---------------------------------------------------------------------------
# Reusable fixtures
# ---------------------------------------------------------------------------


LINEAGE = LineageContext(
    tenant_id=42,
    collection_run_id=1001,
    endpoint_run_id=9001,
    observed_at="2026-08-20T12:00:00+00:00",
    retention_class="STANDARD",
)


def _user_record() -> dict:
    return {
        "id": "user-1",
        "displayName": "Alice Example",
        "userPrincipalName": "alice@example.com",
        "userType": "Member",
        "accountEnabled": True,
        "createdDateTime": "2024-01-02T03:04:05Z",
    }


def _role_definition_record() -> dict:
    return {
        "id": "role-1",
        "displayName": "Global Administrator",
        "description": "Can manage all aspects of Azure AD.",
        "isBuiltIn": True,
        # Excluded payload -- must never appear in the envelope.
        "rolePermissions": [{"allowedResourceActions": ["*/*"]}],
    }


def _audit_record() -> dict:
    return {
        "id": "audit-1",
        "activityDateTime": "2026-08-19T12:00:00Z",
        "activityDisplayName": "Update user",
        "category": "UserManagement",
        "result": "success",
        "loggedByService": "IAM",
    }


def _sign_in_record() -> dict:
    return {
        "id": "sign-in-1",
        "createdDateTime": "2026-08-19T13:00:00Z",
        "userId": "user-1",
        "appId": "app-1",
        "clientAppUsed": "Browser",
        "isInteractive": True,
        "status": {"errorCode": 0, "additionalDetails": "none"},
    }


def _subscribed_sku_record() -> dict:
    return {
        "id": "sku-1",
        "skuId": "abc-123",
        "skuPartNumber": "ENTERPRISE_E5",
        "capabilityStatus": "Enabled",
        "consumedUnits": 5,
        "prepaidUnits": {"enabled": 25, "suspended": 0, "warning": 0},
        "servicePlans": [{"servicePlanId": "sp-1", "servicePlanName": "EXO"}],
    }


def _role_assignment_record() -> dict:
    return {
        "id": "assignment-1",
        "roleDefinitionId": "role-def-1",
        "principalId": "principal-1",
        "directoryScopeId": "/",
    }


def _service_health_issue_record() -> dict:
    return {
        "id": "issue-1",
        "service": "Exchange",
        "status": "investigating",
        "classification": "advisory",
        "startDateTime": "2026-08-19T00:00:00Z",
        "endDateTime": None,
        "lastModifiedDateTime": "2026-08-20T01:00:00Z",
        "isResolved": False,
    }


def _service_update_message_record() -> dict:
    return {
        "id": "message-1",
        "category": "PlanForChange",
        "severity": "Normal",
        "startDateTime": "2026-08-19T00:00:00Z",
        "endDateTime": "2026-08-25T00:00:00Z",
        "lastModifiedDateTime": "2026-08-20T01:00:00Z",
        "isMajorChange": False,
        "actionRequiredByDateTime": None,
        "services": ["Exchange"],
    }


# ---------------------------------------------------------------------------
# Representative dispatch tests -- one per persistence mode
# ---------------------------------------------------------------------------


class GroupsCurrentDispatchTests(unittest.TestCase):
    def test_groups_current_row_and_empty_batch(self):
        record = {
            "id": "group-1",
            "displayName": "All Staff",
            "mail": "staff@example.test",
            "mailEnabled": True,
            "securityEnabled": False,
            "groupTypes": ["Unified", 7],
            "members": ["user-1"],
            "access_token": "must-not-copy",
        }
        envelope = normalize_record("G01-002", record, LINEAGE)
        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT)
        self.assertEqual(envelope.current_row["source_object_id"], "group-1")
        self.assertEqual(envelope.current_row["group_types"], ["Unified"])
        self.assertNotIn("members", envelope.current_row)
        self.assertNotIn("access_token", str(envelope.to_dict()))
        self.assertEqual(normalize_records("G01-002", [], LINEAGE), [])

    def test_groups_rejects_invalid_payload(self):
        with self.assertRaises(TypeError):
            normalize_record("G01-002", ["not-an-object"], LINEAGE)
        with self.assertRaises(ValueError):
            normalize_record("G01-002", {"displayName": "Missing ID"}, LINEAGE)


class OrganizationCurrentDispatchTests(unittest.TestCase):
    """G01-003 is a single-object CURRENT tenant profile."""

    def test_single_organization_normalizes_to_one_current_row(self):
        record = {
            "id": "org-1",
            "displayName": "Example Tenant",
            "verifiedDomains": [{"name": "example.test", "type": "Managed"}],
            "countryLetterCode": "US",
            "tenantType": "AAD",
            "tenantProfile": {"credential": "must-not-copy"},
        }

        envelope = normalize_record("G01-003", record, LINEAGE)

        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT)
        self.assertEqual(envelope.current_row["source_object_id"], "org-1")
        self.assertEqual(envelope.current_row["verified_domains"], record["verifiedDomains"])
        self.assertEqual(
            set(envelope.current_row),
            {
                "tenant_id", "collection_run_id", "endpoint_run_id",
                "last_observed_at", "source_object_id", "display_name",
                "country_letter_code", "tenant_type", "verified_domains",
                "retention_class",
            },
        )
        self.assertNotIn("tenantProfile", str(envelope.to_dict()))

    def test_missing_optional_organization_fields_are_nullable(self):
        row = normalize_record("G01-003", {"id": "org-2"}, LINEAGE).current_row

        self.assertEqual(row["source_object_id"], "org-2")
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["country_letter_code"])
        self.assertIsNone(row["tenant_type"])
        self.assertIsNone(row["verified_domains"])

    def test_malformed_organization_response_fails_instead_of_dropping_item(self):
        with self.assertRaises(TypeError):
            normalize_records("G01-003", ["not-an-organization"], LINEAGE)

    def test_missing_organization_id_fails(self):
        with self.assertRaises(ValueError):
            normalize_record("G01-003", {"displayName": "Missing ID"}, LINEAGE)


class ApplicationsCurrentDispatchTests(unittest.TestCase):
    """G01-007 paginated Applications collection uses CURRENT dispatch."""

    def test_applications_normalize_approved_fields_only(self):
        record = {
            "id": "app-1",
            "appId": "app-id-1",
            "displayName": "Example App",
            "createdDateTime": "2026-08-19T12:00:00Z",
            "signInAudience": "AzureADMyOrg",
            "unknownField": "drop",
            "passwordCredentials": [{"secretText": "drop"}],
            "keyCredentials": [{"key": "drop"}],
            "web": {"redirectUris": ["https://example.test"]},
            "requiredResourceAccess": [{"resourceAppId": "drop"}],
            "access_token": "drop",
        }

        envelope = normalize_record("G01-007", record, LINEAGE)

        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT)
        self.assertEqual(
            set(envelope.current_row),
            {
                "tenant_id", "collection_run_id", "endpoint_run_id",
                "last_observed_at", "source_object_id", "app_id",
                "display_name", "created_date_time", "sign_in_audience",
                "retention_class",
            },
        )
        self.assertEqual(envelope.current_row["source_object_id"], "app-1")
        self.assertEqual(envelope.current_row["app_id"], "app-id-1")
        flat = str(envelope.to_dict())
        self.assertNotIn("passwordCredentials", flat)
        self.assertNotIn("keyCredentials", flat)
        self.assertNotIn("requiredResourceAccess", flat)
        self.assertNotIn("access_token", flat)

    def test_applications_optional_fields_are_nullable(self):
        row = normalize_record("G01-007", {"id": "app-2"}, LINEAGE).current_row
        self.assertEqual(row["source_object_id"], "app-2")
        self.assertIsNone(row["app_id"])
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["created_date_time"])
        self.assertIsNone(row["sign_in_audience"])

    def test_applications_reject_malformed_payload_and_missing_id(self):
        with self.assertRaises(TypeError):
            normalize_records("G01-007", ["not-an-application"], LINEAGE)
        with self.assertRaises(ValueError):
            normalize_record("G01-007", {"displayName": "Missing ID"}, LINEAGE)


class ServicePrincipalsCurrentDispatchTests(unittest.TestCase):
    """G01-008 paginated Service Principals collection uses CURRENT dispatch."""

    def test_service_principals_normalize_approved_fields_only(self):
        record = {
            "id": "sp-1",
            "appId": "app-id-1",
            "displayName": "Example SP",
            "accountEnabled": True,
            "servicePrincipalType": "Application",
            "keyCredentials": [{"key": "drop"}],
            "passwordCredentials": [{"secretText": "drop"}],
            "appRoleAssignments": [{"id": "drop"}],
            "oauth2PermissionGrants": [{"id": "drop"}],
            "permissions": [{"resource": "drop"}],
            "access_token": "drop",
        }

        envelope = normalize_record("G01-008", record, LINEAGE)

        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT)
        self.assertEqual(
            set(envelope.current_row),
            {
                "tenant_id", "collection_run_id", "endpoint_run_id",
                "last_observed_at", "source_object_id", "app_id",
                "display_name", "account_enabled", "service_principal_type",
                "retention_class",
            },
        )
        flat = str(envelope.to_dict())
        for excluded in (
            "keyCredentials", "passwordCredentials", "appRoleAssignments",
            "oauth2PermissionGrants", "permissions", "access_token",
        ):
            self.assertNotIn(excluded, flat)

    def test_service_principals_optional_fields_are_nullable(self):
        row = normalize_record("G01-008", {"id": "sp-2"}, LINEAGE).current_row
        self.assertEqual(row["source_object_id"], "sp-2")
        self.assertIsNone(row["app_id"])
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["account_enabled"])
        self.assertIsNone(row["service_principal_type"])

    def test_service_principals_reject_malformed_payload_and_missing_id(self):
        with self.assertRaises(TypeError):
            normalize_records("G01-008", ["not-a-service-principal"], LINEAGE)
        with self.assertRaises(ValueError):
            normalize_record("G01-008", {"displayName": "Missing ID"}, LINEAGE)


class CurrentDispatchTests(unittest.TestCase):
    """One representative CURRENT endpoint (G01-001)."""

    def test_returns_current_row_only(self):
        record = _user_record()
        snapshot_before = copy.deepcopy(record)
        envelope = normalize_record("G01-001", record, LINEAGE)
        self.assertIsInstance(envelope, NormalizedWorkloadRecord)
        self.assertEqual(envelope.endpoint_id, "G01-001")
        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT)
        self.assertIsNotNone(envelope.current_row)
        self.assertIsNone(envelope.snapshot_row)
        self.assertIsNone(envelope.history_row)
        self.assertIsNone(envelope.event_row)
        self.assertIsNone(envelope.reference_row)
        # Input was not mutated.
        self.assertEqual(record, snapshot_before)
        # Row carries expected lineage fields.
        row = envelope.current_row
        self.assertEqual(row["tenant_id"], 42)
        self.assertEqual(row["source_object_id"], "user-1")
        self.assertEqual(row["display_name"], "Alice Example")
        self.assertEqual(row["user_principal_name"], "alice@example.com")
        self.assertEqual(row["user_type"], "Member")

    def test_envelope_does_not_leak_input(self):
        record = _user_record()
        envelope = normalize_record("G01-001", record, LINEAGE)
        # Mutating the envelope row must not affect subsequent calls.
        envelope.current_row["display_name"] = "MUTATED"
        second = normalize_record("G01-001", record, LINEAGE)
        self.assertEqual(second.current_row["display_name"], "Alice Example")

    def test_excluded_graph_fields_are_not_retained(self):
        record = _user_record()
        record["mail"] = "alice@example.com"
        record["businessPhones"] = ["+1-555-0100"]
        envelope = normalize_record("G01-001", record, LINEAGE)
        self.assertNotIn("mail", envelope.current_row)
        self.assertNotIn("business_phones", envelope.current_row)


class ReferenceDispatchTests(unittest.TestCase):
    """One representative REFERENCE endpoint (G01-018)."""

    def test_reference_envelope_shape(self):
        record = _role_definition_record()
        envelope = normalize_record("G01-018", record, LINEAGE)
        self.assertEqual(envelope.persistence_mode, PersistenceMode.REFERENCE)
        self.assertIsNotNone(envelope.current_row)
        self.assertIsNotNone(envelope.reference_row)
        self.assertIsNone(envelope.snapshot_row)
        self.assertIsNone(envelope.history_row)
        self.assertIsNone(envelope.event_row)
        # ``rolePermissions`` excluded by the G01-018 adapter must not
        # appear anywhere in the envelope.
        flat = str(envelope.to_dict())
        self.assertNotIn("rolePermissions", flat)
        self.assertNotIn("allowedResourceActions", flat)

    def test_current_and_reference_row_share_keys(self):
        record = _role_definition_record()
        envelope = normalize_record("G01-018", record, LINEAGE)
        self.assertEqual(envelope.current_row, envelope.reference_row)


class EventDispatchTests(unittest.TestCase):
    """G01-005 / G01-006 event-stream endpoints."""

    def test_g01_005_event_source_is_directory_audit(self):
        envelope = normalize_record("G01-005", _audit_record(), LINEAGE)
        self.assertEqual(envelope.persistence_mode, PersistenceMode.EVENT)
        self.assertIsNotNone(envelope.event_row)
        self.assertIsNone(envelope.current_row)
        self.assertIsNone(envelope.snapshot_row)
        self.assertIsNone(envelope.history_row)
        self.assertIsNone(envelope.reference_row)
        self.assertEqual(envelope.event_row["event_source"], "DIRECTORY_AUDIT")
        self.assertEqual(envelope.event_row["source_object_id"], "audit-1")
        self.assertEqual(envelope.event_row["event_at"], "2026-08-19T12:00:00Z")
        self.assertEqual(envelope.event_row["activity"], "Update user")
        self.assertEqual(envelope.event_row["result"], "success")

    def test_g01_006_event_source_is_sign_in(self):
        envelope = normalize_record("G01-006", _sign_in_record(), LINEAGE)
        self.assertEqual(envelope.persistence_mode, PersistenceMode.EVENT)
        self.assertIsNotNone(envelope.event_row)
        self.assertEqual(envelope.event_row["event_source"], "SIGN_IN")
        self.assertEqual(envelope.event_row["source_object_id"], "sign-in-1")
        self.assertEqual(envelope.event_row["event_at"], "2026-08-19T13:00:00Z")
        self.assertEqual(envelope.event_row["is_interactive"], True)

    def test_event_rows_are_appended_to_the_same_table(self):
        # G01-005 and G01-006 share ``core.audit_event``.
        audit_envelope = normalize_record("G01-005", _audit_record(), LINEAGE)
        signin_envelope = normalize_record("G01-006", _sign_in_record(), LINEAGE)
        self.assertEqual(
            REGISTRY["G01-005"].event_table,
            REGISTRY["G01-006"].event_table,
        )
        self.assertEqual(audit_envelope.event_row["event_source"], "DIRECTORY_AUDIT")
        self.assertEqual(signin_envelope.event_row["event_source"], "SIGN_IN")

    def test_g01_005_retains_only_approved_fields_and_excludes_credentials(self):
        record = dict(_audit_record(), unknownField="drop", access_token="drop",
                      passwordCredentials=[{"secret": "drop"}], Authorization="drop")
        envelope = normalize_record("G01-005", record, LINEAGE)
        self.assertEqual(
            set(envelope.event_row),
            {"tenant_id", "event_source", "source_object_id", "event_at", "collected_at",
             "collection_run_id", "endpoint_run_id", "actor_user_id", "activity", "category",
             "result", "retention_class"},
        )
        flat = str(envelope.to_dict())
        self.assertNotIn("unknownField", flat)
        self.assertNotIn("access_token", flat)
        self.assertNotIn("passwordCredentials", flat)
        self.assertNotIn("Authorization", flat)

    def test_g01_006_retains_only_approved_fields_and_excludes_sign_in_metadata(self):
        record = dict(_sign_in_record(), ipAddress="192.0.2.1",
                      location={"city": "drop"}, userAgent="drop",
                      correlationId="drop", credential="drop",
                      access_token="drop", unknownField="drop")
        envelope = normalize_record("G01-006", record, LINEAGE)
        self.assertEqual(
            set(envelope.event_row),
            {"tenant_id", "event_source", "source_object_id", "event_at",
             "collected_at", "collection_run_id", "endpoint_run_id",
             "actor_user_id", "actor_app_id", "activity", "category", "result",
             "is_interactive", "retention_class"},
        )
        self.assertEqual(envelope.event_row["event_source"], "SIGN_IN")
        flat = str(envelope.to_dict())
        for excluded in ("192.0.2.1", "drop", "credential", "access_token"):
            self.assertNotIn(excluded, flat)


class CurrentWithSnapshotDispatchTests(unittest.TestCase):
    """G01-004 / G01-019 current + snapshot."""

    def test_g01_004_current_and_snapshot_rows(self):
        envelope = normalize_record(
            "G01-004", _subscribed_sku_record(), LINEAGE
        )
        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT_WITH_SNAPSHOT)
        self.assertIsNotNone(envelope.current_row)
        self.assertIsNotNone(envelope.snapshot_row)
        self.assertIsNone(envelope.history_row)
        self.assertIsNone(envelope.event_row)
        self.assertIsNone(envelope.reference_row)

        cur = envelope.current_row
        snap = envelope.snapshot_row
        self.assertEqual(cur["tenant_id"], 42)
        self.assertEqual(cur["source_object_id"], "sku-1")
        self.assertEqual(cur["sku_part_number"], "ENTERPRISE_E5")
        self.assertEqual(cur["consumed_units"], 5)
        # prepaidUnits.sum -> 25
        self.assertEqual(cur["prepaid_units"], 25)
        # Snapshot row also carries the lineage + table-specific columns.
        self.assertEqual(snap["source_object_id"], "sku-1")
        self.assertEqual(snap["collection_run_id"], 1001)
        self.assertEqual(snap["endpoint_run_id"], 9001)
        self.assertIn("snapshot_at", snap)
        self.assertEqual(snap["prepaid_units"], 25)

    def test_g01_011_current_and_snapshot_rows_are_metadata_only(self):
        record = {
            "id": "cap-1",
            "displayName": "Require MFA",
            "state": "enabled",
            "createdDateTime": "2026-08-19T00:00:00Z",
            "modifiedDateTime": "2026-08-20T00:00:00Z",
            "tenant_id": 999,
            "conditions": {"users": {"includeUsers": ["all"]}},
            "grantControls": {"builtInControls": ["mfa"]},
            "sessionControls": {"signInFrequency": {"value": 1}},
            "credentials": [{"secret": "drop"}],
        }
        envelope = normalize_record("G01-011", record, LINEAGE)
        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT_WITH_SNAPSHOT)
        self.assertEqual(envelope.current_row["source_object_id"], "cap-1")
        self.assertEqual(envelope.current_row["tenant_id"], 42)
        self.assertEqual(envelope.current_row["display_name"], "Require MFA")
        self.assertEqual(envelope.snapshot_row["collection_run_id"], 1001)
        self.assertNotIn("last_observed_at", envelope.snapshot_row)
        for excluded in ("conditions", "grantControls", "sessionControls", "credentials"):
            self.assertNotIn(excluded, str(envelope.to_dict()))

    def test_g01_011_rejects_missing_id_and_malformed_record(self):
        with self.assertRaises(ValueError):
            normalize_record("G01-011", {"displayName": "missing"}, LINEAGE)
        with self.assertRaises(TypeError):
            normalize_record("G01-011", ["not-a-record"], LINEAGE)

    def test_g01_004_retains_only_approved_fields_and_excludes_credentials(self):
        record = _subscribed_sku_record()
        record.update({
            "unknownField": "must-not-copy",
            "access_token": "must-not-copy",
            "passwordCredentials": [{"secret": "must-not-copy"}],
        })

        envelope = normalize_record("G01-004", record, LINEAGE)

        self.assertEqual(
            set(envelope.current_row),
            {
                "tenant_id", "collection_run_id", "endpoint_run_id",
                "last_observed_at", "source_object_id", "sku_id",
                "sku_part_number", "capability_status", "consumed_units",
                "prepaid_units", "service_plans", "retention_class",
            },
        )
        self.assertNotIn("unknownField", str(envelope.to_dict()))
        self.assertNotIn("access_token", str(envelope.to_dict()))
        self.assertNotIn("passwordCredentials", str(envelope.to_dict()))

    def test_g01_004_prepaid_units_variations_are_scalar(self):
        cases = [
            ({"enabled": 2, "suspended": 3, "warning": 4}, 9),
            ({"enabled": 2}, 2),
            ({"enabled": True, "suspended": 3}, 3),
            (None, 0),
            ("not-an-object", 0),
        ]
        for prepaid_units, expected in cases:
            with self.subTest(prepaid_units=prepaid_units):
                record = {"id": "sku-variation", "prepaidUnits": prepaid_units}
                envelope = normalize_record("G01-004", record, LINEAGE)
                self.assertEqual(envelope.current_row["prepaid_units"], expected)
                self.assertIsInstance(envelope.current_row["prepaid_units"], int)

    def test_g01_004_rejects_malformed_and_missing_id_records(self):
        with self.assertRaises(TypeError):
            normalize_record("G01-004", ["not-a-record"], LINEAGE)
        with self.assertRaises(ValueError):
            normalize_record("G01-004", {"skuId": "sku-without-id"}, LINEAGE)

    def test_g01_019_current_and_snapshot_rows(self):
        envelope = normalize_record(
            "G01-019", _role_assignment_record(), LINEAGE
        )
        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT_WITH_SNAPSHOT)
        self.assertIsNotNone(envelope.current_row)
        self.assertIsNotNone(envelope.snapshot_row)
        cur = envelope.current_row
        snap = envelope.snapshot_row
        self.assertEqual(cur["source_object_id"], "assignment-1")
        self.assertEqual(cur["role_definition_id"], "role-def-1")
        self.assertEqual(cur["principal_id"], "principal-1")
        self.assertEqual(cur["directory_scope_id"], "/")
        # Snapshot carries collection_run_id and snapshot_at; no
        # last_observed_at.
        self.assertEqual(snap["collection_run_id"], 1001)
        self.assertIn("snapshot_at", snap)
        self.assertNotIn("last_observed_at", snap)


class CurrentWithHistoryDispatchTests(unittest.TestCase):
    """G01-016 / G01-017 current + versioned history."""

    def test_g01_016_current_and_history_rows(self):
        record = _service_health_issue_record()
        envelope = normalize_record("G01-016", record, LINEAGE)
        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT_WITH_HISTORY)
        self.assertIsNotNone(envelope.current_row)
        self.assertIsNotNone(envelope.history_row)
        self.assertIsNone(envelope.snapshot_row)
        self.assertIsNone(envelope.event_row)
        self.assertIsNone(envelope.reference_row)

        cur = envelope.current_row
        hist = envelope.history_row
        self.assertEqual(cur["service"], "Exchange")
        self.assertEqual(cur["status"], "investigating")
        self.assertEqual(cur["is_resolved"], False)
        # History row carries the deterministic version_identity.
        self.assertIn("version_identity", hist)
        self.assertIsInstance(hist["version_identity"], (bytes, bytearray))
        self.assertEqual(len(hist["version_identity"]), 32)  # SHA-256

    def test_g01_016_history_version_identity_is_stable(self):
        record = _service_health_issue_record()
        first = normalize_record("G01-016", record, LINEAGE)
        second = normalize_record("G01-016", record, LINEAGE)
        self.assertEqual(
            first.history_row["version_identity"],
            second.history_row["version_identity"],
        )

    def test_g01_016_history_changes_with_last_modified(self):
        record = _service_health_issue_record()
        first = normalize_record("G01-016", record, LINEAGE)
        mutated = dict(record)
        mutated["lastModifiedDateTime"] = "2026-08-21T01:00:00Z"
        second = normalize_record("G01-016", mutated, LINEAGE)
        self.assertNotEqual(
            first.history_row["version_identity"],
            second.history_row["version_identity"],
        )

    def test_g01_017_current_and_history_rows(self):
        record = _service_update_message_record()
        envelope = normalize_record("G01-017", record, LINEAGE)
        self.assertEqual(envelope.persistence_mode, PersistenceMode.CURRENT_WITH_HISTORY)
        self.assertIsNotNone(envelope.current_row)
        self.assertIsNotNone(envelope.history_row)
        cur = envelope.current_row
        hist = envelope.history_row
        self.assertEqual(cur["category"], "PlanForChange")
        self.assertEqual(cur["severity"], "Normal")
        self.assertEqual(cur["services"], ["Exchange"])
        self.assertIn("version_identity", hist)

    def test_g01_017_history_version_identity_is_stable(self):
        record = _service_update_message_record()
        first = normalize_record("G01-017", record, LINEAGE)
        second = normalize_record("G01-017", record, LINEAGE)
        self.assertEqual(
            first.history_row["version_identity"],
            second.history_row["version_identity"],
        )

    def test_g01_017_history_changes_with_last_modified(self):
        record = _service_update_message_record()
        first = normalize_record("G01-017", record, LINEAGE)
        mutated = dict(record)
        mutated["lastModifiedDateTime"] = "2026-08-21T01:00:00Z"
        second = normalize_record("G01-017", mutated, LINEAGE)
        self.assertNotEqual(
            first.history_row["version_identity"],
            second.history_row["version_identity"],
        )

    def test_g01_017_history_changes_with_tenant(self):
        record = _service_update_message_record()
        first = normalize_record("G01-017", record, LINEAGE)
        other_lineage = LineageContext(
            tenant_id=99,
            collection_run_id=1001,
            endpoint_run_id=9001,
            observed_at="2026-08-20T12:00:00+00:00",
            retention_class="STANDARD",
        )
        second = normalize_record("G01-017", record, other_lineage)
        self.assertNotEqual(
            first.history_row["version_identity"],
            second.history_row["version_identity"],
        )


# ---------------------------------------------------------------------------
# General contract tests
# ---------------------------------------------------------------------------


class DispatchGeneralContractTests(unittest.TestCase):
    def test_unsupported_endpoint_raises_controlled_error(self):
        with self.assertRaises(WorkloadDispatchError):
            normalize_record("G99-999", {"id": "x"}, LINEAGE)
        with self.assertRaises(WorkloadDispatchError):
            normalize_record("", {"id": "x"}, LINEAGE)

    def test_supported_endpoint_does_not_raise(self):
        # Smoke check: a known endpoint with a valid record passes.
        envelope = normalize_record("G01-001", _user_record(), LINEAGE)
        self.assertEqual(envelope.endpoint_id, "G01-001")

    def test_unknown_endpoint_id_in_batch_raises(self):
        with self.assertRaises(WorkloadDispatchError):
            normalize_records("G99-999", [{"id": "x"}], LINEAGE)

    def test_input_record_not_mutated(self):
        for endpoint_id in ("G01-001", "G01-002", "G01-005", "G01-006",
                            "G01-004", "G01-019", "G01-016", "G01-017",
                            "G01-018"):
            record = _record_for(endpoint_id)
            snapshot = copy.deepcopy(record)
            normalize_record(endpoint_id, record, LINEAGE)
            self.assertEqual(record, snapshot, endpoint_id)

    def test_lineage_mapping_not_mutated(self):
        mapping = {
            "tenant_id": 42,
            "collection_run_id": 1001,
            "endpoint_run_id": 9001,
            "observed_at": "2026-08-20T12:00:00+00:00",
            "retention_class": "STANDARD",
        }
        before = copy.deepcopy(mapping)
        normalize_record("G01-001", _user_record(), mapping)
        self.assertEqual(mapping, before)

    def test_empty_batch_returns_empty_list(self):
        self.assertEqual(normalize_records("G01-001", [], LINEAGE), [])
        self.assertEqual(normalize_records("G01-005", [], LINEAGE), [])

    def test_batch_preserves_source_order(self):
        records = [
            {"id": "u-1", "displayName": "A"},
            {"id": "u-2", "displayName": "B"},
            {"id": "u-3", "displayName": "C"},
            {"id": "u-4", "displayName": "D"},
        ]
        envelopes = normalize_records("G01-001", records, LINEAGE)
        self.assertEqual(
            [e.current_row["source_object_id"] for e in envelopes],
            ["u-1", "u-2", "u-3", "u-4"],
        )

    def test_batch_handles_iterator_input(self):
        # Iterators (single-pass) must work; ``normalize_records``
        # materialises internally.
        def gen():
            for index in range(3):
                yield {"id": "u-{}".format(index), "displayName": "User {}".format(index)}

        envelopes = normalize_records("G01-001", gen(), LINEAGE)
        self.assertEqual(
            [e.current_row["source_object_id"] for e in envelopes],
            ["u-0", "u-1", "u-2"],
        )

    def test_malformed_input_fails_predictably(self):
        # The dispatcher must NOT silently drop records; the adapter
        # is invoked per record and any adapter error propagates.
        with self.assertRaises((TypeError, ValueError)):
            normalize_record("G01-001", "not a mapping", LINEAGE)
        with self.assertRaises((TypeError, ValueError)):
            normalize_record("G01-001", ["a", "list"], LINEAGE)
        with self.assertRaises((TypeError, ValueError)):
            normalize_record("G01-001", None, LINEAGE)

    def test_envelope_contains_no_credential_substrings(self):
        for endpoint_id in EXPECTED_ENDPOINT_IDS:
            record = _record_for(endpoint_id)
            envelope = normalize_record(endpoint_id, record, LINEAGE)
            flat = str(envelope.to_dict())
            for word in SENSITIVE_SUBSTRINGS:
                self.assertNotIn(
                    word.lower(),
                    flat.lower(),
                    "{}: envelope leaks '{}'".format(endpoint_id, word),
                )

    def test_role_definition_role_permissions_excluded(self):
        envelope = normalize_record(
            "G01-018",
            _role_definition_record(),
            LINEAGE,
        )
        flat = str(envelope.to_dict())
        self.assertNotIn("rolePermissions", flat)
        self.assertNotIn("allowedResourceActions", flat)

    def test_envelope_dispatch_is_deterministic(self):
        record = _service_health_issue_record()
        first = normalize_record("G01-016", record, LINEAGE)
        second = normalize_record("G01-016", record, LINEAGE)
        self.assertEqual(
            first.history_row["version_identity"],
            second.history_row["version_identity"],
        )
        self.assertEqual(first.current_row, second.current_row)


class LineageContextTests(unittest.TestCase):
    def test_lineage_from_mapping_g07a_shape(self):
        ctx = LineageContext.from_mapping({
            "tenant_id": 1,
            "collection_run_id": 2,
            "endpoint_run_id": 3,
            "observed_at": "2026-08-20T12:00:00Z",
        })
        self.assertEqual(ctx.tenant_id, 1)
        self.assertEqual(ctx.collection_run_id, 2)
        self.assertEqual(ctx.endpoint_run_id, 3)
        self.assertEqual(ctx.observed_at, "2026-08-20T12:00:00Z")

    def test_lineage_from_mapping_g07b_shape(self):
        ctx = LineageContext.from_mapping({
            "tenant_id": 1,
            "collection_run_id": 2,
            "endpoint_run_id": 3,
            "collected_at": "2026-08-20T12:00:00Z",
            "retention_class": "STANDARD",
        })
        # ``collected_at`` maps to ``observed_at``.
        self.assertEqual(ctx.observed_at, "2026-08-20T12:00:00Z")
        self.assertEqual(ctx.retention_class, "STANDARD")

    def test_lineage_from_mapping_none(self):
        ctx = LineageContext.from_mapping(None)
        self.assertIsNone(ctx.tenant_id)
        self.assertIsNone(ctx.observed_at)

    def test_lineage_from_mapping_rejects_non_mapping(self):
        with self.assertRaises(TypeError):
            LineageContext.from_mapping(42)


class GetEntryContractTests(unittest.TestCase):
    def test_get_entry_for_each_registered_endpoint(self):
        for endpoint_id in EXPECTED_ENDPOINT_IDS:
            entry = get_entry(endpoint_id)
            self.assertIs(entry, REGISTRY[endpoint_id])

    def test_get_entry_rejects_unknown(self):
        with self.assertRaises(WorkloadDispatchError):
            get_entry("G99-999")

    def test_get_entry_rejects_non_string(self):
        with self.assertRaises(WorkloadDispatchError):
            get_entry(None)
        with self.assertRaises(WorkloadDispatchError):
            get_entry(42)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_for(endpoint_id: str) -> dict:
    """Return a small fixture for ``endpoint_id`` covering the columns
    the underlying adapter requires (notably ``id``)."""
    if endpoint_id in ("G01-005",):
        return _audit_record()
    if endpoint_id in ("G01-006",):
        return _sign_in_record()
    if endpoint_id == "G01-004":
        return _subscribed_sku_record()
    if endpoint_id == "G01-016":
        return _service_health_issue_record()
    if endpoint_id == "G01-017":
        return _service_update_message_record()
    if endpoint_id == "G01-018":
        return _role_definition_record()
    if endpoint_id == "G01-019":
        return _role_assignment_record()
    if endpoint_id == "SP-A01":
        return {"Id": "sp-audit-1", "CreationTime": "2024-01-02T03:04:05Z", "Workload": "SharePoint", "Operation": "AnonymousLinkCreated"}
    if endpoint_id == "G01-002":
        return {"id": "g-1", "displayName": "Group", "mailEnabled": True,
                "securityEnabled": False}
    if endpoint_id == "G01-003":
        return {"id": "org-1", "displayName": "Example",
                "verifiedDomains": [], "countryLetterCode": "US",
                "tenantType": "AAD"}
    if endpoint_id == "G01-007":
        return {"id": "app-1", "appId": "app-id-1", "displayName": "App"}
    if endpoint_id == "G01-008":
        return {"id": "sp-1", "appId": "app-id-1", "displayName": "SP"}
    if endpoint_id == "G01-009":
        return {"id": "dev-1", "deviceId": "d-id-1"}
    if endpoint_id == "G01-010":
        return {"id": "au-1", "displayName": "AU", "description": "d"}
    if endpoint_id == "G01-011":
        return {"id": "cap-1", "displayName": "Policy", "state": "enabled"}
    if endpoint_id == "G01-012":
        return {"id": "nl-1", "displayName": "Location"}
    if endpoint_id == "G01-013":
        return {"id": "ru-1", "riskLevel": "low", "riskState": "atRisk"}
    if endpoint_id == "G01-014":
        return {"id": "rd-1", "riskEventType": "anonymizedIPAddress"}
    if endpoint_id == "G01-015":
        return {"id": "sho-1", "service": "Exchange", "status": "Operational"}
    # G01-001 default
    return _user_record()


if __name__ == "__main__":
    unittest.main()
