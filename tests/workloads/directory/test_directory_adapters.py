"""Offline unit tests for G07-A directory / licensing / RBAC adapters.

These tests:
- Use static fixtures (no live Microsoft Graph traffic).
- Verify the module contract required by the task scope.
- Verify that no credential / token material ever appears in any
  normalised row.
- Verify deterministic output for the same input.
- Verify non-object input is rejected with a deterministic error.
- Verify lineage and snapshotted-row semantics for G01-004 and G01-019.
"""
from __future__ import annotations

import json
import unittest

from collectors.workloads.directory import (
    ENDPOINT_IDS,
    administrative_units,
    applications,
    devices,
    directory_role_assignments,
    directory_role_definitions,
    get_adapter,
    groups,
    iter_adapters,
    organization,
    service_principals,
    subscribed_skus,
    users,
)


# A standalone set of substrings that should never appear in any row
# produced by any G07-A adapter. ``password`` is intentionally checked
# as a substring (so ``passwordCredentials`` and ``password_hash``
# would also be caught).
FORBIDDEN_SUBSTRINGS = (
    "Bearer",
    "Authorization",
    "secret",
    "password",
    "access_token",
    "refresh_token",
    "client_secret",
)


# Stable lineage constants used by every test.
TENANT_ID = 42
COLLECTION_RUN_ID = 1001
ENDPOINT_RUN_ID = 9001
OBSERVED_AT = "2026-08-20T12:00:00+00:00"


# Common Graph fixtures (from the inventory's $select lists plus a
# handful of representative fields for the snapshot-style endpoints).
USER_RECORD = {
    "id": "user-1",
    "displayName": "Alice Example",
    "userPrincipalName": "alice@example.com",
    "userType": "Member",
    "accountEnabled": True,
    "createdDateTime": "2024-01-02T03:04:05Z",
    "assignedLicenses": [{"skuId": "abc-123", "disabledPlans": []}],
    # Excluded fields — must NOT be copied into the row.
    "mail": "alice@example.com",
    "businessPhones": ["+1-555-0100"],
    "otherMails": ["alice@example.org"],
    "aboutMe": "free text",
}

GROUP_RECORD = {
    "id": "group-1",
    "displayName": "All Staff",
    "mail": "staff@example.com",
    "mailEnabled": True,
    "securityEnabled": False,
    "groupTypes": ["Unified"],
    # Excluded membership payload — must NOT be copied.
    "members": ["user-1", "user-2"],
}

ORG_RECORD = {
    "id": "org-1",
    "displayName": "Example Tenant",
    "countryLetterCode": "US",
    "tenantType": "AAD",
    "verifiedDomains": [
        {"name": "example.com", "type": "Managed", "isInitial": True},
    ],
}

SKU_RECORD = {
    "id": "sku-1",
    "skuId": "abc-123",
    "skuPartNumber": "ENTERPRISE_E5",
    "capabilityStatus": "Enabled",
    "consumedUnits": 17,
    "prepaidUnits": {"enabled": 25, "suspended": 0, "warning": 0},
    "servicePlans": [
        {"servicePlanId": "sp-1", "servicePlanName": "EXCHANGE_S_ENTERPRISE",
         "provisioningStatus": "Success", "appliesTo": "User"},
    ],
}

APP_RECORD = {
    "id": "app-1",
    "appId": "11111111-1111-1111-1111-111111111111",
    "displayName": "My App",
    "createdDateTime": "2024-06-01T00:00:00Z",
    "signInAudience": "AzureADMyOrg",
    # Excluded credential payloads — must NOT be copied.
    "passwordCredentials": [{"hint": "xx"}],
    "keyCredentials": [{"hint": "yy"}],
}

SP_RECORD = {
    "id": "sp-1",
    "appId": "11111111-1111-1111-1111-111111111111",
    "displayName": "My App SPN",
    "accountEnabled": True,
    "servicePrincipalType": "Application",
    # Excluded role-assignment payload — must NOT be copied.
    "appRoleAssignments": [{"id": "r-1"}],
}

DEVICE_RECORD = {
    "id": "device-1",
    "deviceId": "dev-graph-id-1",
    "accountEnabled": True,
    "operatingSystem": "Windows",
    "operatingSystemVersion": "10.0.22631",
    "trustType": "AzureAD",
    "approximateLastSignInDateTime": "2026-08-01T00:00:00Z",
}

