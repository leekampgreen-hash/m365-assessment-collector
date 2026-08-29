from __future__ import annotations

import json
import unittest
from urllib.error import HTTPError
from io import BytesIO

from collectors.onedrive_audit import AuditTransportError, ManagementActivityTransport
from collectors.core.retry import RetryPolicy


class Response:
    def __init__(self, status=200, payload=None, headers=None):
        self.status = status
        self.payload = json.dumps(payload if payload is not None else []).encode()
        self.headers = headers or {}

    def read(self):
        return self.payload


class DirectTransportRetryTests(unittest.TestCase):
    def transport(self, source, sleeps=None):
        sleeps = [] if sleeps is None else sleeps
        calls = []

        def opener(request, timeout=None):
            calls.append(request.full_url)
            return source(len(calls))

        return ManagementActivityTransport("tenant", lambda: "token", url_open=opener, retry_policy=RetryPolicy(sleep=sleeps.append), sleep=sleeps.append), calls, sleeps

    def test_direct_429_retries_to_success(self):
        transport, _, _ = self.transport(lambda n: Response(429) if n == 1 else Response(payload=[{"ok": True}]))
        self.assertEqual(transport._get("https://manage.office.com/resource"), [{"ok": True}])
        self.assertEqual(transport.retries, 1)

    def test_direct_429_honors_retry_after(self):
        transport, _, sleeps = self.transport(lambda n: Response(429, headers={"Retry-After": "7"}) if n == 1 else Response())
        transport._get("https://manage.office.com/resource")
        self.assertEqual(sleeps, [7.0])

    def test_repeated_direct_429_is_bounded(self):
        transport, _, _ = self.transport(lambda n: Response(429))
        with self.assertRaises(AuditTransportError) as raised:
            transport._get("https://manage.office.com/resource")
        self.assertEqual(raised.exception.classification, "RETRY_EXHAUSTED")
        self.assertNotIsInstance(raised.exception, UnboundLocalError)

    def test_direct_5xx_retries_and_exhausts(self):
        transport, _, _ = self.transport(lambda n: Response(503) if n == 1 else Response(payload=[1]))
        self.assertEqual(transport._get("https://manage.office.com/resource"), [1])
        transport, calls, _ = self.transport(lambda n: Response(500))
        with self.assertRaises(AuditTransportError) as raised:
            transport._get("https://manage.office.com/resource")
        self.assertEqual(len(calls), 4)
        self.assertEqual(raised.exception.classification, "RETRY_EXHAUSTED")

    def test_direct_auth_is_non_retryable(self):
        for status in (401, 403):
            transport, calls, _ = self.transport(lambda n, status=status: Response(status))
            with self.assertRaises(AuditTransportError) as raised:
                transport._get("https://manage.office.com/resource")
            self.assertEqual(raised.exception.classification, "PERMISSION_REQUIRED")
            self.assertEqual(len(calls), 1)

    def test_direct_source_failure_preserves_classification(self):
        transport = ManagementActivityTransport("tenant", lambda: "token", url_open=lambda *args, **kwargs: (_ for _ in ()).throw(AuditTransportError("SOURCE_FAILURE", "blob failed")), sleep=lambda _: None)
        with self.assertRaises(AuditTransportError) as raised:
            transport._get("https://manage.office.com/blob")
        self.assertEqual(raised.exception.classification, "RETRY_EXHAUSTED")
        self.assertNotIsInstance(raised.exception, UnboundLocalError)

    def test_http_error_and_timeout_paths_remain_bounded(self):
        http_error = HTTPError("https://manage.office.com/resource", 429, "throttled", {"Retry-After": "0"}, BytesIO())
        transport = ManagementActivityTransport("tenant", lambda: "token", url_open=lambda *args, **kwargs: (_ for _ in ()).throw(http_error), sleep=lambda _: None)
        with self.assertRaises(AuditTransportError) as raised:
            transport._get("https://manage.office.com/resource")
        self.assertEqual(raised.exception.classification, "RETRY_EXHAUSTED")
        transport = ManagementActivityTransport("tenant", lambda: "token", url_open=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()), sleep=lambda _: None)
        with self.assertRaises(AuditTransportError) as raised:
            transport._get("https://manage.office.com/resource")
        self.assertEqual(raised.exception.classification, "RETRY_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
