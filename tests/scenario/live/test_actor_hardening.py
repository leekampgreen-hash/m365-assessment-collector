"""Negative tests for mandatory live actor verification (G08-D1F, Finding 2).

For every ``allow_live=True`` INTERACTIVE_SIGNIN execution the
expected actor is mandatory and ``GET /me`` verification always runs.
These tests prove:

* a missing / empty expected actor fails closed with
  ``LIVE_CONFIGURATION_INVALID`` BEFORE authentication or any
  network operation starts,
* an expected actor with neither an object ID nor a UPN is rejected,
  including whitespace-only values,
* object-ID-only and UPN-only actors are accepted,
* a matching ``/me`` succeeds, a mismatching ``/me`` yields
  ``ACTOR_IDENTITY_MISMATCH``, and malformed ``/me`` data fails
  closed,
* there is no successful live path that skips actor verification
  (``actor_verification_skipped`` no longer exists anywhere in the
  live executor).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from agents.scenario import (
    ACTOR_IDENTITY_MISMATCH,
    GRAPH_ME_VALIDATION_FAILED,
    LIVE_CONFIGURATION_INVALID,
    LiveScenarioConfig,
    LiveScenarioExecutor,
)
from agents.scenario.auth import (
    ExpectedActor,
    GraphMeValidator,
    TokenTransportResponse,
)
from agents.scenario.auth.transports import (
    FakeDeviceCodeTransport,
    FakeGraphTransport,
)
from agents.scenario.models import STATUS_BLOCKED, STATUS_FAILED, STATUS_SUCCESS

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
    me_object_id=FAKE_USER_OBJECT_ID,
    me_user_principal_name=FAKE_USER_UPN,
    graph_transport=None,
):
    transport = FakeDeviceCodeTransport()
    if graph_transport is None:
        graph = FakeGraphTransport(
            me_object_id=me_object_id,
            me_user_principal_name=me_user_principal_name,
        )
        graph_transport = graph.request
    else:
        # A raw callable was supplied; keep a call-counting shim.
        class _Shim:
            def __init__(self):
                self.me_calls = []

            def record(self, token, url):
                self.me_calls.append((token, url))
                return graph_transport(token, url)

        shim = _Shim()

        def counting(token, url):
            return shim.record(token, url)

        graph = shim
        graph_transport = counting
    config = LiveScenarioConfig(
        scenario_app_client_id=FAKE_CLIENT_ID,
        scenario_app_tenant_id=FAKE_TENANT,
        expected_actor=expected_actor,
    )
    executor = LiveScenarioExecutor(
        allow_live=True,
        config=config,
        device_code_request_transport=transport.request,
        device_code_poll_transport=transport.poll,
        graph_me_transport=graph_transport,
        sleep=lambda s: None,
        clock=lambda: 0.0,
    )
    return executor, transport, graph


class MissingActorRejectedTests(unittest.TestCase):
    """7 + 15. missing expected actor rejected before auth/network."""

    def test_missing_expected_actor_blocked(self):
        executor, transport, graph = _make_executor(expected_actor=None)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_CONFIGURATION_INVALID)
        self.assertIn("live:refused", result.evidence_labels)

    def test_rejection_occurs_before_any_network_or_auth_operation(self):
        executor, transport, graph = _make_executor(expected_actor=None)
        plan, step, actor = build_signin_plan()
        with patch("urllib.request.urlopen") as mocked_urlopen, patch(
            "socket.socket"
        ) as mocked_socket:
            executor.execute(step, actor, plan)
            mocked_urlopen.assert_not_called()
            mocked_socket.assert_not_called()
        # The device-code request / poll / /me never happened.
        self.assertEqual(transport.request_calls, [])
        self.assertEqual(transport.poll_calls, [])
        self.assertEqual(graph.me_calls, [])

    def test_blocked_result_carries_no_token_evidence(self):
        executor, transport, graph = _make_executor(expected_actor=None)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        encoded = repr(result) + repr(result.to_dict())
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", encoded)


class EmptyActorRejectedTests(unittest.TestCase):
    """8. expected actor with neither object ID nor UPN rejected."""

    def test_fully_empty_expected_actor_blocked(self):
        executor, transport, graph = _make_executor(expected_actor=ExpectedActor())
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_CONFIGURATION_INVALID)
        self.assertEqual(transport.request_calls, [])
        self.assertEqual(graph.me_calls, [])

    def test_whitespace_only_fields_do_not_count_as_identity(self):
        for actor in (
            ExpectedActor(object_id="   "),
            ExpectedActor(user_principal_name="   "),
            ExpectedActor(object_id="\t", user_principal_name=" \n"),
        ):
            executor, transport, graph = _make_executor(expected_actor=actor)
            plan, step, _ = build_signin_plan()
            result = executor.execute(step, actor, plan)
            self.assertEqual(result.status, STATUS_BLOCKED)
            self.assertEqual(result.error_code, LIVE_CONFIGURATION_INVALID)
            self.assertEqual(transport.request_calls, [])
            self.assertEqual(graph.me_calls, [])


class PartialActorAcceptedTests(unittest.TestCase):
    """9 + 10. one verifiable field is enough."""

    def test_object_id_only_accepted(self):
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_SUCCESS)
        labels = list(result.evidence_labels)
        self.assertIn("actor_verified", labels)
        self.assertIn(
            "authenticated_object_id:{0}".format(FAKE_USER_OBJECT_ID), labels
        )
        self.assertEqual(len(graph.me_calls), 1)

    def test_upn_only_accepted(self):
        expected = ExpectedActor(user_principal_name=FAKE_USER_UPN)
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_SUCCESS)
        labels = list(result.evidence_labels)
        self.assertIn("actor_verified", labels)
        self.assertEqual(len(graph.me_calls), 1)


class MeVerificationTests(unittest.TestCase):
    """11 + 12 + 13. matching / malformed / mismatching /me."""

    def test_matching_me_succeeds(self):
        expected = ExpectedActor(
            object_id=FAKE_USER_OBJECT_ID,
            user_principal_name=FAKE_USER_UPN,
        )
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertIn("actor_verified", list(result.evidence_labels))

    def test_second_authenticated_account_is_mismatch(self):
        # Another account completed sign-in: /me returns a different
        # identity than the expected actor.
        other_oid = "00000000-0000-0000-0000-000000000099"
        other_upn = "other-user@example.test"
        expected = ExpectedActor(
            object_id=FAKE_USER_OBJECT_ID,
            user_principal_name=FAKE_USER_UPN,
        )
        executor, transport, graph = _make_executor(
            expected_actor=expected,
            me_object_id=other_oid,
            me_user_principal_name=other_upn,
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, ACTOR_IDENTITY_MISMATCH)

    def test_partial_mismatch_still_fails(self):
        # Object id matches but UPN does not (both supplied): both
        # must match (defence in depth).
        expected = ExpectedActor(
            object_id=FAKE_USER_OBJECT_ID,
            user_principal_name="expected-user@example.test",
        )
        executor, transport, graph = _make_executor(expected_actor=expected)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, ACTOR_IDENTITY_MISMATCH)

    def test_malformed_me_body_missing_id_fails_closed(self):
        def malformed_me(token, url):
            return TokenTransportResponse(
                status=200,
                body={"userPrincipalName": FAKE_USER_UPN},  # missing "id"
                is_error=False,
            )

        executor, transport, graph = _make_executor(graph_transport=malformed_me)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, GRAPH_ME_VALIDATION_FAILED)

    def test_non_mapping_me_body_fails_closed(self):
        def non_mapping_me(token, url):
            return TokenTransportResponse(status=200, body=None, is_error=False)

        executor, transport, graph = _make_executor(graph_transport=non_mapping_me)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.error_code, GRAPH_ME_VALIDATION_FAILED)

    def test_mismatch_does_not_leak_token_in_failure_evidence(self):
        other_oid = "00000000-0000-0000-0000-000000000099"
        expected = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)
        executor, transport, graph = _make_executor(
            expected_actor=expected,
            me_object_id=other_oid,
        )
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.error_code, ACTOR_IDENTITY_MISMATCH)
        joined = " ".join(result.evidence_labels)
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", joined)


class CannotSkipVerificationTests(unittest.TestCase):
    """14. actor validation cannot be skipped."""

    def test_no_successful_result_without_me_call(self):
        # Drive several successful configurations; every success must
        # have performed exactly one /me call and carry actor_verified.
        configs = [
            ExpectedActor(object_id=FAKE_USER_OBJECT_ID),
            ExpectedActor(user_principal_name=FAKE_USER_UPN),
            ExpectedActor(
                object_id=FAKE_USER_OBJECT_ID,
                user_principal_name=FAKE_USER_UPN,
            ),
        ]
        for expected in configs:
            executor, transport, graph = _make_executor(expected_actor=expected)
            plan, step, actor = build_signin_plan()
            result = executor.execute(step, actor, plan)
            self.assertEqual(result.status, STATUS_SUCCESS)
            self.assertGreaterEqual(len(graph.me_calls), 1)
            labels = list(result.evidence_labels)
            self.assertIn("actor_verified", labels)
            self.assertNotIn("actor_verification_skipped", labels)

    def test_skip_label_removed_from_live_executor_source(self):
        # Structural proof: the skip path no longer exists in the
        # live executor module.
        from pathlib import Path

        from agents.scenario import live_executor

        source = Path(live_executor.__file__).read_text(encoding="utf-8")
        self.assertNotIn("actor_verification_skipped", source)

    def test_validator_refuses_empty_expected_actor(self):
        with self.assertRaises(ValueError):
            GraphMeValidator(
                transport=FakeGraphTransport().request,
                expected=ExpectedActor(),
            )

    def test_validator_refuses_none_expected_actor(self):
        with self.assertRaises(ValueError):
            GraphMeValidator(
                transport=FakeGraphTransport().request,
                expected=None,
            )


if __name__ == "__main__":
    unittest.main()
