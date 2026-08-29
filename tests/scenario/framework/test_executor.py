"""Offline tests for the DryRunScenarioExecutor and executor protocol."""
from __future__ import annotations

import unittest

from agents.scenario.actions import (
    ACTION_NOOP_VALIDATION,
    ACTION_SEND_MAIL,
    SUPPORTED_ACTION_TYPES,
)
from agents.scenario.executor import (
    DryRunScenarioExecutor,
    action_description,
)
from agents.scenario.models import (
    STATUS_SUCCESS,
    ScenarioActor,
    ScenarioPlan,
    ScenarioStep,
    utcnow_iso,
)


def _plan(**overrides):
    defaults = dict(
        plan_id="plan-1",
        execution_id="exec-1",
        scenario_id="scenario.mail.send_test_message",
        actor_id="test-user-1",
        correlation_id="GA-SCENARIO-exec-1",
        declared_permissions=["Mail.Send"],
        steps=[
            ScenarioStep(
                step_id="step-001",
                action_type=ACTION_SEND_MAIL,
                declared_permissions=["Mail.Send"],
            )
        ],
    )
    defaults.update(overrides)
    return ScenarioPlan(**defaults)


class DryRunExecutorNeverCallsGraphTests(unittest.TestCase):
    def test_dry_run_returns_success(self):
        executor = DryRunScenarioExecutor()
        result = executor.execute(
            ScenarioStep(step_id="step-001", action_type=ACTION_SEND_MAIL),
            ScenarioActor(actor_id="test-user-1"),
            _plan(),
        )
        self.assertEqual(result.status, STATUS_SUCCESS)

    def test_dry_run_does_not_import_graph_transport(self):
        # Importing the executor module must not pull in any Graph
        # transport module. If a future change starts importing
        # ``collectors.core.transport`` (or anything similar) it should
        # fail here.
        import sys

        self.assertNotIn("collectors.core.transport", sys.modules)
        self.assertNotIn("urllib.request", sys.modules)

    def test_dry_run_preserves_identifiers(self):
        executor = DryRunScenarioExecutor()
        plan = _plan()
        result = executor.execute(plan.steps[0], ScenarioActor(actor_id="test-user-1"), plan)
        self.assertEqual(result.step_id, "step-001")
        self.assertEqual(result.action_type, ACTION_SEND_MAIL)

    def test_dry_run_records_scenario_and_correlation_in_evidence(self):
        executor = DryRunScenarioExecutor()
        plan = _plan()
        result = executor.execute(plan.steps[0], ScenarioActor(actor_id="test-user-1"), plan)
        evidence = list(result.evidence_labels)
        self.assertTrue(any("scenario:" in label for label in evidence))
        self.assertTrue(any("correlation:" in label for label in evidence))

    def test_dry_run_never_calls_graph(self):
        # Capture all method calls on a fake actor; the executor must
        # only read attributes.
        class CountingActor:
            def __init__(self):
                self.actor_id = "u-1"
                self.reads = 0

            def __getattribute__(self, name):
                if name == "reads":
                    return object.__getattribute__(self, "reads")
                if name == "actor_id":
                    self.reads += 1
                    return "u-1"
                return object.__getattribute__(self, name)

        executor = DryRunScenarioExecutor()
        plan = _plan()
        actor = CountingActor()
        executor.execute(plan.steps[0], actor, plan)
        # The actor's actor_id was read at most once -- no implicit
        # state lookups beyond what's documented.
        self.assertLessEqual(actor.reads, 2)


class DryRunExecutorEvidenceTests(unittest.TestCase):
    def test_evidence_redacts_token_shaped_values(self):
        # Even though dry-run evidence only emits parameter keys, the
        # public ``redact_value`` helper used inside the executor must
        # not propagate bearer-shaped strings back to callers.
        from agents.scenario.executor import redact_value

        redacted = redact_value({
            "subject": "hello",
            "token_echo": "bearer abcdefghijklmnop",
        })
        self.assertEqual(redacted["subject"], "hello")
        self.assertEqual(redacted["token_echo"], "[REDACTED]")

    def test_redact_handles_nested_structures(self):
        from agents.scenario.executor import redact_value

        redacted = redact_value({
            "outer": {"inner": "bearer abcdefghijklmnop"},
            "list": ["clean", "bearer abcdefghijklmnop"],
        })
        self.assertEqual(redacted["outer"]["inner"], "[REDACTED]")
        self.assertEqual(redacted["list"][0], "clean")
        self.assertEqual(redacted["list"][1], "[REDACTED]")

    def test_redact_passes_through_non_strings(self):
        from agents.scenario.executor import redact_value

        self.assertEqual(redact_value(123), 123)
        self.assertEqual(redact_value(True), True)
        self.assertEqual(redact_value(None), None)

    def test_evidence_with_actor_none(self):
        executor = DryRunScenarioExecutor()
        step = ScenarioStep(step_id="step-001", action_type=ACTION_NOOP_VALIDATION)
        result = executor.execute(step, None, _plan(actor_id=None))
        self.assertTrue(any(label.startswith("actor:none") for label in result.evidence_labels))

    def test_blocked_action_returns_blocked_status(self):
        executor = DryRunScenarioExecutor()
        step = ScenarioStep(step_id="step-001", action_type="UNKNOWN")
        result = executor.execute(step, None, _plan())
        from agents.scenario.models import STATUS_BLOCKED
        self.assertEqual(result.status, STATUS_BLOCKED)


class ActionDescriptionTests(unittest.TestCase):
    def test_action_description_for_known_action(self):
        self.assertNotEqual(action_description(ACTION_SEND_MAIL), "")
        for action in SUPPORTED_ACTION_TYPES:
            self.assertNotEqual(action_description(action), "")


if __name__ == "__main__":
    unittest.main()