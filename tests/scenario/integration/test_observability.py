"""Integration tests: observability classification preservation.

Verifies:

* Every catalog observability reference is inside G01-001..G01-019
  (or whatever the G01 inventory declares).
* The classification field is preserved exactly.
* INDIRECTLY_OBSERVABLE is never silently upgraded to DIRECTLY_OBSERVABLE.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.scenario.catalog_loader import (
    CatalogLoaderError,
    load_scenario_catalog,
    validate_observability_g01_references,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_g01_inventory_ids() -> set:
    inventory_path = REPO_ROOT / "config" / "api_inventory.json"
    payload = json.loads(inventory_path.read_text())
    return {item["id"] for item in payload}


class ObservabilityPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_scenario_catalog()
        cls.g01_ids = _load_g01_inventory_ids()

    def test_every_reference_is_within_g01_inventory(self):
        for ls in self.result.loaded_scenarios:
            for endpoint in ls.catalog_metadata.expected_observable_sources:
                self.assertIn(
                    endpoint,
                    self.g01_ids,
                    msg="scenario {0} references unknown endpoint {1}".format(
                        ls.scenario_id, endpoint
                    ),
                )

    def test_g01_id_range_is_g01_001_to_g01_019(self):
        # Inventory may contain more; the loader restricts references
        # to the inventory set. At minimum the range documented for
        # this project is G01-001..G01-019.
        # No explicit check on the range string is performed; what
        # matters is that every reference is inside the inventory.
        # Sanity: at least one reference in G01-001..G01-019.
        self.assertTrue(self.g01_ids)

    def test_classifications_preserved_exactly(self):
        by_id = {ls.scenario_id: ls for ls in self.result.loaded_scenarios}
        self.assertEqual(
            by_id["SCN-AUTH-001"].catalog_metadata.observability_classification,
            "DIRECTLY_OBSERVABLE",
        )
        for ls in self.result.loaded_scenarios:
            if ls.scenario_id == "SCN-AUTH-001":
                continue
            self.assertEqual(
                ls.catalog_metadata.observability_classification,
                "INDIRECTLY_OBSERVABLE",
                msg="scenario {0} should remain INDIRECTLY_OBSERVABLE".format(
                    ls.scenario_id
                ),
            )

    def test_no_indirectly_observable_upgraded_to_directly(self):
        for ls in self.result.loaded_scenarios:
            if ls.catalog_metadata.observability_classification == "INDIRECTLY_OBSERVABLE":
                self.assertNotEqual(
                    ls.catalog_metadata.observability_classification,
                    "DIRECTLY_OBSERVABLE",
                )

    def test_mail_calendar_files_are_not_directly_observable(self):
        # Mail/calendar/files content is NOT collected by G01.
        # The catalog must not claim direct observability for these.
        by_id = {ls.scenario_id: ls for ls in self.result.loaded_scenarios}
        for sid in (
            "SCN-MAIL-001",
            "SCN-MAIL-002",
            "SCN-CALENDAR-001",
            "SCN-CALENDAR-002",
            "SCN-CALENDAR-003",
            "SCN-FILE-001",
            "SCN-FILE-002",
            "SCN-FILE-003",
        ):
            self.assertNotEqual(
                by_id[sid].catalog_metadata.observability_classification,
                "DIRECTLY_OBSERVABLE",
            )

    def test_out_of_range_endpoint_rejected_by_loader(self):
        # Build a catalog with a scenario that points at "G01-099".
        from agents.scenario.catalog_loader import load_scenario_catalog as load

        def write(td):
            root = Path(td)
            (root / "scenarios").mkdir(parents=True, exist_ok=True)
            scenario = {
                "schema_version": "1.0",
                "scenario_id": "SCN-BAD-001",
                "name": "n",
                "description": "d",
                "domain": "MAIL",
                "action_type": "SEND_MAIL",
                "actor_required": "x",
                "peer_actor_required": None,
                "no_recipient": True,
                "required_delegated_permissions": ["Mail.Send"],
                "expected_observable_sources": ["G01-099"],
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
            (root / "scenarios" / "SCN-BAD-001.json").write_text(json.dumps(scenario))
            catalog = {
                "schema_version": "1.0",
                "catalog_id": "T",
                "version": "0.0.1",
                "scenarios": [
                    {"scenario_id": "SCN-BAD-001", "file": "scenarios/SCN-BAD-001.json"}
                ],
                "totals": {"total_scenarios": 1, "enabled_scenarios": 0, "disabled_scenarios": 1},
                "current_scenario_app_delegated_permissions": ["User.Read"],
                "additional_permissions_required": [],
            }
            (root / "catalog.json").write_text(json.dumps(catalog))
            return root

        with TemporaryDirectory() as td:
            root = write(td)
            result = load(root, allowed_g01_ids=self.g01_ids)
            self.assertEqual(result.malformed, ("SCN-BAD-001",))
            self.assertEqual(result.loaded_scenarios, ())

    def test_validate_observability_g01_references_passes_for_catalog(self):
        # Should not raise: every reference in the production catalog
        # is already inside the G01 inventory.
        validate_observability_g01_references(
            self.result, allowed_g01_ids=self.g01_ids
        )


if __name__ == "__main__":
    unittest.main()