AU_RECORD = {
    "id": "au-1",
    "displayName": "HQ AU",
    "description": "Administrative unit for HQ",
    "visibility": "Hidden",
}

ROLE_DEF_RECORD = {
    "id": "role-def-1",
    "displayName": "User Administrator",
    "description": "Can manage all aspects of users and groups.",
    "isBuiltIn": True,
    # Excluded permission payload — must NOT be copied.
    "rolePermissions": [
        {"allowedResourceActions": ["microsoft.directory/users/*"]},
    ],
}

ROLE_ASSIGN_RECORD = {
    "id": "role-assign-1",
    "roleDefinitionId": "role-def-1",
    "principalId": "user-1",
    "directoryScopeId": "/",
}


def _forbidden_substrings_in(row):
    """Return the list of forbidden substrings that appear in row."""
    blob = json.dumps(row, default=str)
    return [s for s in FORBIDDEN_SUBSTRINGS if s in blob]


class EndpointSetTests(unittest.TestCase):
    """Smoke tests for the worker-scope contract."""

    def test_all_ten_endpoint_ids_present_and_ordered(self):
        self.assertEqual(
            ENDPOINT_IDS,
            [
                "G01-001",
                "G01-002",
                "G01-003",
                "G01-004",
                "G01-007",
                "G01-008",
                "G01-009",
                "G01-010",
                "G01-018",
                "G01-019",
            ],
        )

    def test_get_adapter_unknown_returns_none(self):
        self.assertIsNone(get_adapter("G01-999"))

    def test_get_adapter_each_returns_correct_module(self):
        for module in iter_adapters():
            self.assertIs(get_adapter(module.ENDPOINT_ID), module)

    def test_iter_adapters_yields_all_ten(self):
        seen = [m.ENDPOINT_ID for m in iter_adapters()]
        self.assertEqual(len(seen), 10)
        self.assertEqual(len(set(seen)), 10)

    def test_each_adapter_exposes_contract_metadata(self):
        for module in iter_adapters():
            with self.subTest(endpoint=module.ENDPOINT_ID):
                spec = module.ADAPTER_SPEC
                self.assertEqual(spec.endpoint_id, module.ENDPOINT_ID)
                self.assertEqual(spec.target_table, module.TARGET_TABLE)
                self.assertEqual(spec.snapshot_table, module.SNAPSHOT_TABLE)
                self.assertEqual(spec.history_mode, module.HISTORY_MODE)
                self.assertEqual(spec.retention_class, module.RETENTION_CLASS)
                self.assertIs(spec.normalize, module.normalize)


