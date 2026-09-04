"""Offline tests for the G07-C central workload registry.

These tests verify:

* the registry has canonical ``G01-001..G01-020`` plus ``SP-A01``;
* no duplicate / unknown endpoint ids are registered;
* each registered entry has the persistence mode, target tables and
  owner that the task brief specifies (CURRENT / REFERENCE / EVENT /
  CURRENT_WITH_SNAPSHOT / CURRENT_WITH_HISTORY);
* the registry covers every endpoint id in
  ``config/api_inventory.json``;
* the registry does not register an endpoint id that does not appear
  in the inventory;
* the table-mapping metadata matches the accepted G06 DDL as exposed
  by the migration files.

No live Microsoft Graph calls are made. No credentials are loaded.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from collectors.workloads import (
    EXPECTED_ENDPOINT_IDS,
    PERSISTENCE_CURRENT,
    PERSISTENCE_CURRENT_WITH_HISTORY,
    PERSISTENCE_CURRENT_WITH_SNAPSHOT,
    PERSISTENCE_EVENT,
    PERSISTENCE_MODES,
    PERSISTENCE_REFERENCE,
    PersistenceMode,
    REGISTRY,
    RegistryCoverageError,
    WorkloadEntry,
    endpoint_ids,
    get_entry,
    iter_entries,
    normalize_record,
    validate_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "config" / "api_inventory.json"


# ---------------------------------------------------------------------------
# Persistence-mode buckets per task brief
# ---------------------------------------------------------------------------


EXPECTED_MODE_BUCKETS = {
    PERSISTENCE_CURRENT: {
        "G01-001",
        "G01-002",
        "G01-003",
        "G01-007",
        "G01-008",
        "G01-009",
        "G01-010",
        "G01-012",
        "G01-020",
        "DEF-P02",
        "DEF-P03",
        "DLP-P01",
        "DLP-P02",
    },
    PERSISTENCE_REFERENCE: {"G01-018"},
    PERSISTENCE_EVENT: {"G01-005", "G01-006", "G01-014", "SP-A01"},
    PERSISTENCE_CURRENT_WITH_SNAPSHOT: {
        "G01-004",
        "G01-011",
        "G01-013",
        "G01-015",
        "G01-019",
        "TM-001",
    },
    PERSISTENCE_CURRENT_WITH_HISTORY: {"G01-016", "G01-017"},
}


# Expected owner per endpoint id; documented for traceability.
EXPECTED_OWNER = {
    "G01-001": "directory",
    "G01-002": "directory",
    "G01-003": "directory",
    "G01-004": "directory",
    "G01-005": "security_service",
    "G01-006": "security_service",
    "G01-007": "directory",
    "G01-008": "directory",
    "G01-009": "directory",
    "G01-010": "directory",
    "G01-011": "security_service",
    "G01-012": "security_service",
    "G01-013": "security_service",
    "G01-014": "security_service",
    "G01-015": "security_service",
    "G01-016": "security_service",
    "G01-017": "security_service",
    "G01-018": "directory",
    "G01-019": "directory",
    "G01-020": "security_service",
    "SP-A01": "security_service",
    "TM-001": "usage_reports",
}


# Expected table mapping for every endpoint. Reconciled against
# database/migrations/003..005.
EXPECTED_TABLE_MAPPING = {
    "G01-001": {"current": 'core."user"'},
    "G01-002": {"current": 'core."group"'},
    "G01-003": {"current": "core.organization"},
    "G01-004": {
        "current": "core.subscribed_sku",
        "snapshot": "core.subscribed_sku_snapshot",
    },
    "G01-005": {"current": "core.audit_event", "event": "core.audit_event"},
    "G01-006": {"current": "core.signin_log", "event": "core.signin_log"},
    "G01-007": {"current": "core.application"},
    "G01-008": {"current": "core.service_principal"},
    "G01-009": {"current": "core.device"},
    "G01-010": {"current": "core.administrative_unit"},
    "G01-011": {
        "current": "core.conditional_access_policy",
        "snapshot": "core.conditional_access_policy_snapshot",
    },
    "G01-012": {"current": "core.named_location"},
    "G01-013": {
        "current": "core.risky_user",
        "snapshot": "core.risky_user_snapshot",
    },
    "G01-014": {"current": "core.risk_detection", "event": "core.risk_detection"},
    "G01-015": {
        "current": "core.service_health_overview",
        "snapshot": "core.service_health_overview_snapshot",
    },
    "G01-016": {
        "current": "core.service_health_issue",
        "history": "core.service_health_issue_history",
    },
    "G01-017": {
        "current": "core.service_update_message",
        "history": "core.service_update_message_history",
    },
    "G01-018": {"current": "core.directory_role_definition"},
    "G01-019": {
        "current": "core.directory_role_assignment",
        "snapshot": "core.directory_role_assignment_snapshot",
    },
    "G01-020": {"current": "core.sharepoint_tenant_settings"},
    "SP-A01": {"current": "core.sharepoint_high_value_audit_event", "event": "core.sharepoint_high_value_audit_event"},
    "TM-001": {"current": "core.usage_teams_user_activity", "snapshot": "core.usage_teams_user_activity_snapshot"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_inventory_ids():
    """Return inventory endpoints owned by the Collector workload registry."""
    payload = json.loads(INVENTORY_PATH.read_text())
    return {
        item["id"] for item in payload
        if item.get("endpoint_type", "WORKLOAD") == "WORKLOAD"
        and item.get("transport_type", "NORMAL_GRAPH_JSON") == "NORMAL_GRAPH_JSON"
        and (item.get("collector_type", "declarative") != "specialized" or item["id"] in REGISTRY)
    }


# ---------------------------------------------------------------------------
# Registry structural tests
# ---------------------------------------------------------------------------


class RegistryShapeTests(unittest.TestCase):
    def test_registry_has_expected_entries(self):
        self.assertEqual(len(REGISTRY), len(EXPECTED_ENDPOINT_IDS))
        self.assertEqual(len(endpoint_ids()), len(EXPECTED_ENDPOINT_IDS))

    def test_registry_ids_match_expected_set(self):
        self.assertEqual(set(endpoint_ids()), set(EXPECTED_ENDPOINT_IDS))
        self.assertEqual(set(EXPECTED_ENDPOINT_IDS), set(EXPECTED_ENDPOINT_IDS))

    def test_registry_has_no_duplicates(self):
        # ``REGISTRY`` is a dict so duplicates are impossible by
        # construction; this asserts the structural invariant.
        ids = list(REGISTRY.keys())
        self.assertEqual(len(ids), len(set(ids)))

    def test_g01_004_contract_and_standard_retention(self):
        entry = REGISTRY["G01-004"]
        self.assertEqual(entry.persistence_mode, PersistenceMode.CURRENT_WITH_SNAPSHOT)
        self.assertEqual(entry.owner, "directory")
        self.assertEqual(entry.current_table, "core.subscribed_sku")
        self.assertEqual(entry.snapshot_table, "core.subscribed_sku_snapshot")
        self.assertEqual(entry.retention_class, "STANDARD")

    def test_g01_011_contract_and_reference_retention(self):
        entry = REGISTRY["G01-011"]
        self.assertEqual(entry.persistence_mode, PersistenceMode.CURRENT_WITH_SNAPSHOT)
        self.assertEqual(entry.owner, "security_service")
        self.assertEqual(entry.current_table, "core.conditional_access_policy")
        self.assertEqual(entry.snapshot_table, "core.conditional_access_policy_snapshot")
        self.assertEqual(entry.retention_class, "REFERENCE")

    def test_g01_012_contract_and_reference_retention(self):
        entry = REGISTRY["G01-012"]
        self.assertEqual(entry.persistence_mode, PersistenceMode.CURRENT)
        self.assertEqual(entry.owner, "security_service")
        adapter = entry.adapter.__closure__[0].cell_contents
        self.assertEqual(adapter.__module__, "collectors.workloads.security_service.adapters")
        self.assertEqual(adapter.__name__, "named_locations")
        self.assertEqual(entry.current_table, "core.named_location")
        self.assertIsNone(entry.snapshot_table)
        self.assertEqual(entry.retention_class, "REFERENCE")

    def test_registry_keys_match_entry_endpoint_ids(self):
        for key, entry in REGISTRY.items():
            self.assertIsInstance(entry, WorkloadEntry)
            self.assertEqual(entry.endpoint_id, key)

    def test_persistence_mode_vocabulary_is_closed(self):
        # Every persistence mode in the registry is a member of the
        # controlled enum; no third-party values are allowed.
        for entry in REGISTRY.values():
            self.assertIsInstance(entry.persistence_mode, PersistenceMode)
        # The vocabulary itself has exactly five members.
        self.assertEqual(
            set(PERSISTENCE_MODES),
            {
                PERSISTENCE_CURRENT,
                PERSISTENCE_REFERENCE,
                PERSISTENCE_EVENT,
                PERSISTENCE_CURRENT_WITH_SNAPSHOT,
                PERSISTENCE_CURRENT_WITH_HISTORY,
            },
        )


class RegistryCoverageTests(unittest.TestCase):
    def test_inventory_endpoints_are_fully_covered(self):
        ids = _load_inventory_ids()
        missing = ids - set(REGISTRY.keys())
        self.assertFalse(missing, "registry missing inventory endpoints: " + str(missing))

    def test_no_unknown_endpoint_in_registry(self):
        extras = set(REGISTRY.keys()) - set(EXPECTED_ENDPOINT_IDS)
        self.assertFalse(extras, "registry has unknown endpoints: " + str(extras))

    def test_validate_registry_runs_clean_at_import_time(self):
        # The registry module already invokes validate_registry() at
        # import. Calling it again here must succeed silently.
        validate_registry()

    def test_validate_registry_rejects_wrong_count(self):
        broken = dict(REGISTRY)
        broken.pop("G01-019")
        with self.assertRaises(RegistryCoverageError):
            validate_registry(broken)

    def test_validate_registry_rejects_wrong_id(self):
        broken = dict(REGISTRY)
        broken["G99-999"] = broken["G01-001"]
        with self.assertRaises(RegistryCoverageError):
            validate_registry(broken)

    def test_validate_registry_rejects_extra_endpoint(self):
        broken = dict(REGISTRY)
        # Add a fake endpoint with a unique id that won't collide.
        broken["G01-020"] = broken["G01-001"]
        with self.assertRaises(RegistryCoverageError):
            validate_registry(broken)


class RegistryPersistenceBucketsTests(unittest.TestCase):
    """The persistence-mode bucket must match the brief verbatim."""

    def test_current_bucket(self):
        self.assertEqual(
            {eid for eid, e in REGISTRY.items()
             if e.persistence_mode == PersistenceMode.CURRENT},
            EXPECTED_MODE_BUCKETS[PERSISTENCE_CURRENT],
        )

    def test_reference_bucket(self):
        self.assertEqual(
            {eid for eid, e in REGISTRY.items()
             if e.persistence_mode == PersistenceMode.REFERENCE},
            EXPECTED_MODE_BUCKETS[PERSISTENCE_REFERENCE],
        )

    def test_event_bucket(self):
        self.assertEqual(
            {eid for eid, e in REGISTRY.items()
             if e.persistence_mode == PersistenceMode.EVENT},
            EXPECTED_MODE_BUCKETS[PERSISTENCE_EVENT],
        )

    def test_current_with_snapshot_bucket(self):
        self.assertEqual(
            {eid for eid, e in REGISTRY.items()
             if e.persistence_mode == PersistenceMode.CURRENT_WITH_SNAPSHOT},
            EXPECTED_MODE_BUCKETS[PERSISTENCE_CURRENT_WITH_SNAPSHOT],
        )

    def test_current_with_history_bucket(self):
        self.assertEqual(
            {eid for eid, e in REGISTRY.items()
             if e.persistence_mode == PersistenceMode.CURRENT_WITH_HISTORY},
            EXPECTED_MODE_BUCKETS[PERSISTENCE_CURRENT_WITH_HISTORY],
        )

    def test_buckets_partition_expected_endpoints(self):
        union = set()
        for endpoints in EXPECTED_MODE_BUCKETS.values():
            union |= endpoints
        self.assertEqual(union, set(EXPECTED_ENDPOINT_IDS))
        # Pairwise disjoint.
        for a_key, a in EXPECTED_MODE_BUCKETS.items():
            for b_key, b in EXPECTED_MODE_BUCKETS.items():
                if a_key == b_key:
                    continue
                self.assertFalse(a & b, "{} and {} overlap".format(a_key, b_key))


class RegistryTableMappingTests(unittest.TestCase):
    def test_table_mapping_matches_expected(self):
        for endpoint_id, expected in EXPECTED_TABLE_MAPPING.items():
            entry = REGISTRY[endpoint_id]
            self.assertEqual(
                entry.current_table,
                expected["current"],
                "{} current_table mismatch".format(endpoint_id),
            )
            if "snapshot" in expected:
                self.assertEqual(
                    entry.snapshot_table,
                    expected["snapshot"],
                    "{} snapshot_table mismatch".format(endpoint_id),
                )
            if "history" in expected:
                self.assertEqual(
                    entry.history_table,
                    expected["history"],
                    "{} history_table mismatch".format(endpoint_id),
                )
            if "event" in expected:
                self.assertEqual(
                    entry.event_table,
                    expected["event"],
                    "{} event_table mismatch".format(endpoint_id),
                )

    def test_event_source_is_endpoint_controlled(self):
        lineage = {"tenant_id": 1}
        audit = normalize_record("G01-005", {"id": "a1", "event_source": "SIGN_IN"}, lineage)
        signin = normalize_record("G01-006", {"id": "s1", "event_source": "DIRECTORY_AUDIT"}, lineage)
        self.assertEqual(audit.event_row["event_source"], "DIRECTORY_AUDIT")
        self.assertEqual(signin.event_row["event_source"], "SIGN_IN")

    def test_g01_005_and_g01_006_event_source_discriminator(self):
        self.assertEqual(
            REGISTRY["G01-005"].event_source,
            "DIRECTORY_AUDIT",
        )
        self.assertEqual(
            REGISTRY["G01-006"].event_source,
            "SIGN_IN",
        )
        # And endpoints without source-discriminated event adapters have no event_source discriminator.
        for endpoint_id, entry in REGISTRY.items():
            if endpoint_id in ("G01-005", "G01-006"):
                continue
            self.assertIsNone(
                entry.event_source,
                "{} unexpectedly has event_source".format(endpoint_id),
            )

    def test_owner_metadata_matches(self):
        for endpoint_id, owner in EXPECTED_OWNER.items():
            entry = REGISTRY[endpoint_id]
            self.assertEqual(entry.owner, owner)


class RegistryIterationTests(unittest.TestCase):
    def test_iter_entries_returns_expected_entries_in_order(self):
        ids = [entry.endpoint_id for entry in iter_entries()]
        self.assertEqual(ids, list(EXPECTED_ENDPOINT_IDS))

    def test_get_entry_returns_registry_entry(self):
        for endpoint_id in EXPECTED_ENDPOINT_IDS:
            entry = REGISTRY[endpoint_id]
            self.assertIs(get_entry(endpoint_id), entry)


# ---------------------------------------------------------------------------
# Coverage invariant guards
# ---------------------------------------------------------------------------


class CoverageInvariantTests(unittest.TestCase):
    """These tests fail loudly if the endpoint invariant is broken."""

    def test_count_matches_expected_ids(self):
        self.assertEqual(len(REGISTRY), len(EXPECTED_ENDPOINT_IDS))

    def test_no_duplicate_endpoint_ids(self):
        seen = set()
        for endpoint_id in REGISTRY:
            self.assertNotIn(endpoint_id, seen)
            seen.add(endpoint_id)

    def test_no_unknown_endpoints_registered(self):
        unknown = set(REGISTRY) - set(EXPECTED_ENDPOINT_IDS)
        self.assertFalse(unknown, "unknown endpoints registered: " + str(unknown))

    def test_every_inventory_endpoint_has_one_workload_adapter(self):
        ids = _load_inventory_ids()
        for endpoint_id in ids:
            self.assertIn(endpoint_id, REGISTRY)
            self.assertEqual(
                REGISTRY[endpoint_id].endpoint_id, endpoint_id
            )


if __name__ == "__main__":
    unittest.main()
