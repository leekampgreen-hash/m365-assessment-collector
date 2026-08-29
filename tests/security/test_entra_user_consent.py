import io
import json
import unittest
from urllib.error import HTTPError

from collectors.core import GraphTransport
from collectors.security import (
    EntraUserConsentCollector,
    normalize_user_consent_policy,
)
from collectors.security.entra_user_consent import AUTHORIZATION_POLICY_PATH
from security import FindingStatus, Severity


class Response:
    status = 200
    headers = {}

    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def collect(assigned, *, calls=None, error=None):
    calls = calls if calls is not None else []

    def opener(request, timeout=None):
        calls.append((request.full_url, request.get_method()))
        if error:
            raise error
        return Response({"defaultUserRolePermissions": {"permissionGrantPoliciesAssigned": assigned}})

    return EntraUserConsentCollector(
        GraphTransport(lambda: "test-token", url_open=opener, timeout=1)
    ).collect()


class ConsentPolicyTests(unittest.TestCase):
    def test_normalization_matrix(self):
        cases = (
            ([], "user_consent_disabled"),
            (["managePermissionGrantsForSelf.microsoft-user-default-recommended"], "microsoft_recommended"),
            (["managePermissionGrantsForSelf.microsoft-user-default-low"], "limited_low_risk"),
            (["managePermissionGrantsForSelf.microsoft-user-default-legacy"], "legacy_broad_consent"),
            (["managePermissionGrantsForSelf.custom-policy"], "custom_or_unknown"),
            (["managePermissionGrantsForOwnedResource.microsoft-user-default-legacy"], "user_consent_disabled"),
        )
        for policies, expected in cases:
            self.assertEqual(normalize_user_consent_policy(policies), expected)

    def test_legacy_precedes_safe_and_unknown_is_fail_closed(self):
        result = collect([
            "managePermissionGrantsForSelf.microsoft-user-default-recommended",
            "managePermissionGrantsForSelf.microsoft-user-default-legacy",
        ])
        self.assertEqual(result.finding.status, FindingStatus.OPEN)
        self.assertEqual(result.finding.severity, Severity.HIGH)
        self.assertEqual(normalize_user_consent_policy([
            "managePermissionGrantsForSelf.microsoft-user-default-low",
            "managePermissionGrantsForSelf.custom",
        ]), "custom_or_unknown")

    def test_case_variation_and_safe_multiple_policies(self):
        result = collect([
            "MANAGEpermissiongrantsFORself.Microsoft-User-Default-LOW",
            "managePermissionGrantsForSelf.microsoft-user-default-recommended",
        ])
        self.assertEqual(result.normalized_state, "microsoft_recommended")
        self.assertEqual(result.finding.status, FindingStatus.PASS)

    def test_missing_and_malformed_are_not_evaluated(self):
        for assigned in (None, {}, "not-a-list", ["managePermissionGrantsForSelf.valid", 3]):
            calls = []
            result = collect(assigned, calls=calls)
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
            self.assertEqual(len(calls), 1)

    def test_dependency_failures_do_not_open(self):
        for status in (403, 500, 503):
            result = collect([], error=HTTPError(AUTHORIZATION_POLICY_PATH, status, "error", {}, io.BytesIO(b"")))
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)

    def test_bounded_read_and_sanitized_evidence(self):
        calls = []
        result = collect(["managePermissionGrantsForSelf.microsoft-user-default-legacy"], calls=calls)
        self.assertEqual(calls[0], (
            "https://graph.microsoft.com/v1.0/policies/authorizationPolicy?%24select=defaultUserRolePermissions", "GET"
        ))
        evidence = str(result.finding.to_dict()).lower()
        for forbidden in ("test-token", "defaultuserrolepermissions", "token"):
            self.assertNotIn(forbidden, evidence)
        self.assertEqual(result.finding.evidence.sanitized_value, "legacy_broad_consent")


if __name__ == "__main__":
    unittest.main()
