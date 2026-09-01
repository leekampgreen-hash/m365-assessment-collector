"""Tests for the deterministic Security Findings foundation.

Covers the CH8 contract matrix:
- compliant -> PASS
- stricter -> PASS
- violated -> OPEN
- unavailable -> NOT_EVALUATED
- malformed -> NOT_EVALUATED
- unsupported value -> NOT_EVALUATED
- deterministic severity
- deterministic recommendation
- repeated evaluation deterministic
- evidence preserved
- sensitive data excluded
- disabled rule does not OPEN
- no network dependency
- no AI dependency
"""
import unittest
import re

from security import (
    BASELINE_ID,
    BASELINE_VERSION,
    DependencyStatus,
    DeterministicSecurityFindingService,
    EvidenceReference,
    FindingStatus,
    SecurityObservation,
    Severity,
    recommended_baseline,
)
from security.rules.sp_ext_001 import (
    BASELINE_VALUE,
    EXTERNAL_SHARING_LEVELS,
    RULE_ID,
)


def obs(value, *, source_available=True, **kw):
    return SecurityObservation(
        rule_id=RULE_ID,
        value=value,
        source_available=source_available,
        source_type="sharepoint_tenant_settings",
        graph_endpoint="/sites",
        collection_run_id="run-1",
        endpoint_run_id="endpoint-1",
        normalized_field="external_sharing",
        **kw,
    )


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.baseline = recommended_baseline()
        self.service = DeterministicSecurityFindingService(self.baseline)

    def test_baseline_identity_and_version(self):
        self.assertEqual(self.baseline.baseline_id, "m365-security-recommended-v1")
        self.assertTrue(self.baseline.version)
        self.assertFalse(self.baseline.formal_compliance_claim)
        self.assertFalse(self.baseline.to_dict()["formal_compliance_claim"])

    def test_baseline_version_is_explicit(self):
        from security.baseline import BASELINE_VERSION
        self.assertTrue(re.match(r"^\d+\.\d+\.\d+$", BASELINE_VERSION))
        self.assertEqual(self.baseline.version, BASELINE_VERSION)

    def test_finding_minimum_fields_present(self):
        finding = self.service.evaluate(obs("none"))
        payload = finding.to_dict()
        for field in (
            "finding_id", "rule_id", "baseline_id", "baseline_version",
            "category", "title", "severity", "status", "baseline_expectation",
            "observed_state", "risk", "evidence", "recommendation",
            "dependency_status", "evaluated_at",
        ):
            self.assertIn(field, payload)

    def test_canonical_levels_ordered_strict_to_permissive(self):
        self.assertEqual(EXTERNAL_SHARING_LEVELS, (
            "none", "existing_guests", "new_and_existing_guests", "anyone"))
        self.assertEqual(BASELINE_VALUE, "existing_guests")


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.baseline = recommended_baseline()
        self.service = DeterministicSecurityFindingService(self.baseline)

    def test_compliant_equal_to_baseline_is_pass(self):
        finding = self.service.evaluate(obs("existing_guests"))
        self.assertEqual(finding.status, FindingStatus.PASS)

    def test_stricter_than_baseline_is_pass(self):
        finding = self.service.evaluate(obs("none"))
        self.assertEqual(finding.status, FindingStatus.PASS)

    def test_more_permissive_is_open(self):
        finding = self.service.evaluate(obs("anyone"))
        self.assertEqual(finding.status, FindingStatus.OPEN)
        self.assertEqual(finding.severity, Severity.MEDIUM)

    def test_new_and_existing_guests_more_permissive_is_open(self):
        finding = self.service.evaluate(obs("new_and_existing_guests"))
        self.assertEqual(finding.status, FindingStatus.OPEN)

    def test_source_unavailable_is_not_evaluated(self):
        finding = self.service.evaluate(obs(None, source_available=False))
        self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED)
        self.assertNotEqual(finding.status, FindingStatus.OPEN)

    def test_malformed_value_is_not_evaluated(self):
        finding = self.service.evaluate(obs(12345))
        self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED)

    def test_boolean_value_is_not_evaluated(self):
        finding = self.service.evaluate(obs(True))
        self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED)

    def test_unsupported_value_is_not_evaluated(self):
        finding = self.service.evaluate(obs("nonsense_sharing_mode"))
        self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED)

    def test_none_value_is_not_evaluated(self):
        # No evidence is never a gap.
        finding = self.service.evaluate(obs(None))
        self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED)

    def test_no_evidence_never_open_invariant(self):
        for value in (None, "", "   ", 12345, True, "unknown_mode"):
            finding = self.service.evaluate(obs(value))
            self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED,
                             f"value {value!r} must be NOT_EVALUATED")