class CurrentOnlyAdapterTests(unittest.TestCase):
    """Adapters for G01-001/002/003/007/008/009/010 emit a single dict."""

    def _call(self, module, record):
        return module.normalize(
            record,
            tenant_id=TENANT_ID,
            collection_run_id=COLLECTION_RUN_ID,
            endpoint_run_id=ENDPOINT_RUN_ID,
            observed_at=OBSERVED_AT,
        )

    def test_users_normalises_full_record(self):
        row = self._call(users, USER_RECORD)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "user-1")
        self.assertEqual(row["user_principal_name"], "alice@example.com")
        self.assertEqual(row["display_name"], "Alice Example")
        self.assertEqual(row["user_type"], "Member")
        self.assertTrue(row["account_enabled"])
        self.assertEqual(row["created_date_time"], "2024-01-02T03:04:05Z")
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")
        self.assertEqual(row["collection_run_id"], COLLECTION_RUN_ID)
        self.assertEqual(row["endpoint_run_id"], ENDPOINT_RUN_ID)
        # Excluded fields are not copied.
        self.assertNotIn("mail", row)
        self.assertNotIn("businessPhones", row)
        self.assertNotIn("otherMails", row)
        self.assertNotIn("aboutMe", row)

    def test_users_handles_null_and_missing_optional_fields(self):
        # Only the source id is required by the catalog; everything else
        # is optional / nullable.
        row = self._call(users, {"id": "user-2"})
        self.assertEqual(row["source_object_id"], "user-2")
        self.assertIsNone(row["user_principal_name"])
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["user_type"])
        self.assertIsNone(row["account_enabled"])
        self.assertIsNone(row["created_date_time"])
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)

    def test_users_rejects_non_object_input(self):
        for bad in ([], "string", 42, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    self._call(users, bad)

    def test_users_rejects_missing_id(self):
        with self.assertRaises(ValueError):
            self._call(users, {"displayName": "No Id"})

    def test_users_no_credential_substrings(self):
        row = self._call(users, USER_RECORD)
        self.assertEqual(_forbidden_substrings_in(row), [])

    def test_users_extracts_immutable_license_ids_without_retaining_payload(self):
        row = self._call(users, USER_RECORD)
        self.assertEqual(row["_assigned_licenses"], ["abc-123"])
        self.assertTrue(row["_assigned_licenses_available"])
        self.assertNotIn("disabledPlans", row)

    def test_users_marks_missing_entitlement_as_unavailable(self):
        row = self._call(users, {"id": "user-no-entitlement"})
        self.assertFalse(row["_assigned_licenses_available"])
        self.assertIsNone(row["_assigned_licenses"])

    def test_groups_normalises_full_record(self):
        row = self._call(groups, GROUP_RECORD)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "group-1")
        self.assertEqual(row["display_name"], "All Staff")
        self.assertEqual(row["mail"], "staff@example.com")
        self.assertTrue(row["mail_enabled"])
        self.assertFalse(row["security_enabled"])
        self.assertEqual(row["group_types"], ["Unified"])
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")
        # Membership payload is excluded.
        self.assertNotIn("members", row)

    def test_groups_handles_null_and_missing_optional_fields(self):
        row = self._call(groups, {"id": "g-2"})
        self.assertEqual(row["source_object_id"], "g-2")
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["mail"])
        self.assertIsNone(row["mail_enabled"])
        self.assertIsNone(row["security_enabled"])
        self.assertEqual(row["group_types"], [])

    def test_groups_filters_non_string_group_types(self):
        row = self._call(groups, {"id": "g-3", "groupTypes": ["ok", 42, "also-ok"]})
        self.assertEqual(row["group_types"], ["ok", "also-ok"])

    def test_groups_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call(groups, "not-a-dict")

    def test_groups_no_credential_substrings(self):
        self.assertEqual(_forbidden_substrings_in(self._call(groups, GROUP_RECORD)), [])

    def test_organization_normalises_full_record(self):
        row = self._call(organization, ORG_RECORD)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "org-1")
        self.assertEqual(row["display_name"], "Example Tenant")
        self.assertEqual(row["country_letter_code"], "US")
        self.assertEqual(row["tenant_type"], "AAD")
        self.assertEqual(row["verified_domains"], [
            {"name": "example.com", "type": "Managed", "isInitial": True},
        ])
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")

    def test_organization_handles_null_and_missing_optional_fields(self):
        row = self._call(organization, {"id": "org-2"})
        self.assertEqual(row["source_object_id"], "org-2")
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["country_letter_code"])
        self.assertIsNone(row["tenant_type"])
        self.assertIsNone(row["verified_domains"])

    def test_organization_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call(organization, 99)

    def test_organization_no_credential_substrings(self):
        self.assertEqual(_forbidden_substrings_in(self._call(organization, ORG_RECORD)), [])

    def test_applications_normalises_full_record(self):
        row = self._call(applications, APP_RECORD)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "app-1")
        self.assertEqual(row["app_id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(row["display_name"], "My App")
        self.assertEqual(row["sign_in_audience"], "AzureADMyOrg")
        self.assertEqual(row["created_date_time"], "2024-06-01T00:00:00Z")
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")
        # Credential payloads are excluded.
        self.assertNotIn("passwordCredentials", row)
        self.assertNotIn("keyCredentials", row)

    def test_applications_handles_null_and_missing_optional_fields(self):
        row = self._call(applications, {"id": "app-2"})
        self.assertEqual(row["source_object_id"], "app-2")
        self.assertIsNone(row["app_id"])
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["sign_in_audience"])
        self.assertIsNone(row["created_date_time"])

    def test_applications_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call(applications, None)

    def test_applications_no_credential_substrings(self):
        self.assertEqual(_forbidden_substrings_in(self._call(applications, APP_RECORD)), [])

    def test_service_principals_normalises_full_record(self):
        row = self._call(service_principals, SP_RECORD)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "sp-1")
        self.assertEqual(row["app_id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(row["display_name"], "My App SPN")
        self.assertTrue(row["account_enabled"])
        self.assertEqual(row["service_principal_type"], "Application")
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")
        # Excluded payload.
        self.assertNotIn("appRoleAssignments", row)

    def test_service_principals_handles_null_and_missing_optional_fields(self):
        row = self._call(service_principals, {"id": "sp-2"})
        self.assertEqual(row["source_object_id"], "sp-2")
        self.assertIsNone(row["app_id"])
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["account_enabled"])
        self.assertIsNone(row["service_principal_type"])

    def test_service_principals_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call(service_principals, [])

    def test_service_principals_no_credential_substrings(self):
        self.assertEqual(
            _forbidden_substrings_in(self._call(service_principals, SP_RECORD)),
            [],
        )

    def test_devices_normalises_full_record(self):
        row = self._call(devices, {
            **DEVICE_RECORD,
            "unknownProperty": "drop",
            "keyCredentials": [{"key": "drop"}],
            "passwordCredentials": [{"secretText": "drop"}],
            "tokenMaterial": "drop",
            "authorizationData": {"scope": "drop"},
        })
        self.assertEqual(set(row), {
            "tenant_id", "collection_run_id", "endpoint_run_id",
            "last_observed_at", "source_object_id", "device_graph_id",
            "account_enabled", "operating_system", "operating_system_version",
            "trust_type", "approximate_last_sign_in_date_time",
            "retention_class",
        })
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "device-1")
        self.assertEqual(row["device_graph_id"], "dev-graph-id-1")
        self.assertTrue(row["account_enabled"])
        self.assertEqual(row["operating_system"], "Windows")
        self.assertEqual(row["operating_system_version"], "10.0.22631")
        self.assertEqual(row["trust_type"], "AzureAD")
        self.assertEqual(row["approximate_last_sign_in_date_time"],
                         "2026-08-01T00:00:00Z")
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")

    def test_devices_handles_null_and_missing_optional_fields(self):
        row = self._call(devices, {"id": "device-2"})
        self.assertEqual(row["source_object_id"], "device-2")
        self.assertIsNone(row["device_graph_id"])
        self.assertIsNone(row["account_enabled"])
        self.assertIsNone(row["operating_system"])
        self.assertIsNone(row["operating_system_version"])
        self.assertIsNone(row["trust_type"])
        self.assertIsNone(row["approximate_last_sign_in_date_time"])

    def test_devices_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call(devices, "oops")

    def test_devices_rejects_missing_id(self):
        with self.assertRaises(ValueError):
            self._call(devices, {"deviceId": "without-source-id"})

    def test_devices_no_credential_substrings(self):
        self.assertEqual(_forbidden_substrings_in(self._call(devices, DEVICE_RECORD)), [])

    def test_administrative_units_normalises_full_record(self):
        row = self._call(administrative_units, AU_RECORD)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "au-1")
        self.assertEqual(row["display_name"], "HQ AU")
        self.assertEqual(row["description"], "Administrative unit for HQ")
        self.assertEqual(row["visibility"], "Hidden")
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")

    def test_administrative_units_handles_null_and_missing_optional_fields(self):
        row = self._call(administrative_units, {"id": "au-2"})
        self.assertEqual(row["source_object_id"], "au-2")
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["description"])
        self.assertIsNone(row["visibility"])

    def test_administrative_units_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call(administrative_units, 0)

    def test_administrative_units_rejects_missing_id(self):
        with self.assertRaises(ValueError):
            self._call(administrative_units, {"displayName": "Missing ID"})

    def test_administrative_units_retains_only_approved_fields(self):
        row = self._call(administrative_units, {
            **AU_RECORD,
            "unknownField": "drop",
            "membershipRule": "drop",
            "access_token": "drop",
            "passwordCredentials": [{"secretText": "drop"}],
        })
        self.assertEqual(
            set(row),
            {
                "tenant_id", "collection_run_id", "endpoint_run_id",
                "last_observed_at", "source_object_id", "display_name",
                "description", "visibility", "retention_class",
            },
        )

    def test_administrative_units_no_credential_substrings(self):
        self.assertEqual(
            _forbidden_substrings_in(self._call(administrative_units, AU_RECORD)),
            [],
        )


