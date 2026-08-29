"""Offline tests for the ScenarioAgent planning and execution engine."""
from __future__ import annotations

import unittest

from agents.scenario.actions import (
    ACTION_NOOP_VALIDATION,
    ACTION_SEND_MAIL,
    declared_permissions_for,
)
from agents.scenario.engine import ScenarioAgent
from agents.scenario.models import (
    IDENTITY_REQUIRED,
    RISK_LOW,
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_PARTIAL_SUCCESS,
    STATUS_SUCCESS,
    ScenarioActor,
    ScenarioDefinition,
    ScenarioRequest,
    correlation_prefix,
)
from agents.scenario.registry import ScenarioRegistry
from agents.scenario.safety import (
    REASON_MISSING_ACTOR,
    REASON_UNKNOWN_SCENARIO,
    ScenarioBlockedError,
)


def _actor(**overrides):
    defaults = dict(actor_id="test-user-1")
    defaults.update(overrides)
    return ScenarioActor(**defaults)


class PlanTests(unittest.TestCase):
    def test_plan_for_registered_scenario(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"parameters": {"subject": "hi"}},
        )
        plan = agent.plan(request)
        self.assertEqual(plan.scenario_id, "scenario.mail.send_test_message")
        self.assertEqual(plan.actor_id, "test-user-1")
        self.assertEqual(plan.steps[0].action_type, ACTION_SEND_MAIL)

    def test_plan_preserves_declared_permissions(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        plan = agent.plan(request)
        self.assertIn("Mail.Send", plan.declared_permissions)

    def test_plan_sanitizes_caller_parameters(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"parameters": {"url": "https://graph.microsoft.com/v1.0/me/sendMail"}},
        )
        plan = agent.plan(request)
        self.assertNotIn("url", plan.steps[0].safe_parameters)

    def test_plan_is_blocked_for_unknown_scenario(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.does.not.exist",
            actor=_actor(),
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            agent.plan(request)
        self.assertEqual(ctx.exception.reason_code, REASON_UNKNOWN_SCENARIO)

    def test_plan_is_blocked_for_missing_actor(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=None,
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            agent.plan(request)
        self.assertEqual(ctx.exception.reason_code, REASON_MISSING_ACTOR)

    def test_plan_assigns_unique_execution_and_correlation_ids(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        plans = [agent.plan(request) for _ in range(3)]
        ids = {plan.execution_id for plan in plans}
        self.assertEqual(len(ids), 3)
        for plan in plans:
            self.assertEqual(plan.correlation_id, correlation_prefix(plan.execution_id))

    def test_plan_does_not_mutate_request(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"parameters": {"subject": "hi"}},
        )
        snapshot_metadata = dict(request.metadata)
        snapshot_parameters = dict(request.metadata["parameters"])
        agent.plan(request)
        self.assertEqual(request.metadata, snapshot_metadata)
        self.assertEqual(request.metadata["parameters"], snapshot_parameters)


class ExecuteTests(unittest.TestCase):
    def test_execute_returns_success_in_dry_run(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(result.actor_id, "test-user-1")
        self.assertEqual(result.scenario_id, "scenario.mail.send_test_message")

    def test_execute_starts_and_completes_with_timestamps(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.completed_at)
        self.assertIsNotNone(result.duration)
        self.assertGreaterEqual(result.duration, 0)

    def test_execute_records_correlation_id_in_result(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertEqual(result.correlation_id, correlation_prefix(result.execution_id))

    def test_execute_records_cleanup_metadata(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.files.create_test_file",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertTrue(result.cleanup_required)

    def test_execute_blocks_when_actor_missing(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        # Plan with a not-required scenario so planning succeeds.
        definition = ScenarioDefinition(
            scenario_id="scenario.framework.noop_validation",
            name="noop",
            description="noop",
            workload="framework",
            action_type=ACTION_NOOP_VALIDATION,
            identity_requirement=IDENTITY_REQUIRED,
            required_delegated_permissions=["User.Read"],
            risk_level=RISK_LOW,
        )
        registry_extra = ScenarioRegistry(extra=[definition])
        agent = ScenarioAgent(registry_extra)
        request = ScenarioRequest(
            scenario_id="scenario.framework.noop_validation",
            actor=None,
        )
        with self.assertRaises(ScenarioBlockedError):
            agent.plan(request)

    def test_execute_blocks_when_plan_actor_not_supplied(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        plan_request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        plan = agent.plan(plan_request)
        with self.assertRaises(ScenarioBlockedError) as ctx:
            agent.execute(plan)  # no actor
        self.assertIn(ctx.exception.reason_code, {"ACTOR_MISSING"})

    def test_execute_blocks_when_supplied_actor_mismatches(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        plan_request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(actor_id="u-1"),
        )
        plan = agent.plan(plan_request)
        with self.assertRaises(ScenarioBlockedError):
            agent.execute(plan, actor=_actor(actor_id="u-2"))

    def test_execute_blocks_when_plan_refers_to_unknown_scenario(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        plan_request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        plan = agent.plan(plan_request)
        # Forge an unknown scenario_id on the plan.
        from dataclasses import replace
        bad_plan = replace(plan, scenario_id="scenario.does.not.exist")
        with self.assertRaises(ScenarioBlockedError):
            agent.execute(bad_plan, actor=_actor())


class ResultSafetyTests(unittest.TestCase):
    def test_result_does_not_contain_credentials(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"parameters": {"subject": "hi"}},
        )
        result = agent.plan_and_execute(request)
        data = result.to_dict()
        encoded = repr(data)
        self.assertNotIn("password", encoded)
        self.assertNotIn("access_token", encoded)
        self.assertNotIn("client_secret", encoded)
        self.assertNotIn("Authorization", encoded)
        self.assertNotIn("bearer", encoded.lower())

    def test_result_declares_permissions(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertIn("Mail.Send", result.declared_permissions)

    def test_result_includes_risk_level(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertEqual(result.risk_level, RISK_LOW)

    def test_step_result_status_round_trips(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        request = ScenarioRequest(
            scenario_id="scenario.framework.noop_validation",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertGreaterEqual(len(result.step_results), 1)
        self.assertEqual(result.step_results[0].status, STATUS_SUCCESS)


class DryRunExecutorIntegrationTests(unittest.TestCase):
    def test_dry_run_uses_default_executor(self):
        registry = ScenarioRegistry()
        agent = ScenarioAgent(registry)
        self.assertEqual(type(agent.executor).__name__, "DryRunScenarioExecutor")

    def test_custom_executor_can_be_injected(self):
        registry = ScenarioRegistry()
        calls = []

        class RecordingExecutor:
            def execute(self, step, actor, plan):
                calls.append((step.step_id, plan.scenario_id))
                from agents.scenario.models import ScenarioStepResult, STATUS_SUCCESS, utcnow_iso
                return ScenarioStepResult(
                    step_id=step.step_id,
                    action_type=step.action_type,
                    status=STATUS_SUCCESS,
                    started_at=utcnow_iso(),
                    completed_at=utcnow_iso(),
                )

        agent = ScenarioAgent(registry, executor=RecordingExecutor())
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "scenario.mail.send_test_message")

    def test_custom_executor_returning_failure_propagates(self):
        registry = ScenarioRegistry()
        from agents.scenario.models import (
            ScenarioStepResult, STATUS_FAILED, utcnow_iso,
        )

        class FailingExecutor:
            def execute(self, step, actor, plan):
                return ScenarioStepResult(
                    step_id=step.step_id,
                    action_type=step.action_type,
                    status=STATUS_FAILED,
                    started_at=utcnow_iso(),
                    completed_at=utcnow_iso(),
                    error_code="FORCED",
                )

        agent = ScenarioAgent(registry, executor=FailingExecutor())
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        result = agent.plan_and_execute(request)
        self.assertEqual(result.status, STATUS_FAILED)

    def test_custom_executor_returning_partial(self):
        registry = ScenarioRegistry()
        from agents.scenario.models import (
            ScenarioStepResult, STATUS_FAILED, STATUS_SUCCESS, utcnow_iso,
        )

        class PartialExecutor:
            def __init__(self):
                self.calls = 0

            def execute(self, step, actor, plan):
                self.calls += 1
                # Pretend first call succeeds, second call fails.
                status = STATUS_SUCCESS if self.calls == 1 else STATUS_FAILED
                return ScenarioStepResult(
                    step_id=step.step_id,
                    action_type=step.action_type,
                    status=status,
                    started_at=utcnow_iso(),
                    completed_at=utcnow_iso(),
                )

        agent = ScenarioAgent(registry, executor=PartialExecutor())
        # We construct a multi-step plan manually for this test.
        from agents.scenario.models import ScenarioPlan, ScenarioStep

        plan = ScenarioPlan(
            plan_id="plan-multi",
            execution_id="exec-multi",
            scenario_id="scenario.mail.send_test_message",
            actor_id="test-user-1",
            correlation_id=correlation_prefix("exec-multi"),
            declared_permissions=declared_permissions_for(ACTION_SEND_MAIL),
            steps=[
                ScenarioStep(step_id="step-001", action_type=ACTION_SEND_MAIL),
                ScenarioStep(step_id="step-002", action_type=ACTION_SEND_MAIL),
            ],
        )
        result = agent.execute(plan, actor=_actor())
        self.assertEqual(result.status, STATUS_PARTIAL_SUCCESS)


if __name__ == "__main__":
    unittest.main()