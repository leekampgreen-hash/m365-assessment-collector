"""Offline tests for the Scenario Registry."""
from __future__ import annotations

import unittest

from agents.scenario.actions import (
    ACTION_CREATE_CALENDAR_EVENT,
    ACTION_CREATE_FILE,
    ACTION_CREATE_GROUP_CONTENT,
    ACTION_CREATE_TEAMS_MESSAGE,
    ACTION_NOOP_VALIDATION,
    ACTION_SEND_MAIL,
    ACTION_UPDATE_FILE,
)
from agents.scenario.models import (
    IDENTITY_REQUIRED,
    RISK_LOW,
    ScenarioDefinition,
)
from agents.scenario.registry import ScenarioRegistry


class BuiltinRegistryTests(unittest.TestCase):
    def test_builtin_registry_exposes_seven_known_scenarios(self):
        registry = ScenarioRegistry()
        ids = set(registry.scenario_ids())
        self.assertEqual(
            ids,
            {
                "scenario.mail.send_test_message",
                "scenario.calendar.create_test_event",
                "scenario.files.create_test_file",
                "scenario.files.update_test_file",
                "scenario.teams.post_test_message",
                "scenario.groups.post_test_content",
                "scenario.framework.noop_validation",
            },
        )

    def test_builtin_scenarios_cover_supported_action_types(self):
        registry = ScenarioRegistry()
        covered = {definition.action_type for definition in registry.values()}
        self.assertEqual(
            covered,
            {
                ACTION_SEND_MAIL,
                ACTION_CREATE_CALENDAR_EVENT,
                ACTION_CREATE_FILE,
                ACTION_UPDATE_FILE,
                ACTION_CREATE_TEAMS_MESSAGE,
                ACTION_CREATE_GROUP_CONTENT,
                ACTION_NOOP_VALIDATION,
            },
        )

    def test_builtin_scenarios_require_identity(self):
        registry = ScenarioRegistry()
        for definition in registry.values():
            self.assertEqual(
                definition.identity_requirement,
                IDENTITY_REQUIRED,
                msg="scenario {0!r} must require identity".format(
                    definition.scenario_id
                ),
            )

    def test_builtin_scenarios_declare_permissions(self):
        registry = ScenarioRegistry()
        for definition in registry.values():
            self.assertGreaterEqual(
                len(definition.required_delegated_permissions),
                1,
                msg="scenario {0!r} must declare permissions".format(
                    definition.scenario_id
                ),
            )


class CustomRegistryTests(unittest.TestCase):
    def test_extra_scenarios_can_be_added(self):
        definition = ScenarioDefinition(
            scenario_id="scenario.custom.x",
            name="Custom scenario",
            description="For tests.",
            workload="custom",
            action_type=ACTION_NOOP_VALIDATION,
            identity_requirement=IDENTITY_REQUIRED,
            required_delegated_permissions=["User.Read"],
            risk_level=RISK_LOW,
        )
        registry = ScenarioRegistry(extra=[definition])
        self.assertIn("scenario.custom.x", registry)
        self.assertIsNotNone(registry.get("scenario.custom.x"))

    def test_extra_without_permissions_rejected_at_construction(self):
        definition = ScenarioDefinition(
            scenario_id="scenario.custom.no_perms",
            name="Custom scenario",
            description="For tests.",
            workload="custom",
            action_type=ACTION_NOOP_VALIDATION,
            identity_requirement=IDENTITY_REQUIRED,
            required_delegated_permissions=[],
            risk_level=RISK_LOW,
        )
        with self.assertRaises(ValueError):
            ScenarioRegistry(extra=[definition])

    def test_extra_without_id_rejected_at_construction(self):
        definition = ScenarioDefinition(
            scenario_id="",
            name="Custom scenario",
            description="For tests.",
            workload="custom",
            action_type=ACTION_NOOP_VALIDATION,
            identity_requirement=IDENTITY_REQUIRED,
            required_delegated_permissions=["User.Read"],
            risk_level=RISK_LOW,
        )
        with self.assertRaises(ValueError):
            ScenarioRegistry(extra=[definition])


class RegistryShapeTests(unittest.TestCase):
    def test_scenario_ids_is_stable_across_instances(self):
        first = ScenarioRegistry().scenario_ids()
        second = ScenarioRegistry().scenario_ids()
        self.assertEqual(first, second)

    def test_to_dict_round_trip_is_json_safe(self):
        import json

        registry = ScenarioRegistry()
        encoded = json.dumps(registry.to_dict())
        decoded = json.loads(encoded)
        self.assertIn("scenario.mail.send_test_message", decoded)


if __name__ == "__main__":
    unittest.main()