class DirectoryRoleDefinitionTests(unittest.TestCase):
    """G01-018 is a REFERENCE table -- not a snapshot."""

    def _call(self, record):
        return directory_role_definitions.normalize(
            record,
            tenant_id=TENANT_ID,
            collection_run_id=COLLECTION_RUN_ID,
            endpoint_run_id=ENDPOINT_RUN_ID,
            observed_at=OBSERVED_AT,
        )

    def test_role_definition_normalises_full_record(self):
        row = self._call(ROLE_DEF_RECORD)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_object_id"], "role-def-1")
        self.assertEqual(row["display_name"], "User Administrator")
        self.assertEqual(row["description"],
                         "Can manage all aspects of users and groups.")
        self.assertTrue(row["is_built_in"])
        self.assertEqual(row["last_observed_at"], OBSERVED_AT)
        self.assertEqual(row["retention_class"], "REFERENCE")
        # rolePermissions payload is excluded per the catalog.
        self.assertNotIn("rolePermissions", row)

    def test_role_definition_handles_null_and_missing_optional_fields(self):
        row = self._call({"id": "rd-2"})
        self.assertEqual(row["source_object_id"], "rd-2")
        self.assertIsNone(row["display_name"])
        self.assertIsNone(row["description"])
        self.assertIsNone(row["is_built_in"])

    def test_role_definition_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call("not-a-dict")

    def test_role_definition_rejects_missing_id(self):
        with self.assertRaises(ValueError):
            self._call({"displayName": "No Id"})

    def test_role_definition_no_credential_substrings(self):
        self.assertEqual(_forbidden_substrings_in(self._call(ROLE_DEF_RECORD)), [])

    def test_role_definition_history_mode_is_reference(self):
        self.assertEqual(
            directory_role_definitions.HISTORY_MODE, "REFERENCE",
        )
        self.assertIsNone(directory_role_definitions.SNAPSHOT_TABLE)


