"""Offline regression tests for CH3 delegated live-validation controls."""
from __future__ import annotations

import json
import unittest

from agents.scenario import (
    ACTION_SEND_MAIL,
    ACTOR_IDENTITY_MISMATCH,
    LIVE_EXECUTION_DISABLED,
    UNSUPPORTED_LIVE_ACTION,
    LiveScenarioConfig,
    LiveScenarioExecutor,
)
from agents.scenario.auth import ExpectedActor
from agents.scenario.auth.transports import FakeDeviceCodeTransport, FakeGraphTransport
from agents.scenario.executor import sanitize_evidence
from agents.scenario.models import STATUS_BLOCKED, STATUS_FAILED, ScenarioStep

from tests.scenario.live._helpers import (
    FAKE_CLIENT_ID,
    FAKE_TENANT,
    FAKE_USER_OBJECT_ID,
    build_signin_plan,
)


def _enabled_executor(*, expected_actor, graph_object_id=FAKE_USER_OBJECT_ID):
    device = FakeDeviceCodeTransport()
    graph = FakeGraphTransport(me_object_id=graph_object_id)
    return LiveScenarioExecutor(
        allow_live=True,
        config=LiveScenarioConfig(
            scenario_app_client_id=FAKE_CLIENT_ID,
            scenario_app_tenant_id=FAKE_TENANT,
            expected_actor=expected_actor,
        ),
        device_code_request_transport=device.request,
        device_code_poll_transport=device.poll,
        graph_me_transport=graph.request,
        sleep=lambda _: None,
        clock=lambda: 0.0,
    )


