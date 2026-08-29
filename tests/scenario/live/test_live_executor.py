"""End-to-end offline tests for ``LiveScenarioExecutor``.

These tests drive the live executor through the entire
INTERACTIVE_SIGNIN flow with fake transports. They prove:

* A successful fake device-code login results in a ``SUCCESS`` step
  result with the expected observable endpoint label.
* The ``/me`` identity verification is mandatory: every successful
  execution performs a single ``GET /me`` and records
  ``actor_verified``; a missing/empty expected actor fails closed
  with ``LIVE_CONFIGURATION_INVALID`` before any network or auth
  operation starts.
* An actor mismatch results in a controlled ``ACTOR_IDENTITY_MISMATCH``
  failure.
* Timeouts / declines / token errors propagate to deterministic
  step-result error codes.
* The token is never present in the result's evidence or in the
  result's ``__repr__``.
* No real network call is performed (transport calls are recorded by
  the fakes only).
* The correlation id is preserved in the evidence, and the
  ``GA-SCENARIO-*`` marker is documented as plan-side only (i.e. not
  embedded in the upstream sign-in event).
"""
from __future__ import annotations

import unittest

from agents.scenario import (
    ACTOR_IDENTITY_MISMATCH,
    AUTH_DECLINED,
    AUTH_DEVICE_CODE_ERROR,
    AUTH_TIMEOUT,
    AUTH_TOKEN_ERROR,
    GRAPH_ME_VALIDATION_FAILED,
    LIVE_CONFIGURATION_INVALID,
    LiveScenarioConfig,
    LiveScenarioExecutor,
)
from agents.scenario.auth import ExpectedActor, TokenTransportResponse
from agents.scenario.auth.transports import (
    FakeDeviceCodeTransport,
    FakeGraphTransport,
)
from agents.scenario.models import (
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_SUCCESS,
)

from tests.scenario.live._helpers import (
    EXPECTED_TEST_ACTOR,
    FAKE_CLIENT_ID,
    FAKE_TENANT,
    FAKE_USER_OBJECT_ID,
    FAKE_USER_UPN,
    build_signin_plan,
)


def _make_executor(
    *,
    expected_actor=EXPECTED_TEST_ACTOR,
    request_response=None,
    poll_response=None,
    poll_queue=None,
    request_error=None,
    poll_error=None,
    me_object_id=FAKE_USER_OBJECT_ID,
    me_user_principal_name=FAKE_USER_UPN,
    me_error=None,
    me_exception=None,
    sleep=None,
    clock=None,
    timeout_seconds=300.0,
):
    transport = FakeDeviceCodeTransport()
    if request_response is not None:
        transport.request_response = request_response
    if poll_response is not None:
        transport.poll_response = poll_response
    if poll_queue is not None:
        transport._poll_queue = list(poll_queue)
    if request_error is not None:
        transport.request_error = request_error
    if poll_error is not None:
        transport.poll_error = poll_error
    graph = FakeGraphTransport(
        me_object_id=me_object_id,
        me_user_principal_name=me_user_principal_name,
    )
    if me_error is not None:
        graph.me_error = me_error
    if me_exception is not None:
        graph.me_exception = me_exception
    config = LiveScenarioConfig(
        scenario_app_client_id=FAKE_CLIENT_ID,
        scenario_app_tenant_id=FAKE_TENANT,
        expected_actor=expected_actor,
        timeout_seconds=timeout_seconds,
    )
    return LiveScenarioExecutor(
        allow_live=True,
        config=config,
        device_code_request_transport=transport.request,
        device_code_poll_transport=transport.poll,
        graph_me_transport=graph.request,
        sleep=sleep or (lambda s: None),
        clock=clock or (lambda: 0.0),
    ), transport, graph