class HistoricalWithSnapshotAdapterTests(unittest.TestCase):
    """G01-004 and G01-019 emit TWO row-shaped dicts."""

    def _call_sku(self, record):
        return subscribed_skus.normalize(
            record,
            tenant_id=TENANT_ID,
            collection_run_id=COLLECTION_RUN_ID,
            endpoint_run_id=ENDPOINT_RUN_ID,
            observed_at=OBSERVED_AT,
        )

    def _call_ra(self, record):
        return directory_role_assignments.normalize(
            record,
            tenant_id=TENANT_ID,
            collection_run_id=COLLECTION_RUN_ID,
            endpoint_run_id=ENDPOINT_RUN_ID,
            observed_at=OBSERVED_AT,
        )

    def test_sku_returns_current_and_snapshot_pair(self):
        current, snapshot = self._call_sku(SKU_RECORD)
        # ----- current-state row -----
        self.assertEqual(current["tenant_id"], TENANT_ID)
        self.assertEqual(current["source_object_id"], "sku-1")
        self.assertEqual(current["sku_id"], "abc-123")
        self.assertEqual(current["sku_part_number"], "ENTERPRISE_E5")
        self.assertEqual(current["capability_status"], "Enabled")
        self.assertEqual(current["consumed_units"], 17)
        # total prepaid = enabled + suspended + warning = 25
        self.assertEqual(current["prepaid_units"], 25)
        self.assertEqual(current["service_plans"], SKU_RECORD["servicePlans"])
        self.assertEqual(current["last_observed_at"], OBSERVED_AT)
        self.assertEqual(current["retention_class"], "STANDARD")
        # ----- snapshot row -----
        self.assertEqual(snapshot["tenant_id"], TENANT_ID)
        self.assertEqual(snapshot["source_object_id"], "sku-1")
        self.assertEqual(snapshot["collection_run_id"], COLLECTION_RUN_ID)
        self.assertEqual(snapshot["endpoint_run_id"], ENDPOINT_RUN_ID)
        self.assertEqual(snapshot["snapshot_at"], OBSERVED_AT)
        self.assertEqual(snapshot["consumed_units"], 17)
        self.assertEqual(snapshot["prepaid_units"], 25)
        self.assertEqual(snapshot["capability_status"], "Enabled")
        self.assertEqual(snapshot["service_plans"], SKU_RECORD["servicePlans"])
        self.assertEqual(snapshot["retention_class"], "STANDARD")

    def test_sku_handles_null_and_missing_optional_fields(self):
        current, snapshot = self._call_sku({"id": "sku-2"})
        self.assertEqual(current["source_object_id"], "sku-2")
        self.assertIsNone(current["sku_id"])
        self.assertIsNone(current["sku_part_number"])
        self.assertIsNone(current["capability_status"])
        self.assertIsNone(current["consumed_units"])
        self.assertEqual(current["prepaid_units"], 0)
        self.assertIsNone(current["service_plans"])
        self.assertEqual(snapshot["source_object_id"], "sku-2")
        self.assertEqual(snapshot["prepaid_units"], 0)

    def test_sku_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call_sku("not-a-dict")

    def test_sku_no_credential_substrings(self):
        current, snapshot = self._call_sku(SKU_RECORD)
        self.assertEqual(_forbidden_substrings_in(current), [])
        self.assertEqual(_forbidden_substrings_in(snapshot), [])

    def test_sku_history_mode_is_historical_with_snapshot(self):
        self.assertEqual(
            subscribed_skus.HISTORY_MODE, "HISTORICAL_WITH_SNAPSHOT",
        )
        self.assertEqual(
            subscribed_skus.SNAPSHOT_TABLE, "core.subscribed_sku_snapshot",
        )

    def test_sku_snapshot_uniqueness_identity_present(self):
        # The snapshot row must carry the trio the schema requires for
        # UNIQUE(tenant_id, source_object_id, collection_run_id).
        _, snapshot = self._call_sku(SKU_RECORD)
        self.assertIn("tenant_id", snapshot)
        self.assertIn("source_object_id", snapshot)
        self.assertIn("collection_run_id", snapshot)

    def test_role_assign_returns_current_and_snapshot_pair(self):
        current, snapshot = self._call_ra(ROLE_ASSIGN_RECORD)
        # ----- current-state row -----
        self.assertEqual(current["tenant_id"], TENANT_ID)
        self.assertEqual(current["source_object_id"], "role-assign-1")
        self.assertEqual(current["role_definition_id"], "role-def-1")
        self.assertEqual(current["principal_id"], "user-1")
        self.assertEqual(current["directory_scope_id"], "/")
        self.assertEqual(current["last_observed_at"], OBSERVED_AT)
        self.assertEqual(current["retention_class"], "LONG")
        # ----- snapshot row -----
        self.assertEqual(snapshot["tenant_id"], TENANT_ID)
        self.assertEqual(snapshot["source_object_id"], "role-assign-1")
        self.assertEqual(snapshot["collection_run_id"], COLLECTION_RUN_ID)
        self.assertEqual(snapshot["endpoint_run_id"], ENDPOINT_RUN_ID)
        self.assertEqual(snapshot["snapshot_at"], OBSERVED_AT)
        self.assertEqual(snapshot["role_definition_id"], "role-def-1")
        self.assertEqual(snapshot["principal_id"], "user-1")
        self.assertEqual(snapshot["directory_scope_id"], "/")
        self.assertEqual(snapshot["retention_class"], "LONG")

    def test_role_assign_handles_null_and_missing_optional_fields(self):
        current, snapshot = self._call_ra({"id": "ra-2"})
        self.assertEqual(current["source_object_id"], "ra-2")
        self.assertIsNone(current["role_definition_id"])
        self.assertIsNone(current["principal_id"])
        self.assertIsNone(current["directory_scope_id"])
        self.assertEqual(snapshot["source_object_id"], "ra-2")
        self.assertIsNone(snapshot["role_definition_id"])
        self.assertIsNone(snapshot["principal_id"])
        self.assertIsNone(snapshot["directory_scope_id"])

    def test_role_assign_rejects_non_object_input(self):
        with self.assertRaises(TypeError):
            self._call_ra(None)

    def test_role_assign_history_mode_is_historical_with_snapshot(self):
        self.assertEqual(
            directory_role_assignments.HISTORY_MODE,
            "HISTORICAL_WITH_SNAPSHOT",
        )
        self.assertEqual(
            directory_role_assignments.SNAPSHOT_TABLE,
            "core.directory_role_assignment_snapshot",
        )

    def test_role_assign_snapshot_uniqueness_identity_present(self):
        _, snapshot = self._call_ra(ROLE_ASSIGN_RECORD)
        self.assertIn("tenant_id", snapshot)
        self.assertIn("source_object_id", snapshot)
        self.assertIn("collection_run_id", snapshot)

    def test_role_assign_no_credential_substrings(self):
        current, snapshot = self._call_ra(ROLE_ASSIGN_RECORD)
        self.assertEqual(_forbidden_substrings_in(current), [])
        self.assertEqual(_forbidden_substrings_in(snapshot), [])


