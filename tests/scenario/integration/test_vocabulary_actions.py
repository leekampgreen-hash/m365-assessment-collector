"""Integration tests: action vocabulary normalization (catalog -> framework).

The catalog uses action identifiers such as CREATE_EVENT, UPDATE_EVENT,
DELETE_EVENT, DELETE_FILE, INTERACTIVE_SIGNIN. These are normalized to
the framework's closed vocabulary via an explicit mapping.

Semantic preservation rules:

* CREATE_EVENT -> CREATE_CALENDAR_EVENT
* UPDATE_EVENT -> UPDATE_CALENDAR_EVENT
* DELETE_EVENT -> DELETE_CALENDAR_EVENT
* CREATE_FILE / UPDATE_FILE / DELETE_FILE -> framework equivalents
* INTERACTIVE_SIGNIN -> INTERACTIVE_SIGNIN (no Graph write, distinct
  from NOOP_VALIDATION)
* Unknown catalog action types are rejected.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.scenario.catalog_loader import load_scenario_catalog
from agents.scenario.actions import (
    ACTION_CREATE_CALENDAR_EVENT,
    ACTION_DELETE_CALENDAR_EVENT,
    ACTION_DELETE_FILE,
    ACTION_INTERACTIVE_SIGNIN,
    ACTION_SEND_MAIL,
    ACTION_UPDATE_CALENDAR_EVENT,
    ACTION_UPDATE_FILE,
)


def _write_catalog_with_action(td: str, catalog_action: str) -> Path:
    root = Path(td)
    (root / "scenarios").mkdir(parents=True, exist_ok=True)
    scenario = {
        "schema_version": "1.0",
        "scenario_id": "SCN-T-001",
        "name": "n",
        "description": "d",
        "domain": "MAIL",
        "action_type": catalog_action,
        "actor_required": "x",
        "peer_actor_required": None,
        "no_recipient": True,
        "required_delegated_permissions": [],
        "expected_observable_sources": ["G01-006"],
        "observability_classification": "INDIRECTLY_OBSERVABLE",
        "correlation_strategy": "x",
        "correlation_token_field": "y",
        "cleanup_required": False,
        "cleanup_behavior": "NO_CLEANUP_REQUIRED",
        "destructive": False,
        "risk": "LOW",
        "enabled": False,
        "permission_pack": "PACK-MAIL",
        "notes": "ok",
    }
    (root / "scenarios" / "SCN-T-001.json").write_text(json.dumps(scenario))
    catalog = {
        "schema_version": "1.0",
        "catalog_id": "T",
        "version": "0.0.1",
        "scenarios": [{"scenario_id": "SCN-T-001", "file": "scenarios/SCN-T-001.json"}],
        "totals": {"total_scenarios": 1, "enabled_scenarios": 0, "disabled_scenarios": 1},
        "current_scenario_app_delegated_permissions": ["User.Read"],
        "additional_permissions_required": [],
    }
    (root / "catalog.json").write_text(json.dumps(catalog))
    return root


class ActionNormalizationTests(unittest.TestCase):
    def test_send_mail_direct_match(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "SEND_MAIL")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                ACTION_SEND_MAIL,
            )

    def test_create_event_maps_to_create_calendar_event(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "CREATE_EVENT")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                ACTION_CREATE_CALENDAR_EVENT,
            )

    def test_update_event_maps_to_update_calendar_event(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "UPDATE_EVENT")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                ACTION_UPDATE_CALENDAR_EVENT,
            )

    def test_delete_event_maps_to_delete_calendar_event(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "DELETE_EVENT")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                ACTION_DELETE_CALENDAR_EVENT,
            )

    def test_create_file_direct_match(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "CREATE_FILE")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                "CREATE_FILE",
            )

    def test_update_file_direct_match(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "UPDATE_FILE")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                ACTION_UPDATE_FILE,
            )

    def test_delete_file_preserved_as_distinct_action(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "DELETE_FILE")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                ACTION_DELETE_FILE,
            )
            # DELETE_FILE must not silently alias to UPDATE_FILE or
            # CREATE_FILE. They are semantically different.
            self.assertNotEqual(ACTION_DELETE_FILE, ACTION_UPDATE_FILE)
            self.assertNotEqual(ACTION_DELETE_FILE, "CREATE_FILE")

    def test_interactive_signin_preserved_as_distinct_action(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "INTERACTIVE_SIGNIN")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(
                result.loaded_scenarios[0].definition.action_type,
                ACTION_INTERACTIVE_SIGNIN,
            )
            # INTERACTIVE_SIGNIN must remain distinct from NOOP_VALIDATION.
            self.assertNotEqual(ACTION_INTERACTIVE_SIGNIN, "NOOP_VALIDATION")

    def test_unknown_action_is_rejected(self):
        for bad in ("DROP_TABLE", "EXECUTE_ARBITRARY", "DELETE_EVERYTHING", "POST_FAKE"):
            with TemporaryDirectory() as td:
                root = _write_catalog_with_action(td, bad)
                result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
                self.assertEqual(
                    result.malformed,
                    ("SCN-T-001",),
                    msg="unknown action {0!r} should be rejected".format(bad),
                )
                self.assertEqual(result.loaded_scenarios, ())

    def test_case_sensitive_action_match(self):
        with TemporaryDirectory() as td:
            root = _write_catalog_with_action(td, "send_mail")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(result.malformed, ("SCN-T-001",))


class ProductionCatalogActionMappingTests(unittest.TestCase):
    """End-to-end mapping check against the real catalog on disk."""

    def test_all_production_actions_map_to_framework(self):
        from agents.scenario.catalog_loader import load_scenario_catalog as load

        result = load()
        by_id = {ls.scenario_id: ls for ls in result.loaded_scenarios}
        self.assertEqual(
            by_id["SCN-MAIL-001"].definition.action_type,
            ACTION_SEND_MAIL,
        )
        self.assertEqual(
            by_id["SCN-MAIL-002"].definition.action_type,
            ACTION_SEND_MAIL,
        )
        self.assertEqual(
            by_id["SCN-CALENDAR-001"].definition.action_type,
            ACTION_CREATE_CALENDAR_EVENT,
        )
        self.assertEqual(
            by_id["SCN-CALENDAR-002"].definition.action_type,
            ACTION_UPDATE_CALENDAR_EVENT,
        )
        self.assertEqual(
            by_id["SCN-CALENDAR-003"].definition.action_type,
            ACTION_DELETE_CALENDAR_EVENT,
        )
        self.assertEqual(by_id["SCN-FILE-001"].definition.action_type, "CREATE_FILE")
        self.assertEqual(by_id["SCN-FILE-002"].definition.action_type, ACTION_UPDATE_FILE)
        self.assertEqual(by_id["SCN-FILE-003"].definition.action_type, ACTION_DELETE_FILE)
        self.assertEqual(
            by_id["SCN-AUTH-001"].definition.action_type,
            ACTION_INTERACTIVE_SIGNIN,
        )


if __name__ == "__main__":
    unittest.main()