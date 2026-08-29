"""Representative registered Security rule through the real internal path."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from collectors.core import CollectorRuntime, RuntimeOptions, dict_source
from collectors.security import SecurityOrchestrator
from security.rules.entra_ca_enforcement_001 import RULE_ID
from security.rules.entra_ca_legacy_auth_001 import RULE_ID as LEGACY_AUTH_RULE_ID
from tests.core.test_auth_runtime_cli import FakeResponse
from tests.security.test_security_persistence import Connection, Cursor


def tearDownModule() -> None:
    """Keep Scenario import-isolation tests independent of discovery order."""
    for name in (
        "collectors.core.auth", "collectors.core.config", "collectors.core.runtime",
        "collectors.core.transport", "urllib.request",
    ):
        sys.modules.pop(name, None)


class _PipelineCursor(Cursor):
    def execute(self, sql, params):
        if "FROM core.subscribed_sku" in sql:
            self.fetchall_result = [(self.connection.plans,)]
            return
        if sql.startswith("SELECT tenant_id FROM core.tenant"):
            self.fetchall_result = [(7,)]
            return
        return super().execute(sql, params)

    def fetchall(self):
        result = getattr(self, "fetchall_result", [])
        self.fetchall_result = []
        return result


class _PipelineConnection(Connection):
    """Existing Security persistence contract connection plus capability query."""

    def __init__(self, plans: list[dict[str, str]]):
        super().__init__()
        self.plans = plans

    def cursor(self):
        return _PipelineCursor(self)


class SecurityProductionPathIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.inventory = Path(self.directory.name) / "inventory.json"
        self.inventory.write_text(json.dumps([{
            "id": "G01-011", "name": "Conditional Access",
            "path": "/v1.0/identity/conditionalAccess/policies", "method": "GET",
            "auth": "application", "documented_permissions": ["Policy.Read.All"],
            "required_capabilities": ["ENTRA_P1"], "enabled": True,
        }]), encoding="utf-8")

    def _runtime(self, graph_reads: list[str], records=None) -> CollectorRuntime:
        records = records if records is not None else [{"state": "enabled"}]
        def fake_http(request, timeout=None):
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse(200, {"access_token": "token", "expires_in": 3600})
            graph_reads.append(request.full_url)
            return FakeResponse(200, {"value": records})

        return CollectorRuntime(
            self.inventory,
            dict_source({"GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret"}),
            options=RuntimeOptions(http_open=fake_http, tenant_resolver=lambda config: 7),
        )

    def test_registered_rule_uses_real_internal_pipeline_with_fake_graph(self) -> None:
        graph_reads: list[str] = []
        connection = _PipelineConnection([
            {"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"},
        ])

        outcome = SecurityOrchestrator(
            self._runtime(graph_reads), connection,
            granted_graph_permissions=("Policy.Read.All",),
        ).run(RULE_ID)

        self.assertEqual(outcome["plan"].decision.value, "COLLECT")
        self.assertEqual(outcome["collection"].status, "PASS")
        self.assertEqual(outcome["observation"].value["enabled_policy_count"], 1)
        self.assertEqual(outcome["finding"].status.value, "PASS")
        self.assertTrue(outcome["persistence"]["observation_inserted"])
        self.assertEqual(outcome["persistence"]["observation_id"], 11)
        self.assertEqual(outcome["persistence"]["evaluation_id"], 21)
        self.assertTrue(any("INSERT INTO security.finding_current" in sql for sql, _ in connection.sql))
        self.assertEqual(len(graph_reads), 1)
        self.assertIn("graph.microsoft.com", graph_reads[0])
        self.assertGreaterEqual(connection.commits, 1)

    def test_not_entitled_registered_rule_does_not_construct_graph_path(self) -> None:
        graph_reads: list[str] = []
        connection = _PipelineConnection([
            {"servicePlanName": "EXCHANGE_S_STANDARD", "provisioningStatus": "Success"},
        ])

        outcome = SecurityOrchestrator(
            self._runtime(graph_reads), connection,
            granted_graph_permissions=("Policy.Read.All",),
        ).run(RULE_ID)

        self.assertEqual(outcome["plan"].decision.value, "SKIP_NOT_LICENSED")
        self.assertEqual(outcome["collection"].status, "SKIPPED")
        self.assertEqual(outcome["collection"].capability_decision, "SKIP_NOT_LICENSED")
        self.assertIsNone(outcome["observation"])
        self.assertIsNone(outcome["finding"])
        self.assertEqual(graph_reads, [])
        self.assertEqual(connection.sql, [])

    def test_rule11_production_path_pass_open_and_not_evaluated(self) -> None:
        cases = (
            ([{"id": "pass", "displayName": "Legacy block", "state": "enabled",
               "conditions": {"clientAppTypes": ["other"]},
               "grantControls": {"builtInControls": ["block"]}}], "PASS"),
            ([{"id": "open", "displayName": "Modern only", "state": "enabled",
               "conditions": {"clientAppTypes": ["browser"]},
               "grantControls": {"builtInControls": ["block"]}}], "OPEN"),
            ([{"id": "incomplete", "displayName": "Unknown", "state": "enabled",
               "grantControls": {"builtInControls": ["block"]}}], "NOT_EVALUATED"),
        )
        for records, expected in cases:
            graph_reads = []
            connection = _PipelineConnection([
                {"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"},
            ])
            outcome = SecurityOrchestrator(
                self._runtime(graph_reads, records), connection,
                granted_graph_permissions=("Policy.Read.All",),
            ).run(LEGACY_AUTH_RULE_ID)
            self.assertEqual(outcome["finding"].status.value, expected)
            self.assertEqual(outcome["collection"].http_status, 200)
            self.assertEqual(len(graph_reads), 1)
            self.assertTrue(outcome["persistence"]["observation_inserted"])
