"""Offline tests for the canonical Scenario delegated auth provider."""
from __future__ import annotations

import dataclasses
import unittest
from unittest.mock import patch

from agents.scenario.auth import (
    DelegatedScenarioAuthenticationProvider,
    ExpectedActor,
    FakeDeviceCodeTransport,
    FakeGraphTransport,
    ScenarioIdentityConfig,
    TokenTransportResponse,
)
from agents.scenario.auth.device_code import DeviceCodeError, DeviceCodeToken
from agents.scenario.auth.identity import GraphMeError


def _provider(*, scopes=("User.Read",), expected=None, device=None, graph=None):
    device = device or FakeDeviceCodeTransport()
    graph = graph or FakeGraphTransport(me_object_id="actor-id", me_user_principal_name="scenario@example.test")
    provider = DelegatedScenarioAuthenticationProvider(
        identity_config=ScenarioIdentityConfig(tenant_id="tenant-id", client_id="scenario-client-id"),
        expected_actor=expected or ExpectedActor(object_id="actor-id", user_principal_name="scenario@example.test"),
        correlation_id="corr-123",
        delegated_scopes=scopes,
        device_code_request_transport=device.request,
        device_code_poll_transport=device.poll,
        graph_me_transport=graph.request,
        sleep=lambda _: None,
        clock=lambda: 0.0,
        epoch_clock=lambda: 1000.0,
    )
    return provider, device, graph


class DelegatedProviderTests(unittest.TestCase):
    def test_device_code_success_creates_safe_verified_context(self):
        provider, device, graph = _provider()
        result = provider.authenticate()
        self.assertTrue(result.context.is_valid(clock=lambda: 0.0))
        self.assertEqual(result.context.actor.object_id, "actor-id")
        self.assertEqual(result.context.expires_at_epoch, 4600)
        self.assertEqual(len(device.request_calls), 1)
        self.assertEqual(len(device.poll_calls), 1)
        self.assertEqual(len(graph.me_calls), 1)

    def test_provider_clears_token_before_return(self):
        provider, _, _ = _provider()
        token = DeviceCodeToken(
            access_token="fake-access-token-DO-NOT-LEAK",
            expires_in_seconds=3600,
            token_type="Bearer",
            scope="User.Read",
        )
        with patch("agents.scenario.auth.delegated.DeviceCodeFlow") as flow:
            flow.return_value.run.return_value = token
            provider.authenticate()

        self.assertEqual(token.access_token, "")

    def test_device_code_timeout_is_propagated(self):
        device = FakeDeviceCodeTransport(poll_response=TokenTransportResponse(400, {"error": "expired_token"}, True))
        provider, _, _ = _provider(device=device)
        with self.assertRaises(DeviceCodeError) as raised:
            provider.authenticate()
        self.assertEqual(raised.exception.classification, "AUTH_TIMEOUT")

    def test_actor_mismatch_is_blocked_before_context_exists(self):
        provider, _, _ = _provider(expected=ExpectedActor(object_id="other-id"))
        with self.assertRaises(GraphMeError) as raised:
            provider.authenticate()
        self.assertEqual(raised.exception.classification, "ACTOR_IDENTITY_MISMATCH")

    def test_missing_or_unapproved_delegated_permission_is_blocked(self):
        with self.assertRaises(ValueError):
            _provider(scopes=())
        with self.assertRaises(ValueError):
            _provider(scopes=("User.Read", "Directory.Read.All"))
        with self.assertRaises(ValueError):
            _provider(scopes=("User.ReadWrite.All",))

    def test_auth_result_contains_no_token(self):
        provider, _, _ = _provider()
        result = provider.authenticate()
        rendered = repr(result) + repr(result.context) + repr(dataclasses.asdict(result.context))
        self.assertNotIn("fake-access-token-DO-NOT-LEAK", rendered)
        self.assertNotIn("Authorization", rendered)
        self.assertNotIn("refresh_token", rendered)

    def test_provider_has_no_collector_or_client_secret_configuration(self):
        fields = {field.name for field in dataclasses.fields(ScenarioIdentityConfig)}
        self.assertNotIn("client_secret", fields)
        self.assertNotIn("collector", " ".join(fields).lower())
        self.assertNotIn("collectors", DelegatedScenarioAuthenticationProvider.__module__)


if __name__ == "__main__":
    unittest.main()
