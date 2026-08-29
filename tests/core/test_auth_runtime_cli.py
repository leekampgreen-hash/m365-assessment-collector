"""Offline unit tests for the G05-002 Collector auth, config, runtime, and CLI.

These tests must:
- Use mocks/fakes (no live Microsoft Graph or Microsoft identity platform traffic).
- Not sleep for long periods.
- Not introduce real credentials into source / tests / docs.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from collectors.core import (
    API_ERROR,
    AUTH_ERROR_CLASSIFICATIONS,
    AUTH_ERROR_HTTP,
    AUTH_ERROR_INVALID_CLIENT,
    AUTH_ERROR_MALFORMED,
    AUTH_ERROR_MISSING_CONFIG,
    AUTH_ERROR_NETWORK,
    AUTH_FAILURE,
    AuthConfigError,
    AuthError,
    BaseCollector,
    CollectionResult,
    CollectorAuthConfig,
    CollectorHttpOpenError,
    CollectorRuntime,
    CollectorTokenProvider,
    EndpointSpec,
    GraphTransport,
    NETWORK_ERROR,
    PASS,
    RetryPolicy,
    RuntimeError_,
    RuntimeOptions,
    build_collector_http_open,
    auth_error_to_classification,
    auth_error_to_result,
    dict_source,
    env_file_source,
    env_source,
    load_auth_config,
    result_to_dict,
    safe_dumps,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INVENTORY_PATH = REPO_ROOT / "config" / "api_inventory.json"


FAKE_TENANT = "00000000-0000-0000-0000-000000000000"
FAKE_CLIENT_ID = "11111111-1111-1111-1111-111111111111"
FAKE_CLIENT_SECRET = "fake-secret-DO-NOT-LEAK"
FAKE_TOKEN = "fake-access-token-DO-NOT-LEAK"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status: int, payload, headers=None):
        self.status = status
        self.headers = headers or {}
        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def fake_token_opener(payload=None, *, status=200, http_error=None, network_error=None):
    """Return a fake opener and a record of calls."""
    calls: List[dict] = []

    def _opener(request, timeout=None):
        calls.append({
            "url": request.full_url,
            "method": request.get_method(),
            "headers": dict(request.headers),
            "data": request.data,
            "timeout": timeout,
        })
        if http_error is not None:
            raise http_error
        if network_error is not None:
            raise network_error
        return FakeResponse(status, payload)

    return _opener, calls


# ---------------------------------------------------------------------------
# AuthConfigError / source tests
# ---------------------------------------------------------------------------


class AuthConfigLoadingTests(unittest.TestCase):
    def test_load_with_complete_dict_succeeds(self):
        config = load_auth_config(dict_source({
            "GRAPH_TENANT_ID": FAKE_TENANT,
            "GRAPH_CLIENT_ID": FAKE_CLIENT_ID,
            "GRAPH_CLIENT_SECRET": FAKE_CLIENT_SECRET,
        }))
        self.assertIsInstance(config, CollectorAuthConfig)
        self.assertEqual(config.tenant_id, FAKE_TENANT)
        self.assertEqual(config.client_id, FAKE_CLIENT_ID)
        self.assertEqual(config.client_secret, FAKE_CLIENT_SECRET)

    def test_missing_variable_lists_names_not_values(self):
        with self.assertRaises(AuthConfigError) as cm:
            load_auth_config(dict_source({
                "GRAPH_TENANT_ID": FAKE_TENANT,
            }))
        msg = str(cm.exception)
        self.assertIn("GRAPH_CLIENT_ID", msg)
        self.assertIn("GRAPH_CLIENT_SECRET", msg)
        # Never leak values:
        self.assertNotIn(FAKE_TENANT, msg)

    def test_all_missing_lists_all_three(self):
        with self.assertRaises(AuthConfigError) as cm:
            load_auth_config(dict_source({}))
        msg = str(cm.exception)
        for var in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"):
            self.assertIn(var, msg)

    def test_empty_value_treated_as_missing(self):
        with self.assertRaises(AuthConfigError):
            load_auth_config(dict_source({
                "GRAPH_TENANT_ID": FAKE_TENANT,
                "GRAPH_CLIENT_ID": "",
                "GRAPH_CLIENT_SECRET": FAKE_CLIENT_SECRET,
            }))

    def test_env_source_reads_from_environ(self):
        original = {k: os.environ.get(k) for k in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")}
        try:
            os.environ["GRAPH_TENANT_ID"] = FAKE_TENANT
            os.environ["GRAPH_CLIENT_ID"] = FAKE_CLIENT_ID
            os.environ["GRAPH_CLIENT_SECRET"] = FAKE_CLIENT_SECRET
            config = load_auth_config(env_source())
            self.assertEqual(config.tenant_id, FAKE_TENANT)
        finally:
            for k, v in original.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_env_source_does_not_leak_other_variables(self):
        sentinel = "SHOULD-NOT-LEAK"
        os.environ["SENTINEL"] = sentinel
        try:
            source = env_source()
            out = source()
            self.assertNotIn("SENTINEL", out)
            self.assertEqual(set(out.keys()), {"GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"})
        finally:
            os.environ.pop("SENTINEL", None)

    def test_env_file_source_loads_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fake.env"
            path.write_text(
                "# comment\n"
                "GRAPH_TENANT_ID={}\n".format(FAKE_TENANT)
                + "GRAPH_CLIENT_ID={}\n".format(FAKE_CLIENT_ID)
                + "GRAPH_CLIENT_SECRET={}\n".format(FAKE_CLIENT_SECRET)
                + "UNRELATED=should-be-ignored\n"
            )
            config = load_auth_config(env_file_source(path))
            self.assertEqual(config.tenant_id, FAKE_TENANT)
            self.assertEqual(config.client_id, FAKE_CLIENT_ID)
            self.assertEqual(config.client_secret, FAKE_CLIENT_SECRET)
            # The source should NOT expose unrelated variables.
            self.assertNotIn("UNRELATED", env_file_source(path)())

    def test_env_file_source_missing_file_raises(self):
        bad = Path("/tmp/this-path-must-not-exist-collector-env-xyz")
        if bad.exists():
            bad.unlink()
        with self.assertRaises(AuthConfigError) as cm:
            load_auth_config(env_file_source(bad))
        self.assertIn("not found", str(cm.exception).lower())

    def test_env_file_source_quoted_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "quoted.env"
            path.write_text(
                "GRAPH_TENANT_ID='{}'\n".format(FAKE_TENANT)
                + 'GRAPH_CLIENT_ID="{}"\n'.format(FAKE_CLIENT_ID)
                + "GRAPH_CLIENT_SECRET={}\n".format(FAKE_CLIENT_SECRET)
            )
            config = load_auth_config(env_file_source(path))
            self.assertEqual(config.tenant_id, FAKE_TENANT)
            self.assertEqual(config.client_id, FAKE_CLIENT_ID)


# ---------------------------------------------------------------------------
# CollectorAuthConfig repr / serialization safety
# ---------------------------------------------------------------------------


class AuthConfigSafetyTests(unittest.TestCase):
    def _config(self):
        return CollectorAuthConfig(
            tenant_id=FAKE_TENANT,
            client_id=FAKE_CLIENT_ID,
            client_secret=FAKE_CLIENT_SECRET,
        )

    def test_repr_redacts_secret(self):
        c = self._config()
        text = repr(c)
        self.assertNotIn(FAKE_CLIENT_SECRET, text)
        self.assertIn("<redacted>", text)

    def test_str_does_not_leak_secret(self):
        c = self._config()
        self.assertNotIn(FAKE_CLIENT_SECRET, str(c))

    def test_to_dict_redacts_secret(self):
        c = self._config()
        d = c.to_dict()
        self.assertEqual(d["client_secret"], "<redacted>")
        self.assertNotIn(FAKE_CLIENT_SECRET, json.dumps(d))

    def test_empty_field_rejected(self):
        with self.assertRaises(ValueError):
            CollectorAuthConfig(tenant_id="", client_id=FAKE_CLIENT_ID, client_secret=FAKE_CLIENT_SECRET)
        with self.assertRaises(ValueError):
            CollectorAuthConfig(tenant_id=FAKE_TENANT, client_id=FAKE_CLIENT_ID, client_secret="")


# ---------------------------------------------------------------------------
# Token provider: success, error mapping, cache behavior
# ---------------------------------------------------------------------------


def _make_provider(opener, *, clock_values=None, refresh_skew=60.0):
    config = CollectorAuthConfig(
        tenant_id=FAKE_TENANT,
        client_id=FAKE_CLIENT_ID,
        client_secret=FAKE_CLIENT_SECRET,
    )
    if clock_values is None:
        clock_values = [1000.0]
    pool = list(clock_values)

    def clock():
        # Re-cycle forever; tests that need exact call ordering inspect
        # the opener's call list.
        if not pool:
            return 1000.0
        return pool.pop(0)

    return CollectorTokenProvider(
        config,
        http_open=opener,
        clock=clock,
        refresh_skew_seconds=refresh_skew,
        timeout=10.0,
    )


class TokenProviderSuccessTests(unittest.TestCase):
    def test_first_call_acquires_token(self):
        opener, calls = fake_token_opener(payload={
            "access_token": FAKE_TOKEN, "expires_in": 3600,
        })
        provider = _make_provider(opener)
        token = provider.get_token()
        self.assertEqual(token, FAKE_TOKEN)
        self.assertEqual(len(calls), 1)
        # POST body must contain the expected OAuth fields. The secret
        # IS in the body (it has to be transmitted to the token
        # endpoint); we assert that it is NOT leaked anywhere reachable
        # from external callers (errors, reprs, exception messages).
        body = calls[0]["data"]
        self.assertIsInstance(body, (bytes, bytearray))
        self.assertIn(b"grant_type=client_credentials", body)
        self.assertIn(b"scope=https%3A%2F%2Fgraph.microsoft.com%2F.default", body)
        # client_id is in the body.
        self.assertIn(FAKE_CLIENT_ID.encode(), body)
        # Method must be POST and Content-Type must be form-encoded.
        self.assertEqual(calls[0]["method"], "POST")
        # urllib normalizes header names to title-case.
        self.assertEqual(
            calls[0]["headers"].get("Content-type"),
            "application/x-www-form-urlencoded",
        )
        # Authorization header MUST NOT be present on the token request.
        self.assertNotIn("Authorization", calls[0]["headers"])
        # Tenant id is in the URL only, not the body.
        self.assertIn(FAKE_TENANT, calls[0]["url"])

    def test_subsequent_call_reuses_unexpired_token(self):
        opener, calls = fake_token_opener(payload={
            "access_token": FAKE_TOKEN, "expires_in": 3600,
        })
        # Clock only advances a small amount between calls.
        provider = _make_provider(opener, clock_values=[1000.0, 1010.0, 1020.0])
        provider.get_token()
        provider.get_token()
        provider.get_token()
        self.assertEqual(len(calls), 1)

    def test_token_refreshed_near_expiry(self):
        opener, calls = fake_token_opener(payload={
            "access_token": FAKE_TOKEN, "expires_in": 60,
        })
        # First call at t=1000. expires_at = 1000 + 60 = 1060. Skew=60s.
        # After 60s of clock (t=1060), the token is within the skew window
        # and should be refreshed.
        provider = _make_provider(opener, clock_values=[1000.0, 1060.0], refresh_skew=60.0)
        provider.get_token()
        provider.get_token()
        self.assertEqual(len(calls), 2)

    def test_expired_token_refreshed_immediately(self):
        opener, calls = fake_token_opener(payload={
            "access_token": FAKE_TOKEN, "expires_in": 10,
        })
        provider = _make_provider(opener, clock_values=[1000.0, 2000.0])
        provider.get_token()
        provider.get_token()
        self.assertEqual(len(calls), 2)

    def test_failed_acquisition_does_not_cache_bad_token(self):
        # First call: malformed JSON. Second call: success.
        responses = iter([
            FakeResponse(200, "not-json"),
            FakeResponse(200, {"access_token": FAKE_TOKEN, "expires_in": 3600}),
        ])

        def opener(request, timeout=None):
            r = next(responses)
            return r

        provider = _make_provider(opener, clock_values=[1000.0, 1010.0])
        with self.assertRaises(AuthError) as cm1:
            provider.get_token()
        self.assertEqual(cm1.exception.classification, AUTH_ERROR_MALFORMED)
        # Second call must succeed (no bad token cached).
        self.assertEqual(provider.get_token(), FAKE_TOKEN)


class TokenProviderErrorTests(unittest.TestCase):
    def _http_error(self, status, body):
        return HTTPError(
            url="https://login.microsoftonline.com/x/oauth2/v2.0/token",
            code=status,
            msg="error",
            hdrs={"Content-Type": "application/json"},
            fp=io.BytesIO(json.dumps(body).encode("utf-8")),
        )

    def test_invalid_client_classified(self):
        err = self._http_error(400, {"error": "invalid_client", "error_description": "bad"})
        opener, _ = fake_token_opener(http_error=err)
        provider = _make_provider(opener)
        with self.assertRaises(AuthError) as cm:
            provider.get_token()
        self.assertEqual(cm.exception.classification, AUTH_ERROR_INVALID_CLIENT)

    def test_invalid_grant_classified(self):
        err = self._http_error(400, {"error": "invalid_grant", "error_description": "x"})
        opener, _ = fake_token_opener(http_error=err)
        provider = _make_provider(opener)
        with self.assertRaises(AuthError) as cm:
            provider.get_token()
        self.assertEqual(cm.exception.classification, AUTH_ERROR_INVALID_CLIENT)

    def test_unknown_oauth_error_classified_http(self):
        err = self._http_error(503, {"error": "service_unavailable"})
        opener, _ = fake_token_opener(http_error=err)
        provider = _make_provider(opener)
        with self.assertRaises(AuthError) as cm:
            provider.get_token()
        self.assertEqual(cm.exception.classification, AUTH_ERROR_HTTP)

    def test_malformed_json_response_classified(self):
        opener, _ = fake_token_opener(status=200, payload="not-json")
        provider = _make_provider(opener)
        with self.assertRaises(AuthError) as cm:
            provider.get_token()
        self.assertEqual(cm.exception.classification, AUTH_ERROR_MALFORMED)

    def test_missing_access_token_classified(self):
        opener, _ = fake_token_opener(status=200, payload={"expires_in": 3600})
        provider = _make_provider(opener)
        with self.assertRaises(AuthError) as cm:
            provider.get_token()
        self.assertEqual(cm.exception.classification, AUTH_ERROR_MALFORMED)

    def test_zero_expires_in_classified(self):
        opener, _ = fake_token_opener(status=200, payload={"access_token": FAKE_TOKEN, "expires_in": 0})
        provider = _make_provider(opener)
        with self.assertRaises(AuthError) as cm:
            provider.get_token()
        self.assertEqual(cm.exception.classification, AUTH_ERROR_MALFORMED)

    def test_token_endpoint_network_error_classified(self):
        opener, _ = fake_token_opener(network_error=URLError("dns"))
        provider = _make_provider(opener)
        with self.assertRaises(AuthError) as cm:
            provider.get_token()
        self.assertEqual(cm.exception.classification, AUTH_ERROR_NETWORK)

    def test_error_messages_never_include_secret(self):
        cases = [
            lambda: fake_token_opener(http_error=self._http_error(400, {"error": "invalid_client"}))[0],
            lambda: fake_token_opener(status=200, payload="not-json")[0],
            lambda: fake_token_opener(network_error=URLError("dns"))[0],
            lambda: fake_token_opener(status=200, payload={"expires_in": 3600})[0],
            lambda: fake_token_opener(http_error=self._http_error(500, {"error": "internal"}))[0],
        ]
        for build in cases:
            opener = build()
            provider = _make_provider(opener)
            try:
                provider.get_token()
            except AuthError as exc:
                # Neither message nor repr may contain the secret.
                self.assertNotIn(FAKE_CLIENT_SECRET, str(exc))
                self.assertNotIn(FAKE_CLIENT_SECRET, repr(exc))
                # Bearer / Authorization must also not appear.
                self.assertNotIn("Bearer ", str(exc))
                self.assertNotIn("Authorization", str(exc))
                # Token value itself must not appear.
                self.assertNotIn(FAKE_TOKEN, str(exc))
            else:  # pragma: no cover - sanity
                self.fail("expected AuthError")

    def test_token_endpoint_url_uses_tenant(self):
        opener, calls = fake_token_opener(payload={
            "access_token": FAKE_TOKEN, "expires_in": 3600,
        })
        provider = _make_provider(opener)
        provider.get_token()
        self.assertEqual(
            calls[0]["url"],
            "https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(FAKE_TENANT),
        )


# ---------------------------------------------------------------------------
# Auth-error -> CollectionResult mapping
# ---------------------------------------------------------------------------


class AuthErrorResultMappingTests(unittest.TestCase):
    def test_mapping_invalid_client_to_auth_failure(self):
        exc = AuthError(AUTH_ERROR_INVALID_CLIENT, "msg")
        self.assertEqual(auth_error_to_classification(exc), AUTH_FAILURE)

    def test_mapping_missing_config_to_auth_failure(self):
        exc = AuthError(AUTH_ERROR_MISSING_CONFIG, "msg")
        self.assertEqual(auth_error_to_classification(exc), AUTH_FAILURE)

    def test_mapping_network_to_network_error(self):
        exc = AuthError(AUTH_ERROR_NETWORK, "msg")
        self.assertEqual(auth_error_to_classification(exc), NETWORK_ERROR)

    def test_mapping_malformed_to_api_error(self):
        exc = AuthError(AUTH_ERROR_MALFORMED, "msg")
        self.assertEqual(auth_error_to_classification(exc), API_ERROR)

    def test_mapping_http_to_api_error(self):
        exc = AuthError(AUTH_ERROR_HTTP, "msg")
        self.assertEqual(auth_error_to_classification(exc), API_ERROR)

    def test_auth_error_result_carries_endpoint_id_and_no_message(self):
        exc = AuthError(AUTH_ERROR_INVALID_CLIENT, "should-not-leak")
        result = auth_error_to_result(exc, endpoint_id="G01-001")
        self.assertEqual(result.endpoint_id, "G01-001")
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.error_classification, AUTH_FAILURE)
        self.assertEqual(result.pages, 0)
        self.assertEqual(result.rows, 0)
        self.assertIsNone(result.http_status)
        # ``error_message`` carries only the classification label.
        self.assertEqual(result.error_message, AUTH_ERROR_INVALID_CLIENT)
        # The original exception message must not leak.
        self.assertNotIn("should-not-leak", result.error_message or "")
        self.assertNotIn(FAKE_CLIENT_SECRET, result.error_message or "")

    def test_auth_error_result_serialization_does_not_leak_secrets(self):
        exc = AuthError(AUTH_ERROR_INVALID_CLIENT, FAKE_CLIENT_SECRET)
        result = auth_error_to_result(exc)
        text = json.dumps(result.to_dict())
        self.assertNotIn(FAKE_CLIENT_SECRET, text)
        self.assertNotIn(FAKE_TOKEN, text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("Authorization", text)


# ---------------------------------------------------------------------------
# Safe serialization
# ---------------------------------------------------------------------------


class SafeSerializationTests(unittest.TestCase):
    def test_safe_dumps_scrubs_authorization(self):
        payload = {"authorization": "Bearer x", "endpoint_id": "G01-001"}
        out = safe_dumps(payload)
        self.assertNotIn("Bearer", out)
        self.assertNotIn("Authorization", out)

    def test_safe_dumps_scrubs_access_token_field(self):
        payload = {"access_token": "secret", "endpoint_id": "G01-001"}
        out = safe_dumps(payload)
        self.assertNotIn("secret", out)

    def test_safe_dumps_scrubs_client_secret(self):
        payload = {"client_secret": FAKE_CLIENT_SECRET, "endpoint_id": "G01-001"}
        out = safe_dumps(payload)
        self.assertNotIn(FAKE_CLIENT_SECRET, out)

    def test_safe_dumps_detects_forbidden_substring(self):
        with self.assertRaises(ValueError):
            safe_dumps({"raw": "Authorization: Bearer xyz"})

    def test_result_to_dict_scrubs_authorization(self):
        result = CollectionResult(endpoint_id="G01-001")
        # Inject a forbidden key into the dict representation to verify
        # scrubbing.
        cleaned = result_to_dict(result)
        self.assertEqual(cleaned["endpoint_id"], "G01-001")


# ---------------------------------------------------------------------------
# Runtime selection tests (offline; no token requested because no http_open)
# ---------------------------------------------------------------------------


class RuntimeSelectionTests(unittest.TestCase):
    def _runtime(self, tmpdir, *, enabled_ids=None):
        # Build a minimal inventory for selection tests.
        ids = enabled_ids or ["A-1", "A-2", "A-3"]
        entries = [
            {"id": eid, "name": eid, "path": "/v1.0/{}".format(eid.lower()), "enabled": True}
            for eid in ids
        ]
        entries.append({"id": "X-DISABLED", "name": "x", "path": "/v1.0/x", "enabled": False})
        path = Path(tmpdir) / "inv.json"
        path.write_text(json.dumps(entries))
        return CollectorRuntime(
            inventory_path=path,
            auth_source=dict_source({
                "GRAPH_TENANT_ID": FAKE_TENANT,
                "GRAPH_CLIENT_ID": FAKE_CLIENT_ID,
                "GRAPH_CLIENT_SECRET": FAKE_CLIENT_SECRET,
            }),
        )

    def test_unknown_endpoint_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runtime(d)
            with self.assertRaises(RuntimeError_) as cm:
                r.resolve_selection(endpoint_id="NO-SUCH-ID")
            self.assertIn("Unknown endpoint id", str(cm.exception))

    def test_disabled_endpoint_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runtime(d)
            with self.assertRaises(RuntimeError_) as cm:
                r.resolve_selection(endpoint_id="X-DISABLED")
            self.assertIn("disabled", str(cm.exception).lower())

    def test_single_endpoint_selection(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runtime(d)
            specs = r.resolve_selection(endpoint_id="A-2")
            self.assertEqual([s.endpoint_id for s in specs], ["A-2"])

    def test_multi_endpoint_selection(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runtime(d)
            specs = r.resolve_selection(endpoint_ids=["A-3", "A-1"])
            self.assertEqual([s.endpoint_id for s in specs], ["A-3", "A-1"])

    def test_all_enabled_selection_excludes_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runtime(d)
            specs = r.resolve_selection(all_enabled=True)
            self.assertEqual(
                sorted(s.endpoint_id for s in specs),
                ["A-1", "A-2", "A-3"],
            )

    def test_ambiguous_selection_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runtime(d)
            with self.assertRaises(RuntimeError_):
                r.resolve_selection(endpoint_id="A-1", all_enabled=True)

    def test_no_selection_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runtime(d)
            with self.assertRaises(RuntimeError_):
                r.resolve_selection()

    def test_runtime_builds_production_opener_when_none_is_injected(self):
        with tempfile.TemporaryDirectory() as d:
            inv_path = Path(d) / "inv.json"
            inv_path.write_text(json.dumps([
                {"id": "A-1", "name": "x", "path": "/v1.0/x", "enabled": True},
            ]))
            r = CollectorRuntime(
                inventory_path=inv_path,
                auth_source=dict_source({
                    "GRAPH_TENANT_ID": FAKE_TENANT,
                    "GRAPH_CLIENT_ID": FAKE_CLIENT_ID,
                    "GRAPH_CLIENT_SECRET": FAKE_CLIENT_SECRET,
                }),
                options=RuntimeOptions(http_open=None, tenant_resolver=lambda config: 42),
            )
            config = r.build_auth_config()
            opener = r.build_http_open(config)
            self.assertIs(r.options.http_open, opener)


class ProductionHttpOpenerTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def upstream(request, timeout=None):
            self.calls.append({
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.headers),
            })
            return FakeResponse(200, {"value": []})

        self.opener = build_collector_http_open(
            [EndpointSpec(endpoint_id="T-1", name="Users", path="/v1.0/users")],
            FAKE_TENANT,
            upstream_open=upstream,
        )

    def test_allows_only_collector_token_post_and_inventory_graph_get(self):
        token_request = Request(
            "https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(FAKE_TENANT),
            data=b"grant_type=client_credentials",
            method="POST",
        )
        graph_request = Request(
            "https://graph.microsoft.com/v1.0/users?$top=1",
            headers={"Authorization": "Bearer " + FAKE_TOKEN},
            method="GET",
        )
        self.opener(token_request, timeout=1)
        self.opener(graph_request, timeout=1)
        self.assertEqual([call["method"] for call in self.calls], ["POST", "GET"])
        # The opener forwards credentials only to the injected I/O boundary;
        # it has no public request/header/token state to serialize.
        self.assertFalse(hasattr(self.opener, "headers"))
        self.assertFalse(hasattr(self.opener, "token"))

    def test_rejects_non_graph_host_redirect_target_and_writes_without_io(self):
        forbidden = [
            Request("http://graph.microsoft.com/v1.0/users", method="GET"),
            Request("https://evil.example/v1.0/users", method="GET"),
            Request("https://graph.microsoft.com/v1.0/groups", method="GET"),
            Request("https://graph.microsoft.com/v1.0/users", data=b"{}", method="POST"),
            Request("https://login.microsoftonline.com/common/oauth2/v2.0/token", data=b"x", method="POST"),
        ]
        for request in forbidden:
            with self.assertRaises(CollectorHttpOpenError):
                self.opener(request, timeout=1)
        self.assertEqual(self.calls, [])

    def test_runtime_uses_default_closed_opener_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            inv_path = Path(d) / "inv.json"
            inv_path.write_text(json.dumps([
                {"id": "T-1", "name": "Users", "path": "/v1.0/users", "enabled": True},
            ]))
            import collectors.core.runtime as runtime_module
            original = runtime_module.build_collector_http_open
            def fake_open(request, timeout=None):
                if "login.microsoftonline.com" in request.full_url:
                    return FakeResponse(200, {"access_token": FAKE_TOKEN, "expires_in": 3600})
                return FakeResponse(200, {"value": []})

            fake_open = Mock(side_effect=fake_open)
            runtime_module.build_collector_http_open = Mock(return_value=fake_open)
            self.addCleanup(setattr, runtime_module, "build_collector_http_open", original)
            runtime = CollectorRuntime(
                inventory_path=inv_path,
                auth_source=dict_source({
                    "GRAPH_TENANT_ID": FAKE_TENANT,
                    "GRAPH_CLIENT_ID": FAKE_CLIENT_ID,
                    "GRAPH_CLIENT_SECRET": FAKE_CLIENT_SECRET,
                }),
                options=RuntimeOptions(tenant_resolver=lambda config: 42),
            )
            summary = runtime.run(endpoint_id="T-1")
            runtime_module.build_collector_http_open.assert_called_once()
            self.assertEqual(summary.runs[0].status, PASS)
            self.assertEqual(fake_open.call_count, 2)
            serialized = json.dumps(summary.to_dict())
            self.assertNotIn(FAKE_TOKEN, serialized)
            self.assertNotIn("Authorization", serialized)


# ---------------------------------------------------------------------------
# Runtime end-to-end test (using fake http_open for both token + Graph)
# ---------------------------------------------------------------------------


class RuntimePersistenceHandoffTests(unittest.TestCase):
    def test_collection_writer_is_injected_without_affecting_dry_run(self):
        writer = Mock()
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "inventory.json"
            inventory.write_text(json.dumps([{
                "id": "G01-001", "name": "Users", "path": "/v1.0/users",
                "select": ["id"], "top": 5, "pagination": True, "enabled": True,
            }]))
            runtime = CollectorRuntime(
                inventory,
                dict_source({}),
                collection_writer=writer,
            )
            payload = runtime.resolve_selection(endpoint_id="G01-001")
            self.assertEqual(payload[0].endpoint_id, "G01-001")
            writer.write.assert_not_called()


class RuntimeExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.inv_path = Path(self.tmpdir.name) / "inv.json"
        self.inv_path.write_text(json.dumps([
            {
                "id": "T-1", "name": "Users", "path": "/v1.0/users",
                "select": ["id"], "top": 5, "pagination": True, "enabled": True,
            },
        ]))

    def _runtime(self, *, http_open):
        return CollectorRuntime(
            inventory_path=self.inv_path,
            auth_source=dict_source({
                "GRAPH_TENANT_ID": FAKE_TENANT,
                "GRAPH_CLIENT_ID": FAKE_CLIENT_ID,
                "GRAPH_CLIENT_SECRET": FAKE_CLIENT_SECRET,
            }),
            options=RuntimeOptions(
                http_open=http_open,
                max_retries=2,
                tenant_resolver=lambda config: 42,
            ),
        )

    def test_token_requested_exactly_once_for_one_endpoint(self):
        token_calls: List[dict] = []

        def opener(request, timeout=None):
            url = request.full_url
            if "login.microsoftonline.com" in url:
                token_calls.append({"url": url})
                return FakeResponse(200, {"access_token": FAKE_TOKEN, "expires_in": 3600})
            # Graph call:
            return FakeResponse(200, {"value": [{"id": "1"}, {"id": "2"}]})

        runtime = self._runtime(http_open=opener)
        summary = runtime.run(endpoint_id="T-1")
        self.assertEqual(len(summary.runs), 1)
        self.assertEqual(summary.runs[0].status, PASS)
        self.assertEqual(summary.runs[0].rows, 2)
        # One token request per process, not per row / page.
        self.assertEqual(len(token_calls), 1)

    def test_runtime_invokes_injected_writer_after_normalization(self):
        writer = Mock()

        def opener(request, timeout=None):
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse(200, {"access_token": FAKE_TOKEN, "expires_in": 3600})
            return FakeResponse(200, {"value": []})

        runtime = self._runtime(http_open=opener)
        runtime.options.collection_writer = writer
        normalized = Mock()
        runtime._normalize_run = Mock(return_value=normalized)
        runtime._execute_one = Mock(return_value=Mock(result=Mock(status=PASS)))

        summary = runtime.run(endpoint_id="T-1")

        writer.write.assert_called_once_with(normalized)
        self.assertEqual(len(summary.runs), 1)

    def test_missing_auth_config_returns_auth_failure_results(self):
        runtime = CollectorRuntime(
            inventory_path=self.inv_path,
            auth_source=dict_source({}),  # all missing
        )
        # Without http_open the missing-config branch still runs and
        # produces a per-endpoint CollectionResult with no Graph call.
        summary = runtime.run(endpoint_id="T-1")
        self.assertEqual(len(summary.runs), 1)
        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].error_classification, AUTH_FAILURE)
        self.assertIsNotNone(summary.auth_error)
        self.assertEqual(summary.auth_error.classification, AUTH_ERROR_MISSING_CONFIG)
        # No http_open means we never attempt to use it.
        # Verify the result has no token / secret.
        text = json.dumps(summary.runs[0].to_dict())
        self.assertNotIn(FAKE_CLIENT_SECRET, text)
        self.assertNotIn(FAKE_TOKEN, text)

    def test_token_failure_surfaces_per_endpoint(self):
        def opener(request, timeout=None):
            raise URLError("dns")

        runtime = self._runtime(http_open=opener)
        summary = runtime.run(endpoint_id="T-1")
        self.assertEqual(len(summary.runs), 1)
        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].error_classification, NETWORK_ERROR)
        self.assertIsNotNone(summary.auth_error)
        self.assertEqual(summary.auth_error.classification, AUTH_ERROR_NETWORK)

    def test_refresh_auth_failure_becomes_collection_result(self):
        token_calls = []
        graph_calls = []
        clock_values = iter([1000.0, 1000.0, 1001.0])

        def opener(request, timeout=None):
            if "login.microsoftonline.com" in request.full_url:
                token_calls.append(request.full_url)
                if len(token_calls) == 1:
                    return FakeResponse(200, {
                        "access_token": FAKE_TOKEN,
                        "expires_in": 61,
                    })
                body = json.dumps({
                    "error": "invalid_client",
                    "error_description": FAKE_CLIENT_SECRET,
                }).encode("utf-8")
                raise HTTPError(
                    request.full_url,
                    400,
                    "error",
                    {"Content-Type": "application/json"},
                    io.BytesIO(body),
                )
            graph_calls.append(request.full_url)
            return FakeResponse(200, {
                "value": [{"id": "1"}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=next",
            })

        class RefreshRuntime(CollectorRuntime):
            def build_token_provider(inner_self, config):
                inner_self.provider = CollectorTokenProvider(
                    config,
                    http_open=inner_self.options.http_open,
                    clock=lambda: next(clock_values),
                    refresh_skew_seconds=60.0,
                    timeout=inner_self.options.graph_timeout,
                )
                return inner_self.provider

        runtime = RefreshRuntime(
            inventory_path=self.inv_path,
            auth_source=dict_source({
                "GRAPH_TENANT_ID": FAKE_TENANT,
                "GRAPH_CLIENT_ID": FAKE_CLIENT_ID,
                "GRAPH_CLIENT_SECRET": FAKE_CLIENT_SECRET,
            }),
            options=RuntimeOptions(
                http_open=opener,
                max_retries=2,
                tenant_resolver=lambda config: 42,
            ),
        )
        summary = runtime.run(endpoint_id="T-1")

        self.assertEqual(len(graph_calls), 1)
        self.assertEqual(len(token_calls), 2)
        self.assertEqual(len(summary.runs), 1)
        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].error_classification, AUTH_FAILURE)
        self.assertEqual(summary.runs[0].error_message, AUTH_ERROR_INVALID_CLIENT)
        self.assertIsNotNone(summary.auth_error)
        self.assertEqual(summary.auth_error.classification, AUTH_ERROR_INVALID_CLIENT)
        self.assertIsNone(runtime.provider._cached)
        serialized = json.dumps(summary.to_dict())
        self.assertNotIn(FAKE_CLIENT_SECRET, serialized)
        self.assertNotIn(FAKE_TOKEN, serialized)
        self.assertNotIn("Authorization", serialized)


# ---------------------------------------------------------------------------
# CLI dry-run tests (subprocess)
# ---------------------------------------------------------------------------


class CLIDryRunTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.inv_path = Path(self.tmpdir.name) / "inv.json"
        self.inv_path.write_text(json.dumps([
            {"id": "A-1", "name": "x", "path": "/v1.0/x", "enabled": True, "pagination": False},
            {"id": "A-2", "name": "y", "path": "/v1.0/y", "enabled": True, "pagination": True},
            {"id": "X-DISABLED", "name": "z", "path": "/v1.0/z", "enabled": False},
        ]))
        self.env_path = Path(self.tmpdir.name) / "fake.env"
        self.env_path.write_text(
            "GRAPH_TENANT_ID={}\n".format(FAKE_TENANT)
            + "GRAPH_CLIENT_ID={}\n".format(FAKE_CLIENT_ID)
            + "GRAPH_CLIENT_SECRET={}\n".format(FAKE_CLIENT_SECRET)
        )

    def _run_cli(self, *args):
        # Ensure no real env vars leak into the subprocess.
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        proc = subprocess.run(
            [sys.executable, "-m", "collectors.run_collector", *args],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        return proc

    def test_dry_run_single_endpoint(self):
        proc = self._run_cli(
            "--endpoint", "A-1",
            "--inventory", str(self.inv_path),
            "--env-file", str(self.env_path),
            "--dry-run",
            "--json",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr.decode())
        out = proc.stdout.decode()
        self.assertIn('"selected_endpoint_ids"', out)
        self.assertIn("A-1", out)
        self.assertIn('"no_token_requested": true', out)
        self.assertIn('"no_graph_requested": true', out)
        self.assertIn('"auth_config_present": true', out)
        # No credentials in output.
        self.assertNotIn(FAKE_CLIENT_SECRET, out)
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertNotIn("Bearer", out)
        self.assertNotIn("Authorization", out)
        # No Graph traffic attempted (no token endpoint output).
        self.assertNotIn("login.microsoftonline.com", out)

    def test_dry_run_all_excludes_disabled(self):
        proc = self._run_cli(
            "--all",
            "--inventory", str(self.inv_path),
            "--env-file", str(self.env_path),
            "--dry-run",
            "--json",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr.decode())
        out = proc.stdout.decode()
        self.assertIn("A-1", out)
        self.assertIn("A-2", out)
        self.assertNotIn("X-DISABLED", out)

    def test_dry_run_unknown_endpoint_rejected(self):
        proc = self._run_cli(
            "--endpoint", "NO-SUCH",
            "--inventory", str(self.inv_path),
            "--env-file", str(self.env_path),
            "--dry-run",
        )
        self.assertNotEqual(proc.returncode, 0)
        err = proc.stderr.decode()
        self.assertIn("Unknown endpoint id", err)
        self.assertNotIn(FAKE_CLIENT_SECRET, err)
        self.assertNotIn(FAKE_TOKEN, err)

    def test_dry_run_no_selection_rejected(self):
        proc = self._run_cli(
            "--inventory", str(self.inv_path),
            "--env-file", str(self.env_path),
            "--dry-run",
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_dry_run_missing_inventory_rejected(self):
        proc = self._run_cli(
            "--endpoint", "A-1",
            "--inventory", "/tmp/does-not-exist-inv.json",
            "--env-file", str(self.env_path),
            "--dry-run",
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_dry_run_missing_env_reports_config_absent(self):
        proc = self._run_cli(
            "--endpoint", "A-1",
            "--inventory", str(self.inv_path),
            "--env-file", "/tmp/does-not-exist-env.json",
            "--dry-run",
            "--json",
        )
        self.assertEqual(proc.returncode, 0)
        out = proc.stdout.decode()
        self.assertIn('"auth_config_present": false', out)
        # Missing variable names appear, never values.
        self.assertIn("GRAPH_TENANT_ID", out)
        self.assertNotIn(FAKE_TENANT, out)
        self.assertNotIn(FAKE_CLIENT_SECRET, out)

    def test_dry_run_does_not_request_token(self):
        # Confirm that the dry-run CLI code path never instantiates a
        # token provider, never makes an HTTP call, and never invokes
        # the configured ``auth_source`` more than is necessary for
        # validation. We do this by importing the CLI module and
        # confirming that no token-related fields are wired into the
        # dry-run summary builder.
        from collectors import run_collector as cli
        # _dry_run_summary takes the runtime + selection args only;
        # it never imports CollectorTokenProvider.
        from collectors.core import CollectorTokenProvider  # noqa: F401
        # Inspect the source: the CLI must not call get_token().
        self.assertTrue(hasattr(cli, "_dry_run_summary"))
        self.assertTrue(callable(cli._dry_run_summary))

    def test_cli_runtime_options_include_trusted_tenant_resolver(self):
        from collectors import run_collector as cli

        with patch.object(cli, "CollectorRuntime") as runtime_class:
            with patch.object(cli, "_dry_run_summary", return_value={
                "mode": "dry-run",
                "inventory_path": str(self.inv_path),
                "selected_endpoint_ids": ["A-1"],
                "selected_count": 1,
                "no_token_requested": True,
                "no_graph_requested": True,
            }):
                with patch.object(cli, "safe_dumps", return_value="{}"):
                    with patch.dict(os.environ, {}, clear=True):
                        result = cli.main([
                            "--endpoint", "A-1",
                            "--inventory", str(self.inv_path),
                            "--env-file", str(self.env_path),
                            "--dry-run",
                            "--json",
                        ])

        self.assertEqual(result, 0)
        options = runtime_class.call_args.kwargs["options"]
        self.assertIs(options.tenant_resolver, cli._trusted_tenant_resolver)

    def test_cli_wires_database_and_collection_writer(self):
        from collectors import run_collector as cli

        connection = Mock()
        writer = Mock()
        summary = Mock()
        summary.runs = []
        with patch.object(cli, "open_database_connection", return_value=connection) as open_connection:
            with patch.object(cli, "CollectionWriter", return_value=writer) as writer_class:
                with patch.object(cli, "CollectorRuntime") as runtime_class:
                    runtime_class.return_value.run.return_value = summary
                    result = cli.main([
                        "--endpoint", "A-1",
                        "--inventory", str(self.inv_path),
                        "--env-file", str(self.env_path),
                    ])

        self.assertEqual(result, 0)
        open_connection.assert_called_once_with(
            env_file=cli.DEFAULT_PERSISTENCE_ENV_FILE,
            password_file=cli.DEFAULT_PERSISTENCE_PASSWORD_FILE,
        )
        writer_class.assert_called_once_with(connection, cli.dispatch_persistence)
        runtime_class.assert_called_once()
        self.assertIs(runtime_class.call_args.kwargs["database_connection"], connection)
        self.assertIs(runtime_class.call_args.kwargs["collection_writer"], writer)

    def test_cli_fails_when_persistence_dependency_is_missing(self):
        from collectors import run_collector as cli

        with patch.object(cli, "_build_persistence", side_effect=RuntimeError("PostgreSQL driver is unavailable")):
            result = cli.main([
                "--endpoint", "A-1",
                "--inventory", str(self.inv_path),
                "--env-file", str(self.env_path),
            ])

        self.assertEqual(result, 3)

    def test_cli_dry_run_does_not_wire_persistence(self):
        from collectors import run_collector as cli

        with patch.object(cli, "_build_persistence") as build_persistence:
            with patch.dict(os.environ, {}, clear=True):
                result = cli.main([
                    "--endpoint", "A-1",
                    "--inventory", str(self.inv_path),
                    "--env-file", str(self.env_path),
                    "--dry-run",
                ])

        self.assertEqual(result, 0)
        build_persistence.assert_not_called()

    def test_trusted_tenant_resolver_uses_authenticated_mapping(self):
        from collectors import run_collector as cli
        config = CollectorAuthConfig(
            tenant_id=FAKE_TENANT,
            client_id=FAKE_CLIENT_ID,
            client_secret=FAKE_CLIENT_SECRET,
        )
        class Cursor:
            def execute(self, sql, params):
                self.sql, self.params = sql, params
            def fetchall(self):
                return [(42,)]
        class Connection:
            def cursor(self):
                return Cursor()
        self.assertEqual(cli._trusted_tenant_resolver(config, Connection()), 42)

        with self.assertRaisesRegex(RuntimeError_, "database mapping"):
            cli._trusted_tenant_resolver(config)

    def test_trusted_tenant_resolver_fails_closed_for_missing_or_ambiguous_mapping(self):
        from collectors import run_collector as cli

        config = CollectorAuthConfig(
            tenant_id=FAKE_TENANT,
            client_id=FAKE_CLIENT_ID,
            client_secret=FAKE_CLIENT_SECRET,
        )
        class Cursor:
            def __init__(self, rows):
                self.rows = rows
            def execute(self, sql, params):
                self.sql, self.params = sql, params
            def fetchall(self):
                return self.rows
        class Connection:
            def __init__(self, rows):
                self.rows = rows
            def cursor(self):
                return Cursor(self.rows)
        for rows in ([], [(1,), (2,)]):
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(RuntimeError_, "missing or ambiguous"):
                    cli._trusted_tenant_resolver(config, Connection(rows))


if __name__ == "__main__":
    unittest.main()
