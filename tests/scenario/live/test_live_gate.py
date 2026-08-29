"""Offline tests for the live executor's allow_live gate and action allowlist.

These tests prove:

* The default ``allow_live`` is ``False`` and a live executor refuses
  to perform any action when constructed without the explicit
  opt-in.
* The live executor is action-restricted: only ``INTERACTIVE_SIGNIN``
  is allowed; every other action type is refused with
  ``UNSUPPORTED_LIVE_ACTION``.
* Constructing an executor with ``allow_live=True`` without the
  required transports raises ``ValueError`` and never performs I/O.
* ``DryRunScenarioExecutor`` semantics are unchanged.
"""
from __future__ import annotations

import unittest

from agents.scenario import (
    ACTION_CREATE_CALENDAR_EVENT,
    ACTION_CREATE_FILE,
    ACTION_CREATE_GROUP_CONTENT,
    ACTION_CREATE_TEAMS_MESSAGE,
    ACTION_DELETE_CALENDAR_EVENT,
    ACTION_DELETE_FILE,
    ACTION_INTERACTIVE_SIGNIN,
    ACTION_NOOP_VALIDATION,
    ACTION_SEND_MAIL,
    ACTION_UPDATE_CALENDAR_EVENT,
    ACTION_UPDATE_FILE,
    LIVE_EXECUTION_DISABLED,
    LIVE_SUPPORTED_ACTIONS,
    LiveScenarioConfig,
    LiveScenarioExecutor,
    UNSUPPORTED_LIVE_ACTION,
)
from agents.scenario.executor import DryRunScenarioExecutor
from agents.scenario.models import (
    STATUS_BLOCKED,
    STATUS_SUCCESS,
    ScenarioActor,
    ScenarioPlan,
    ScenarioStep,
)

from tests.scenario.live._helpers import build_signin_plan


class AllowLiveGateTests(unittest.TestCase):
    def test_default_allow_live_is_false(self):
        ex = LiveScenarioExecutor()
        self.assertFalse(ex.allow_live)
        self.assertFalse(ex.is_live_enabled)

    def test_disabled_executor_blocks_signin_action(self):
        ex = LiveScenarioExecutor()
        plan, step, actor = build_signin_plan()
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_EXECUTION_DISABLED)

    def test_disabled_executor_blocks_unknown_action(self):
        ex = LiveScenarioExecutor()
        plan, step, actor = build_signin_plan()
        step = ScenarioStep(
            step_id=step.step_id,
            action_type="UNKNOWN",
        )
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_EXECUTION_DISABLED)

    def test_disabled_executor_blocks_when_explicit_allow_live_false(self):
        ex = LiveScenarioExecutor(allow_live=False)
        self.assertFalse(ex.is_live_enabled)
        plan, step, actor = build_signin_plan()
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_EXECUTION_DISABLED)

    def test_allow_live_true_requires_config(self):
        with self.assertRaises(ValueError):
            LiveScenarioExecutor(allow_live=True)

    def test_allow_live_true_requires_transports(self):
        config = LiveScenarioConfig(
            scenario_app_client_id="cid",
            scenario_app_tenant_id="tid",
        )
        with self.assertRaises(ValueError):
            LiveScenarioExecutor(allow_live=True, config=config)

    def test_allow_live_true_with_config_and_transports_constructs(self):
        from agents.scenario.auth.transports import (
            FakeDeviceCodeTransport,
            FakeGraphTransport,
        )
        config = LiveScenarioConfig(
            scenario_app_client_id="cid",
            scenario_app_tenant_id="tid",
        )
        ex = LiveScenarioExecutor(
            allow_live=True,
            config=config,
            device_code_request_transport=FakeDeviceCodeTransport().request,
            device_code_poll_transport=FakeDeviceCodeTransport().poll,
            graph_me_transport=FakeGraphTransport().request,
        )
        self.assertTrue(ex.is_live_enabled)


class ActionRestrictionTests(unittest.TestCase):
    """The live executor must refuse every action except INTERACTIVE_SIGNIN."""

    def _make_executor(self):
        from agents.scenario.auth.transports import (
            FakeDeviceCodeTransport,
            FakeGraphTransport,
        )
        config = LiveScenarioConfig(
            scenario_app_client_id="cid",
            scenario_app_tenant_id="tid",
        )
        return LiveScenarioExecutor(
            allow_live=True,
            config=config,
            device_code_request_transport=FakeDeviceCodeTransport().request,
            device_code_poll_transport=FakeDeviceCodeTransport().poll,
            graph_me_transport=FakeGraphTransport().request,
        )

    def test_supported_actions_allowlist(self):
        self.assertEqual(LIVE_SUPPORTED_ACTIONS, (ACTION_INTERACTIVE_SIGNIN,))
        executor = self._make_executor()
        self.assertEqual(executor.supported_actions, (ACTION_INTERACTIVE_SIGNIN,))

    def test_send_mail_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_SEND_MAIL)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_create_calendar_event_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_CREATE_CALENDAR_EVENT)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_update_calendar_event_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_UPDATE_CALENDAR_EVENT)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_delete_calendar_event_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_DELETE_CALENDAR_EVENT)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_create_file_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_CREATE_FILE)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_update_file_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_UPDATE_FILE)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_delete_file_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_DELETE_FILE)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_create_teams_message_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_CREATE_TEAMS_MESSAGE)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_create_group_content_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_CREATE_GROUP_CONTENT)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_noop_validation_blocked_in_live(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type=ACTION_NOOP_VALIDATION)
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_arbitrary_url_action_blocked(self):
        ex = self._make_executor()
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="s", action_type="RAW_GRAPH_CALL")
        result = ex.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        # Unknown action type is reported as UNSUPPORTED_LIVE_ACTION
        # because the live executor restricts the allowlist to
        # INTERACTIVE_SIGNIN. This proves the executor does not accept
        # arbitrary action types.
        self.assertIn(result.error_code, (UNSUPPORTED_LIVE_ACTION,))


class DryRunUnchangedTests(unittest.TestCase):
    """DryRunScenarioExecutor semantics must be unchanged."""

    def test_dry_run_still_works(self):
        from agents.scenario.actions import ACTION_NOOP_VALIDATION
        plan = ScenarioPlan(
            plan_id="p1",
            execution_id="e1",
            scenario_id="scenario.framework.noop_validation",
            actor_id="test-user-01",
            correlation_id="GA-SCENARIO-e1",
            steps=[ScenarioStep(step_id="s", action_type=ACTION_NOOP_VALIDATION)],
        )
        actor = ScenarioActor(actor_id="test-user-01")
        result = DryRunScenarioExecutor().execute(plan.steps[0], actor, plan)
        self.assertEqual(result.status, STATUS_SUCCESS)


if __name__ == "__main__":
    unittest.main()