class EndToEndSuccessTests(unittest.TestCase):
    def test_missing_expected_actor_fails_closed_before_auth(self):
        # No expected_actor -> the live boundary refuses to run at
        # all. This is a controlled BLOCKED result raised BEFORE the
        # device-code flow, so no network or auth operation starts.
        executor, transport, graph = _make_executor(expected_actor=None)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_CONFIGURATION_INVALID)
        # Nothing was sent: no device-code request, no poll, no /me.
        self.assertEqual(len(transport.request_calls), 0)
        self.assertEqual(len(transport.poll_calls), 0)
        self.assertEqual(len(graph.me_calls), 0)
        labels = list(result.evidence_labels)
        self.assertNotIn("actor_verification_skipped", labels)

    def test_successful_signin_with_actor_verification(self):
        expected = ExpectedActor(
            object_id=FAKE_USER_OBJECT_ID,
            user_principal_name=FAKE_USER_UPN,
        )
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_SUCCESS)
        # Evidence includes the safe labels.
        labels = list(result.evidence_labels)
        self.assertIn("live:INTERACTIVE_SIGNIN", labels)
        self.assertIn("scenario:SCN-AUTH-001", labels)
        self.assertIn("actor:test-user-01", labels)
        self.assertIn("expected_observable_endpoint:G01-006", labels)
        self.assertIn("authentication_started", labels)
        self.assertIn("authentication_completed", labels)
        self.assertIn("actor_verified", labels)
        self.assertIn("authenticated_object_id:{0}".format(FAKE_USER_OBJECT_ID), labels)
        # /me was called once with the token.
        self.assertEqual(len(graph.me_calls), 1)
        token_arg, url_arg = graph.me_calls[0]
        # The token is not echoed in the evidence.
        self.assertNotIn(token_arg, repr(result))
        self.assertNotIn(token_arg, repr(result.evidence_labels))
        # The request and poll were recorded.
        self.assertEqual(len(transport.request_calls), 1)
        self.assertEqual(len(transport.poll_calls), 1)

    def test_correlation_id_is_preserved(self):
        executor, transport, graph = _make_executor()
        plan, step, actor = build_signin_plan(execution_id="exec-xyz")
        result = executor.execute(step, actor, plan)
        labels = list(result.evidence_labels)
        self.assertIn("correlation:GA-SCENARIO-exec-xyz", labels)

    def test_expected_observable_endpoint_is_g01_006(self):
        executor, transport, graph = _make_executor()
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        labels = list(result.evidence_labels)
        self.assertIn("expected_observable_endpoint:G01-006", labels)

    def test_scenario_correlation_is_plan_side_only(self):
        # The marker is recorded but explicitly tagged as
        # "plan-side only"; it is NOT embedded into the actual
        # Microsoft sign-in event.
        executor, transport, graph = _make_executor()
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        labels = list(result.evidence_labels)
        self.assertIn("scenario_correlation:plan_correlation_only", labels)

    def test_device_code_prompt_is_not_in_execution_result(self):
        executor, transport, graph = _make_executor()
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        serialized = repr(result.to_dict())
        self.assertNotIn("FAKE-USER-CODE", serialized)
        self.assertNotIn("https://microsoft.com/devicelogin", serialized)


class EndToEndFailureTests(unittest.TestCase):
    def test_actor_mismatch_blocks(self):
        expected = ExpectedActor(
            object_id="00000000-0000-0000-0000-000000000099",
            user_principal_name="other@e.test",
        )
        executor, transport, graph = _make_executor(
            expected_actor=expected,
            me_object_id=FAKE_USER_OBJECT_ID,
            me_user_principal_name=FAKE_USER_UPN,
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, ACTOR_IDENTITY_MISMATCH)

    def test_graph_me_http_error(self):
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(
            expected_actor=expected,
            me_error=TokenTransportResponse(
                status=401,
                body={"error": "invalid_token"},
                is_error=True,
            ),
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, GRAPH_ME_VALIDATION_FAILED)

    def test_graph_me_transport_error(self):
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(
            expected_actor=expected,
            me_exception=OSError("network down"),
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, GRAPH_ME_VALIDATION_FAILED)

    def test_auth_declined(self):
        executor, transport, graph = _make_executor(
            poll_response=TokenTransportResponse(
                status=400,
                body={"error": "authorization_declined"},
                is_error=True,
            ),
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, AUTH_DECLINED)

    def test_auth_timeout_via_clock(self):
        fake_now = [0.0]

        def sleep_then_advance(s):
            fake_now[0] = 999.0

        def clock():
            return fake_now[0]

        executor, transport, graph = _make_executor(
            poll_response=TokenTransportResponse(
                status=400,
                body={"error": "authorization_pending"},
                is_error=True,
            ),
            sleep=sleep_then_advance,
            clock=clock,
            timeout_seconds=10.0,
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, AUTH_TIMEOUT)

    def test_auth_token_error(self):
        executor, transport, graph = _make_executor(
            poll_response=TokenTransportResponse(
                status=400,
                body={"error": "invalid_grant"},
                is_error=True,
            ),
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, AUTH_TOKEN_ERROR)

    def test_auth_device_code_error(self):
        executor, transport, graph = _make_executor(
            request_error=OSError("request broke"),
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, AUTH_DEVICE_CODE_ERROR)