class DeterminismTests(unittest.TestCase):
    def setUp(self):
        self.baseline = recommended_baseline()
        self.service = DeterministicSecurityFindingService(self.baseline)

    def test_severity_deterministic(self):
        for level in EXTERNAL_SHARING_LEVELS:
            f1 = self.service.evaluate(obs(level))
            f2 = self.service.evaluate(obs(level))
            self.assertEqual(f1.severity, f2.severity)
        self.assertEqual(self.service.evaluate(obs("anyone")).severity, Severity.MEDIUM)

    def test_recommendation_deterministic(self):
        open1 = self.service.evaluate(obs("anyone"))
        open2 = self.service.evaluate(obs("anyone"))
        self.assertEqual(open1.recommendation.action, open2.recommendation.action)
        self.assertEqual(open1.recommendation.text, open2.recommendation.text)
        self.assertEqual(open1.recommendation.to_dict(), open2.recommendation.to_dict())
        self.assertEqual(open1.recommendation.action, "remediate")

    def test_repeated_evaluation_deterministic(self):
        for level in EXTERNAL_SHARING_LEVELS:
            first = self.service.evaluate(obs(level)).to_dict()
            for _ in range(5):
                again = self.service.evaluate(obs(level)).to_dict()
                again.pop("evaluated_at", None)
                first_copy = dict(first)
                first_copy.pop("evaluated_at", None)
                self.assertEqual(first_copy, again)

    def test_stable_finding_id_same_input(self):
        f1 = self.service.evaluate(obs("anyone"))
        f2 = self.service.evaluate(obs("anyone"))
        self.assertEqual(f1.finding_id, f2.finding_id)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.service = DeterministicSecurityFindingService(recommended_baseline())

    def test_evidence_preserved(self):
        finding = self.service.evaluate(obs("anyone"))
        evidence = finding.evidence
        self.assertIsInstance(evidence, EvidenceReference)
        self.assertEqual(evidence.source_type, "sharepoint_tenant_settings")
        self.assertEqual(evidence.graph_endpoint, "/sites")
        self.assertEqual(evidence.collection_run_id, "run-1")
        self.assertEqual(evidence.endpoint_run_id, "endpoint-1")
        self.assertEqual(evidence.normalized_field, "external_sharing")
        self.assertEqual(evidence.sanitized_value, "anyone")

    def test_sensitive_data_excluded(self):
        for level in EXTERNAL_SHARING_LEVELS:
            finding = self.service.evaluate(obs(level))
            payload = finding.to_dict()
            text = str(payload)
            for sensitive in ("token", "Bearer ", "password", "secret",
                              "Authorization", "alice@example"):
                self.assertNotIn(sensitive.lower(), text.lower())
            self.assertEqual(payload["evidence"]["sanitized_value"], level)
            self.assertNotIn("user@example", text.lower())

    def test_evidence_reference_never_contains_credentials(self):
        ref = EvidenceReference(
            source_type="sharepoint_tenant_settings",
            graph_endpoint="/sites",
            collection_run_id="run-1",
            endpoint_run_id="endpoint-1",
            observed_at="2026-01-01T00:00:00Z",
            normalized_field="external_sharing",
            sanitized_value="anyone",
        )
        self.assertNotIn("token", str(ref.to_dict()).lower())
        self.assertNotIn("credential", str(ref.to_dict()).lower())


class DisabledRuleTests(unittest.TestCase):
    def test_disabled_rule_does_not_open(self):
        from security.models import SecurityRule
        from security.service import DeterministicSecurityFindingService
        baseline = recommended_baseline()

        # Disable the rule via the service by monkeypatching resolution.
        service = DeterministicSecurityFindingService(baseline)
        original = service.resolve_rule

        def disabled_resolve(rule_id):
            rule = original(rule_id)
            from dataclasses import replace
            return replace(rule, enabled=False)

        service.resolve_rule = disabled_resolve
        finding = service.evaluate(obs("anyone"))
        self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED)
        self.assertNotEqual(finding.status, FindingStatus.OPEN)


class NoDependencyTests(unittest.TestCase):
    def test_no_network_dependency(self):
        # The service imports only stdlib + local modules; no http client,
        # requests, graph sdk, or AI module is imported.
        import sys
        loaded = ".".join(sys.modules)
        for forbidden in ("requests", "msgraph", "httpx"):
            # only flag top-level modules actually imported
            self.assertFalse(any(m == forbidden or m.startswith(forbidden + ".") for m in sys.modules),
                             f"unexpected dependency {forbidden} loaded")

    def test_service_has_no_ai(self):
        service = DeterministicSecurityFindingService(recommended_baseline())
        self.assertFalse(hasattr(service, "model"))
        self.assertFalse(hasattr(service, "llm"))
        # Evaluator is a pure python function reference.
        finding = service.evaluate(obs("anyone"))
        self.assertEqual(finding.status, FindingStatus.OPEN)

    def test_no_remediation_executed(self):
        # There is no side-effecting remediation callable on the service.
        service = DeterministicSecurityFindingService(recommended_baseline())
        self.assertFalse(hasattr(service, "remediate"))
        self.assertFalse(hasattr(service, "apply"))
        self.assertFalse(hasattr(service, "execute"))


class UnknownRuleTests(unittest.TestCase):
    def test_unknown_rule_is_not_evaluated(self):
        service = DeterministicSecurityFindingService(recommended_baseline())
        finding = service.evaluate(SecurityObservation(rule_id="UNKNOWN-RULE-999", value="none"))
        self.assertEqual(finding.status, FindingStatus.NOT_EVALUATED)
        self.assertNotEqual(finding.status, FindingStatus.OPEN)


if __name__ == "__main__":
    unittest.main()
