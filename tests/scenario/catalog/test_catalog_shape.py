"""Offline structural tests for the G08-B scenario catalog.

These tests validate that the catalog on disk is syntactically valid
and that every scenario carries the contract fields required by the
G08-B task brief. No live Graph calls are made. No credentials are
loaded.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_DIR = REPO_ROOT / "config" / "scenarios"
CATALOG_PATH = SCENARIOS_DIR / "catalog.json"
SCENARIOS_SUBDIR = SCENARIOS_DIR / "scenarios"
ACTOR_MODEL_PATH = SCENARIOS_DIR / "actor_model.json"
PERMISSION_PACKS_PATH = SCENARIOS_DIR / "permission_packs.json"
OBSERVABILITY_MAP_PATH = SCENARIOS_DIR / "observability_map.json"
G01_INVENTORY_PATH = REPO_ROOT / "config" / "api_inventory.json"


REQUIRED_FIELDS = (
    "scenario_id",
    "name",
    "description",
    "domain",
    "action_type",
    "actor_required",
    "required_delegated_permissions",
    "expected_observable_sources",
    "correlation_strategy",
    "cleanup_required",
    "destructive",
    "enabled",
    "notes",
)


KNOWN_DOMAINS = {"MAIL", "CALENDAR", "FILES", "AUTH", "TEAMS"}
KNOWN_ACTION_TYPES = {
    "SEND_MAIL",
    "CREATE_EVENT",
    "UPDATE_EVENT",
    "DELETE_EVENT",
    "CREATE_FILE",
    "UPDATE_FILE",
    "DELETE_FILE",
    "INTERACTIVE_SIGNIN",
    "POST_CHAT_MESSAGE",
    "POST_CHANNEL_MESSAGE",
}


CLEANUP_BEHAVIORS = {
    "AUTO_CLEANUP_SUPPORTED",
    "MANUAL_CLEANUP",
    "NO_CLEANUP_REQUIRED",
}
RISK_LEVELS = {"LOW", "MODERATE", "HIGH"}
OBSERVABILITY_CLASSIFICATIONS = {
    "DIRECTLY_OBSERVABLE",
    "INDIRECTLY_OBSERVABLE",
    "NOT_COVERED_BY_CURRENT_G01_INVENTORY",
}


SCENARIO_ID_PATTERN = re.compile(r"^SCN-[A-Z0-9_]+-\d{3}$")


FORBIDDEN_CREDENTIAL_SUBSTRINGS = (
    "password=",
    "Password=",
    "secret=",
    "Secret=",
    "client_secret",
    "clientSecret",
    "Bearer ",
    "eyJ",
    "upn:",
    "tenant_id:",
    "tenantId:",
)


def _load_scenarios():
    """Yield ``(scenario_id, payload)`` for every scenario on disk."""
    catalog = json.loads(CATALOG_PATH.read_text())
    items = []
    for entry in catalog["scenarios"]:
        path = SCENARIOS_DIR / entry["file"]
        payload = json.loads(path.read_text())
        items.append((entry["scenario_id"], payload, path))
    return items


def _load_inventory_ids():
    """Return the set of G01 endpoint ids in the inventory file."""
    payload = json.loads(G01_INVENTORY_PATH.read_text())
    return {item["id"] for item in payload}


class CatalogShapeTests(unittest.TestCase):
    """Verify the catalog index file is well-formed."""

    def test_catalog_index_parses(self):
        payload = json.loads(CATALOG_PATH.read_text())
        self.assertIn("scenarios", payload)
        self.assertIn("totals", payload)

    def test_catalog_lists_8_to_12_scenarios(self):
        # Per the task brief, the initial catalog is 8-12 scenarios.
        catalog = json.loads(CATALOG_PATH.read_text())
        count = len(catalog["scenarios"])
        self.assertGreaterEqual(count, 8)
        self.assertLessEqual(count, 12)

    def test_catalog_scenario_ids_are_unique(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        ids = [s["scenario_id"] for s in catalog["scenarios"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate scenario_id in catalog")

    def test_scenario_ids_match_naming_pattern(self):
        for scenario_id, _payload, _path in _load_scenarios():
            self.assertRegex(scenario_id, SCENARIO_ID_PATTERN)

    def test_scenario_files_exist(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        for entry in catalog["scenarios"]:
            path = SCENARIOS_DIR / entry["file"]
            self.assertTrue(path.is_file(), "missing scenario file: " + str(path))

    def test_scenario_ids_match_file_payload(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertEqual(payload["scenario_id"], scenario_id)

    def test_scenario_file_referenced_in_catalog_matches_on_disk(self):
        catalog = json.loads(CATALOG_PATH.read_text())
        ids = [s["scenario_id"] for s in catalog["scenarios"]]
        on_disk_ids = sorted(p.stem for p in SCENARIOS_SUBDIR.glob("*.json"))
        self.assertEqual(sorted(ids), sorted(on_disk_ids))


class ScenarioFieldShapeTests(unittest.TestCase):
    """Verify every scenario carries the required contract fields."""

    def test_required_fields_present(self):
        for scenario_id, payload, _path in _load_scenarios():
            for field in REQUIRED_FIELDS:
                self.assertIn(
                    field,
                    payload,
                    "scenario {} missing field {}".format(scenario_id, field),
                )

    def test_string_fields_are_strings(self):
        string_fields = (
            "scenario_id",
            "name",
            "description",
            "domain",
            "action_type",
            "actor_required",
            "correlation_strategy",
        )
        for scenario_id, payload, _path in _load_scenarios():
            for field in string_fields:
                self.assertIsInstance(
                    payload[field],
                    str,
                    "scenario {} field {} not a string".format(scenario_id, field),
                )
            self.assertGreater(len(payload["name"]), 0)
            self.assertGreater(len(payload["description"]), 0)

    def test_list_fields_are_lists(self):
        list_fields = (
            "required_delegated_permissions",
            "expected_observable_sources",
        )
        for scenario_id, payload, _path in _load_scenarios():
            for field in list_fields:
                self.assertIsInstance(
                    payload[field],
                    list,
                    "scenario {} field {} not a list".format(scenario_id, field),
                )

    def test_boolean_fields_are_booleans(self):
        bool_fields = ("cleanup_required", "destructive", "enabled")
        for scenario_id, payload, _path in _load_scenarios():
            for field in bool_fields:
                self.assertIsInstance(
                    payload[field],
                    bool,
                    "scenario {} field {} not a bool".format(scenario_id, field),
                )

    def test_domain_in_known_set(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIn(
                payload["domain"],
                KNOWN_DOMAINS,
                "scenario {} unknown domain {}".format(scenario_id, payload["domain"]),
            )

    def test_action_type_in_known_set(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIn(
                payload["action_type"],
                KNOWN_ACTION_TYPES,
                "scenario {} unknown action_type {}".format(
                    scenario_id, payload["action_type"]
                ),
            )

    def test_cleanup_required_implies_cleanup_behavior_field(self):
        # If cleanup_required is True, the catalog must declare a
        # cleanup_behavior in the controlled vocabulary.
        for scenario_id, payload, _path in _load_scenarios():
            if payload["cleanup_required"]:
                self.assertIn("cleanup_behavior", payload)
                self.assertIn(payload["cleanup_behavior"], CLEANUP_BEHAVIORS)

    def test_risk_in_known_set(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIn(payload["risk"], RISK_LEVELS)

    def test_observability_classification_when_present(self):
        for scenario_id, payload, _path in _load_scenarios():
            if "observability_classification" in payload:
                self.assertIn(
                    payload["observability_classification"],
                    OBSERVABILITY_CLASSIFICATIONS,
                )

    def test_actor_required_is_non_empty_string(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertTrue(payload["actor_required"])
            self.assertNotEqual(payload["actor_required"], "")

    def test_peer_actor_either_null_or_string(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIn("peer_actor_required", payload)
            peer = payload["peer_actor_required"]
            self.assertTrue(peer is None or isinstance(peer, str))

    def test_no_recipient_is_boolean(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIn("no_recipient", payload)
            self.assertIsInstance(payload["no_recipient"], bool)


class CatalogParseTests(unittest.TestCase):
    """Verify every JSON file in the catalog parses."""

    def test_catalog_json_parses(self):
        json.loads(CATALOG_PATH.read_text())

    def test_actor_model_json_parses(self):
        json.loads(ACTOR_MODEL_PATH.read_text())

    def test_permission_packs_json_parses(self):
        json.loads(PERMISSION_PACKS_PATH.read_text())

    def test_observability_map_json_parses(self):
        json.loads(OBSERVABILITY_MAP_PATH.read_text())

    def test_every_scenario_file_parses(self):
        for path in SCENARIOS_SUBDIR.glob("*.json"):
            with self.subTest(file=str(path)):
                json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()