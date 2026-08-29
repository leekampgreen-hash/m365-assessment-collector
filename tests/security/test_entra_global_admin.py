import io
import json
import unittest
from urllib.error import HTTPError

from collectors.core import GraphTransport
from collectors.security import (
    EntraGlobalAdminCollector, GLOBAL_ADMIN_ASSIGNMENTS_PATH,
    GLOBAL_ADMIN_PERMISSION, GLOBAL_ADMIN_ROLE_DEFINITION_ID,
)
from security import FindingStatus, Severity
from security.rules.entra_global_admin_001 import RULE_ID


class Response:
    status = 200
    headers = {}
    def __init__(self, payload): self.body = json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


def collect(payloads=None, error=None, calls=None):
    payloads = list(payloads or [])
    calls = calls if calls is not None else []
    def opener(request, timeout=None):
        calls.append((request.full_url, request.get_method()))
        if error is not None: raise error
        return Response(payloads.pop(0))
    return EntraGlobalAdminCollector(GraphTransport(lambda: "test-token", url_open=opener, timeout=1)).collect()


class GlobalAdminTests(unittest.TestCase):
    def test_boundary_counts(self):
        for count in (0, 1, 4):
            result = collect([{"value": [{"id": str(i), "principalId": str(i)} for i in range(count)]}])
            self.assertEqual(result.finding.status, FindingStatus.PASS)
        for count in (5, 7):
            result = collect([{"value": [{"id": str(i), "principalId": str(i)} for i in range(count)]}])
            self.assertEqual(result.finding.status, FindingStatus.OPEN)
            self.assertEqual(result.finding.severity, Severity.HIGH)

    def test_pagination_and_exact_deduplication(self):
        link = "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments?$skiptoken=x"
        result = collect([
            {"value": [{"id": "a", "principalId": "p1"}, {"id": "b", "principalId": "p2"}], "@odata.nextLink": link},
            {"value": [{"id": "b", "principalId": "p2"}, {"id": "c", "principalId": "p1"}]},
        ])
        self.assertEqual((result.pages_read, result.assignment_count, result.distinct_principal_count), (2, 3, 2))

    def test_malformed_and_next_link_fail_closed(self):
        for payload in ({}, {"value": "bad"}, {"value": [{"id": "a"}]},
                        {"value": [], "@odata.nextLink": "https://evil.example/x"}):
            result = collect([payload])
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)

    def test_http_failures_and_read_only_contract(self):
        for status in (403, 500, 503):
            result = collect(error=HTTPError(GLOBAL_ADMIN_ASSIGNMENTS_PATH, status, "error", {}, io.BytesIO(b"")))
            self.assertEqual(result.finding.status, FindingStatus.NOT_EVALUATED)
        self.assertEqual(GLOBAL_ADMIN_PERMISSION, "RoleManagement.Read.Directory")
        self.assertNotIn("Write", GLOBAL_ADMIN_PERMISSION)
        self.assertEqual(RULE_ID, "M365-ENTRA-GA-001")
        self.assertEqual(GLOBAL_ADMIN_ROLE_DEFINITION_ID, "62e90394-69f5-4237-9190-012177145e10")

    def test_sanitized_evidence_and_bounded_filter(self):
        calls = []
        result = collect([{"value": [{"id": "a", "principalId": "p1", "userPrincipalName": "secret"}]}], calls=calls)
        self.assertEqual(result.observation.graph_endpoint, "/roleManagement/directory/roleAssignments")
        self.assertNotIn("secret", str(result.finding.evidence.to_dict()))
        self.assertIn("roleDefinitionId", calls[0][0])
        self.assertEqual(calls[0][1], "GET")


if __name__ == "__main__": unittest.main()