class EndToEndSafetyTests(unittest.TestCase):
    def test_token_never_appears_in_result_repr(self):
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        rep = repr(result)
        # The fake token is "fake-access-token-DO-NOT-LEAK".
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", rep)
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", repr(result.evidence_labels))

    def test_authorization_never_appears_in_evidence(self):
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        labels = " ".join(result.evidence_labels)
        # 'Authorization' is a case-sensitive string; the live executor
        # must never embed the Authorization header.
        self.assertNotIn("Authorization", labels)
        # The bearer scheme must not appear.
        self.assertNotIn("Bearer ", labels)
        self.assertNotIn("bearer ", labels)

    def test_authorization_never_appears_in_result_to_dict(self):
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        encoded = repr(result.to_dict())
        self.assertNotIn("Authorization", encoded)
        self.assertNotIn("Bearer ", encoded)
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", encoded)

    def test_authorization_never_appears_in_failure_evidence(self):
        # Even on the failure path, the executor must not echo the
        # token in evidence.
        expected = ExpectedActor(
            object_id="00000000-0000-0000-0000-000000000099",
        )
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        labels = " ".join(result.evidence_labels)
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", labels)
        self.assertNotIn("Authorization", labels)

    def test_evidence_contains_no_token(self):
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        labels = " ".join(result.evidence_labels)
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", labels)
        self.assertNotIn("Authorization", labels)
        self.assertNotIn("Bearer ", labels)

    def test_no_persistence_to_disk(self):
        # The live executor never accepts a file path. This test
        # documents that the dataclass has no "persist_to" field and
        # that the execute() method does not write any file.
        import dataclasses
        fields = {f.name for f in dataclasses.fields(LiveScenarioExecutor)}
        self.assertNotIn("persist_to", fields)
        self.assertNotIn("token_file", fields)
        self.assertNotIn("cache_file", fields)
        # And no method called write/save is exposed.
        self.assertFalse(hasattr(LiveScenarioExecutor, "save_token"))
        self.assertFalse(hasattr(LiveScenarioExecutor, "write_token"))


class EndToEndNetworkSafetyTests(unittest.TestCase):
    def test_no_real_network_call(self):
        # Patch every transport seam and prove they were not called.
        import socket
        from unittest.mock import patch
        executor, transport, graph = _make_executor()
        plan, step, actor = build_signin_plan()
        with patch("urllib.request.urlopen") as mocked_urlopen, patch(
            "socket.socket"
        ) as mocked_socket:
            executor.execute(step, actor, plan)
            mocked_urlopen.assert_not_called()
            mocked_socket.assert_not_called()
        # The fakes were used instead.
        self.assertEqual(len(transport.request_calls), 1)
        self.assertEqual(len(transport.poll_calls), 1)

    def test_no_real_network_call_on_failure(self):
        import socket
        from unittest.mock import patch
        executor, transport, graph = _make_executor(
            poll_response=TokenTransportResponse(
                status=400,
                body={"error": "authorization_declined"},
                is_error=True,
            ),
        )
        plan, step, actor = build_signin_plan()
        with patch("urllib.request.urlopen") as mocked_urlopen, patch(
            "socket.socket"
        ) as mocked_socket:
            executor.execute(step, actor, plan)
            mocked_urlopen.assert_not_called()
            mocked_socket.assert_not_called()


if __name__ == "__main__":
    unittest.main()
