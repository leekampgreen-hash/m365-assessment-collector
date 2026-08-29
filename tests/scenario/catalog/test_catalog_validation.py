"""Offline catalog validation tests for G08-B.

These tests verify:

* every scenario has a valid observability classification,
* every observability reference is to a G01 endpoint that exists in
  the inventory (G01-001..G01-019),
* the Scenario App current permission state is represented as
  ``User.Read`` only,
* every additional permission in the catalog is marked
  ``REQUIRED_NOT_GRANTED``,
* the permission matrix covers every scenario,
* the permission packs cover the declared scenarios.

No live Graph calls are made. No credentials are loaded.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_DIR = REPO_ROOT / "config" / "scenarios"
CATALOG_PATH = SCENARIOS_DIR / "catalog.json"
SCENARIOS_SUBDIR = SCENARIOS_DIR / "scenarios"
PERMISSION_PACKS_PATH = SCENARIOS_DIR / "permission_packs.json"
OBSERVABILITY_MAP_PATH = SCENARIOS_DIR / "observability_map.json"
PERMISSION_MATRIX_DOC = REPO_ROOT / "docs" / "g08-scenario-permission-matrix.md"
CATALOG_DOC = REPO_ROOT / "docs" / "g08-scenario-catalog.md"
G01_INVENTORY_PATH = REPO_ROOT / "config" / "api_inventory.json"


OBSERVABILITY_CLASSIFICATIONS = {
    "DIRECTLY_OBSERVABLE",
    "INDIRECTLY_OBSERVABLE",
    "NOT_COVERED_BY_CURRENT_G01_INVENTORY",
}


def _load_scenarios():
    catalog = json.loads(CATALOG_PATH.read_text())
    items = []
    for entry in catalog["scenarios"]:
        path = SCENARIOS_DIR / entry["file"]
        items.append((entry["scenario_id"], json.loads(path.read_text()), path))
    return items


def _load_inventory_ids():
    payload = json.loads(G01_INVENTORY_PATH.read_text())
    return {item["id"] for item in payload}


class CatalogValidationTests(unittest.TestCase):
    """End-to-end consistency across the catalog files."""

    def test_catalog_totals_match_actual_scenarios(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        on_disk = sorted(p.stem for p in SCENARIOS_SUBDIR.glob("*.json"))
        ids = sorted(s["scenario_id"] for s in catalog["scenarios"])
        self.assertEqual(ids, on_disk)

    def test_catalog_totals_count_matches(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        total = len(catalog["scenarios"])
        self.assertEqual(catalog["totals"]["total_scenarios"], total)
        # Validate enabled count from disk matches the catalog totals.
        actual_enabled = sum(
            1 for entry in catalog["scenarios"]
            if json.loads((SCENARIOS_DIR / entry["file"]).read_text())["enabled"]
        )
        self.assertEqual(catalog["totals"]["enabled_scenarios"], actual_enabled)

    def test_catalog_domain_count_matches(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        expected = catalog["totals"]["by_domain"]
        actual = {"MAIL": 0, "CALENDAR": 0, "FILES": 0, "AUTH": 0}
        for entry in catalog["scenarios"]:
            payload = json.loads((SCENARIOS_DIR / entry["file"]).read_text())
            actual[payload["domain"]] = actual.get(payload["domain"], 0) + 1
        self.assertEqual(expected, actual)

    def test_every_scenario_lists_observability(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIn(
                "observability_classification",
                payload,
                "scenario {} missing observability_classification".format(scenario_id),
            )
            self.assertIn(
                payload["observability_classification"],
                OBSERVABILITY_CLASSIFICATIONS,
                "scenario {} unknown observability_classification".format(scenario_id),
            )

    def test_every_observable_source_is_a_g01_endpoint(self):
        inventory_ids = _load_inventory_ids()
        for scenario_id, payload, _path in _load_scenarios():
            for endpoint_id in payload["expected_observable_sources"]:
                self.assertIn(
                    endpoint_id,
                    inventory_ids,
                    "scenario {} references unknown endpoint {}".format(
                        scenario_id, endpoint_id
                    ),
                )

    def test_observability_map_matches_catalog(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        obs_map = json.loads(OBSERVABILITY_MAP_PATH.read_text())
        obs_ids = {entry["scenario_id"] for entry in obs_map["scenario_observability"]}
        catalog_ids = {entry["scenario_id"] for entry in catalog["scenarios"]}
        self.assertEqual(catalog_ids, obs_ids)

    def test_additional_permissions_listed_in_catalog(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        listed = {
            entry["permission"]
            for entry in catalog["additional_permissions_required"]
        }
        # Mail.Send, Calendars.ReadWrite, Files.ReadWrite must all be
        # in the catalog's additional_permissions_required list.
        for expected in ("Mail.Send", "Calendars.ReadWrite", "Files.ReadWrite"):
            self.assertIn(expected, listed)

    def test_additional_permissions_are_required_not_granted(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        for entry in catalog["additional_permissions_required"]:
            self.assertEqual(
                entry["status"],
                "REQUIRED_NOT_GRANTED",
                "permission {} should be REQUIRED_NOT_GRANTED".format(entry["permission"]),
            )

    def test_current_scenario_app_permission_is_user_read_only(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        self.assertEqual(
            catalog["current_scenario_app_delegated_permissions"],
            ["User.Read"],
        )


class PermissionContractTests(unittest.TestCase):
    """Tests the per-scenario permission contract."""

    def test_every_scenario_with_permission_appears_in_matrix_doc(self):
        matrix_text = PERMISSION_MATRIX_DOC.read_text()
        for scenario_id, _payload, _path in _load_scenarios():
            self.assertIn(
                scenario_id,
                matrix_text,
                "scenario {} not present in permission matrix doc".format(scenario_id),
            )

    def test_every_scenario_listed_in_permission_packs(self):
        packs = json.loads(PERMISSION_PACKS_PATH.read_text())
        listed = set()
        for pack in packs["packs"]:
            listed.update(pack["scenarios_enabled"])
        for scenario_id, _payload, _path in _load_scenarios():
            # AUTH scenarios may not be in any pack that adds
            # permissions. They are still listed in PACK-AUTH which
            # does not add any permission.
            self.assertIn(
                scenario_id,
                listed,
                "scenario {} not covered by any permission pack".format(scenario_id),
            )

    def test_no_wildcard_permission_in_any_scenario(self):
        for scenario_id, payload, _path in _load_scenarios():
            for perm in payload["required_delegated_permissions"]:
                self.assertNotIn(
                    "*",
                    perm,
                    "scenario {} declares wildcard permission {}".format(
                        scenario_id, perm
                    ),
                )

    def test_no_directory_wildcard_in_any_scenario(self):
        forbidden_prefixes = ("Directory.", "RoleManagement.", "Policy.", "AuditLog.")
        for scenario_id, payload, _path in _load_scenarios():
            for perm in payload["required_delegated_permissions"]:
                for prefix in forbidden_prefixes:
                    self.assertFalse(
                        perm.startswith(prefix),
                        "scenario {} declares tenant-wide permission {}".format(
                            scenario_id, perm
                        ),
                    )

    def test_no_application_permission_in_any_scenario(self):
        # Application permissions must never appear in a scenario that
        # is meant to run as a delegated user.
        for scenario_id, payload, _path in _load_scenarios():
            for perm in payload["required_delegated_permissions"]:
                self.assertFalse(
                    perm.endswith(".All") and not perm.startswith("User."),
                    "scenario {} declares possibly broad scope {}".format(
                        scenario_id, perm
                    ),
                )

    def test_current_scenario_app_permission_state_in_matrix_doc(self):
        matrix_text = PERMISSION_MATRIX_DOC.read_text()
        self.assertIn("User.Read", matrix_text)
        self.assertIn("REQUIRED_NOT_GRANTED", matrix_text)


class ObservabilityMappingTests(unittest.TestCase):
    """Tests the observability classification map."""

    def test_observability_totals(self):
        obs_map = json.loads(OBSERVABILITY_MAP_PATH.read_text())
        self.assertIn("totals", obs_map)
        # Validate the totals match the on-disk counts.
        direct = sum(
            1 for entry in obs_map["scenario_observability"]
            if entry["classification"] == "DIRECTLY_OBSERVABLE"
        )
        indirect = sum(
            1 for entry in obs_map["scenario_observability"]
            if entry["classification"] == "INDIRECTLY_OBSERVABLE"
        )
        not_covered = sum(
            1 for entry in obs_map["scenario_observability"]
            if entry["classification"] == "NOT_COVERED_BY_CURRENT_G01_INVENTORY"
        )
        self.assertEqual(obs_map["totals"]["directly_observable"], direct)
        self.assertEqual(obs_map["totals"]["indirectly_observable"], indirect)
        self.assertEqual(obs_map["totals"]["not_covered"], not_covered)

    def test_no_scenario_claims_direct_observability_for_workload_endpoint(self):
        # The catalog must not falsely claim that a mail/calendar/file
        # scenario action will appear in a G01 endpoint that does not
        # collect workload data. The only workload-aware endpoints in
        # G01 are G01-005 (directoryAudits) and G01-006 (signIns),
        # which only see sign-in events, not the workload artifact.
        workload_domains = {"MAIL", "CALENDAR", "FILES"}
        inventory_ids = _load_inventory_ids()
        workload_endpoints = set()
        for item in json.loads(G01_INVENTORY_PATH.read_text()):
            if item.get("key") not in ("signIns", "directoryAuditLogs"):
                workload_endpoints.add(item["id"])
        # Sanity: workload_endpoints is non-empty for the above filter.
        self.assertTrue(workload_endpoints)

        for scenario_id, payload, _path in _load_scenarios():
            if payload["domain"] not in workload_domains:
                continue
            if payload["observability_classification"] != "DIRECTLY_OBSERVABLE":
                continue
            # If a workload scenario is directly observable, every
            # expected endpoint must be either a sign-in or
            # directory-audit endpoint, or it must reference a
            # workload endpoint that does NOT exist.
            for endpoint_id in payload["expected_observable_sources"]:
                if endpoint_id not in inventory_ids:
                    continue
                self.assertIn(
                    endpoint_id,
                    {"G01-005", "G01-006"},
                    "scenario {} claims DIRECTLY_OBSERVABLE via non-signin "
                    "endpoint {}".format(scenario_id, endpoint_id),
                )


if __name__ == "__main__":
    unittest.main()