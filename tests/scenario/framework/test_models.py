"""Offline tests for the Scenario Agent typed models.

The Scenario Agent model layer is pure data; these tests assert that:

* the closed status / risk / identity vocabularies are stable,
* dataclasses round-trip through ``to_dict``,
* the correlation marker helper produces the documented shape,
* serialization never leaks fields a caller may try to smuggle in.
"""
from __future__ import annotations

import json
import unittest

from agents.scenario.models import (
    EXECUTION_STATUSES,
    IDENTITY_NOT_REQUIRED,
    IDENTITY_OPTIONAL,
    IDENTITY_REQUIRED,
    IDENTITY_REQUIREMENTS,
    RISK_HIGH,
    RISK_LEVELS,
    RISK_LOW,
    RISK_MEDIUM,
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_PARTIAL_SUCCESS,
    STATUS_PLANNED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    TERMINAL_STATUSES,
    ScenarioActor,
    ScenarioDefinition,
    ScenarioExecutionResult,
    ScenarioPlan,
    ScenarioRequest,
    ScenarioStep,
    ScenarioStepResult,
    correlation_prefix,
    utcnow_iso,
)


class VocabulariesTests(unittest.TestCase):
    def test_execution_statuses_are_stable(self):
        self.assertEqual(
            EXECUTION_STATUSES,
            (
                STATUS_PLANNED,
                STATUS_RUNNING,
                STATUS_SUCCESS,
                STATUS_PARTIAL_SUCCESS,
                STATUS_FAILED,
                STATUS_BLOCKED,
            ),
        )

    def test_terminal_statuses_are_a_subset(self):
        for status in TERMINAL_STATUSES:
            self.assertIn(status, EXECUTION_STATUSES)
        self.assertNotIn(STATUS_PLANNED, TERMINAL_STATUSES)
        self.assertNotIn(STATUS_RUNNING, TERMINAL_STATUSES)

    def test_risk_levels_are_closed(self):
        self.assertEqual(RISK_LEVELS, (RISK_LOW, RISK_MEDIUM, RISK_HIGH))

    def test_identity_requirements_are_closed(self):
        self.assertEqual(
            IDENTITY_REQUIREMENTS,
            (IDENTITY_NOT_REQUIRED, IDENTITY_OPTIONAL, IDENTITY_REQUIRED),
        )


class CorrelationPrefixTests(unittest.TestCase):
    def test_correlation_prefix_uses_documented_shape(self):
        self.assertEqual(correlation_prefix("abc123"), "GA-SCENARIO-abc123")

    def test_correlation_prefix_is_stable_across_calls(self):
        self.assertEqual(
            correlation_prefix("xyz"),
            correlation_prefix("xyz"),
        )

    def test_correlation_prefix_does_not_include_input_echo(self):
        # The marker must not incorporate caller-supplied input beyond
        # the execution id itself.
        marker = correlation_prefix("exec-1")
        self.assertTrue(marker.startswith("GA-SCENARIO-"))
        self.assertIn("exec-1", marker)


class ActorModelTests(unittest.TestCase):
    def test_actor_to_dict_has_no_secret_fields(self):
        actor = ScenarioActor(
            actor_id="test-user-1",
            user_principal_name="test@example.org",
            object_id="00000000-0000-0000-0000-000000000001",
            description="A test actor.",
        )
        data = actor.to_dict()
        self.assertEqual(set(data.keys()), {
            "actor_id",
            "user_principal_name",
            "object_id",
            "allowed_scenario_ids",
            "allowed_workloads",
            "enabled",
            "description",
        })
        # Round trip through json to prove no field we did not expect.
        encoded = json.dumps(data)
        decoded = json.loads(encoded)
        self.assertNotIn("password", decoded)
        self.assertNotIn("token", decoded)
        self.assertNotIn("secret", decoded)


class ScenarioStepResultSerializationTests(unittest.TestCase):
    def test_step_result_serializes_safely(self):
        step_result = ScenarioStepResult(
            step_id="step-001",
            action_type="SEND_MAIL",
            status=STATUS_SUCCESS,
            evidence_labels=("dry_run:SEND_MAIL", "scenario:scenario.mail.send_test_message"),
        )
        data = step_result.to_dict()
        encoded = json.dumps(data)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["step_id"], "step-001")
        self.assertEqual(decoded["status"], STATUS_SUCCESS)

    def test_execution_result_serializes_safely(self):
        result = ScenarioExecutionResult(
            execution_id="exec-abc",
            correlation_id="GA-SCENARIO-exec-abc",
            scenario_id="scenario.framework.noop_validation",
            actor_id="test-user-1",
            status=STATUS_SUCCESS,
        )
        data = result.to_dict()
        encoded = json.dumps(data)
        decoded = json.loads(encoded)
        self.assertNotIn("token", decoded)
        self.assertNotIn("authorization", decoded)
        self.assertEqual(decoded["actor_id"], "test-user-1")


class PlanToDictTests(unittest.TestCase):
    def test_plan_to_dict_round_trip(self):
        step = ScenarioStep(
            step_id="step-001",
            action_type="NOOP_VALIDATION",
            declared_permissions=["User.Read"],
        )
        plan = ScenarioPlan(
            plan_id="plan-1",
            execution_id="exec-1",
            scenario_id="scenario.framework.noop_validation",
            actor_id="test-user-1",
            correlation_id="GA-SCENARIO-exec-1",
            declared_permissions=["User.Read"],
            steps=[step],
        )
        data = plan.to_dict()
        self.assertEqual(data["plan_id"], "plan-1")
        self.assertEqual(data["steps"][0]["action_type"], "NOOP_VALIDATION")
        # No raw transport fields appear in the plan.
        self.assertNotIn("url", data)
        self.assertNotIn("method", data)


class UtcNowIsoTests(unittest.TestCase):
    def test_utcnow_iso_is_iso8601_utc(self):
        value = utcnow_iso()
        # ISO-8601 in UTC ends with +00:00 or Z.
        self.assertTrue(value.endswith("+00:00") or value.endswith("Z"))
        # Re-parseable as ISO-8601.
        from datetime import datetime
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self.assertIsNotNone(parsed)


class RequestToDictTests(unittest.TestCase):
    def test_request_to_dict_without_actor(self):
        request = ScenarioRequest(scenario_id="scenario.framework.noop_validation")
        data = request.to_dict()
        self.assertIsNone(data["actor"])
        self.assertEqual(data["scenario_id"], "scenario.framework.noop_validation")

    def test_request_with_metadata_isolates_actor_serialization(self):
        actor = ScenarioActor(actor_id="u-1")
        request = ScenarioRequest(
            scenario_id="scenario.framework.noop_validation",
            actor=actor,
            metadata={"parameters": {"subject": "hello"}},
        )
        data = request.to_dict()
        self.assertEqual(data["actor"]["actor_id"], "u-1")
        self.assertEqual(data["metadata"]["parameters"]["subject"], "hello")


if __name__ == "__main__":
    unittest.main()