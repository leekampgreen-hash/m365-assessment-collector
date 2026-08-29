"""Offline tests for the device-code flow.

These tests drive :class:`DeviceCodeFlow` exclusively through fake
transports. They prove:

* A successful device-code flow returns a safe prompt and a token
  whose ``__repr__`` is redacted.
* A pending flow correctly waits (``authorization_pending``) and
  eventually completes.
* Auth-declined / expired-token / invalid-grant are classified
  deterministically.
* The flow never accepts a client secret, username, or password.
* The flow performs no real network I/O; the only outbound payload
  is what the fake transport records.
"""
from __future__ import annotations

import unittest

from agents.scenario.auth import (
    DeviceCodeError,
    DeviceCodeFlow,
    DeviceCodeToken,
    TokenTransportResponse,
)
from agents.scenario.auth.transports import FakeDeviceCodeTransport


def _make_flow(transport, *, timeout=300.0, sleep=None, clock=None, prompt_callback=None):
    sleep = sleep or (lambda s: None)
    clock = clock or (lambda: 0.0)
    return DeviceCodeFlow(
        client_id="cid",
        tenant_id="tid",
        scopes=("User.Read",),
        request_transport=transport.request,
        poll_transport=transport.poll,
        prompt_callback=prompt_callback,
        sleep=sleep,
        timeout_seconds=timeout,
        clock=clock,
    )


class DeviceCodeSuccessTests(unittest.TestCase):
    def test_successful_flow_delivers_prompt_and_returns_token(self):
        transport = FakeDeviceCodeTransport()
        prompts = []
        flow = _make_flow(transport, prompt_callback=prompts.append)
        token = flow.run()
        self.assertEqual(len(prompts), 1)
        prompt = prompts[0]
        self.assertEqual(prompt.user_code, "FAKE-USER-CODE")
        self.assertTrue(prompt.verification_uri.startswith("https://"))
        self.assertGreater(prompt.expires_in_seconds, 0)
        self.assertGreater(prompt.interval_seconds, 0)
        self.assertIsInstance(token, DeviceCodeToken)
        # The token is a non-empty string and the flow's repr does
        # NOT echo the value.
        self.assertTrue(token.access_token)
        self.assertNotIn(token.access_token, repr(token))
        self.assertNotIn(token.access_token, repr(prompt))

    def test_prompt_is_safe(self):
        # The prompt is what the operator sees; it must never contain
        # the access token, refresh token, or device_code.
        transport = FakeDeviceCodeTransport()
        prompts = []
        flow = _make_flow(transport, prompt_callback=prompts.append)
        token = flow.run()
        prompt = prompts[0]
        # access_token lives on the token, not the prompt. The prompt
        # only carries user_code / verification_uri / expires / etc.
        for attr in ("user_code", "verification_uri", "expires_in_seconds",
                     "interval_seconds", "message"):
            self.assertTrue(hasattr(prompt, attr))
        # Prompt stringification never includes the token or challenge data.
        self.assertNotIn("access_token", repr(prompt))
        self.assertNotIn(token.access_token, repr(prompt))
        self.assertNotIn("device_code", repr(prompt))
        self.assertNotIn(prompt.user_code, repr(prompt))
        self.assertNotIn(prompt.verification_uri, repr(prompt))

    def test_request_form_includes_client_id_and_scope_only(self):
        transport = FakeDeviceCodeTransport()
        flow = _make_flow(transport)
        flow.run()
        self.assertEqual(len(transport.request_calls), 1)
        form = transport.request_calls[0]
        self.assertEqual(form.get("client_id"), "cid")
        self.assertEqual(form.get("scope"), "User.Read")
        # No client secret, no password, no username.
        for forbidden in (
            "client_secret",
            "password",
            "username",
            "token",
            "access_token",
            "refresh_token",
        ):
            self.assertNotIn(forbidden, form)

    def test_poll_form_uses_device_code_grant(self):
        transport = FakeDeviceCodeTransport()
        flow = _make_flow(transport)
        flow.run()
        self.assertEqual(len(transport.poll_calls), 1)
        form = transport.poll_calls[0]
        self.assertEqual(
            form.get("grant_type"),
            "urn:ietf:params:oauth:grant-type:device_code",
        )
        self.assertEqual(form.get("client_id"), "cid")
        self.assertIn("device_code", form)

    def test_token_repr_is_redacted(self):
        transport = FakeDeviceCodeTransport()
        flow = _make_flow(transport)
        token = flow.run()
        rep = repr(token)
        self.assertIn("<redacted>", rep)
        self.assertNotIn(token.access_token, rep)


