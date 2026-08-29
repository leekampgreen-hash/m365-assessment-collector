"""Offline unit tests for the collector framework.

These tests must:
- Use mocks/fakes (no live Microsoft Graph traffic).
- Not sleep for long periods (use a fake ``sleep`` callable).
- Not introduce real credentials into source / tests / docs.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from collectors.core import (
    API_ERROR,
    AUTH_FAILURE,
    BaseCollector,
    CollectionResult,
    EndpointSpec,
    GraphHttpError,
    GraphNetworkError,
    GraphTransport,
    InventoryValidationError,
    NETWORK_ERROR,
    PASS,
    PERMISSION_REQUIRED,
    Paginator,
    RetryDecision,
    RetryPolicy,
    THROTTLED,
    UNKNOWN,
    build_endpoint_url,
    classify_http_status,
    enabled_specs,
    entry_to_spec,
    is_retryable,
    load_inventory,
)


SENSITIVE_TOKEN = "secret-token-DO-NOT-LEAK"


def make_response(status, payload, headers=None):
    body = json.dumps(payload).encode("utf-8")

    class Response:
        def __init__(self):
            self.status = status
            self.headers = headers or {}
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return self._body

    return Response()


def make_http_error(status, payload, headers=None):
    return HTTPError(
        url="https://example.invalid",
        code=status,
        msg="error",
        hdrs=headers or {},
        fp=__import__("io").BytesIO(json.dumps(payload).encode("utf-8")),
    )


def raiser(exc):
    """Build a callable that raises ``exc`` when invoked."""
    def _raise(*args, **kwargs):
        raise exc
    return _raise


class ErrorClassificationTests(unittest.TestCase):
    def test_401_is_auth_failure_not_retryable(self):
        self.assertEqual(classify_http_status(401), AUTH_FAILURE)
        self.assertFalse(is_retryable(AUTH_FAILURE))

    def test_403_is_permission_required_not_retryable(self):
        self.assertEqual(classify_http_status(403), PERMISSION_REQUIRED)
        self.assertFalse(is_retryable(PERMISSION_REQUIRED))

    def test_429_is_throttled_and_retryable(self):
        self.assertEqual(classify_http_status(429), THROTTLED)
        self.assertTrue(is_retryable(THROTTLED))

    def test_429_is_not_auth_failure(self):
        self.assertNotEqual(classify_http_status(429), AUTH_FAILURE)

    def test_500_is_api_error(self):
        self.assertEqual(classify_http_status(500), API_ERROR)
        self.assertTrue(is_retryable(API_ERROR))

    def test_2xx_is_pass_not_retryable(self):
        self.assertEqual(classify_http_status(200), PASS)
        self.assertFalse(is_retryable(PASS))

    def test_204_is_pass(self):
        self.assertEqual(classify_http_status(204), PASS)

    def test_none_status_is_network_error(self):
        self.assertEqual(classify_http_status(None), NETWORK_ERROR)


class EndpointSpecParsingTests(unittest.TestCase):
    def test_minimal_entry_parses(self):
        spec = entry_to_spec({
            "id": "G99-001",
            "name": "Users",
            "path": "/v1.0/users",
        })
        self.assertEqual(spec.endpoint_id, "G99-001")
        self.assertEqual(spec.name, "Users")
        self.assertEqual(spec.path, "/v1.0/users")
        self.assertTrue(spec.pagination)
        self.assertEqual(spec.collection_pattern, "paged")

    def test_pagination_false_yields_single_pattern(self):
        spec = entry_to_spec({
            "id": "G99-002",
            "name": "Organization",
            "path": "/v1.0/organization",
            "pagination": False,
        })
        self.assertFalse(spec.pagination)
        self.assertEqual(spec.collection_pattern, "single")

    def test_documented_permissions_string_fallback(self):
        spec = entry_to_spec({
            "id": "G99-003",
            "name": "X",
            "path": "/v1.0/x",
            "permission": "X.Read.All",
        })
        self.assertEqual(spec.documented_permissions, ["X.Read.All"])

    def test_documented_permissions_array_sorted(self):
        spec = entry_to_spec({
            "id": "G99-004",
            "name": "X",
            "path": "/v1.0/x",
            "documented_permissions": ["X.Read.All", "X.Read"],
        })
        # Framework returns a stable sorted list of unique permissions.
        self.assertEqual(spec.documented_permissions, ["X.Read", "X.Read.All"])

    def test_invalid_top_raises(self):
        with self.assertRaises(InventoryValidationError):
            entry_to_spec({
                "id": "G99-005",
                "name": "X",
                "path": "/v1.0/x",
                "top": "not-a-number",
            })

    def test_invalid_pagination_raises(self):
        with self.assertRaises(InventoryValidationError):
            entry_to_spec({
                "id": "G99-006",
                "name": "X",
                "path": "/v1.0/x",
                "pagination": "yes",
            })

    def test_missing_required_field_raises(self):
        with self.assertRaises(InventoryValidationError):
            entry_to_spec({"id": "G99-007", "name": "X"})

    def test_inventory_load_and_enabled_filter(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "inv.json"
            path.write_text(json.dumps([
                {"id": "A", "name": "A", "path": "/v1.0/a", "pagination": True, "enabled": True},
                {"id": "B", "name": "B", "path": "/v1.0/b", "pagination": True, "enabled": False},
            ]))
            specs = load_inventory(path)
            self.assertEqual(len(specs), 2)
            enabled = enabled_specs(specs)
            self.assertEqual([s.endpoint_id for s in enabled], ["A"])

    def test_inventory_root_must_be_list(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "inv.json"
            path.write_text(json.dumps({"id": "A"}))
            with self.assertRaises(InventoryValidationError):
                load_inventory(path)


class RetryPolicyTests(unittest.TestCase):
    def test_never_retries_pass(self):
        p = RetryPolicy(max_retries=3, sleep=lambda s: None)
        self.assertFalse(p.should_retry(PASS, attempts_so_far=1).retry)

    def test_never_retries_auth_failure(self):
        p = RetryPolicy(max_retries=3, sleep=lambda s: None)
        self.assertFalse(p.should_retry(AUTH_FAILURE, attempts_so_far=1).retry)

    def test_never_retries_permission_required(self):
        p = RetryPolicy(max_retries=3, sleep=lambda s: None)
        self.assertFalse(p.should_retry(PERMISSION_REQUIRED, attempts_so_far=1).retry)

    def test_retries_throttled_when_under_cap(self):
        p = RetryPolicy(max_retries=3, sleep=lambda s: None)
        d = p.should_retry(THROTTLED, attempts_so_far=1)
        self.assertTrue(d.retry)
        self.assertEqual(d.sleep_seconds, 0.0)

    def test_honors_retry_after_for_throttled(self):
        p = RetryPolicy(max_retries=3, sleep=lambda s: None)
        d = p.should_retry(THROTTLED, retry_after="7", attempts_so_far=1)
        self.assertTrue(d.retry)
        self.assertEqual(d.sleep_seconds, 7.0)
        self.assertEqual(d.reason, "honor-retry-after")

    def test_retry_after_invalid_value_ignored(self):
        p = RetryPolicy(max_retries=3, sleep=lambda s: None)
        d = p.should_retry(THROTTLED, retry_after="not-a-number", attempts_so_far=1)
        self.assertTrue(d.retry)
        self.assertEqual(d.sleep_seconds, 0.0)
        self.assertEqual(d.reason, "retryable")

    def test_bounded_no_infinite_retry(self):
        p = RetryPolicy(max_retries=2, sleep=lambda s: None)
        # Already attempted max_retries+1 times -> no further retry.
        # With max_retries=2 and attempts_so_far=3 we have already done
        # 2 retries (attempts - 1); the policy must stop.
        d = p.should_retry(API_ERROR, attempts_so_far=3)
        self.assertFalse(d.retry)
        self.assertEqual(d.reason, "max-retries-reached")

    def test_max_retries_zero_means_no_retry(self):
        p = RetryPolicy(max_retries=0, sleep=lambda s: None)
        d = p.should_retry(API_ERROR, attempts_so_far=0)
        self.assertFalse(d.retry)

    def test_sleep_invoked_when_decision_says_so(self):
        slept = []
        p = RetryPolicy(max_retries=3, sleep=slept.append)
        d = RetryDecision(True, sleep_seconds=2.5, reason="r")
        p.wait(d)
        self.assertEqual(slept, [2.5])

    def test_no_sleep_when_decision_says_no(self):
        slept = []
        p = RetryPolicy(max_retries=3, sleep=slept.append)
        d = RetryDecision(False, sleep_seconds=2.5, reason="no")
        p.wait(d)
        self.assertEqual(slept, [])


class PaginatorTests(unittest.TestCase):
    def test_single_page(self):
        def fetch(url):
            return {"value": [{"id": "1"}, {"id": "2"}]}
        p = Paginator(fetch)
        result = p.run("https://g/v1.0/users")
        self.assertEqual(result.pages, 1)
        self.assertEqual(result.rows, 2)
        self.assertEqual(result.items, [{"id": "1"}, {"id": "2"}])
        self.assertEqual(result.error_classification, PASS)

    def test_multi_page_follows_next_link(self):
        pages = iter([
            {"value": [{"id": "1"}], "@odata.nextLink": "https://g/v1.0/users?$skiptoken=abc"},
            {"value": [{"id": "2"}, {"id": "3"}], "@odata.nextLink": "https://g/v1.0/users?$skiptoken=def"},
            {"value": [{"id": "4"}]},
        ])
        def fetch(url):
            return next(pages)
        result = Paginator(fetch).run("https://g/v1.0/users")
        self.assertEqual(result.pages, 3)
        self.assertEqual(result.rows, 4)
        self.assertEqual([i["id"] for i in result.items], ["1", "2", "3", "4"])
        self.assertEqual(result.error_classification, PASS)

    def test_empty_value(self):
        def fetch(url):
            return {"value": []}
        result = Paginator(fetch).run("https://g/v1.0/x")
        self.assertEqual(result.pages, 1)
        self.assertEqual(result.rows, 0)
        self.assertEqual(result.error_classification, PASS)

    def test_missing_value_is_malformed(self):
        result = Paginator(lambda url: {}).run("https://g/v1.0/x")
        self.assertEqual(result.error_classification, API_ERROR)
        self.assertEqual(result.rows, 0)

    def test_non_list_value_is_malformed(self):
        result = Paginator(lambda url: {"value": {"id": "x"}}).run("https://g/v1.0/x")
        self.assertEqual(result.error_classification, API_ERROR)
        self.assertEqual(result.rows, 0)

    def test_non_string_next_link_is_malformed(self):
        result = Paginator(lambda url: {"value": [], "@odata.nextLink": 7}).run("https://g/v1.0/x")
        self.assertEqual(result.error_classification, API_ERROR)

    def test_single_page_no_next_link(self):
        def fetch(url):
            return {"value": [{"id": "x"}]}
        result = Paginator(fetch).run("https://g/v1.0/x")
        self.assertFalse(any(bool(p.next_link) for p in result.pages_detail))


class TransportTests(unittest.TestCase):
    def _make_transport(self, opener):
        return GraphTransport(
            token_provider=lambda: SENSITIVE_TOKEN,
            url_open=opener,
            timeout=10,
        )

    def test_successful_single_page(self):
        opener = Mock(return_value=make_response(200, {"value": [{"id": "1"}]}))
        t = self._make_transport(opener)
        response = t.get("https://graph.microsoft.com/v1.0/users")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.payload, {"value": [{"id": "1"}]})

    def test_query_parameters_attached(self):
        captured = {}

        def opener(request, timeout=None):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.headers)
            captured["method"] = request.get_method()
            return make_response(200, {"value": []})

        t = self._make_transport(opener)
        t.get("/v1.0/users", params={"$select": ["id", "displayName"], "$top": 5})
        # urlencode may percent-encode '$' as %24; check for either form.
        self.assertTrue("$select=id" in captured["url"] or "%24select=id" in captured["url"])
        self.assertIn("id", captured["url"])
        self.assertIn("displayName", captured["url"])
        self.assertTrue("$top=5" in captured["url"] or "%24top=5" in captured["url"])
        self.assertEqual(captured["method"], "GET")
        # Authorization header is set, but its VALUE must not leak into
        # any result, exception, or log captured by the test framework.
        self.assertTrue(captured["headers"]["Authorization"].startswith("Bearer "))

    def test_401_raises_http_error_with_status(self):
        opener = Mock(side_effect=make_http_error(
            401,
            {"error": {"code": "InvalidAuthenticationToken", "message": "bad"}},
            headers={"Content-Type": "application/json"},
        ))
        t = self._make_transport(opener)
        with self.assertRaises(GraphHttpError) as cm:
            t.get("https://g/v1.0/users")
        self.assertEqual(cm.exception.status, 401)

    def test_403_raises_http_error_with_status(self):
        opener = Mock(side_effect=make_http_error(
            403,
            {"error": {"code": "Authorization_RequestDenied", "message": "no"}},
        ))
        t = self._make_transport(opener)
        with self.assertRaises(GraphHttpError) as cm:
            t.get("https://g/v1.0/users")
        self.assertEqual(cm.exception.status, 403)

    def test_429_captures_retry_after(self):
        opener = Mock(side_effect=make_http_error(
            429,
            {"error": {"code": "TooManyRequests", "message": "slow"}},
            headers={"Retry-After": "12"},
        ))
        t = self._make_transport(opener)
        with self.assertRaises(GraphHttpError) as cm:
            t.get("https://g/v1.0/users")
        self.assertEqual(cm.exception.status, 429)
        self.assertEqual(cm.exception.retry_after(), "12")

    def test_network_error_wrapped(self):
        opener = Mock(side_effect=URLError("dns failure"))
        t = self._make_transport(opener)
        with self.assertRaises(GraphNetworkError):
            t.get("https://g/v1.0/users")

    def test_http_error_message_does_not_contain_token(self):
        opener = Mock(side_effect=make_http_error(
            500,
            {"error": {"code": "InternalError", "message": "boom"}},
        ))
        t = self._make_transport(opener)
        with self.assertRaises(GraphHttpError) as cm:
            t.get("https://g/v1.0/users")
        self.assertNotIn(SENSITIVE_TOKEN, str(cm.exception))
        self.assertNotIn(SENSITIVE_TOKEN, repr(cm.exception))

    def test_build_endpoint_url_includes_select_and_top(self):
        url = build_endpoint_url("/v1.0/users", select=["id", "displayName"], top=10)
        self.assertIn("graph.microsoft.com", url)
        self.assertIn("users", url)
        self.assertIn("id", url)
        self.assertIn("displayName", url)
        self.assertIn("10", url)

    def test_build_endpoint_url_path_already_full(self):
        url = build_endpoint_url("https://g/v1.0/users", top=5)
        self.assertTrue(url.startswith("https://g/v1.0/users?"))
        self.assertIn("5", url)


class BaseCollectorTests(unittest.TestCase):
    def _make_collector(self, opener, *, max_retries=2, base_delay=0.0):
        spec = EndpointSpec(
            endpoint_id="G99-100",
            name="Users",
            path="/v1.0/users",
            select=["id", "displayName"],
            top=10,
            pagination=True,
            documented_permissions=["User.Read.All"],
        )
        transport = GraphTransport(
            token_provider=lambda: SENSITIVE_TOKEN,
            url_open=opener,
            timeout=10,
        )
        retry = RetryPolicy(max_retries=max_retries, base_delay_seconds=base_delay, sleep=lambda s: None)
        return BaseCollector(spec, transport, retry_policy=retry), spec

    def test_successful_collection_returns_pass_result(self):
        opener = Mock(return_value=make_response(200, {"value": [{"id": "1"}]}))
        collector, spec = self._make_collector(opener)
        run = collector.collect()
        self.assertEqual(run.result.endpoint_id, spec.endpoint_id)
        self.assertEqual(run.result.status, "PASS")
        self.assertEqual(run.result.pages, 1)
        self.assertEqual(run.result.rows, 1)
        self.assertEqual(run.result.http_status, 200)
        self.assertEqual(run.result.error_classification, PASS)
        self.assertEqual(run.result.retry_count, 0)

    def test_multi_page_collection_counts_pages_and_rows(self):
        opener = Mock(side_effect=[
            make_response(200, {"value": [{"id": "1"}, {"id": "2"}], "@odata.nextLink": "https://g/v1.0/users?$skiptoken=a"}),
            make_response(200, {"value": [{"id": "3"}]}),
        ])
        collector, _ = self._make_collector(opener)
        run = collector.collect()
        self.assertEqual(run.result.pages, 2)
        self.assertEqual(run.result.rows, 3)
        self.assertTrue(run.result.pagination_detected)
        self.assertEqual(run.result.status, "PASS")

    def test_empty_value_collection(self):
        opener = Mock(return_value=make_response(200, {"value": []}))
        collector, _ = self._make_collector(opener)
        run = collector.collect()
        self.assertEqual(run.result.pages, 1)
        self.assertEqual(run.result.rows, 0)
        self.assertEqual(run.result.status, "PASS")

    def test_401_classifies_auth_failure_no_retry(self):
        opener = Mock(side_effect=make_http_error(
            401, {"error": {"code": "InvalidAuthenticationToken", "message": "bad"}},
        ))
        collector, _ = self._make_collector(opener, max_retries=3)
        run = collector.collect()
        self.assertEqual(run.result.error_classification, AUTH_FAILURE)
        self.assertEqual(run.result.retry_count, 0)

    def test_403_classifies_permission_required_no_retry(self):
        opener = Mock(side_effect=make_http_error(
            403, {"error": {"code": "Authorization_RequestDenied", "message": "no"}},
        ))
        collector, _ = self._make_collector(opener, max_retries=3)
        run = collector.collect()
        self.assertEqual(run.result.error_classification, PERMISSION_REQUIRED)
        self.assertEqual(run.result.retry_count, 0)

    def test_429_classifies_throttled(self):
        opener = Mock(side_effect=make_http_error(
            429, {"error": {"code": "TooManyRequests", "message": "slow"}}, headers={"Retry-After": "5"},
        ))
        collector, _ = self._make_collector(opener, max_retries=3)
        run = collector.collect()
        self.assertEqual(run.result.error_classification, THROTTLED)
        # Retry-After is captured in the result for downstream observers
        self.assertEqual(run.result.retry_after, "5")

    def test_429_retry_after_honored_via_policy(self):
        slept = []
        spec = EndpointSpec(endpoint_id="G99-T", name="X", path="/v1.0/x")
        # First attempt: 429 with Retry-After=3. Second: success.
        err = make_http_error(429, {"error": {"code": "TooManyRequests"}}, headers={"Retry-After": "3"})
        ok = make_response(200, {"value": [{"id": "ok"}]})
        opener = Mock(side_effect=[err, ok])
        transport = GraphTransport(token_provider=lambda: "t", url_open=opener, timeout=10)
        retry = RetryPolicy(max_retries=3, base_delay_seconds=0.0, sleep=slept.append)
        run = BaseCollector(spec, transport, retry_policy=retry).collect()
        self.assertEqual(run.result.status, "PASS")
        self.assertEqual(run.result.retry_count, 1)
        self.assertEqual(slept, [3.0])

    def test_api_error_is_retryable_bounded(self):
        # 500 then 500 then 200 -> succeeds after bounded retries
        opener = Mock(side_effect=[
            make_http_error(500, {"error": {"code": "InternalError"}}),
            make_http_error(500, {"error": {"code": "InternalError"}}),
            make_response(200, {"value": [{"id": "ok"}]}),
        ][0:3])
        # Re-build with a flat list (the above is just for readability)
        opener = Mock(side_effect=[
            make_http_error(500, {"error": {"code": "InternalError"}}),
            make_http_error(500, {"error": {"code": "InternalError"}}),
            make_response(200, {"value": [{"id": "ok"}]}),
        ])
        collector, _ = self._make_collector(opener, max_retries=3)
        run = collector.collect()
        self.assertEqual(run.result.status, "PASS")
        self.assertEqual(run.result.retry_count, 2)

    def test_api_error_exhausts_retry_and_returns_classification(self):
        opener = Mock(side_effect=[
            make_http_error(500, {"error": {"code": "InternalError"}}),
            make_http_error(500, {"error": {"code": "InternalError"}}),
            make_http_error(500, {"error": {"code": "InternalError"}}),
        ])
        collector, _ = self._make_collector(opener, max_retries=2)
        run = collector.collect()
        self.assertEqual(run.result.error_classification, API_ERROR)
        self.assertEqual(run.result.retry_count, 2)
        self.assertEqual(run.result.status, "ERROR")

    def test_network_error_is_classified(self):
        opener = Mock(side_effect=URLError("dns"))
        collector, _ = self._make_collector(opener, max_retries=1)
        run = collector.collect()
        self.assertEqual(run.result.error_classification, NETWORK_ERROR)

    def test_retry_count_matches_attempts(self):
        # 2 x 500 then success -> retry_count = 2
        opener = Mock(side_effect=[
            make_http_error(500, {"error": {"code": "x"}}),
            make_http_error(500, {"error": {"code": "x"}}),
            make_response(200, {"value": []}),
        ])
        collector, _ = self._make_collector(opener, max_retries=3)
        run = collector.collect()
        self.assertEqual(run.result.retry_count, 2)

    def test_retry_does_not_loop_on_auth_failure(self):
        # 401 must NEVER trigger retry, even with high max_retries
        opener = Mock(side_effect=make_http_error(401, {"error": {"code": "InvalidAuthenticationToken"}}))
        collector, _ = self._make_collector(opener, max_retries=10)
        run = collector.collect()
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(run.result.retry_count, 0)

    def test_retry_does_not_loop_on_permission_required(self):
        opener = Mock(side_effect=make_http_error(403, {"error": {"code": "Authorization_RequestDenied"}}))
        collector, _ = self._make_collector(opener, max_retries=10)
        run = collector.collect()
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(run.result.retry_count, 0)

    def test_result_has_no_token(self):
        opener = Mock(return_value=make_response(200, {"value": [{"id": "x"}]}))
        collector, _ = self._make_collector(opener)
        run = collector.collect()
        # The CollectionResult dataclass and its dict representation must
        # never contain the bearer token.
        text = json.dumps(run.result.to_dict())
        self.assertNotIn(SENSITIVE_TOKEN, text)
        self.assertNotIn("Bearer ", text)
        self.assertNotIn("Authorization", text)

    def test_collection_result_serialization_no_secrets(self):
        r = CollectionResult(
            endpoint_id="X",
            status="PASS",
            pages=1, rows=1,
            http_status=200,
            error_classification=PASS,
            error_message=None,
            retry_count=0,
        )
        text = json.dumps(r.to_dict())
        self.assertNotIn(SENSITIVE_TOKEN, text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("Authorization", text)


class EndpointIdAndCountersTests(unittest.TestCase):
    def test_endpoint_id_propagated(self):
        spec = EndpointSpec(endpoint_id="G07-007", name="X", path="/v1.0/x")
        self.assertEqual(spec.endpoint_id, "G07-007")

    def test_result_counters_default_zero(self):
        r = CollectionResult(endpoint_id="X")
        self.assertEqual(r.pages, 0)
        self.assertEqual(r.rows, 0)
        self.assertEqual(r.retry_count, 0)
        self.assertEqual(r.error_classification, None)
        self.assertEqual(r.status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
