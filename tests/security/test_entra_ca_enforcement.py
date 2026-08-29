import unittest

from capabilities import Capability, CollectionDecision, EntitlementState, plan_collection
from collectors.security.entra_ca_enforcement import aggregate_policy_states, normalize_policy_state
from security import DeterministicSecurityFindingService, FindingStatus, SecurityObservation, Severity
from security.rules.entra_ca_enforcement_001 import RULE_ID


class ConditionalAccessEnforcementTests(unittest.TestCase):
    def observation(self, records, available=True):
        return SecurityObservation(
            rule_id=RULE_ID,
            value=aggregate_policy_states(records),
            source_available=available,
            source_type="conditional_access_policies",
            graph_endpoint="/v1.0/identity/conditionalAccess/policies",
        )

    def test_state_normalization(self):
        self.assertEqual(normalize_policy_state("enabled"), "enabled")
        self.assertEqual(normalize_policy_state("enabledForReportingButNotEnforced"), "report_only")
        self.assertEqual(normalize_policy_state("disabled"), "disabled")
        self.assertEqual(normalize_policy_state("future"), "unknown_state")

    def test_license_gate_matrix_skips_before_collection(self):
        cases = (
            (EntitlementState.NOT_ENTITLED, (), CollectionDecision.SKIP_NOT_LICENSED),
            (EntitlementState.UNKNOWN, ("Policy.Read.All",), CollectionDecision.SKIP_CAPABILITY_UNKNOWN),
            (EntitlementState.ENTITLED, (), CollectionDecision.SKIP_PERMISSION_REQUIRED),
        )
        for entitlement, permissions, expected in cases:
            plan = plan_collection(
                [Capability.ENTRA_P1], ["Policy.Read.All"],
                {Capability.ENTRA_P1: entitlement}, permissions,
            )
            self.assertEqual(plan.decision, expected)
            self.assertEqual(plan.collector_status, "NOT_EXECUTED")

    def test_zero_disabled_and_report_only_are_open(self):
        service = DeterministicSecurityFindingService()
        for records in ([], [{"state": "disabled"}], [{"state": "enabledForReportingButNotEnforced"}]):
            finding = service.evaluate(self.observation(records))
            self.assertEqual(finding.status, FindingStatus.OPEN)
            self.assertEqual(finding.severity, Severity.MEDIUM)
            self.assertEqual(finding.title, "No Conditional Access policy is actively enforced")

    def test_enabled_or_mixed_policies_pass(self):
        finding = DeterministicSecurityFindingService().evaluate(self.observation([
            {"state": "enabled"}, {"state": "disabled"},
            {"state": "enabledForReportingButNotEnforced"},
        ]))
        self.assertEqual(finding.status, FindingStatus.PASS)
        self.assertEqual(finding.evidence.sanitized_value["total_policy_count"], 3)

    def test_unknown_and_source_failure_are_not_evaluated(self):
        service = DeterministicSecurityFindingService()
        self.assertEqual(service.evaluate(self.observation([{"state": "future"}])).status, FindingStatus.NOT_EVALUATED)
        self.assertEqual(service.evaluate(self.observation([], available=False)).status, FindingStatus.NOT_EVALUATED)

    def test_evidence_is_aggregate_only(self):
        finding = DeterministicSecurityFindingService().evaluate(self.observation([{
            "id": "secret-policy", "displayName": "Sensitive", "state": "enabled",
        }]))
        text = str(finding.to_dict())
        self.assertNotIn("secret-policy", text)
        self.assertNotIn("Sensitive", text)


if __name__ == "__main__":
    unittest.main()