class DeviceCodePendingTests(unittest.TestCase):
    def test_pending_then_success(self):
        from urllib.error import HTTPError
        # The fake always returns a successful token. To simulate
        # "pending then success" we script the poll queue.
        transport = FakeDeviceCodeTransport()
        # Set the default to a pending body so the queue drives the
        # multi-step behaviour.
        transport.poll_response = TokenTransportResponse(
            status=400,
            body={"error": "authorization_pending"},
            is_error=True,
        )
        # Two pendings, then a success.
        success = TokenTransportResponse(
            status=200,
            body={
                "access_token": "TOKEN-VALUE",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "User.Read",
            },
            is_error=False,
        )
        pending = TokenTransportResponse(
            status=400,
            body={"error": "authorization_pending"},
            is_error=True,
        )
        transport._poll_queue = [pending, pending, success]
        sleep_calls = []
        flow = _make_flow(transport, sleep=lambda s: sleep_calls.append(s))
        token = flow.run()
        self.assertEqual(len(sleep_calls), 2)
        self.assertEqual(token.access_token, "TOKEN-VALUE")
        self.assertEqual(len(transport.poll_calls), 3)


class DeviceCodeFailureTests(unittest.TestCase):
    def test_declined(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=400,
            body={"error": "authorization_declined"},
            is_error=True,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_DECLINED")

    def test_expired_token(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=400,
            body={"error": "expired_token"},
            is_error=True,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TIMEOUT")

    def test_invalid_grant(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=400,
            body={"error": "invalid_grant"},
            is_error=True,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TOKEN_ERROR")

    def test_invalid_client(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=400,
            body={"error": "invalid_client"},
            is_error=True,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TOKEN_ERROR")

    def test_flow_timeout_via_clock(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=400,
            body={"error": "authorization_pending"},
            is_error=True,
        )
        # A clock that always reports past the deadline.
        fake_now = [0.0]

        def clock():
            return fake_now[0]

        def sleep_then_advance(s):
            fake_now[0] = 999.0

        flow = DeviceCodeFlow(
            client_id="cid",
            tenant_id="tid",
            scopes=("User.Read",),
            request_transport=transport.request,
            poll_transport=transport.poll,
            sleep=sleep_then_advance,
            timeout_seconds=10.0,
            clock=clock,
        )
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TIMEOUT")

    def test_request_error_classified(self):
        transport = FakeDeviceCodeTransport()
        transport.queue_request_error(OSError("transport broke"))
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_DEVICE_CODE_ERROR")

    def test_request_http_error(self):
        transport = FakeDeviceCodeTransport()
        transport.request_response = TokenTransportResponse(
            status=500,
            body={"error": "server_error"},
            is_error=True,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_DEVICE_CODE_ERROR")

    def test_request_malformed_body(self):
        transport = FakeDeviceCodeTransport()
        transport.request_response = TokenTransportResponse(
            status=200,
            body={"user_code": "OK"},  # missing verification_uri etc
            is_error=False,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_DEVICE_CODE_ERROR")

    def test_poll_transport_error(self):
        transport = FakeDeviceCodeTransport()
        transport.queue_poll_error(OSError("poll broke"))
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TOKEN_ERROR")

    def test_poll_response_missing_access_token(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=200,
            body={"expires_in": 3600},
            is_error=False,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TOKEN_ERROR")

    def test_poll_response_zero_expires_in(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=200,
            body={"access_token": "X", "expires_in": 0},
            is_error=False,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TOKEN_ERROR")


class DeviceCodeSecretlessTests(unittest.TestCase):
    def test_flow_does_not_accept_client_secret(self):
        # The DeviceCodeFlow dataclass has no client_secret field.
        import dataclasses
        fields = {f.name for f in dataclasses.fields(DeviceCodeFlow)}
        self.assertNotIn("client_secret", fields)
        self.assertNotIn("password", fields)
        self.assertNotIn("username", fields)

    def test_request_form_never_carries_secret(self):
        transport = FakeDeviceCodeTransport()
        flow = _make_flow(transport)
        flow.run()
        form = transport.request_calls[0]
        encoded = repr(form)
        for forbidden in (
            "bearer ",
            "Bearer ",
            "Basic ",
            "secret=",
            "client_secret=",
            "password=",
        ):
            self.assertNotIn(forbidden, encoded)


if __name__ == "__main__":
    unittest.main()
