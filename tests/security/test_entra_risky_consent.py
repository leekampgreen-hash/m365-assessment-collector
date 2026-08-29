import io
import json
import unittest
from urllib.error import HTTPError

from collectors.core import GraphTransport
from collectors.security import EntraRiskyConsentCollector, normalize_risky_app_consent
from collectors.security.entra_risky_consent import AUTHORIZATION_POLICY_PATH
from security import FindingStatus, Severity, SecurityObservation, DeterministicSecurityFindingService, recommended_baseline
from security.rules.entra_risky_consent_001 import (
    DISABLED_STATE, ENABLED_STATE, RULE_ID, evaluate_risky_consent,
)


class Response:
    status = 200
    headers = {}

    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


def collect(payload=None, *, calls=None, error=None):
    calls = calls if calls is not None else []

    def opener(request, timeout=None):
        calls.append((request.full_url, request.get_method()))
        if error is not None:
            raise error
        return Response(payload)

    return EntraRiskyConsentCollector(
        GraphTransport(lambda: "test-token", url_open=opener, timeout=1)
    ).collect()


class RiskyConsentTests(unittest.TestCase):
    def test_normalization_matrix(self):
        self.assertEqual(normalize_risky_app_consent(False), DISABLED_STATE)
        self.assertEqual(normalize_risky_app_consent(True), ENABLED_STATE)
        for value in (None, "false", 0, 1, {}, []):
            self.assertEqual(normalize_risky_app_consent(value), "dependency_unavailable")

    def test_false_passes_and_true_opens_high(self):
        disabled = collect({"allowUserConsentForRiskyApps": False})
        enabled = collect({"allowUserConsentForRiskyApps": True})
        self.assertEqual(disabled.finding.status, FindingStatus.PASS)
        self.assertEqual(enabled.finding.status, FindingStatus.OPEN)
        self.assertEqual(enabled.finding.severity, Severity.HIGH)
        self.assertEqual(enabled.finding.title, "User consent for risky applications is enabled")

    def test_missing_null_and_malformed_fail_closed(self):
        for payload in ({}, {"allowUserConsentForRiskyApps": None},
                        {"allowUserConsentForRiskyApps": "true"},
                        {"allowUserConsentForRiskyApps": 1}, []):
            result = collect(payload)
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
            self.assertNotEqual(result.finding.status, FindingStatus.OPEN)
            self.assertEqual(result.observation.value, "dependency_unavailable")

    def test_dependency_failures_fail_closed(self):
        for status in (403, 500, 503):
            result = collect(error=HTTPError(AUTHORIZATION_POLICY_PATH, status, "error", {}, io.BytesIO(b"")))
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
            self.assertEqual(result.finding.severity, Severity.HIGH)

    def test_single_bounded_get_and_sanitized_evidence(self):
        calls = []
        result = collect({"allowUserConsentForRiskyApps": True, "other": "do not retain"}, calls=calls)
        self.assertEqual(calls, [("https://graph.microsoft.com/v1.0/policies/authorizationPolicy?%24select=allowUserConsentForRiskyApps", "GET")])
        evidence = str(result.finding.to_dict()).lower()
        self.assertNotIn("test-token", evidence)
        self.assertNotIn("do not retain", evidence)
        self.assertEqual(result.finding.evidence.graph_endpoint, "/policies/authorizationPolicy")
        self.assertEqual(result.finding.evidence.normalized_field, "allow_user_consent_for_risky_apps")
        self.assertEqual(result.finding.evidence.sanitized_value, ENABLED_STATE)

    def test_content_and_same_input_are_deterministic(self):
        first = collect({"allowUserConsentForRiskyApps": True}).finding
        second = collect({"allowUserConsentForRiskyApps": True}).finding
        self.assertEqual(first.finding_id, second.finding_id)
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.severity, second.severity)
        self.assertIn("Disable user consent for risky applications", first.recommendation.text)
        self.assertIn("re-evaluate M365-ENTRA-RISKY-CONSENT-001", " ".join(first.recommendation.steps))

    def test_rule_registry_preserves_existing_rules(self):
        service = DeterministicSecurityFindingService()
        for rule_id in ("M365-SP-EXT-001", "M365-ENTRA-GUEST-001", "M365-ENTRA-CONSENT-001", RULE_ID):
            self.assertIsNotNone(service.resolve_rule(rule_id))


if __name__ == "__main__":
    unittest.main()
