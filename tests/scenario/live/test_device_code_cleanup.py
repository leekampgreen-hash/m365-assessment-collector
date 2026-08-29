"""Negative tests for device-code private state cleanup (G08-D1F, Finding 3).

``DeviceCodeFlow`` retains the confidential ``device_code`` in a
private attribute while polling requires it. These tests prove the
state is explicitly cleared as soon as the flow reaches ANY terminal
outcome:

* success,
* declined authorization,
* timeout / expiry (both via clock budget and ``expired_token``),
* token error,
* transport / error paths,

and that the state is NOT cleared prematurely while polling is still
in progress.
"""
from __future__ import annotations

import unittest

from agents.scenario.auth import (
    DeviceCodeError,
    DeviceCodeFlow,
    TokenTransportResponse,
)
from agents.scenario.auth.transports import FakeDeviceCodeTransport


def _make_flow(transport, *, timeout=300.0, sleep=None, clock=None):
    return DeviceCodeFlow(
        client_id="cid",
        tenant_id="tid",
        scopes=("User.Read",),
        request_transport=transport.request,
        poll_transport=transport.poll,
        sleep=sleep or (lambda s: None),
        timeout_seconds=timeout,
        clock=clock or (lambda: 0.0),
    )


class StateClearedOnSuccessTests(unittest.TestCase):
    """16. state cleared after success."""

    def test_device_code_state_cleared_after_success(self):
        transport = FakeDeviceCodeTransport()
        flow = _make_flow(transport)
        token = flow.run()
        self.assertTrue(token.access_token)
        # Terminal outcome reached: the confidential value is gone.
        self.assertIsNone(flow._device_code)
        self.assertNotIn("_device_code", repr(flow))

    def test_state_is_present_while_polling_still_requires_it(self):
        # The cleanup must not be premature: while the flow is still
        # waiting on pending polls, the private state must be set.
        transport = FakeDeviceCodeTransport()
        pending = TokenTransportResponse(
            status=400,
            body={"error": "authorization_pending"},
            is_error=True,
        )
        transport._poll_queue = [pending, pending]
        observed_during_poll = []

        def spy_sleep(seconds):
            observed_during_poll.append(flow._device_code)

        flow = _make_flow(transport, sleep=spy_sleep)
        flow.run()
        self.assertEqual(len(observed_during_poll), 2)
        for value in observed_during_poll:
            # Polling still required the state at sleep time.
            self.assertEqual(value, "fake-device-code")
        # After the terminal success it is cleared.
        self.assertIsNone(flow._device_code)


class StateClearedOnDeclineTests(unittest.TestCase):
    """17. state cleared after declined auth."""

    def test_device_code_state_cleared_after_declined(self):
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
        self.assertIsNone(flow._device_code)


class StateClearedOnTimeoutTests(unittest.TestCase):
    """18. state cleared after timeout/expiry."""

    def test_device_code_state_cleared_after_clock_timeout(self):
        transport = FakeDeviceCodeTransport()
        transport.poll_response = TokenTransportResponse(
            status=400,
            body={"error": "authorization_pending"},
            is_error=True,
        )
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
        self.assertIsNone(flow._device_code)

    def test_device_code_state_cleared_after_expired_token(self):
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
        self.assertIsNone(flow._device_code)


class StateClearedOnTokenErrorTests(unittest.TestCase):
    """19. state cleared after token error."""

    def test_device_code_state_cleared_after_invalid_grant(self):
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
        self.assertIsNone(flow._device_code)

    def test_device_code_state_cleared_after_missing_access_token(self):
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
        self.assertIsNone(flow._device_code)


class StateClearedOnTransportErrorTests(unittest.TestCase):
    """20. state cleared after transport/error terminal path."""

    def test_device_code_state_cleared_after_poll_transport_exception(self):
        transport = FakeDeviceCodeTransport()
        transport.queue_poll_error(OSError("poll broke"))
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_TOKEN_ERROR")
        self.assertIsNone(flow._device_code)

    def test_state_absent_when_request_phase_fails(self):
        # The request phase failed before any device code was
        # received; nothing may remain behind.
        transport = FakeDeviceCodeTransport()
        transport.queue_request_error(OSError("request broke"))
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError) as ctx:
            flow.run()
        self.assertEqual(ctx.exception.classification, "AUTH_DEVICE_CODE_ERROR")
        self.assertIsNone(flow._device_code)

    def test_state_absent_on_non_object_request_body(self):
        transport = FakeDeviceCodeTransport()
        transport.request_response = TokenTransportResponse(
            status=500,
            body={"error": "server_error"},
            is_error=True,
        )
        flow = _make_flow(transport)
        with self.assertRaises(DeviceCodeError):
            flow.run()
        self.assertIsNone(flow._device_code)

    def test_rerun_does_not_reuse_cleared_state(self):
        # After a terminal outcome the state is gone; a second run
        # must go through a fresh device-code request rather than
        # resurrect the old device code.
        transport = FakeDeviceCodeTransport()
        flow = _make_flow(transport)
        flow.run()
        self.assertIsNone(flow._device_code)
        self.assertEqual(len(transport.request_calls), 1)
        flow.run()
        self.assertEqual(len(transport.request_calls), 2)
        self.assertEqual(
            transport.poll_calls[1].get("device_code"), "fake-device-code"
        )
        self.assertIsNone(flow._device_code)


if __name__ == "__main__":
    unittest.main()
