import unittest

from capabilities import CollectionDecision, EntitlementState, plan_collection
from collectors.security.entra_ca_enforcement import aggregate_policy_security_counts
from security import DeterministicSecurityFindingService, FindingStatus, SecurityObservation, Severity
from security.rules.entra_ca_mfa_001 import RULE_ID


def policy(state, *, mfa=False, strength=False):
    controls = {"builtInControls": ["mfa"] if mfa else []}
    if strength:
        controls["authenticationStrength"] = {"id": "opaque"}
    return {"state": state, "grantControls": controls}


class ConditionalAccessMfaTests(unittest.TestCase):
    def evaluate(self, records, available=True):
        counts, reliable = aggregate_policy_security_counts(records)
        return DeterministicSecurityFindingService().evaluate(SecurityObservation(
            rule_id=RULE_ID, value=counts, source_available=available and reliable,
            source_type="conditional_access_policies",
            graph_endpoint="/v1.0/identity/conditionalAccess/policies",
        ))

    def test_required_matrix(self):
        for records in ([], [policy("disabled", mfa=True)], [policy("enabledForReportingButNotEnforced", mfa=True)]):
            finding = self.evaluate(records)
            self.assertEqual(finding.status, FindingStatus.OPEN)
            self.assertEqual(finding.severity, Severity.MEDIUM)
        self.assertEqual(self.evaluate([policy("enabled", mfa=True)]).status, FindingStatus.PASS)
        self.assertEqual(self.evaluate([policy("disabled", mfa=True), policy("enabledForReportingButNotEnforced", mfa=True), policy("enabled", mfa=True)]).status, FindingStatus.PASS)
        self.assertEqual(self.evaluate([policy("enabled")]).status, FindingStatus.OPEN)

    def test_sanitized_aggregate_contains_only_required_fields(self):
        counts, reliable = aggregate_policy_security_counts([
            policy("disabled", mfa=True), policy("enabledForReportingButNotEnforced", mfa=True),
        ])
        self.assertTrue(reliable)
        self.assertEqual(set(counts), {
            "total_policy_count", "enabled_policy_count", "explicit_mfa_policy_count",
            "enabled_explicit_mfa_policy_count", "report_only_explicit_mfa_policy_count",
            "disabled_explicit_mfa_policy_count", "enabled_authentication_strength_policy_count",
        })
        self.assertEqual(counts["explicit_mfa_policy_count"], 2)
        self.assertEqual(counts["report_only_explicit_mfa_policy_count"], 1)
        self.assertEqual(counts["disabled_explicit_mfa_policy_count"], 1)

    def test_authentication_strength_safety_guard(self):
        self.assertEqual(self.evaluate([policy("enabled", strength=True)]).status, FindingStatus.NOT_EVALUATED)
        self.assertEqual(self.evaluate([policy("enabled", mfa=True), policy("enabled", strength=True)]).status, FindingStatus.PASS)

    def test_malformed_and_source_failure_are_not_evaluated(self):
        self.assertEqual(self.evaluate([{"state": "enabled", "grantControls": None}]).status, FindingStatus.NOT_EVALUATED)
        self.assertEqual(self.evaluate([policy("enabled")], available=False).status, FindingStatus.NOT_EVALUATED)

    def test_license_gate_skips_without_graph(self):
        for entitlement, permissions, expected in (
            (EntitlementState.NOT_ENTITLED, (), CollectionDecision.SKIP_NOT_LICENSED),
            (EntitlementState.UNKNOWN, ("Policy.Read.All",), CollectionDecision.SKIP_CAPABILITY_UNKNOWN),
            (EntitlementState.ENTITLED, (), CollectionDecision.SKIP_PERMISSION_REQUIRED),
        ):
            plan = plan_collection(["ENTRA_P1"], ["Policy.Read.All"], {"ENTRA_P1": entitlement}, permissions)
            self.assertEqual(plan.decision, expected)
            self.assertEqual(plan.collector_status, "NOT_EXECUTED")


if __name__ == "__main__":
    unittest.main()
