"""Integration tests: cleanup behavior preservation.

The catalog declares ``cleanup_behavior`` (AUTO_CLEANUP_SUPPORTED /
MANUAL_CLEANUP / NO_CLEANUP_REQUIRED) per scenario. The loader must
preserve the catalog behavior but must NOT infer a paired
``cleanup_scenario_id`` from numeric ID adjacency.
"""
from __future__ import annotations

import unittest

from agents.scenario.catalog_loader import load_scenario_catalog


class CleanupSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_scenario_catalog()
        cls.by_id = {ls.scenario_id: ls for ls in cls.result.loaded_scenarios}

    def test_cleanup_behavior_preserved(self):
        self.assertEqual(
            self.by_id["SCN-MAIL-001"].catalog_metadata.cleanup_behavior,
            "MANUAL_CLEANUP",
        )
        self.assertEqual(
            self.by_id["SCN-MAIL-002"].catalog_metadata.cleanup_behavior,
            "MANUAL_CLEANUP",
        )
        self.assertEqual(
            self.by_id["SCN-CALENDAR-001"].catalog_metadata.cleanup_behavior,
            "AUTO_CLEANUP_SUPPORTED",
        )
        self.assertEqual(
            self.by_id["SCN-CALENDAR-002"].catalog_metadata.cleanup_behavior,
            "AUTO_CLEANUP_SUPPORTED",
        )
        self.assertEqual(
            self.by_id["SCN-CALENDAR-003"].catalog_metadata.cleanup_behavior,
            "NO_CLEANUP_REQUIRED",
        )
        self.assertEqual(
            self.by_id["SCN-FILE-001"].catalog_metadata.cleanup_behavior,
            "AUTO_CLEANUP_SUPPORTED",
        )
        self.assertEqual(
            self.by_id["SCN-FILE-002"].catalog_metadata.cleanup_behavior,
            "AUTO_CLEANUP_SUPPORTED",
        )
        self.assertEqual(
            self.by_id["SCN-FILE-003"].catalog_metadata.cleanup_behavior,
            "NO_CLEANUP_REQUIRED",
        )
        self.assertEqual(
            self.by_id["SCN-AUTH-001"].catalog_metadata.cleanup_behavior,
            "NO_CLEANUP_REQUIRED",
        )

    def test_no_inferred_cleanup_scenario_id_from_numbering(self):
        # SCN-CALENDAR-001 must NOT have a cleanup_scenario_id of
        # SCN-CALENDAR-003 unless the catalog declares it. The current
        # catalog does not declare it.
        self.assertIsNone(self.by_id["SCN-CALENDAR-001"].definition.cleanup_scenario_id)
        self.assertIsNone(self.by_id["SCN-CALENDAR-002"].definition.cleanup_scenario_id)
        self.assertIsNone(self.by_id["SCN-CALENDAR-003"].definition.cleanup_scenario_id)
        self.assertIsNone(self.by_id["SCN-FILE-001"].definition.cleanup_scenario_id)
        self.assertIsNone(self.by_id["SCN-FILE-002"].definition.cleanup_scenario_id)
        self.assertIsNone(self.by_id["SCN-FILE-003"].definition.cleanup_scenario_id)

    def test_cleanup_required_flag_preserved(self):
        # From the catalog: cleanup_required=true for SCN-MAIL-001/002,
        # SCN-CALENDAR-001/002, SCN-FILE-001/002. cleanup_required=false
        # for SCN-CALENDAR-003, SCN-FILE-003, SCN-AUTH-001.
        expected = {
            "SCN-MAIL-001": True,
            "SCN-MAIL-002": True,
            "SCN-CALENDAR-001": True,
            "SCN-CALENDAR-002": True,
            "SCN-CALENDAR-003": False,
            "SCN-FILE-001": True,
            "SCN-FILE-002": True,
            "SCN-FILE-003": False,
            "SCN-AUTH-001": False,
        }
        for sid, want in expected.items():
            self.assertEqual(
                self.by_id[sid].definition.cleanup_required,
                want,
                msg="scenario {0!r} cleanup_required expected {1}".format(sid, want),
            )

    def test_no_cleanup_scenario_id_field_in_scenarios(self):
        # Confirm that none of the per-scenario JSON files have a
        # ``cleanup_scenario_id`` field. If the catalog ever adds it,
        # the loader should pass it through; until then it stays None.
        from pathlib import Path

        REPO_ROOT = Path(__file__).resolve().parents[3]
        scenarios_dir = REPO_ROOT / "config" / "scenarios" / "scenarios"
        for path in sorted(scenarios_dir.glob("SCN-*.json")):
            import json

            payload = json.loads(path.read_text())
            self.assertNotIn(
                "cleanup_scenario_id",
                payload,
                msg="scenario {0} has unexpected cleanup_scenario_id field".format(
                    path.name
                ),
            )


if __name__ == "__main__":
    unittest.main()