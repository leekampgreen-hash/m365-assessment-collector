import json
import tempfile
import unittest
from pathlib import Path

from collectors.core import CollectorRuntime, RuntimeOptions, dict_source
from collectors.security import SecurityOrchestrator
from security import DeterministicSecurityFindingService, SecurityObservation, FindingStatus
from security.rules.entra_mfa_registration_001 import RULE_ID, evaluate_mfa_registration
from tests.core.test_auth_runtime_cli import FakeResponse
from tests.security.test_security_persistence import Connection, Cursor


def value(enabled=39, rows=39, matched=39, gap=0, registered=2):
    return {
        "enabled_user_count": enabled, "registration_row_count": rows,
        "matched_enabled_user_count": matched, "unexplained_population_gap": gap,
        "mfa_registered_count": registered, "mfa_not_registered_count": matched - registered,
        "registration_coverage_percent": round(registered / enabled * 100, 2) if enabled else 100.0,
    }


class MfaRegistrationRuleTests(unittest.TestCase):
    def evaluate(self, observed, available=True):
        return DeterministicSecurityFindingService().evaluate(SecurityObservation(
            rule_id=RULE_ID, value=observed, source_available=available,
            observed_at="2026-08-27T00:00:00Z", source_type="entra_user_registration_details",
        ))

    def test_all_registered_passes(self):
        self.assertEqual(self.evaluate(value(registered=39)).status, FindingStatus.PASS)

    def test_partial_registration_opens_medium(self):
        finding = self.evaluate(value())
        self.assertEqual(finding.status, FindingStatus.OPEN)
        self.assertEqual(finding.severity.value, "MEDIUM")
        self.assertEqual(finding.title, "Enabled users have incomplete MFA registration coverage")

    def test_population_gaps_are_not_evaluated(self):
        for observed in (value(matched=38, gap=1), value(rows=40, gap=1), None):
            self.assertEqual(self.evaluate(observed).status, FindingStatus.NOT_EVALUATED)

    def test_source_failure_is_not_evaluated(self):
        self.assertEqual(self.evaluate(None, available=False).status, FindingStatus.NOT_EVALUATED)


class _UserCursor(Cursor):
    def execute(self, sql, params):
        if "FROM core.subscribed_sku" in sql:
            self.fetchall_result = [(self.connection.plans,)]
            return
        if sql.startswith("SELECT tenant_id FROM core.tenant"):
            self.fetchall_result = [(7,)]
            return
        if 'FROM core."user"' in sql:
            self.result = None
            self.fetchall_result = [("u1", "u1@example.test"), ("u2", "u2@example.test")]
            return
        super().execute(sql, params)

    def fetchall(self):
        result = getattr(self, "fetchall_result", [])
        self.fetchall_result = []
        return result


class _UserConnection(Connection):
    def __init__(self):
        super().__init__()
        self.plans = [{"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"}]

    def cursor(self):
        return _UserCursor(self)


class MfaRegistrationProductionPathTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.inventory = Path(self.directory.name) / "inventory.json"
        self.inventory.write_text(json.dumps([{
            "id": "G01-021", "name": "MFA Registration",
            "path": "/v1.0/reports/authenticationMethods/userRegistrationDetails",
            "method": "GET", "auth": "application",
            "documented_permissions": ["AuditLog.Read.All"],
            "required_capabilities": ["ENTRA_P1"], "pagination": True,
            "endpoint_type": "SECURITY_ONLY", "enabled": True,
        }]), encoding="utf-8")

    def runtime(self, reads):
        def fake_http(request, timeout=None):
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse(200, {"access_token": "token", "expires_in": 3600})
            reads.append(request.full_url)
            return FakeResponse(200, {"value": [
                {"id": "u1", "userPrincipalName": "u1@example.test", "isMfaRegistered": True, "isMfaCapable": True},
                {"id": "u2", "userPrincipalName": "u2@example.test", "isMfaRegistered": False, "isMfaCapable": False},
            ]})
        return CollectorRuntime(self.inventory, dict_source({
            "GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret",
        }), options=RuntimeOptions(http_open=fake_http, tenant_resolver=lambda config: 7))

    def test_registered_rule_uses_internal_path_and_persists_aggregate(self):
        reads, connection = [], _UserConnection()
        outcome = SecurityOrchestrator(self.runtime(reads), connection,
            granted_graph_permissions=("AuditLog.Read.All",)).run(RULE_ID)
        self.assertEqual(outcome["finding"].status, FindingStatus.OPEN)
        self.assertEqual(outcome["observation"].value["enabled_user_count"], 2)
        self.assertEqual(len(reads), 1)
        self.assertTrue(outcome["persistence"])

    def test_not_entitled_skips_before_collector_and_graph(self):
        reads, connection = [], _UserConnection()
        connection.plans = [{"servicePlanName": "EXCHANGE_S_STANDARD", "provisioningStatus": "Success"}]
        outcome = SecurityOrchestrator(self.runtime(reads), connection,
            granted_graph_permissions=("AuditLog.Read.All",)).run(RULE_ID)
        self.assertEqual(outcome["plan"].decision.value, "SKIP_NOT_LICENSED")
        self.assertEqual(reads, [])
        self.assertIsNone(outcome["observation"])