class LineageAndDeterminismTests(unittest.TestCase):
    """Cross-cutting properties every adapter must satisfy."""

    def _normalize_all(self, record):
        """Normalise the same record against every adapter and return
        the resulting row(s) per adapter."""
        results = {}
        for module in iter_adapters():
            out = module.normalize(
                record,
                tenant_id=TENANT_ID,
                collection_run_id=COLLECTION_RUN_ID,
                endpoint_run_id=ENDPOINT_RUN_ID,
                observed_at=OBSERVED_AT,
            )
            results[module.ENDPOINT_ID] = out
        return results

    def test_all_adapters_preserve_tenant_id(self):
        results = self._normalize_all({
            "id": "obj-1",
            "displayName": "x",
            "userPrincipalName": "u@x",
            "userType": "Member",
            "accountEnabled": True,
            "createdDateTime": "2024-01-01T00:00:00Z",
            "mail": "x",
            "mailEnabled": True,
            "securityEnabled": False,
            "groupTypes": ["Unified"],
            "countryLetterCode": "US",
            "tenantType": "AAD",
            "verifiedDomains": [],
            "skuId": "x",
            "skuPartNumber": "x",
            "capabilityStatus": "Enabled",
            "consumedUnits": 1,
            "prepaidUnits": {"enabled": 1, "suspended": 0, "warning": 0},
            "servicePlans": [],
            "appId": "x",
            "signInAudience": "AzureADMyOrg",
            "servicePrincipalType": "Application",
            "deviceId": "x",
            "operatingSystem": "Linux",
            "operatingSystemVersion": "1.0",
            "trustType": "AzureAD",
            "approximateLastSignInDateTime": "2026-01-01T00:00:00Z",
            "description": "x",
            "visibility": "Hidden",
            "isBuiltIn": True,
            "roleDefinitionId": "rd",
            "principalId": "p",
            "directoryScopeId": "/",
        })
        for endpoint_id, out in results.items():
            with self.subTest(endpoint_id=endpoint_id):
                rows = out if isinstance(out, tuple) else (out,)
                for row in rows:
                    self.assertEqual(row["tenant_id"], TENANT_ID)
                    self.assertEqual(row["collection_run_id"], COLLECTION_RUN_ID)
                    self.assertEqual(row["endpoint_run_id"], ENDPOINT_RUN_ID)
                    self.assertEqual(row["source_object_id"], "obj-1")

    def test_all_adapters_are_deterministic(self):
        # Two calls with identical inputs must produce byte-identical
        # dicts (modulo any field that the adapter explicitly omits).
        for module in iter_adapters():
            with self.subTest(endpoint_id=module.ENDPOINT_ID):
                record = self._build_minimal_record(module)
                first = module.normalize(
                    record,
                    tenant_id=TENANT_ID,
                    collection_run_id=COLLECTION_RUN_ID,
                    endpoint_run_id=ENDPOINT_RUN_ID,
                    observed_at=OBSERVED_AT,
                )
                second = module.normalize(
                    record,
                    tenant_id=TENANT_ID,
                    collection_run_id=COLLECTION_RUN_ID,
                    endpoint_run_id=ENDPOINT_RUN_ID,
                    observed_at=OBSERVED_AT,
                )
                self.assertEqual(
                    json.dumps(first, default=str, sort_keys=True),
                    json.dumps(second, default=str, sort_keys=True),
                )

    def _build_minimal_record(self, module):
        """Build a record that satisfies the catalog's required id for
        the given adapter. The body is intentionally sparse so the
        determinism check focuses on the adapter's branch logic."""
        return {"id": module.ENDPOINT_ID + "-obj-1"}

    def test_invalid_input_is_rejected_everywhere(self):
        for module in iter_adapters():
            with self.subTest(endpoint_id=module.ENDPOINT_ID):
                for bad in (None, "string", 42, 3.14, [], True):
                    with self.assertRaises(TypeError):
                        module.normalize(
                            bad,
                            tenant_id=TENANT_ID,
                            collection_run_id=COLLECTION_RUN_ID,
                            endpoint_run_id=ENDPOINT_RUN_ID,
                            observed_at=OBSERVED_AT,
                        )

    def test_missing_id_is_rejected_everywhere(self):
        for module in iter_adapters():
            with self.subTest(endpoint_id=module.ENDPOINT_ID):
                with self.assertRaises(ValueError):
                    module.normalize(
                        {"displayName": "no-id"},
                        tenant_id=TENANT_ID,
                        collection_run_id=COLLECTION_RUN_ID,
                        endpoint_run_id=ENDPOINT_RUN_ID,
                        observed_at=OBSERVED_AT,
                    )


