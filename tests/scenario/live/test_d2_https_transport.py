"""Offline D2-A tests for the fixed Microsoft HTTPS transport."""
from __future__ import annotations

import io
import socket
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from agents.scenario.auth.transports import (
    GRAPH_ME_URL,
    FakeGraphTransport,
    MicrosoftDeviceCodeHttpsTransport,
)

from tests.scenario.live._helpers import FAKE_TENANT


class _HttpResponse:
    def __init__(self, status, body):
        self._status = status
        self._body = body

    def getcode(self):
        return self._status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _NoRedirectOpener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FixedHttpsTransportTests(unittest.TestCase):
    def setUp(self):
        self.transport = MicrosoftDeviceCodeHttpsTransport(tenant_id=FAKE_TENANT)

    def test_endpoint_allowlist_is_exact(self):
        self.assertEqual(
            self.transport.allowed_endpoints,
            (
                "https://login.microsoftonline.com/{0}/oauth2/v2.0/devicecode".format(FAKE_TENANT),
                "https://login.microsoftonline.com/{0}/oauth2/v2.0/token".format(FAKE_TENANT),
                GRAPH_ME_URL,
            ),
        )

    def test_invalid_tenant_fails_before_network(self):
        with patch("urllib.request.urlopen") as urlopen, patch("socket.socket") as sock:
            with self.assertRaises(ValueError):
                MicrosoftDeviceCodeHttpsTransport(tenant_id="common")
        urlopen.assert_not_called()
        sock.assert_not_called()

    def test_device_code_request_uses_fixed_post_and_form(self):
        opener = _NoRedirectOpener(
            _HttpResponse(200, b'{"device_code":"private","user_code":"ABCD"}')
        )
        with patch("urllib.request.build_opener", return_value=opener), patch(
            "socket.socket"
        ) as sock:
            response = self.transport.request_device_code(
                {"client_id": "client", "scope": "User.Read"}
            )
        request = opener.requests[0][0]
        self.assertEqual(request.full_url, self.transport.device_code_endpoint)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.data, b"client_id=client&scope=User.Read")
        self.assertEqual(response.body["user_code"], "ABCD")
        sock.assert_not_called()

    def test_token_poll_uses_fixed_post_and_exact_grant(self):
        form = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": "client",
            "device_code": "private",
        }
        opener = _NoRedirectOpener(_HttpResponse(400, b'{"error":"authorization_pending"}'))
        with patch("urllib.request.build_opener", return_value=opener):
            response = self.transport.poll_token(form)
        request = opener.requests[0][0]
        self.assertEqual(request.full_url, self.transport.token_endpoint)
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(response.is_error)
        self.assertEqual(response.oauth_error_code(), "authorization_pending")

    def test_graph_me_accepts_only_fixed_url_and_get(self):
        opener = _NoRedirectOpener(_HttpResponse(200, b'{"id":"actor"}'))
        with patch("urllib.request.build_opener", return_value=opener):
            response = self.transport.get_me("private-token", GRAPH_ME_URL)
        request = opener.requests[0][0]
        self.assertEqual(request.full_url, GRAPH_ME_URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(response.body, {"id": "actor"})
        self._assert_graph_me_redirect_fails_closed()
        self._assert_fake_graph_transport_repr_redacts_recorded_token()

    def test_unallowlisted_url_or_form_fails_before_network(self):
        with patch("urllib.request.build_opener") as build, patch(
            "socket.socket"
        ) as sock:
            with self.assertRaises(ValueError):
                self.transport.get_me("private-token", "https://graph.microsoft.com/v1.0/users")
            with self.assertRaises(ValueError):
                self.transport.request_device_code(
                    {"client_id": "client", "scope": "User.Read", "extra": "no"}
                )
        build.assert_not_called()
        sock.assert_not_called()

    def test_http_error_is_parsed_without_raw_response_leak(self):
        error = HTTPError(
            self.transport.token_endpoint,
            400,
            "bad request",
            {},
            io.BytesIO(b'{"error":"invalid_client","access_token":"private"}'),
        )
        form = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": "client",
            "device_code": "private",
        }
        opener = _NoRedirectOpener(error)
        with patch("urllib.request.build_opener", return_value=opener):
            response = self.transport.poll_token(form)
        self.assertTrue(response.is_error)
        self.assertEqual(response.oauth_error_code(), "invalid_client")
        self._assert_oauth_redirects_fail_closed()

    def _assert_oauth_redirects_fail_closed(self):
        redirect_target = "https://redirect-target.example.test/capture"
        operations = (
            (
                self.transport.request_device_code,
                {"client_id": "client-secret-value", "scope": "User.Read"},
                self.transport.device_code_endpoint,
            ),
            (
                self.transport.poll_token,
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": "client-secret-value",
                    "device_code": "device-secret-value",
                },
                self.transport.token_endpoint,
            ),
        )
        for operation, form, endpoint in operations:
            with self.subTest(endpoint=endpoint):
                error = HTTPError(endpoint, 302, "Found", {"Location": redirect_target}, io.BytesIO(b"token"))
                opener = _NoRedirectOpener(error)
                with patch("urllib.request.build_opener", return_value=opener) as build, patch(
                    "socket.socket"
                ) as sock:
                    response = operation(form)
                handler = build.call_args.args[0]
                self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, redirect_target))
                self.assertEqual([request.full_url for request, _ in opener.requests], [endpoint])
                self.assertNotIn(redirect_target, [request.full_url for request, _ in opener.requests])
                self.assertEqual(response.status, 302)
                self.assertTrue(response.is_error)
                self.assertEqual(response.body, {})
                self.assertIsNone(response.oauth_error_code())
                sock.assert_not_called()

    def _assert_graph_me_redirect_fails_closed(self):
        redirect_target = "https://redirect-target.example.test/capture"
        access_token = "access-token-secret-value"
        error = HTTPError(GRAPH_ME_URL, 302, "Found", {"Location": redirect_target}, io.BytesIO(b"token"))
        opener = _NoRedirectOpener(error)
        with patch("urllib.request.build_opener", return_value=opener) as build, patch(
            "socket.socket"
        ) as sock:
            response = self.transport.get_me(access_token, GRAPH_ME_URL)
        handler = build.call_args.args[0]
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, redirect_target))
        self.assertEqual([request.full_url for request, _ in opener.requests], [GRAPH_ME_URL])
        self.assertNotIn(redirect_target, [request.full_url for request, _ in opener.requests])
        request = opener.requests[0][0]
        self.assertEqual(request.get_header("Authorization"), "Bearer " + access_token)
        self.assertNotIn(access_token, redirect_target)
        self.assertEqual(response.status, 302)
        self.assertTrue(response.is_error)
        self.assertEqual(response.body, {})
        sock.assert_not_called()

    def _assert_fake_graph_transport_repr_redacts_recorded_token(self):
        transport = FakeGraphTransport()
        token = "fake-access-token-DO-NOT-LEAK"
        transport.request(token, GRAPH_ME_URL)
        self.assertNotIn(token, repr(transport))


if __name__ == "__main__":
    unittest.main()