class LiveValidationGateTests(unittest.TestCase):
    def test_gate_disabled_blocks_execution(self):
        plan, step, actor = build_signin_plan()
        result = LiveScenarioExecutor().execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_EXECUTION_DISABLED)

    def test_actor_mismatch_blocked(self):
        plan, step, actor = build_signin_plan()
        executor = _enabled_executor(
            expected_actor=ExpectedActor(object_id="expected-object-id"),
        )
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, ACTOR_IDENTITY_MISMATCH)

    def test_unsupported_operation_blocked(self):
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="mutation", action_type=ACTION_SEND_MAIL)
        executor = _enabled_executor(
            expected_actor=ExpectedActor(object_id=FAKE_USER_OBJECT_ID),
        )
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)

    def test_evidence_sanitizer_removes_sensitive_fields(self):
        evidence = sanitize_evidence(
            {
                "execution_id": "execution-1",
                "actor": {"object_id": "actor-1", "access_token": "secret"},
                "authorization": "Bearer secret",
                "raw_payload": {"value": "must-not-appear"},
                "nested": [{"refresh_token": "secret", "status": "success"}],
            }
        )
        self.assertEqual(
            evidence,
            {
                "execution_id": "execution-1",
                "actor": {"object_id": "actor-1"},
                "nested": [{"status": "success"}],
            },
        )

    def test_device_code_not_in_evidence(self):
        evidence = sanitize_evidence({"device_code": "device-secret", "status": "success"})
        self.assertEqual(evidence, {"status": "success"})

    def test_user_code_not_in_evidence(self):
        evidence = sanitize_evidence({"user_code": "ABCD-EFGH", "status": "success"})
        self.assertEqual(evidence, {"status": "success"})

    def test_verification_uri_not_in_evidence(self):
        evidence = sanitize_evidence(
            {"verification_uri": "https://microsoft.com/devicelogin", "status": "success"}
        )
        self.assertEqual(evidence, {"status": "success"})

    def test_device_prompt_not_in_execution_result(self):
        plan, step, actor = build_signin_plan()
        device = FakeDeviceCodeTransport()
        device.request_response = device.request_response.__class__(
            status=200,
            body={
                "device_code": "device-secret",
                "user_code": "ABCD-EFGH",
                "verification_uri": "https://microsoft.com/devicelogin",
                "message": "Use code ABCD-EFGH at https://microsoft.com/devicelogin",
                "expires_in": 900,
                "interval": 5,
            },
        )
        graph = FakeGraphTransport(me_object_id=FAKE_USER_OBJECT_ID)
        executor = LiveScenarioExecutor(
            allow_live=True,
            config=LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                expected_actor=ExpectedActor(object_id=FAKE_USER_OBJECT_ID),
            ),
            device_code_request_transport=device.request,
            device_code_poll_transport=device.poll,
            graph_me_transport=graph.request,
            sleep=lambda _: None,
            clock=lambda: 0.0,
        )
        result = executor.execute(step, actor, plan)
        serialized = repr(result.to_dict())
        self.assertNotIn("DeviceCodePrompt", serialized)
        self.assertNotIn("Use code ABCD-EFGH", serialized)
        self.assertNotIn("ABCD-EFGH", serialized)
        self.assertNotIn("https://microsoft.com/devicelogin", serialized)

    def test_user_code_not_serialized(self):
        plan, step, actor = build_signin_plan()
        prompt_values = []
        device = FakeDeviceCodeTransport()
        executor = LiveScenarioExecutor(
            allow_live=True,
            config=LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                expected_actor=ExpectedActor(object_id=FAKE_USER_OBJECT_ID),
            ),
            device_code_request_transport=device.request,
            device_code_poll_transport=device.poll,
            graph_me_transport=FakeGraphTransport(me_object_id=FAKE_USER_OBJECT_ID).request,
            prompt_callback=lambda prompt: prompt_values.append(prompt.user_code),
            sleep=lambda _: None,
            clock=lambda: 0.0,
        )
        result = executor.execute(step, actor, plan)
        self.assertEqual(prompt_values, ["FAKE-USER-CODE"])
        self.assertNotIn("FAKE-USER-CODE", json.dumps(result.to_dict()))

    def test_verification_uri_not_serialized(self):
        plan, step, actor = build_signin_plan()
        prompt_values = []
        device = FakeDeviceCodeTransport()
        executor = LiveScenarioExecutor(
            allow_live=True,
            config=LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                expected_actor=ExpectedActor(object_id=FAKE_USER_OBJECT_ID),
            ),
            device_code_request_transport=device.request,
            device_code_poll_transport=device.poll,
            graph_me_transport=FakeGraphTransport(me_object_id=FAKE_USER_OBJECT_ID).request,
            prompt_callback=lambda prompt: prompt_values.append(prompt.verification_uri),
            sleep=lambda _: None,
            clock=lambda: 0.0,
        )
        result = executor.execute(step, actor, plan)
        self.assertEqual(prompt_values, ["https://microsoft.com/devicelogin"])
        self.assertNotIn("https://microsoft.com/devicelogin", json.dumps(result.to_dict()))

    def test_prompt_callback_data_not_in_evidence(self):
        evidence = sanitize_evidence(
            {
                "prompt": {
                    "user_code": "ABCD-EFGH",
                    "verification_uri": "https://microsoft.com/devicelogin",
                    "verification_uri_complete": "https://microsoft.com/devicelogin?code=ABCD-EFGH",
                    "message": "Use code ABCD-EFGH",
                },
                "status": "success",
            }
        )
        self.assertEqual(evidence, {"status": "success"})

    def test_nested_device_fields_removed(self):
        evidence = sanitize_evidence(
            {
                "dict": {"device_code": "secret", "safe": "value"},
                "list": [{"user_code": "ABCD"}, {"safe": "value"}],
                "tuple": (
                    {"verification_uri_complete": "https://example.test"},
                    {"prompt": {"message": "challenge", "safe": "value"}},
                ),
            }
        )
        self.assertEqual(
            evidence,
            {
                "dict": {"safe": "value"},
                "list": [{}, {"safe": "value"}],
                "tuple": [{}, {}],
            },
        )

    def test_mutation_attempt_blocked(self):
        plan, _, actor = build_signin_plan()
        step = ScenarioStep(step_id="mutation", action_type="DELETE_RESOURCE")
        executor = _enabled_executor(
            expected_actor=ExpectedActor(object_id=FAKE_USER_OBJECT_ID),
        )
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, UNSUPPORTED_LIVE_ACTION)


if __name__ == "__main__":
    unittest.main()