class SecurityAndExclusionTests(unittest.TestCase):
    """Cross-cutting security: no credential / token material in any
    row produced by any G07-A adapter."""

    def test_forbidden_substrings_absent_for_all_fixtures(self):
        fixtures = {
            "G01-001": USER_RECORD,
            "G01-002": GROUP_RECORD,
            "G01-003": ORG_RECORD,
            "G01-004": SKU_RECORD,
            "G01-007": APP_RECORD,
            "G01-008": SP_RECORD,
            "G01-009": DEVICE_RECORD,
            "G01-010": AU_RECORD,
            "G01-018": ROLE_DEF_RECORD,
            "G01-019": ROLE_ASSIGN_RECORD,
        }
        for module in iter_adapters():
            with self.subTest(endpoint_id=module.ENDPOINT_ID):
                out = module.normalize(
                    fixtures[module.ENDPOINT_ID],
                    tenant_id=TENANT_ID,
                    collection_run_id=COLLECTION_RUN_ID,
                    endpoint_run_id=ENDPOINT_RUN_ID,
                    observed_at=OBSERVED_AT,
                )
                rows = out if isinstance(out, tuple) else (out,)
                for row in rows:
                    self.assertEqual(_forbidden_substrings_in(row), [],
                                     msg="forbidden substrings in {}".format(
                                         module.ENDPOINT_ID))

    def test_known_excluded_fields_are_not_copied(self):
        # Each input fixture contains a payload that the G03 catalog
        # explicitly excludes. The adapter must not copy it.
        exclusions = {
            "G01-001": ("mail", "businessPhones", "otherMails", "aboutMe"),
            "G01-002": ("members",),
            "G01-007": ("passwordCredentials", "keyCredentials"),
            "G01-008": ("appRoleAssignments",),
            "G01-018": ("rolePermissions",),
        }
        fixtures = {
            "G01-001": USER_RECORD,
            "G01-002": GROUP_RECORD,
            "G01-007": APP_RECORD,
            "G01-008": SP_RECORD,
            "G01-018": ROLE_DEF_RECORD,
        }
        for endpoint_id, forbidden_keys in exclusions.items():
            module = get_adapter(endpoint_id)
            with self.subTest(endpoint_id=endpoint_id):
                out = module.normalize(
                    fixtures[endpoint_id],
                    tenant_id=TENANT_ID,
                    collection_run_id=COLLECTION_RUN_ID,
                    endpoint_run_id=ENDPOINT_RUN_ID,
                    observed_at=OBSERVED_AT,
                )
                rows = out if isinstance(out, tuple) else (out,)
                for row in rows:
                    for key in forbidden_keys:
                        self.assertNotIn(key, row)


