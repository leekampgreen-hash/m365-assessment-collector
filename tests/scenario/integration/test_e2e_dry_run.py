"""End-to-end integration tests for SCN-AUTH-001 and disabled scenarios.

These tests prove the full path:

    catalog
    -> loader
    -> ScenarioDefinition
    -> ScenarioRegistry
    -> safety evaluation
    -> plan
    -> DryRunScenarioExecutor
    -> ScenarioExecutionResult

is deterministic, OFFLINE, and never makes network / Graph calls.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from agents.scenario.catalog_loader import (
    build_catalog_registry,
    evaluate_permission_readiness,
    load_scenario_catalog,
)
from agents.scenario.engine import ScenarioAgent
from agents.scenario.executor import DryRunScenarioExecutor
from agents.scenario.models import (
    RISK_LOW,
    ScenarioRequest,
    STATUS_SUCCESS,
)
from agents.scenario.safety import (
    REASON_DISABLED_SCENARIO,
    ScenarioBlockedError,
)


class ScnAuth001EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_scenario_catalog()
        cls.reg_result = build_catalog_registry(cls.result)
        cls.agent = ScenarioAgent(
            cls.reg_result.registry,
            executor=DryRunScenarioExecutor(),
        )
        cls.by_id = {ls.scenario_id: ls for ls in cls.result.loaded_scenarios}
        cls.actor = next(a for a in cls.result.actors if a.actor_id == "test-user-01")

    def test_load(self):
        auth = self.by_id["SCN-AUTH-001"]
        self.assertTrue(auth.enabled)
        self.assertEqual(auth.definition.action_type, "INTERACTIVE_SIGNIN")
        self.assertEqual(auth.definition.risk_level, RISK_LOW)
        self.assertFalse(auth.definition.destructive)
        self.assertFalse(auth.definition.cleanup_required)

    def test_actor_bind(self):
        request = ScenarioRequest(
            scenario_id="SCN-AUTH-001", actor=self.actor
        )
        plan = self.agent.plan(request)
        self.assertEqual(plan.actor_id, "test-user-01")

    def test_safety_gate_passes(self):
        # No exception is raised: SCN-AUTH-001 is enabled, has actor,
        # declares its baseline permission, and the action is supported.
        request = ScenarioRequest(
            scenario_id="SCN-AUTH-001", actor=self.actor
        )
        plan = self.agent.plan(request)
        self.assertIsNotNone(plan)

    def test_plan(self):
        request = ScenarioRequest(
            scenario_id="SCN-AUTH-001", actor=self.actor
        )
        plan = self.agent.plan(request)
        self.assertEqual(plan.scenario_id, "SCN-AUTH-001")
        self.assertEqual(plan.steps[0].action_type, "INTERACTIVE_SIGNIN")
        # declared permissions come from the framework action mapping
        # for INTERACTIVE_SIGNIN, which resolves to User.Read.
        self.assertIn("User.Read", plan.declared_permissions)
        self.assertEqual(plan.risk_level, RISK_LOW)
        self.assertFalse(plan.cleanup_required)
        self.assertIsNone(plan.cleanup_scenario_id)

    def test_correlation_id_format(self):
        request = ScenarioRequest(
            scenario_id="SCN-AUTH-001", actor=self.actor
        )
        plan = self.agent.plan(request)
        self.assertTrue(plan.correlation_id.startswith("GA-SCENARIO-"))
        self.assertIn(plan.execution_id, plan.correlation_id)

    def test_dry_run_executes_to_success(self):
        request = ScenarioRequest(
            scenario_id="SCN-AUTH-001", actor=self.actor
        )
        result = self.agent.plan_and_execute(request)
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertTrue(result.correlation_id.startswith("GA-SCENARIO-"))
        # Evidence includes the actor id and the correlation marker.
        self.assertIn(self.actor.actor_id, " ".join(result.final_evidence))
        self.assertIn(result.correlation_id, result.final_evidence)
        # The single step is SUCCESS.
        self.assertEqual(len(result.step_results), 1)
        self.assertEqual(result.step_results[0].status, STATUS_SUCCESS)
        self.assertEqual(result.step_results[0].action_type, "INTERACTIVE_SIGNIN")

    def test_effective_permission_contract_recognizes_baseline(self):
        pr = evaluate_permission_readiness(
            self.by_id["SCN-AUTH-001"],
            available_permissions=["User.Read"],
        )
        self.assertEqual(pr.status, "READY")
        self.assertEqual(pr.missing_permissions, ())
        self.assertEqual(pr.currently_available_permissions, ("User.Read",))

    def test_no_graph_calls_during_dry_run(self):
        # The DryRunScenarioExecutor never imports collectors.core.transport
        # and never opens a socket. Patch builtins.open / urlopen to
        # detect any stray network call.
        request = ScenarioRequest(
            scenario_id="SCN-AUTH-001", actor=self.actor
        )
        with patch("urllib.request.urlopen") as mocked_urlopen, patch(
            "socket.socket"
        ) as mocked_socket:
            self.agent.plan_and_execute(request)
            mocked_urlopen.assert_not_called()
            mocked_socket.assert_not_called()


class DisabledScenarioEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_scenario_catalog()
        cls.reg_result = build_catalog_registry(cls.result)
        cls.agent = ScenarioAgent(
            cls.reg_result.registry,
            executor=DryRunScenarioExecutor(),
        )
        cls.actor = next(a for a in cls.result.actors if a.actor_id == "test-user-01")
        cls.by_id = {ls.scenario_id: ls for ls in cls.result.loaded_scenarios}

    def test_disabled_mail_scenario_is_blocked_at_safety_gate(self):
        for sid in ("SCN-MAIL-001", "SCN-MAIL-002"):
            request = ScenarioRequest(scenario_id=sid, actor=self.actor)
            with self.assertRaises(ScenarioBlockedError) as ctx:
                self.agent.plan(request)
            self.assertEqual(ctx.exception.reason_code, REASON_DISABLED_SCENARIO)

    def test_disabled_calendar_scenario_is_blocked_at_safety_gate(self):
        for sid in ("SCN-CALENDAR-001", "SCN-CALENDAR-002", "SCN-CALENDAR-003"):
            request = ScenarioRequest(scenario_id=sid, actor=self.actor)
            with self.assertRaises(ScenarioBlockedError) as ctx:
                self.agent.plan(request)
            self.assertEqual(ctx.exception.reason_code, REASON_DISABLED_SCENARIO)

    def test_disabled_file_scenario_is_blocked_at_safety_gate(self):
        for sid in ("SCN-FILE-001", "SCN-FILE-002", "SCN-FILE-003"):
            request = ScenarioRequest(scenario_id=sid, actor=self.actor)
            with self.assertRaises(ScenarioBlockedError) as ctx:
                self.agent.plan(request)
            self.assertEqual(ctx.exception.reason_code, REASON_DISABLED_SCENARIO)

    def test_missing_permission_blocks_future_enabled_scenario(self):
        # The OFFLINE permission readiness evaluation is the place
        # where a future enabled scenario is flagged as blocked due
        # to a missing permission. Even though SCN-MAIL-001 is
        # currently disabled in the catalog, evaluating its readiness
        # with only the User.Read baseline reports MISSING_PERMISSION
        # for Mail.Send, which is what a future enabled Mail scenario
        # would face without a permission grant.
        mail = self.by_id["SCN-MAIL-001"]
        # The status for the disabled scenario is DISABLED; we then
        # inspect the missing_permissions field which already lists
        # Mail.Send. This documents the missing-permission evidence
        # that would block the scenario if it were enabled.
        pr = evaluate_permission_readiness(
            mail, available_permissions=["User.Read"]
        )
        self.assertEqual(pr.status, "DISABLED")
        self.assertEqual(pr.missing_permissions, ("Mail.Send",))

    def test_no_live_graph_or_network_calls_in_disabled_path(self):
        with patch("urllib.request.urlopen") as mocked_urlopen, patch(
            "socket.socket"
        ) as mocked_socket:
            try:
                self.agent.plan(
                    ScenarioRequest(scenario_id="SCN-MAIL-001", actor=self.actor)
                )
            except ScenarioBlockedError:
                pass
            mocked_urlopen.assert_not_called()
            mocked_socket.assert_not_called()


if __name__ == "__main__":
    unittest.main()