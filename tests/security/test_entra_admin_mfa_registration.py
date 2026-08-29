import json
import tempfile
import unittest
from pathlib import Path

from collectors.core.inventory import load_inventory
from collectors.security.orchestration import _EXECUTIONS
from security import DeterministicSecurityFindingService, FindingStatus, SecurityObservation
from security.rules.entra_admin_mfa_registration_001 import (
    INTERPRETATION_SCOPE, RULE_ID, evaluate_admin_mfa_registration,
)


def aggregate(admins, registered):
    return {
        "admin_user_count": admins,
        "admin_mfa_registered_count": registered,
        "admin_mfa_not_registered_count": admins - registered,
        "admin_registration_coverage_percent": round(registered / admins * 100, 2) if admins else 0.0,
    }


class AdminMfaRuleTests(unittest.TestCase):
    def evaluate(self, value, available=True):
        return DeterministicSecurityFindingService().evaluate(SecurityObservation(
            rule_id=RULE_ID, value=value, source_available=available,
            source_type="entra_user_registration_details",
        ))

    def test_five_registered_passes(self):
        self.assertEqual(self.evaluate(aggregate(5, 5)).status, FindingStatus.PASS)

    def test_partial_registration_opens_high(self):
        finding = self.evaluate(aggregate(5, 1))
        self.assertEqual(finding.status, FindingStatus.OPEN)
        self.assertEqual(finding.severity.value, "HIGH")
        self.assertEqual(finding.title, "Administrator accounts have incomplete MFA registration coverage")

    def test_one_unregistered_opens(self):
        self.assertEqual(self.evaluate(aggregate(1, 0)).status, FindingStatus.OPEN)

    def test_zero_admins_is_not_evaluated(self):
        self.assertEqual(self.evaluate(aggregate(0, 0)).status, FindingStatus.NOT_EVALUATED)

    def test_malformed_or_incomplete_source_is_not_evaluated(self):
        malformed = aggregate(1, 1)
        malformed["admin_user_count"] = "1"
        inconsistent = aggregate(5, 5)
        inconsistent["admin_mfa_not_registered_count"] = 1
        for value in (malformed, inconsistent, None):
            self.assertEqual(self.evaluate(value).status, FindingStatus.NOT_EVALUATED)
        self.assertEqual(self.evaluate(aggregate(1, 1), available=False).status, FindingStatus.NOT_EVALUATED)

    def test_contract_scope_and_no_identity_data(self):
        finding = self.evaluate(aggregate(5, 1))
        self.assertEqual(INTERPRETATION_SCOPE, "ADMIN_MFA_REGISTRATION_COVERAGE_ONLY")
        self.assertEqual(set(finding.evidence.sanitized_value), {
            "admin_user_count", "admin_mfa_registered_count",
            "admin_mfa_not_registered_count", "admin_registration_coverage_percent",
        })

    def test_generic_execution_registration(self):
        self.assertIn(RULE_ID, _EXECUTIONS)
        self.assertEqual(_EXECUTIONS[RULE_ID].endpoint_id, "G01-021")


class AdminMfaInventoryTests(unittest.TestCase):
    def test_g01_021_includes_is_admin(self):
        root = Path(__file__).resolve().parents[2]
        inventory = {item.endpoint_id: item for item in load_inventory(root / "config" / "api_inventory.json")}
        self.assertIn("isAdmin", inventory["G01-021"].select)
        self.assertEqual(inventory["G01-021"].method, "GET")
        self.assertEqual(inventory["G01-021"].auth_type, "application")


if __name__ == "__main__":
    unittest.main()
