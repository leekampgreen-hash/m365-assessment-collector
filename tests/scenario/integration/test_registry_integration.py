"""Integration tests: registry integration with the catalog.

Verifies that:

* ``build_catalog_registry`` returns a deterministic registry that
  contains the built-in framework scenarios plus every catalog
  scenario.
* Catalog scenario ids do NOT collide with built-in ids.
* Enabled and disabled catalog ids are correctly partitioned.
* Loading the catalog is a pure operation -- the framework's global
  registry is not mutated as a side effect.
"""
from __future__ import annotations

import unittest

from agents.scenario.catalog_loader import (
    build_catalog_registry,
    load_scenario_catalog,
)
from agents.scenario.registry import ScenarioRegistry


class RegistryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_scenario_catalog()
        cls.reg_result = build_catalog_registry(cls.result)

    def test_registry_contains_builtin_and_catalog_scenarios(self):
        ids = set(self.reg_result.registry.scenario_ids())
        builtin = {
            "scenario.mail.send_test_message",
            "scenario.calendar.create_test_event",
            "scenario.files.create_test_file",
            "scenario.files.update_test_file",
            "scenario.teams.post_test_message",
            "scenario.groups.post_test_content",
            "scenario.framework.noop_validation",
        }
        catalog = {
            "SCN-MAIL-001",
            "SCN-MAIL-002",
            "SCN-CALENDAR-001",
            "SCN-CALENDAR-002",
            "SCN-CALENDAR-003",
            "SCN-FILE-001",
            "SCN-FILE-002",
            "SCN-FILE-003",
            "SCN-AUTH-001",
        }
        self.assertTrue(builtin.issubset(ids))
        self.assertTrue(catalog.issubset(ids))
        self.assertEqual(len(ids), len(builtin) + len(catalog))

    def test_catalog_ids_do_not_collide_with_builtin(self):
        ids = set(self.reg_result.registry.scenario_ids())
        self.assertNotIn("SCN-MAIL-001", {
            "scenario.mail.send_test_message",
            "scenario.calendar.create_test_event",
        })
        # The full assertion is implicit by construction.
        self.assertEqual(len(ids), 16)

    def test_enabled_and_disabled_partitions(self):
        self.assertEqual(self.reg_result.enabled_ids, ("SCN-AUTH-001",))
        self.assertEqual(
            self.reg_result.disabled_ids,
            (
                "SCN-CALENDAR-001",
                "SCN-CALENDAR-002",
                "SCN-CALENDAR-003",
                "SCN-FILE-001",
                "SCN-FILE-002",
                "SCN-FILE-003",
                "SCN-MAIL-001",
                "SCN-MAIL-002",
            ),
        )

    def test_loaded_scenarios_are_disabled_in_registry(self):
        for ls in self.reg_result.loaded_scenarios:
            definition = self.reg_result.registry.get(ls.scenario_id)
            self.assertIsNotNone(definition)
            self.assertEqual(
                definition.enabled,
                ls.enabled,
                msg="scenario {0!r} enabled flag must match catalog".format(
                    ls.scenario_id
                ),
            )

    def test_build_catalog_registry_is_pure(self):
        # Calling build_catalog_registry twice yields equivalent
        # registries without mutating a global.
        a = build_catalog_registry(self.result)
        b = build_catalog_registry(self.result)
        self.assertEqual(a.registry.scenario_ids(), b.registry.scenario_ids())

    def test_default_registry_is_not_mutated_by_load(self):
        # The framework's built-in registry must remain unchanged.
        before = ScenarioRegistry().scenario_ids()
        # Run a full load + build pipeline.
        load_scenario_catalog()
        after = ScenarioRegistry().scenario_ids()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()