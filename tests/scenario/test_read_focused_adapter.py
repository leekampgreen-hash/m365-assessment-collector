"""Offline security tests for the allowlisted Graph read adapter."""
from __future__ import annotations

import unittest

from agents.scenario.adapters import (
    AuthorizationContext,
    OperationType,
    PolicyChecker,
    ReadFocusedAdapter,
)
from agents.scenario.auth import ScenarioActorMetadata, ScenarioAuthenticationContext
from agents.scenario.auth.transports import TokenTransportResponse


class FakeReadTransport:
    """Fixed-operation fake: tests cannot invoke arbitrary Graph URLs."""

    def __init__(self) -> None:
        self.calls = []
        self.users_response = TokenTransportResponse(
            status=200,
            body={"value": [{"id": "user-1"}, {"id": "user-2"}]},
        )
        self.groups_response = TokenTransportResponse(
            status=200,
            body={"value": [{"id": "group-1"}]},
        )

    def get_users(self, access_token: str) -> TokenTransportResponse:
        self.calls.append(("GET /users", access_token))
        return self.users_response

    def get_groups(self, access_token: str) -> TokenTransportResponse:
        self.calls.append(("GET /groups", access_token))
        return self.groups_response


class ReadFocusedAdapterTests(unittest.TestCase):
    token = "test-access-token-must-not-leak"

    def setUp(self) -> None:
        self.transport = FakeReadTransport()
        self.authentication = ScenarioAuthenticationContext(
            authenticated=True,
            tenant_id="tenant-id",
            client_id="scenario-client-id",
            correlation_id="corr-fixture",
            actor=ScenarioActorMetadata(object_id="verified-actor-id"),
            expires_at_epoch=4_000_000_000,
        )
        self.authorization = AuthorizationContext(
            authorized_operations=frozenset((OperationType.USER_LIST, OperationType.GROUP_LIST)),
        )
        self.adapter = ReadFocusedAdapter(
            self.transport,
            PolicyChecker((OperationType.USER_LIST.value, OperationType.GROUP_LIST.value)),
        )

    def test_successful_user_read_flow_is_allowlisted_and_sanitized(self) -> None:
        result = self.adapter.read_users(self.authentication, self.authorization, "corr-user", _access_token=self.token)

        self.assertEqual(self.transport.calls, [("GET /users", self.token)])
        self.assertEqual(result.operation, "USER_LIST")
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.object_count, 2)
        self.assertEqual(result.correlation_id, "corr-user")

    def test_successful_group_read_flow_is_allowlisted_and_sanitized(self) -> None:
        result = self.adapter.read_groups(self.authentication, self.authorization, "corr-group", _access_token=self.token)

        self.assertEqual(self.transport.calls, [("GET /groups", self.token)])
        self.assertEqual(result.operation, "GROUP_LIST")
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.object_count, 1)
        self.assertEqual(result.correlation_id, "corr-group")

    def test_unsupported_endpoint_is_rejected_without_transport_call(self) -> None:
        with self.assertRaisesRegex(ValueError, "not registered"):
            self.adapter._execute("GET /applications", self.authentication, self.authorization, "corr", self.token)

        self.assertEqual(self.transport.calls, [])

    def test_missing_policy_approval_is_rejected_without_transport_call(self) -> None:
        adapter = ReadFocusedAdapter(self.transport, PolicyChecker())

        with self.assertRaisesRegex(ValueError, "explicit ALLOW"):
            adapter.read_users(self.authentication, self.authorization, "corr", _access_token=self.token)

        self.assertEqual(self.transport.calls, [])

    def test_missing_auth_context_is_rejected_without_transport_call(self) -> None:
        with self.assertRaisesRegex(ValueError, "authenticated Scenario Agent identity"):
            self.adapter.read_users(None, self.authorization, "corr")

        self.assertEqual(self.transport.calls, [])

    def test_token_and_raw_response_are_not_retained_in_metadata(self) -> None:
        result = self.adapter.read_users(self.authentication, self.authorization, "corr-safe", _access_token=self.token)
        result_values = vars(result).values()

        self.assertNotIn(self.token, result_values)
        self.assertNotIn("user-1", result_values)
        self.assertNotIn("user-2", result_values)
        self.assertNotIn("access_token", vars(result))
        self.assertNotIn("body", vars(result))
        self.assertNotIn("headers", vars(result))


if __name__ == "__main__":
    unittest.main()
