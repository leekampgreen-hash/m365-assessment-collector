import io
import json
import unittest
from urllib.error import HTTPError

from collectors.core import GraphTransport
from collectors.security import (
    AUTHORIZATION_POLICY_ENDPOINT,
    AUTHORIZATION_POLICY_PERMISSION,
    AUTHORIZATION_POLICY_PATH,
    EntraAuthorizationPolicyCollector,
    normalize_allow_invites_from,
)
from security import FindingStatus, Severity, recommended_baseline
from security.rules.entra_guest_001 import RULE_ID


class _Response:
    status = 200
    headers = {}
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


def collect(payload=None, error=None, calls=None):
    calls = calls if calls is not None else []
    def opener(request, timeout=None):
        calls.append((request.full_url, request.get_method()))
        if error is not None: raise error
        return _Response(payload)
    return EntraAuthorizationPolicyCollector(
        GraphTransport(lambda: "test-token", url_open=opener, timeout=1)
    ).collect()


class GuestInvitationTests(unittest.TestCase):
    def test_exact_normalization(self):
        expected = {
            "none": "none",
            "adminsAndGuestInviters": "admins_and_guest_inviters",
            "adminsGuestInvitersAndAllMembers": "admins_guest_inviters_and_all_members",
            "everyone": "everyone",
        }
        for raw, normalized in expected.items():
            self.assertEqual(normalize_allow_invites_from(raw), normalized)
        for value in (None, "unknown", "Everyone", 1, {}):
            self.assertIsNone(normalize_allow_invites_from(value))

    def test_values_evaluate_against_product_baseline(self):
        expected = {
            "none": FindingStatus.PASS,
            "adminsAndGuestInviters": FindingStatus.PASS,
            "adminsGuestInvitersAndAllMembers": FindingStatus.OPEN,
            "everyone": FindingStatus.OPEN,
        }
        for raw, status in expected.items():
            result = collect({"allowInvitesFrom": raw})
            self.assertEqual(result.observation.value, normalize_allow_invites_from(raw))
            self.assertEqual(result.finding.status, status)
            if status is FindingStatus.OPEN:
                self.assertEqual(result.finding.severity, Severity.MEDIUM)

    def test_missing_unknown_and_malformed_fail_closed(self):
        for payload in ({}, {"allowInvitesFrom": "future"}, {"allowInvitesFrom": 4}, []):
            result = collect(payload)
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
            self.assertNotEqual(result.finding.status, FindingStatus.OPEN)

    def test_dependency_failures_do_not_open_and_are_single_get(self):
        calls = []
        for status in (403, 500, 503):
            error = HTTPError(AUTHORIZATION_POLICY_PATH, status, "error", {}, io.BytesIO(b""))
            result = collect(error=error, calls=calls)
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
        self.assertEqual(len(calls), 3)

    def test_contract_evidence_recommendation_and_read_only_boundary(self):
        result = collect({"allowInvitesFrom": "everyone", "displayName": "do not retain"})
        evidence = str(result.finding.evidence.to_dict()).lower()
        self.assertEqual(result.finding.evidence.graph_endpoint, AUTHORIZATION_POLICY_ENDPOINT)
        self.assertEqual(result.finding.evidence.normalized_field, "allow_invites_from")
        self.assertEqual(result.finding.evidence.sanitized_value, "everyone")
        for forbidden in ("token", "secret", "displayname", "do not retain"):
            self.assertNotIn(forbidden, evidence)
        self.assertIn("Restrict guest invitations", result.finding.recommendation.text)
        self.assertIn("re-evaluate M365-ENTRA-GUEST-001", " ".join(result.finding.recommendation.steps))
        self.assertEqual(AUTHORIZATION_POLICY_PERMISSION, "Policy.Read.All")
        self.assertNotIn("ReadWrite", AUTHORIZATION_POLICY_PERMISSION)
        self.assertEqual(result.finding.rule_id, RULE_ID)

    def test_endpoint_is_exactly_one_bounded_get(self):
        calls = []
        collect({"allowInvitesFrom": "none"}, calls=calls)
        self.assertEqual(calls[0][0], "https://graph.microsoft.com/v1.0/policies/authorizationPolicy?%24select=allowInvitesFrom")
        self.assertEqual(calls[0][1], "GET")


if __name__ == "__main__":
    unittest.main()
