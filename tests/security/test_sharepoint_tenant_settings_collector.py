import io
import json
import unittest
from urllib.error import HTTPError

from collectors.core import GraphTransport
from collectors.security import (
    SHAREPOINT_SETTINGS_ENDPOINT,
    SHAREPOINT_SETTINGS_PERMISSION,
    SharePointTenantSettingsCollector,
    normalize_sharing_capability,
)
from security import FindingStatus


class _Response:
    def __init__(self, payload):
        self.headers = {}
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _collector(payload=None, error=None, calls=None):
    calls = calls if calls is not None else []

    def opener(request, timeout=None):
        calls.append((request.full_url, request.get_method()))
        if error is not None:
            raise error
        return _Response(payload)

    return SharePointTenantSettingsCollector(
        GraphTransport(lambda: "test-token", url_open=opener, timeout=1),
    )


class NormalizationTests(unittest.TestCase):
    def test_graph_enum_mapping_is_exact(self):
        self.assertEqual(normalize_sharing_capability("disabled"), "none")
        self.assertEqual(normalize_sharing_capability("existingExternalUserSharingOnly"), "existing_guests")
        self.assertEqual(normalize_sharing_capability("externalUserSharingOnly"), "new_and_existing_guests")
        self.assertEqual(normalize_sharing_capability("externalUserAndGuestSharing"), "anyone")

    def test_missing_and_future_values_fail_closed(self):
        self.assertIsNone(normalize_sharing_capability(None))
        self.assertIsNone(normalize_sharing_capability("unknownFutureValue"))
        self.assertIsNone(normalize_sharing_capability("EXTERNALUSERANDGUESTSHARING"))


class CollectorTests(unittest.TestCase):
    def test_single_get_and_finding_integration(self):
        calls = []
        result = _collector({"sharingCapability": "existingExternalUserSharingOnly"}, calls=calls).collect()
        self.assertEqual(calls, [("https://graph.microsoft.com/v1.0/admin/sharepoint/settings", "GET")])
        self.assertEqual(result.observation.value, "existing_guests")
        self.assertEqual(result.observation.normalized_field, "sharing_capability")
        self.assertEqual(result.finding.status, FindingStatus.PASS)
        self.assertEqual(result.finding.evidence.source_type, "sharepoint_tenant_settings")
        self.assertEqual(result.finding.evidence.graph_endpoint, SHAREPOINT_SETTINGS_ENDPOINT)
        self.assertEqual(result.finding.evidence.normalized_field, "sharing_capability")
        self.assertIsNotNone(result.finding.evidence.observed_at)

    def test_all_valid_levels_have_expected_findings(self):
        expected = {
            "disabled": ("none", FindingStatus.PASS),
            "existingExternalUserSharingOnly": ("existing_guests", FindingStatus.PASS),
            "externalUserSharingOnly": ("new_and_existing_guests", FindingStatus.OPEN),
            "externalUserAndGuestSharing": ("anyone", FindingStatus.OPEN),
        }
        for raw, (normalized, status) in expected.items():
            result = _collector({"sharingCapability": raw}).collect()
            self.assertEqual(result.observation.value, normalized)
            self.assertEqual(result.finding.status, status)

    def test_missing_unknown_and_malformed_are_not_evaluated(self):
        for payload in ({}, {"sharingCapability": "unknownFutureValue"}, {"sharingCapability": 7}, []):
            result = _collector(payload).collect()
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
            self.assertNotEqual(result.finding.status, FindingStatus.OPEN)
            self.assertFalse(result.observation.source_available)

    def test_403_is_permission_failure_and_not_open(self):
        error = HTTPError(
            "https://graph.microsoft.com/v1.0/admin/sharepoint/settings", 403, "forbidden", {},
            io.BytesIO(b'{"error":{"code":"accessDenied"}}'),
        )
        result = _collector(error=error).collect()
        self.assertEqual(result.error_classification, "PERMISSION_REQUIRED")
        self.assertEqual(result.http_status, 403)
        self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)

    def test_5xx_is_not_evaluated_without_retry(self):
        calls = []
        error = HTTPError("https://graph.microsoft.com/v1.0/admin/sharepoint/settings", 503, "unavailable", {}, io.BytesIO(b""))
        result = _collector(error=error, calls=calls).collect()
        self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
        self.assertEqual(len(calls), 1)

    def test_permission_contract_is_read_only(self):
        self.assertEqual(SHAREPOINT_SETTINGS_PERMISSION, "SharePointTenantSettings.Read.All")
        self.assertNotIn("ReadWrite", SHAREPOINT_SETTINGS_PERMISSION)
        self.assertEqual(SharePointTenantSettingsCollector.collect.__name__, "collect")

    def test_evidence_has_no_sensitive_data_or_raw_body(self):
        result = _collector({"sharingCapability": "externalUserAndGuestSharing", "sharingAllowedDomainList": ["secret.example"]}).collect()
        evidence = result.finding.evidence.to_dict()
        text = str(evidence).lower()
        for sensitive in ("token", "secret", "authorization", "sharingalloweddomainlist", "secret.example"):
            self.assertNotIn(sensitive, text)
        self.assertEqual(evidence["sanitized_value"], "anyone")


if __name__ == "__main__":
    unittest.main()
