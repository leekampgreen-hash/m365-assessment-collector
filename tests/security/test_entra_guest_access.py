import io
import json
import unittest
from urllib.error import HTTPError

from collectors.core import GraphTransport
from collectors.security import (
    EntraGuestDirectoryAccessCollector, GUEST_ACCESS_PATH,
    normalize_guest_directory_access,
)
from security import DeterministicSecurityFindingService, FindingStatus, Severity
from security.rules.entra_guest_access_001 import RULE_ID


USER = "a0b1b346-4d3e-4e8b-98f8-753987be4970"
GUEST = "10dae51f-b6af-4016-8d66-8c2a99b929b3"
RESTRICTED = "2af84b1e-32c8-42b7-82bc-daa82404023b"


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

    return EntraGuestDirectoryAccessCollector(
        GraphTransport(lambda: "test-token", url_open=opener, timeout=1)
    ).collect()


class GuestDirectoryAccessTests(unittest.TestCase):
    def test_exact_case_insensitive_normalization(self):
        self.assertEqual(normalize_guest_directory_access(RESTRICTED), "restricted_guest")
        self.assertEqual(normalize_guest_directory_access(GUEST), "limited_guest")
        self.assertEqual(normalize_guest_directory_access(USER), "same_as_members")
        self.assertEqual(normalize_guest_directory_access(USER.upper()), "same_as_members")
        self.assertEqual(normalize_guest_directory_access("future"), "custom_or_unknown")
        self.assertEqual(normalize_guest_directory_access(None), "dependency_unavailable")

    def test_baseline_matrix(self):
        for role, status in ((RESTRICTED, FindingStatus.PASS),
                             (GUEST, FindingStatus.PASS),
                             (USER, FindingStatus.OPEN)):
            result = collect({"guestUserRoleId": role, "unrelated": "do not retain"})
            self.assertEqual(result.finding.status, status)
            if status is FindingStatus.OPEN:
                self.assertEqual(result.finding.severity, Severity.HIGH)
                self.assertEqual(result.finding.title,
                                 "Guest users have member-equivalent directory access")

    def test_unknown_null_missing_and_malformed_fail_closed(self):
        for payload in ({"guestUserRoleId": "future"},
                        {"guestUserRoleId": None}, {}, [],
                        {"guestUserRoleId": 1}):
            result = collect(payload)
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
            self.assertNotEqual(result.finding.status, FindingStatus.OPEN)

    def test_dependency_failures_fail_closed(self):
        for status in (403, 500, 503):
            result = collect(error=HTTPError(GUEST_ACCESS_PATH, status, "error", {}, io.BytesIO(b"")))
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)

    def test_single_bounded_get_and_sanitized_evidence(self):
        calls = []
        result = collect({"guestUserRoleId": USER, "displayName": "do not retain"}, calls=calls)
        self.assertEqual(calls, [("https://graph.microsoft.com/v1.0/policies/authorizationPolicy?%24select=guestUserRoleId", "GET")])
        payload = str(result.finding.to_dict()).lower()
        self.assertNotIn("test-token", payload)
        self.assertNotIn("do not retain", payload)
        self.assertEqual(result.finding.evidence.sanitized_value, "same_as_members")
        self.assertEqual(result.finding.evidence.normalized_field, "guest_directory_access_level")
        self.assertIn("Re-read the tenant authorization policy", result.finding.recommendation.steps[0])

    def test_rule_registry_preserves_rules_one_to_five(self):
        service = DeterministicSecurityFindingService()
        for rule_id in ("M365-SP-EXT-001", "M365-ENTRA-GUEST-001",
                        "M365-ENTRA-CONSENT-001", "M365-ENTRA-RISKY-CONSENT-001",
                        "M365-ENTRA-GA-001", RULE_ID):
            self.assertIsNotNone(service.resolve_rule(rule_id))


if __name__ == "__main__":
    unittest.main()
