"""Offline tests for the explicit SCN-AUTH-001 operator entrypoint."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from agents.scenario.auth import DeviceCodeError, DeviceCodeFlow, TokenTransportResponse
from scripts import run_scn_auth_001

from tests.scenario.live._helpers import (
    FAKE_CLIENT_ID,
    FAKE_TENANT,
    FAKE_USER_OBJECT_ID,
)


class OperatorEntrypointTests(unittest.TestCase):
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "run_scn_auth_001.py")

    def _environment(self):
        return {
            "SCENARIO_TENANT_ID": FAKE_TENANT,
            "SCENARIO_CLIENT_ID": FAKE_CLIENT_ID,
            "SCENARIO_EXPECTED_ACTOR_OBJECT_ID": FAKE_USER_OBJECT_ID,
            "CLIENT_SECRET": "must-not-be-read",
            "COLLECTOR_CLIENT_ID": "must-not-be-read",
        }

    def test_live_flag_is_required_without_network(self):
        with patch("urllib.request.urlopen") as urlopen, patch("socket.socket") as sock:
            with self.assertRaises(SystemExit) as raised, redirect_stderr(StringIO()):
                run_scn_auth_001.main([])
        self.assertEqual(raised.exception.code, 2)
        urlopen.assert_not_called()
        sock.assert_not_called()

    def test_direct_script_execution_from_project_root_imports_and_fails_closed(self):
        environment = {"PATH": os.environ.get("PATH", "")}
        environment.pop("PYTHONPATH", None)
        for arguments, expected_error in (
            ([], "--live is required; no network operation was started"),
            (["--live"], "SCENARIO_TENANT_ID must be set"),
        ):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, self.SCRIPT, *arguments],
                    cwd=self.PROJECT_ROOT,
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected_error, result.stderr)
                self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_missing_runtime_config_is_rejected_without_network(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen") as urlopen:
            with redirect_stderr(StringIO()):
                self.assertEqual(run_scn_auth_001.main(["--live"]), 2)
        urlopen.assert_not_called()

    def test_runtime_contract_uses_only_scenario_ids_and_safe_output(self):
        output = StringIO()
        with patch.dict(os.environ, self._environment(), clear=True), patch(
            "agents.scenario.auth.transports.MicrosoftDeviceCodeHttpsTransport.request_device_code",
            side_effect=OSError("offline test"),
        ) as request, patch("socket.socket") as sock, redirect_stdout(output):
            self.assertEqual(run_scn_auth_001.main(["--live"]), 1)
        self.assertEqual(request.call_count, 1)
        sock.assert_not_called()
        rendered = output.getvalue()
        self.assertNotIn("must-not-be-read", rendered)
        self.assertNotIn("Authorization", rendered)
        self.assertNotIn("access_token", rendered)

    def test_token_polling_starts_only_after_exact_confirmation(self):
        output = StringIO()
        device_response = TokenTransportResponse(
            status=200,
            body={
                "device_code": "private-device-code",
                "user_code": "SAFE-CODE",
                "verification_uri": "https://microsoft.com/devicelogin",
                "expires_in": 900,
                "interval": 5,
            },
        )
        token_response = TokenTransportResponse(
            status=400, body={"error": "authorization_declined"}, is_error=True
        )
        def confirm_after_prompt(_prompt):
            self.assertEqual(poll.call_count, 0)
            return True

        with patch.dict(os.environ, self._environment(), clear=True), patch(
            "agents.scenario.auth.transports.MicrosoftDeviceCodeHttpsTransport.request_device_code",
            return_value=device_response,
        ) as request, patch(
            "agents.scenario.auth.transports.MicrosoftDeviceCodeHttpsTransport.poll_token",
            return_value=token_response,
        ) as poll, patch("socket.socket") as sock, patch(
            "scripts.run_scn_auth_001._await_login_completed",
            side_effect=confirm_after_prompt,
        ), redirect_stdout(output):
            self.assertEqual(run_scn_auth_001.main(["--live"]), 1)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(poll.call_count, 1)
        sock.assert_not_called()
        rendered = output.getvalue()
        self.assertNotIn("private-device-code", rendered)
        self.assertNotIn("access_token", rendered)
        self.assertNotIn("Authorization", rendered)

    def test_invalid_eof_and_interrupt_confirmation_abort_without_polling(self):
        device_response = TokenTransportResponse(
            status=200,
            body={
                "device_code": "private-device-code",
                "user_code": "SAFE-CODE",
                "verification_uri": "https://microsoft.com/devicelogin",
                "expires_in": 900,
                "interval": 5,
            },
        )
        for source in (StringIO("not confirmed\n"), StringIO("")):
            with self.subTest(source=repr(source.getvalue())), patch.dict(
                os.environ, self._environment(), clear=True
            ), patch(
                "agents.scenario.auth.transports.MicrosoftDeviceCodeHttpsTransport.request_device_code",
                return_value=device_response,
            ), patch(
                "agents.scenario.auth.transports.MicrosoftDeviceCodeHttpsTransport.poll_token",
            ) as poll, patch("socket.socket") as sock, patch("sys.stdin", source):
                self.assertEqual(run_scn_auth_001.main(["--live"]), 1)
            poll.assert_not_called()
            sock.assert_not_called()

        class InterruptedInput:
            def readline(self):
                raise KeyboardInterrupt

        with patch.dict(os.environ, self._environment(), clear=True), patch(
            "agents.scenario.auth.transports.MicrosoftDeviceCodeHttpsTransport.request_device_code",
            return_value=device_response,
        ), patch(
            "agents.scenario.auth.transports.MicrosoftDeviceCodeHttpsTransport.poll_token",
        ) as poll, patch("socket.socket") as sock, patch("sys.stdin", InterruptedInput()):
            self.assertEqual(run_scn_auth_001.main(["--live"]), 1)
        poll.assert_not_called()
        sock.assert_not_called()

    def test_expired_confirmation_window_aborts_without_polling(self):
        request = Mock(return_value=TokenTransportResponse(
            status=200,
            body={
                "device_code": "private-device-code",
                "user_code": "SAFE-CODE",
                "verification_uri": "https://microsoft.com/devicelogin",
                "expires_in": 1,
                "interval": 5,
            },
        ))
        poll = Mock()
        clock = iter((0.0, 2.0)).__next__
        flow = DeviceCodeFlow(
            client_id=FAKE_CLIENT_ID,
            tenant_id=FAKE_TENANT,
            scopes=("User.Read",),
            request_transport=request,
            poll_transport=poll,
            confirmation_callback=lambda _prompt: True,
            timeout_seconds=1,
            clock=clock,
        )
        with self.assertRaises(DeviceCodeError) as raised:
            flow.run()
        self.assertEqual(raised.exception.classification, "AUTH_TIMEOUT")
        poll.assert_not_called()


if __name__ == "__main__":
    unittest.main()
