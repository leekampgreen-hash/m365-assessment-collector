"""Negative tests for the live scope pinning (G08-D1F, Finding 1).

The G08-D1 acceptance contract requires ZERO permission expansion:
every allow_live=True construction/execution path must request
exactly ``("User.Read",)``. These tests prove the contract fails
closed:

* exactly ``User.Read`` is accepted,
* empty / extra / duplicate / variant / arbitrary scopes are
  rejected at the config boundary (``ValueError``),
* a config mutated after construction is re-validated at the live
  execution boundary and produces a controlled BLOCKED result with
  ``LIVE_CONFIGURATION_INVALID`` BEFORE any network or auth
  operation can start.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from agents.scenario import (
    LIVE_CONFIGURATION_INVALID,
    LIVE_REQUIRED_DELEGATED_SCOPES,
    LiveScenarioConfig,
    LiveScenarioExecutor,
)
from agents.scenario.auth.transports import (
    FakeDeviceCodeTransport,
    FakeGraphTransport,
)
from agents.scenario.models import STATUS_BLOCKED

from tests.scenario.live._helpers import (
    EXPECTED_TEST_ACTOR,
    FAKE_CLIENT_ID,
    FAKE_TENANT,
    FAKE_USER_OBJECT_ID,
    build_signin_plan,
)


def _make_executor(config):
    transport = FakeDeviceCodeTransport()
    # The /me fake matches the expected test actor so that scope
    # tests isolate the scope behaviour from actor verification.
    graph = FakeGraphTransport(me_object_id=FAKE_USER_OBJECT_ID)
    executor = LiveScenarioExecutor(
        allow_live=True,
        config=config,
        device_code_request_transport=transport.request,
        device_code_poll_transport=transport.poll,
        graph_me_transport=graph.request,
        sleep=lambda s: None,
        clock=lambda: 0.0,
    )
    return executor, transport, graph


def _valid_config():
    return LiveScenarioConfig(
        scenario_app_client_id=FAKE_CLIENT_ID,
        scenario_app_tenant_id=FAKE_TENANT,
        expected_actor=EXPECTED_TEST_ACTOR,
    )


class ExactScopeAcceptedTests(unittest.TestCase):
    """1. exact User.Read accepted."""

    def test_canonical_tuple_accepted(self):
        config = LiveScenarioConfig(
            scenario_app_client_id=FAKE_CLIENT_ID,
            scenario_app_tenant_id=FAKE_TENANT,
            delegated_scopes=("User.Read",),
            expected_actor=EXPECTED_TEST_ACTOR,
        )
        self.assertEqual(config.delegated_scopes, ("User.Read",))
        self.assertIsInstance(config.delegated_scopes, tuple)

    def test_single_entry_list_accepted_and_stored_immutable(self):
        # A list containing exactly User.Read is an equivalent
        # representation; it is normalized to the immutable tuple.
        config = LiveScenarioConfig(
            scenario_app_client_id=FAKE_CLIENT_ID,
            scenario_app_tenant_id=FAKE_TENANT,
            delegated_scopes=["User.Read"],
            expected_actor=EXPECTED_TEST_ACTOR,
        )
        self.assertEqual(config.delegated_scopes, LIVE_REQUIRED_DELEGATED_SCOPES)
        self.assertIsInstance(config.delegated_scopes, tuple)

    def test_exact_user_read_executes_end_to_end(self):
        executor, transport, graph = _make_executor(_valid_config())
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, "SUCCESS")
        # The wire form requests exactly one scope.
        self.assertEqual(len(transport.request_calls), 1)
        self.assertEqual(transport.request_calls[0].get("scope"), "User.Read")
        # The declared permission union is exactly User.Read.
        self.assertEqual(executor.declared_permissions, ("User.Read",))


class EmptyScopeRejectedTests(unittest.TestCase):
    """2. empty scope rejected."""

    def test_empty_tuple_rejected_at_config_boundary(self):
        with self.assertRaises(ValueError):
            LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                delegated_scopes=(),
                expected_actor=EXPECTED_TEST_ACTOR,
            )

    def test_empty_list_rejected_at_config_boundary(self):
        with self.assertRaises(ValueError):
            LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                delegated_scopes=[],
                expected_actor=EXPECTED_TEST_ACTOR,
            )

    def test_blank_string_entry_rejected_at_config_boundary(self):
        for bad in (("",), ("User.Read", "")):
            with self.assertRaises(ValueError):
                LiveScenarioConfig(
                    scenario_app_client_id=FAKE_CLIENT_ID,
                    scenario_app_tenant_id=FAKE_TENANT,
                    delegated_scopes=bad,
                    expected_actor=EXPECTED_TEST_ACTOR,
                )

    def test_empty_scope_mutated_after_construction_blocked_before_network(self):
        config = _valid_config()
        config.delegated_scopes = ()
        executor, transport, graph = _make_executor(config)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_CONFIGURATION_INVALID)
        self.assertEqual(len(transport.request_calls), 0)
        self.assertEqual(len(transport.poll_calls), 0)
        self.assertEqual(len(graph.me_calls), 0)


class ExtraScopeRejectedTests(unittest.TestCase):
    """3 + 4. User.Read combined with a broader scope is rejected."""

    def test_user_read_plus_mail_send_rejected_at_config_boundary(self):
        with self.assertRaises(ValueError):
            LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                delegated_scopes=("User.Read", "Mail.Send"),
                expected_actor=EXPECTED_TEST_ACTOR,
            )

    def test_mail_send_only_rejected_at_config_boundary(self):
        with self.assertRaises(ValueError):
            LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                delegated_scopes=("Mail.Send",),
                expected_actor=EXPECTED_TEST_ACTOR,
            )

    def test_user_read_plus_calendars_readwrite_rejected_at_config_boundary(self):
        with self.assertRaises(ValueError):
            LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                delegated_scopes=("User.Read", "Calendars.ReadWrite"),
                expected_actor=EXPECTED_TEST_ACTOR,
            )

    def test_calendars_readwrite_only_rejected_at_config_boundary(self):
        with self.assertRaises(ValueError):
            LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                delegated_scopes=("Calendars.ReadWrite",),
                expected_actor=EXPECTED_TEST_ACTOR,
            )

    def test_extra_broader_scope_blocked_before_network_when_mutated(self):
        for bad in (("User.Read", "Mail.Send"), ("User.Read", "Calendars.ReadWrite")):
            config = _valid_config()
            config.delegated_scopes = bad
            executor, transport, graph = _make_executor(config)
            plan, step, actor = build_signin_plan()
            result = executor.execute(step, actor, plan)
            self.assertEqual(result.status, STATUS_BLOCKED)
            self.assertEqual(result.error_code, LIVE_CONFIGURATION_INVALID)
            self.assertEqual(len(transport.request_calls), 0)
            self.assertEqual(len(transport.poll_calls), 0)
            self.assertEqual(len(graph.me_calls), 0)


class ArbitraryOrVariantScopeRejectedTests(unittest.TestCase):
    """5. arbitrary / variant / duplicate scope lists are rejected."""

    def test_arbitrary_scopes_rejected_at_config_boundary(self):
        for bad in (
            ("Files.ReadWrite",),
            ("ChannelMessage.Send",),
            ("Group.ReadWrite.All",),
            ("https://graph.microsoft.com/.default",),
            ("*",),
            ("User.Read;Mail.Send",),
        ):
            with self.assertRaises(ValueError):
                LiveScenarioConfig(
                    scenario_app_client_id=FAKE_CLIENT_ID,
                    scenario_app_tenant_id=FAKE_TENANT,
                    delegated_scopes=bad,
                    expected_actor=EXPECTED_TEST_ACTOR,
                )

    def test_variant_casing_not_normalized_into_acceptance(self):
        # Variants must fail closed; no case folding or stripping.
        for bad in (
            ("user.read",),
            ("USER.READ",),
            ("User.read",),
            ("User.Read ",),
            (" User.Read",),
            ("User.Read\t",),
        ):
            with self.assertRaises(ValueError):
                LiveScenarioConfig(
                    scenario_app_client_id=FAKE_CLIENT_ID,
                    scenario_app_tenant_id=FAKE_TENANT,
                    delegated_scopes=bad,
                    expected_actor=EXPECTED_TEST_ACTOR,
                )

    def test_duplicate_user_read_not_silently_normalized(self):
        with self.assertRaises(ValueError):
            LiveScenarioConfig(
                scenario_app_client_id=FAKE_CLIENT_ID,
                scenario_app_tenant_id=FAKE_TENANT,
                delegated_scopes=("User.Read", "User.Read"),
                expected_actor=EXPECTED_TEST_ACTOR,
            )

    def test_non_sequence_input_rejected(self):
        for bad in ("User.Read", None, {"User.Read"}):
            with self.assertRaises((ValueError, TypeError)):
                LiveScenarioConfig(
                    scenario_app_client_id=FAKE_CLIENT_ID,
                    scenario_app_tenant_id=FAKE_TENANT,
                    delegated_scopes=bad,
                    expected_actor=EXPECTED_TEST_ACTOR,
                )

    def test_arbitrary_scope_blocked_before_network_when_mutated(self):
        config = _valid_config()
        config.delegated_scopes = ("user.read",)
        executor, transport, graph = _make_executor(config)
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, LIVE_CONFIGURATION_INVALID)
        self.assertEqual(len(transport.request_calls), 0)
        self.assertEqual(len(transport.poll_calls), 0)
        self.assertEqual(len(graph.me_calls), 0)


class RejectionBeforeNetworkTests(unittest.TestCase):
    """6. rejection occurs before network/auth starts."""

    def test_invalid_scope_never_touches_socket_or_urlopen(self):
        config = _valid_config()
        config.delegated_scopes = ("User.Read", "Mail.Send")
        executor, transport, graph = _make_executor(config)
        plan, step, actor = build_signin_plan()
        with patch("urllib.request.urlopen") as mocked_urlopen, patch(
            "socket.socket"
        ) as mocked_socket:
            result = executor.execute(step, actor, plan)
            mocked_urlopen.assert_not_called()
            mocked_socket.assert_not_called()
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(LIVE_CONFIGURATION_INVALID, result.error_code)
        self.assertEqual(transport.request_calls, [])
        self.assertEqual(transport.poll_calls, [])

    def test_disabled_executor_still_wins_over_config_validation_order(self):
        # The allow_live=False gate short-circuits before the config
        # pre-flight; nothing about the hardened contract changes the
        # default-off behaviour.
        executor = LiveScenarioExecutor()  # allow_live defaults False
        plan, step, actor = build_signin_plan()
        result = executor.execute(step, actor, plan)
        self.assertEqual(result.status, STATUS_BLOCKED)
        self.assertEqual(result.error_code, "LIVE_EXECUTION_DISABLED")


if __name__ == "__main__":
    unittest.main()
