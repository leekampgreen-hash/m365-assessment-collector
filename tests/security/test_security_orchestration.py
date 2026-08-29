import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from capabilities import EntitlementState
from collectors.core import CollectorRuntime, RuntimeOptions, dict_source
from collectors.security import SecurityOrchestrator
from security.rules.entra_ca_enforcement_001 import RULE_ID


class _Cursor:
    def __init__(self, plans):
        self.plans = plans
    def execute(self, sql, params=None):
        self.sql = sql
    def fetchall(self):
        return [(self.plans,)]


class _Connection:
    def __init__(self, plans):
        self.plans = plans
    def cursor(self):
        return _Cursor(self.plans)


class SecurityOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.inventory = Path(self.directory.name) / "inventory.json"
        self.inventory.write_text(json.dumps([{
            "id": "G01-011", "name": "Conditional Access", "path": "/v1.0/identity/conditionalAccess/policies",
            "documented_permissions": ["Policy.Read.All"], "required_capabilities": ["ENTRA_P1"], "enabled": True,
        }]))
        self.auth = dict_source({"GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret"})

    def _runtime(self, opener):
        return CollectorRuntime(self.inventory, self.auth, options=RuntimeOptions(
            http_open=opener, tenant_resolver=lambda config: 1,
        ))

    def test_not_entitled_skips_before_token_or_graph(self):
        calls = []
        runtime = self._runtime(lambda *args, **kwargs: calls.append(args))
        outcome = SecurityOrchestrator(runtime, _Connection([
            {"servicePlanName": "EXCHANGE_S_STANDARD", "provisioningStatus": "Success"},
        ]), granted_graph_permissions=("Policy.Read.All",)).run(RULE_ID)
        self.assertEqual(outcome["collection"].status, "SKIPPED")
        self.assertEqual(outcome["plan"].decision.value, "SKIP_NOT_LICENSED")
        self.assertEqual(calls, [])
        self.assertIsNone(outcome["finding"])

    def test_unknown_and_missing_permission_skip_before_graph(self):
        for plans, permissions, decision in (
            ([{"servicePlanName": "CUSTOM", "provisioningStatus": "Success"}], ("Policy.Read.All",), "SKIP_CAPABILITY_UNKNOWN"),
            ([{"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"}], (), "SKIP_PERMISSION_REQUIRED"),
        ):
            calls = []
            outcome = SecurityOrchestrator(self._runtime(lambda *args, **kwargs: calls.append(args)), _Connection(plans), granted_graph_permissions=permissions).run(RULE_ID)
            self.assertEqual(outcome["plan"].decision.value, decision)
            self.assertEqual(calls, [])

    def test_entitled_collects_evaluates_and_persists_once(self):
        calls = []
        def opener(request, timeout=None):
            calls.append(request.full_url)
            from tests.core.test_auth_runtime_cli import FakeResponse
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse(200, {"access_token": "token", "expires_in": 3600})
            return FakeResponse(200, {"value": [{"state": "enabled"}]})
        writer = Mock()
        writer.persist_authenticated.return_value = {"observation_id": 1}
        outcome = SecurityOrchestrator(self._runtime(opener), _Connection([
            {"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"},
        ]), granted_graph_permissions=("Policy.Read.All",), persistence_writer=writer).run(RULE_ID)
        self.assertEqual(outcome["collection"].status, "PASS")
        self.assertEqual(outcome["finding"].status.value, "PASS")
        writer.persist_authenticated.assert_called_once()
        self.assertEqual(len([url for url in calls if "graph.microsoft.com" in url]), 1)

    def test_source_failure_evaluates_not_evaluated(self):
        def opener(request, timeout=None):
            from tests.core.test_auth_runtime_cli import FakeResponse
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse(200, {"access_token": "token", "expires_in": 3600})
            raise OSError("offline")
        writer = Mock()
        outcome = SecurityOrchestrator(self._runtime(opener), _Connection([
            {"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"},
        ]), granted_graph_permissions=("Policy.Read.All",), persistence_writer=writer).run(RULE_ID)
        self.assertEqual(outcome["finding"].status.value, "NOT_EVALUATED")
        writer.persist_authenticated.assert_called_once()

    def test_persistence_failure_is_terminal_and_does_not_recollect(self):
        lifecycle = Mock()
        lifecycle.begin_collection_run.return_value = 10
        lifecycle.begin_endpoint_run.return_value = 11
        calls = []
        def opener(request, timeout=None):
            calls.append(request.full_url)
            from tests.core.test_auth_runtime_cli import FakeResponse
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse(200, {"access_token": "token", "expires_in": 3600})
            return FakeResponse(200, {"value": []})
        runtime = self._runtime(opener)
        runtime.options.collection_writer = lifecycle
        persistence = Mock()
        persistence.persist_authenticated.side_effect = RuntimeError("database")
        outcome = SecurityOrchestrator(runtime, _Connection([
            {"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"},
        ]), granted_graph_permissions=("Policy.Read.All",), persistence_writer=persistence).run(RULE_ID)
        self.assertEqual(outcome["collection"].error_classification, "PERSISTENCE_ERROR")
        self.assertEqual(persistence.persist_authenticated.call_count, 2)
        lifecycle.complete_endpoint_run.assert_called_once()
        lifecycle.complete_collection_run.assert_called_once()
        self.assertEqual(len([url for url in calls if "graph.microsoft.com" in url]), 1)

    def test_persistence_retry_reuses_observation_without_second_graph_collection(self):
        calls = []
        def opener(request, timeout=None):
            calls.append(request.full_url)
            from tests.core.test_auth_runtime_cli import FakeResponse
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse(200, {"access_token": "token", "expires_in": 3600})
            return FakeResponse(200, {"value": [{"state": "enabled"}]})
        persistence = Mock()
        persistence.persist_authenticated.side_effect = [RuntimeError("transient"), {"observation_id": 1}]
        outcome = SecurityOrchestrator(self._runtime(opener), _Connection([
            {"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"},
        ]), granted_graph_permissions=("Policy.Read.All",), persistence_writer=persistence).run(RULE_ID)
        self.assertEqual(outcome["collection"].status, "PASS")
        self.assertEqual(persistence.persist_authenticated.call_count, 2)
        self.assertEqual(len([url for url in calls if "graph.microsoft.com" in url]), 1)
