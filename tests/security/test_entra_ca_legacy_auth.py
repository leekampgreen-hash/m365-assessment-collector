import unittest

from security import DeterministicSecurityFindingService, FindingStatus, SecurityObservation, Severity
from security.rules.entra_ca_legacy_auth_001 import RULE_ID


def policy(client_types, *, state="enabled", controls=("block",), complete=True, policy_id="p1"):
    return {"policy_id": policy_id, "display_name": "Legacy block", "state": state,
            "client_app_types": list(client_types), "grant_built_in_controls": list(controls),
            "security_evidence_complete": complete}


def observation(policies, complete=True):
    return SecurityObservation(rule_id=RULE_ID,
        value={"policies": policies, "collection_complete": complete},
        source_type="conditional_access_policies",
        graph_endpoint="/v1.0/identity/conditionalAccess/policies",
        normalized_field="conditional_access_legacy_auth_policies",
        observed_at="2026-08-27T00:00:00Z")


class LegacyAuthenticationRuleTests(unittest.TestCase):
    def setUp(self):
        self.service = DeterministicSecurityFindingService()

    def evaluate(self, policies, complete=True):
        return self.service.evaluate(observation(policies, complete))

    def test_legacy_specific_client_types_pass(self):
        for client_type in ("exchangeActiveSync", "other", "easSupported", "easUnsupported"):
            finding = self.evaluate([policy([client_type])])
            self.assertEqual(finding.status, FindingStatus.PASS)
            self.assertEqual(finding.evidence.sanitized_value[0]["coverage_mode"], "LEGACY_SPECIFIC")

    def test_all_client_apps_passes_with_distinct_coverage_mode(self):
        finding = self.evaluate([policy(["all"])])
        self.assertEqual(finding.status, FindingStatus.PASS)
        self.assertEqual(finding.evidence.sanitized_value[0]["coverage_mode"], "ALL_CLIENT_APPS")

    def test_non_enabled_or_non_block_policies_do_not_pass(self):
        for item in (policy(["other"], state="enabled", controls=[]),
                     policy(["other"], state="enabled", controls=("mfa",)),
                     policy(["other"], state="enabledForReportingButNotEnforced"),
                     policy(["other"], state="disabled"),
                     policy(["browser"]), policy(["mobileAppsAndDesktopClients"])):
            self.assertNotEqual(self.evaluate([item]).status, FindingStatus.PASS)

    def test_open_requires_complete_absence_evidence(self):
        finding = self.evaluate([policy(["browser"])])
        self.assertEqual(finding.status, FindingStatus.OPEN)
        self.assertEqual(finding.severity, Severity.HIGH)
        self.assertEqual(self.evaluate([policy(["browser"], complete=False)]).status, FindingStatus.NOT_EVALUATED)

    def test_one_complete_qualifier_wins_over_incomplete_other_policy(self):
        finding = self.evaluate([policy(["other"]), policy(["browser"], complete=False)])
        self.assertEqual(finding.status, FindingStatus.PASS)

    def test_empty_complete_collection_follows_open_convention(self):
        self.assertEqual(self.evaluate([]).status, FindingStatus.OPEN)


if __name__ == "__main__":
    unittest.main()
