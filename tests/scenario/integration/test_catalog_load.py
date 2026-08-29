"""Integration tests: catalog loading and parsing.

Verifies the loader reads the catalog files, normalizes them into
framework-ready representations, and rejects malformed or duplicate
records.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.scenario.catalog_loader import (
    CATALOG_LOADER_DEFAULT_ROOT,
    CatalogLoaderError,
    load_scenario_catalog,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


class CatalogLoadTests(unittest.TestCase):
    def test_default_root_is_project_catalog(self):
        self.assertEqual(
            CATALOG_LOADER_DEFAULT_ROOT,
            REPO_ROOT / "config" / "scenarios",
        )

    def test_load_all_nine_scenarios(self):
        result = load_scenario_catalog()
        self.assertEqual(len(result.loaded_scenarios), 9)
        self.assertEqual(result.duplicates, ())
        self.assertEqual(result.malformed, ())
        ids = {ls.scenario_id for ls in result.loaded_scenarios}
        self.assertEqual(
            ids,
            {
                "SCN-MAIL-001",
                "SCN-MAIL-002",
                "SCN-CALENDAR-001",
                "SCN-CALENDAR-002",
                "SCN-CALENDAR-003",
                "SCN-FILE-001",
                "SCN-FILE-002",
                "SCN-FILE-003",
                "SCN-AUTH-001",
            },
        )

    def test_loaded_ids_are_unique(self):
        result = load_scenario_catalog()
        ids = [ls.scenario_id for ls in result.loaded_scenarios]
        self.assertEqual(len(ids), len(set(ids)))

    def test_loaded_ids_are_deterministically_ordered(self):
        first = [ls.scenario_id for ls in load_scenario_catalog().loaded_scenarios]
        second = [ls.scenario_id for ls in load_scenario_catalog().loaded_scenarios]
        self.assertEqual(first, second)
        # Sorted ascending by scenario_id.
        self.assertEqual(first, sorted(first))

    def test_catalog_id_and_version_are_recorded(self):
        result = load_scenario_catalog()
        self.assertEqual(result.catalog_id, "SCENARIO_CATALOG_G08B")
        self.assertEqual(result.catalog_version, "1.0.0")

    def test_current_baseline_is_user_read(self):
        result = load_scenario_catalog()
        self.assertEqual(result.current_baseline_permissions, ("User.Read",))

    def test_additional_permissions_required_listed(self):
        result = load_scenario_catalog()
        perms = {entry["permission"] for entry in result.additional_permissions_required}
        self.assertEqual(
            perms,
            {"Mail.Send", "Calendars.ReadWrite", "Files.ReadWrite"},
        )

    def test_no_scenario_has_cleanup_scenario_id_inferred(self):
        # The loader must NOT infer cleanup_scenario_id from numeric
        # adjacency; cleanup_scenario_id stays None unless the catalog
        # declares it explicitly. The catalog does not declare it for
        # any scenario today.
        result = load_scenario_catalog()
        for ls in result.loaded_scenarios:
            self.assertIsNone(
                ls.definition.cleanup_scenario_id,
                msg="scenario {0!r} has unexpected cleanup_scenario_id".format(
                    ls.scenario_id
                ),
            )

    def test_observability_classification_preserved(self):
        result = load_scenario_catalog()
        by_id = {ls.scenario_id: ls for ls in result.loaded_scenarios}
        self.assertEqual(
            by_id["SCN-AUTH-001"].catalog_metadata.observability_classification,
            "DIRECTLY_OBSERVABLE",
        )
        for ls in result.loaded_scenarios:
            if ls.scenario_id == "SCN-AUTH-001":
                continue
            self.assertEqual(
                ls.catalog_metadata.observability_classification,
                "INDIRECTLY_OBSERVABLE",
            )

    def test_catalog_metadata_preserves_domain_and_cleanup(self):
        result = load_scenario_catalog()
        by_id = {ls.scenario_id: ls for ls in result.loaded_scenarios}
        self.assertEqual(by_id["SCN-MAIL-001"].catalog_metadata.domain, "MAIL")
        self.assertEqual(by_id["SCN-MAIL-001"].catalog_metadata.cleanup_behavior, "MANUAL_CLEANUP")
        self.assertEqual(
            by_id["SCN-CALENDAR-001"].catalog_metadata.cleanup_behavior,
            "AUTO_CLEANUP_SUPPORTED",
        )
        self.assertEqual(
            by_id["SCN-CALENDAR-003"].catalog_metadata.cleanup_behavior,
            "NO_CLEANUP_REQUIRED",
        )

    def test_loaded_scenarios_do_not_leak_secrets(self):
        result = load_scenario_catalog()
        forbidden_keys = {"password", "token", "secret", "api_key", "client_secret"}
        for ls in result.loaded_scenarios:
            data = ls.to_dict()
            encoded = json.dumps(data).lower()
            for forbidden in forbidden_keys:
                # "client_secret" might appear as a permission metadata
                # key in the framework but the catalog should not embed
                # it as a value.
                self.assertNotIn('"{}"'.format(forbidden), encoded)


class CatalogDuplicateAndMalformedTests(unittest.TestCase):
    def _write_temp_catalog(self, tmp: Path, *, dup=False, missing_id=False):
        tmp.mkdir(parents=True, exist_ok=True)
        scenarios_dir = tmp / "scenarios"
        scenarios_dir.mkdir()
        for sid in ("SCN-A", "SCN-B"):
            (scenarios_dir / "{0}.json".format(sid)).write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "scenario_id": sid,
                        "name": "n",
                        "description": "d",
                        "domain": "MAIL",
                        "action_type": "SEND_MAIL",
                        "actor_required": "x",
                        "peer_actor_required": None,
                        "no_recipient": True,
                        "required_delegated_permissions": ["Mail.Send"],
                        "expected_observable_sources": ["G01-006"],
                        "observability_classification": "INDIRECTLY_OBSERVABLE",
                        "correlation_strategy": "x",
                        "correlation_token_field": "y",
                        "cleanup_required": False,
                        "cleanup_behavior": "NO_CLEANUP_REQUIRED",
                        "destructive": False,
                        "risk": "LOW",
                        "enabled": True,
                        "permission_pack": "PACK-MAIL",
                        "notes": "ok",
                    }
                )
            )
        scenarios_index = [
            {"scenario_id": "SCN-A", "file": "scenarios/SCN-A.json"},
            {"scenario_id": "SCN-B", "file": "scenarios/SCN-B.json"},
        ]
        if dup:
            scenarios_index.append({"scenario_id": "SCN-A", "file": "scenarios/SCN-A.json"})
        catalog = {
            "schema_version": "1.0",
            "catalog_id": "TEST",
            "version": "0.0.1",
            "scenarios": scenarios_index,
            "totals": {
                "total_scenarios": 3 if dup else 2,
                "enabled_scenarios": 1,
                "disabled_scenarios": 2 if dup else 1,
            },
            "current_scenario_app_delegated_permissions": ["User.Read"],
            "additional_permissions_required": [],
            "actor_model_file": "actor_model.json",
            "permission_packs_file": "permission_packs.json",
            "observability_map_file": "observability_map.json",
        }
        (tmp / "catalog.json").write_text(json.dumps(catalog))
        return tmp

    def test_duplicate_scenario_id_is_recorded(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = self._write_temp_catalog(tmp, dup=True)
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(set(result.duplicates), {"SCN-A"})
            # Only the first occurrence is loaded; duplicates are not added.
            ids = [ls.scenario_id for ls in result.loaded_scenarios]
            self.assertEqual(sorted(ids), ["SCN-A", "SCN-B"])

    def test_malformed_scenario_is_recorded(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = tmp
            root.mkdir(parents=True, exist_ok=True)
            (root / "scenarios").mkdir()
            # Write a malformed scenario JSON (missing required fields).
            (root / "scenarios" / "SCN-BAD.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "scenario_id": "SCN-BAD",
                        "name": "broken",
                        # description is missing
                    }
                )
            )
            (root / "scenarios" / "SCN-GOOD.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "scenario_id": "SCN-GOOD",
                        "name": "ok",
                        "description": "ok",
                        "domain": "MAIL",
                        "action_type": "SEND_MAIL",
                        "actor_required": "x",
                        "peer_actor_required": None,
                        "no_recipient": True,
                        "required_delegated_permissions": ["Mail.Send"],
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
                )
            )
            catalog = {
                "schema_version": "1.0",
                "catalog_id": "T",
                "version": "0.0.1",
                "scenarios": [
                    {"scenario_id": "SCN-BAD", "file": "scenarios/SCN-BAD.json"},
                    {"scenario_id": "SCN-GOOD", "file": "scenarios/SCN-GOOD.json"},
                ],
                "totals": {"total_scenarios": 2, "enabled_scenarios": 0, "disabled_scenarios": 2},
                "current_scenario_app_delegated_permissions": ["User.Read"],
                "additional_permissions_required": [],
            }
            (root / "catalog.json").write_text(json.dumps(catalog))
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertIn("SCN-BAD", result.malformed)
            ids = [ls.scenario_id for ls in result.loaded_scenarios]
            self.assertEqual(ids, ["SCN-GOOD"])


if __name__ == "__main__":
    unittest.main()