class HistoryModeMetadataTests(unittest.TestCase):
    """Pin the persistence / history mode of each adapter."""

    def test_history_mode_table_for_each_endpoint(self):
        cases = {
            "G01-001": ("CURRENT_ONLY", "REFERENCE"),
            "G01-002": ("CURRENT_ONLY", "REFERENCE"),
            "G01-003": ("CURRENT_ONLY", "REFERENCE"),
            "G01-004": ("HISTORICAL_WITH_SNAPSHOT", "STANDARD"),
            "G01-007": ("CURRENT_ONLY", "REFERENCE"),
            "G01-008": ("CURRENT_ONLY", "REFERENCE"),
            "G01-009": ("CURRENT_ONLY", "REFERENCE"),
            "G01-010": ("CURRENT_ONLY", "REFERENCE"),
            "G01-018": ("REFERENCE", "REFERENCE"),
            "G01-019": ("HISTORICAL_WITH_SNAPSHOT", "LONG"),
        }
        for endpoint_id, (mode, retention) in cases.items():
            with self.subTest(endpoint_id=endpoint_id):
                module = get_adapter(endpoint_id)
                self.assertEqual(module.HISTORY_MODE, mode)
                self.assertEqual(module.RETENTION_CLASS, retention)
                spec = module.ADAPTER_SPEC
                self.assertEqual(spec.history_mode, mode)
                self.assertEqual(spec.retention_class, retention)

    def test_snapshot_table_only_where_history_mode_says_so(self):
        for module in iter_adapters():
            with self.subTest(endpoint_id=module.ENDPOINT_ID):
                if module.HISTORY_MODE == "HISTORICAL_WITH_SNAPSHOT":
                    self.assertIsNotNone(module.SNAPSHOT_TABLE)
                else:
                    self.assertIsNone(module.SNAPSHOT_TABLE)


if __name__ == "__main__":
    unittest.main()
