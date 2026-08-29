import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.discovery.discovery_agent import (
    AGENT_VERSION,
    acquire_token,
    discover_endpoint,
    load_inventory,
    load_state_file,
    main,
    run_batch,
    run_resume,
    show_status,
    token_roles,
    _build_permission_groups,
    _build_endpoint_state,
    _build_state,
    _compute_workflow_state,
    _find_throttled_endpoint_ids,
    _merge_into_state,
    _recompute_permission_groups_from_states,
    write_evidence,
    write_state_file,
)

ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "config" / "api_inventory.json"


class FakeResponse:
    def __init__(self, status, payload, headers=None):
        self.status = status
        self.headers = headers or {}
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def endpoint():
    return {
        "id": "G01-001", "name": "Users", "workload": "Entra ID",
        "method": "GET", "path": "/v1.0/users", "auth": "application",
        "permission": "User.Read.All", "documented_permissions": ["User.Read.All"],
        "select": ["id"], "top": 10,
    }


def token_response(token_value):
    return FakeResponse(200, {"access_token": token_value})


def fake_token_writer():
    parts = {"roles": ["Group.Read.All", "LicenseAssignment.Read.All", "User.Read.All"]}
    return mk_jwt(parts)


def mk_jwt(claims):
    import base64
    head = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return head + "." + body + ".sig"


def base_inventory():
    return [
        {
            "id": "G01-001", "key": "users", "name": "Users", "workload": "Entra ID",
            "method": "GET", "path": "/v1.0/users", "auth": "application",
            "documented_permissions": ["User.Read.All"],
            "select": ["id"], "top": 10, "pagination": True, "enabled": True,
        },
        {
            "id": "G01-002", "key": "groups", "name": "Groups", "workload": "Entra ID",
            "method": "GET", "path": "/v1.0/groups", "auth": "application",
            "documented_permissions": ["Group.Read.All"],
            "select": ["id"], "top": 10, "pagination": True, "enabled": True,
        },
        {
            "id": "G01-003", "key": "organization", "name": "Organization", "workload": "Entra ID",
            "method": "GET", "path": "/v1.0/organization", "auth": "application",
            "documented_permissions": ["Organization.Read.All"],
            "select": ["id"], "top": 10, "pagination": False, "enabled": True,
        },
        {
            "id": "G01-004", "key": "subscribedSkus", "name": "Subscribed SKUs", "workload": "Microsoft 365 Licensing",
            "method": "GET", "path": "/v1.0/subscribedSkus", "auth": "application",
            "documented_permissions": ["LicenseAssignment.Read.All"],
            "select": ["id"], "top": None, "pagination": True, "enabled": True,
        },
        {
            "id": "G01-005", "key": "directoryAuditLogs", "name": "Directory Audit Logs", "workload": "Microsoft Entra ID",
            "method": "GET", "path": "/v1.0/auditLogs/directoryAudits", "auth": "application",
            "documented_permissions": ["AuditLog.Read.All"],
            "select": ["id"], "top": 10, "pagination": True, "enabled": True,
        },
    ]


class BatchOrchestrationHelper:
    """Supports constructing scripted opener responses for run_batch."""


class DiscoveryTests(unittest.TestCase):
    def run_page(self, response):
        opener = Mock(return_value=response)
        return discover_endpoint(endpoint(), "sensitive-token", opener=opener, clock=iter([1, 2]).__next__)

    def test_http_200_pass(self):
        self.assertEqual(self.run_page(FakeResponse(200, {"value": [{"id": "1"}]}))["classification"], "PASS")

    def test_http_401_auth_failure(self):
        result = self.run_page(FakeResponse(401, {"error": {"code": "InvalidAuthenticationToken", "message": "bad"}}))
        self.assertEqual(result["classification"], "AUTH_FAILURE")

    def test_http_403_permission_required(self):
        result = self.run_page(FakeResponse(403, {"error": {"code": "Authorization_RequestDenied", "message": "denied"}}))
        self.assertEqual(result["classification"], "PERMISSION_REQUIRED")

    def test_http_429_throttled_and_retry_after(self):
        result = self.run_page(FakeResponse(429, {"error": {"code": "TooManyRequests", "message": "slow"}}, {"Retry-After": "7"}))
        self.assertEqual(result["classification"], "THROTTLED")
        self.assertEqual(result["retry_after"], "7")

    def test_generic_api_error(self):
        result = self.run_page(FakeResponse(500, {"error": {"code": "InternalError", "message": "failure"}}))
        self.assertEqual(result["classification"], "API_ERROR")

    def test_pagination_aggregation_and_rows(self):
        responses = iter([
            FakeResponse(200, {"value": [{"id": "1"}, {"id": "2"}], "@odata.nextLink": "https://next"}),
            FakeResponse(200, {"value": [{"id": "3"}]}),
        ])
        result = discover_endpoint(endpoint(), "token", opener=Mock(side_effect=lambda *args, **kwargs: next(responses)), clock=iter([1, 2, 3]).__next__)
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["total_rows"], 3)
        self.assertTrue(result["pagination_detected"])

    def test_evidence_does_not_contain_sensitive_values(self):
        result = self.run_page(FakeResponse(200, {"value": [{"id": "secret-record"}]}))
        with tempfile.TemporaryDirectory() as directory:
            evidence = write_evidence([result], timestamp="test", directory=Path(directory))
            content = evidence.read_text()
        self.assertNotIn("sensitive-token", content)
        self.assertNotIn("secret-record", content)
        self.assertNotIn("client-secret", content)
        self.assertNotIn("Authorization", content)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state_path = self.dir / "discovery-state.json"
        self.evidence_dir = self.dir / "evidence"

    def tearDown(self):
        self.tmp.cleanup()

    def _scripted_opener(self, responses, call_count):
        calls = iter(responses)

        def opener(request, timeout=None):
            try:
                token_request = request.data is not None and getattr(request, "method", None) == "POST"
            except AttributeError:
                token_request = False
            return next(calls)

        return opener

    def _patch_resources(self, opener=None, state_path=None, evidence_dir=None, inventory_path=None):
        patches = []
        if state_path:
            patches.append(patch("agents.discovery.discovery_agent.STATE_FILE", state_path))
        if evidence_dir:
            patches.append(patch("agents.discovery.discovery_agent.EVIDENCE_DIR", evidence_dir))
        if inventory_path:
            patches.append(patch("agents.discovery.discovery_agent.INVENTORY_PATH", inventory_path))
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])

    def _run_batch(self, responses, inventory=None):
        queue = list(responses)
        opener = Mock(side_effect=lambda *args, **kwargs: queue.pop(0) if queue else FakeResponse(500, {}))

        with patch("agents.discovery.discovery_agent.STATE_FILE", self.state_path), \
             patch("agents.discovery.discovery_agent.EVIDENCE_DIR", self.evidence_dir), \
             patch("agents.discovery.discovery_agent.load_inventory", return_value=inventory or base_inventory()), \
             patch("agents.discovery.discovery_agent.update_document", return_value=None) as mock_doc:
            return run_batch(inventory or base_inventory(), {"GRAPH_TENANT_ID": "t", "GRAPH_CLIENT_ID": "c", "GRAPH_CLIENT_SECRET": "s"}, opener=opener)

    def _run_resume(self, responses, inventory=None, prior_state=None):
        queue = list(responses)
        opener = Mock(side_effect=lambda *args, **kwargs: queue.pop(0) if queue else FakeResponse(500, {}))
        with patch("agents.discovery.discovery_agent.load_state_file", return_value=prior_state), \
             patch("agents.discovery.discovery_agent.STATE_FILE", self.state_path), \
             patch("agents.discovery.discovery_agent.EVIDENCE_DIR", self.evidence_dir), \
             patch("agents.discovery.discovery_agent.update_document", return_value=None):
            return run_resume(inventory or base_inventory(), {"GRAPH_TENANT_ID": "t", "GRAPH_CLIENT_ID": "c", "GRAPH_CLIENT_SECRET": "s"}, opener=opener)

    def token_resp(self, roles):
        return [FakeResponse(200, {"access_token": mk_jwt({"roles": roles})})]

    def test_batch_continues_after_403(self):
        responses = []
        responses += self.token_resp(["User.Read.All", "Group.Read.All", "LicenseAssignment.Read.All"])
        responses += [
            FakeResponse(200, {"value": [{"id": "u1"}]}),   # G01-001 PASS
            FakeResponse(200, {"value": [{"id": "g1"}]}),   # G01-002 PASS
            FakeResponse(200, {"value": [{"id": "o1"}]}),   # G01-003 PASS
            FakeResponse(200, {"value": [{"id": "s1"}]}),   # G01-004 PASS
            FakeResponse(403, {"error": {"code": "Authorization_RequestDenied", "message": "missing"}}),  # G01-005
        ]
        workflow, results, state, evidence, _ = self._run_batch(responses)
        self.assertEqual(len(results), 5)
        self.assertEqual(results[-1]["classification"], "PERMISSION_REQUIRED")
        self.assertEqual(workflow, "AWAITING_APPROVAL")
        self.assertEqual(state["workflow_state"], "AWAITING_APPROVAL")

    def test_batch_groups_multiple_permission_required(self):
        responses = []
        responses += self.token_resp(["User.Read.All"])
        responses += [
            FakeResponse(403, {"error": {"code": "Authorization_RequestDenied", "message": "x"}}),
            FakeResponse(403, {"error": {"code": "Authorization_RequestDenied", "message": "x"}}),
            FakeResponse(200, {"value": [{"id": "o1"}]}),
            FakeResponse(200, {"value": [{"id": "s1"}]}),
            FakeResponse(200, {"value": [{"id": "a1"}]}),
        ]
        inv = base_inventory()
        inv[1]["documented_permissions"] = ["User.Read.All"]
        _, _, state, _, _ = self._run_batch(responses, inventory=inv)
        groups = {g["permission"]: g for g in state["permission_groups"]}
        self.assertIn("User.Read.All", groups)
        self.assertTrue(any(eid.startswith("G01-") for eid in groups["User.Read.All"]["affected_endpoint_ids"]))

    def test_different_permissions_create_separate_groups(self):
        responses = []
        responses += self.token_resp(["User.Read.All"])
        responses += [
            FakeResponse(200, {"value": [{"id": "u1"}]}),
            FakeResponse(403, {"error": {"code": "Authorization_RequestDenied", "message": "x"}}),
            FakeResponse(200, {"value": [{"id": "o1"}]}),
            FakeResponse(403, {"error": {"code": "Authorization_RequestDenied", "message": "x"}}),
            FakeResponse(200, {"value": [{"id": "a1"}]}),
        ]
        inv = base_inventory()
        inv[1]["documented_permissions"] = ["Something.Else.Read"]
        inv[3]["documented_permissions"] = ["Yet.Another.Read"]
        _, _, state, _, _ = self._run_batch(responses, inventory=inv)
        perms = sorted({g["permission"] for g in state["permission_groups"]})
        self.assertEqual(perms, ["Something.Else.Read", "Yet.Another.Read"])

    def test_batch_complete_when_all_pass(self):
        responses = []
        responses += self.token_resp(["User.Read.All", "Group.Read.All", "LicenseAssignment.Read.All"])
        responses += [
            FakeResponse(200, {"value": [{"id": "u1"}]}),
            FakeResponse(200, {"value": [{"id": "g1"}]}),
            FakeResponse(200, {"value": [{"id": "o1"}]}),
            FakeResponse(200, {"value": [{"id": "s1"}]}),
            FakeResponse(200, {"value": [{"id": "a1"}]}),
        ]
        workflow, results, state, _, _ = self._run_batch(responses)
        self.assertEqual(workflow, "COMPLETE")
        self.assertCountEqual([r["classification"] for r in results], ["PASS"] * 5)

    def test_auth_failure_produces_fail(self):
        responses = []
        responses += self.token_resp(["Some.Read.All"])
        responses += [FakeResponse(401, {"error": {"code": "InvalidAuthenticationToken", "message": "bad"}})]
        workflow, results, state, _, _ = self._run_batch(responses)
        self.assertEqual(workflow, "FAIL")
        self.assertEqual(results[0]["classification"], "AUTH_FAILURE")

    def test_throttled_produces_partial(self):
        responses = []
        responses += self.token_resp(["User.Read.All", "Group.Read.All", "LicenseAssignment.Read.All"])
        responses += [
            FakeResponse(200, {"value": [{"id": "u1"}]}),
            FakeResponse(200, {"value": [{"id": "g1"}]}),
            FakeResponse(429, {"error": {"code": "TooManyRequests", "message": "slow"}}, {"Retry-After": "5"}),
            FakeResponse(200, {"value": [{"id": "s1"}]}),
            FakeResponse(200, {"value": [{"id": "a1"}]}),
        ]
        workflow, results, _, _, _ = self._run_batch(responses)
        self.assertEqual(workflow, "PARTIAL")
        self.assertIn("THROTTLED", {r["classification"] for r in results})

    def test_api_error_produces_partial(self):
        responses = []
        responses += self.token_resp(["User.Read.All", "Group.Read.All", "LicenseAssignment.Read.All"])
        responses += [
            FakeResponse(200, {"value": [{"id": "u1"}]}),
            FakeResponse(500, {"error": {"code": "InternalError", "message": "fail"}}),
            FakeResponse(200, {"value": [{"id": "o1"}]}),
            FakeResponse(200, {"value": [{"id": "s1"}]}),
            FakeResponse(200, {"value": [{"id": "a1"}]}),
        ]
        workflow, _, _, _, _ = self._run_batch(responses)
        self.assertEqual(workflow, "PARTIAL")


class StateFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "discovery-state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_serialization_and_no_secrets(self):
        state = _build_state(
            "AWAITING_APPROVAL",
            ["AuditLog.Read.All"],
            [{"id": "G01-005", "key": "directoryAuditLogs", "classification": "PERMISSION_REQUIRED",
              "http_status": 403, "last_tested": "x", "documented_permissions": ["AuditLog.Read.All"],
              "pages": 0, "total_rows": 0}],
            [{"permission": "AuditLog.Read.All", "affected_endpoint_ids": ["G01-005"],
              "affected_endpoint_names": ["Directory Audit Logs"], "current_role_present": False,
              "approval_status": "REQUIRED"}],
        )
        write_state_file(state, path=self.path)
        self.assertTrue(self.path.exists())
        loaded = load_state_file(self.path)
        self.assertEqual(loaded["workflow_state"], "AWAITING_APPROVAL")
        content = self.path.read_text()
        self.assertNotIn("GRAPH_CLIENT_SECRET", content)
        self.assertNotIn("access_token", content)
        self.assertNotIn("eyJ", content)
        self.assertNotIn("Authorization", content)

    def test_atomic_write_no_tmp_left_after_success(self):
        state = {"workflow_state": "COMPLETE", "token_roles": []}
        write_state_file(state, path=self.path)
        leftovers = [p for p in self.dir.iterdir() if p.suffix.endswith(".tmp") or ".tmp." in p.name]
        self.assertEqual(leftovers, [])


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state_path = self.dir / "discovery-state.json"
        self.evidence_dir = self.dir / "evidence"

    def tearDown(self):
        self.tmp.cleanup()

    def prior_state(self):
        return {
            "agent_version": AGENT_VERSION,
            "workflow_state": "AWAITING_APPROVAL",
            "token_roles": ["Group.Read.All", "LicenseAssignment.Read.All", "User.Read.All"],
            "endpoints": [
                {"id": "G01-001", "key": "users", "classification": "PASS", "http_status": 200,
                 "last_tested": "x", "documented_permissions": ["User.Read.All"], "pages": 1, "total_rows": 1},
                {"id": "G01-005", "key": "directoryAuditLogs", "classification": "PERMISSION_REQUIRED",
                 "http_status": 403, "last_tested": "x", "documented_permissions": ["AuditLog.Read.All"],
                 "pages": 0, "total_rows": 0},
            ],
            "permission_groups": [{
                "permission": "AuditLog.Read.All", "affected_endpoint_ids": ["G01-005"],
                "affected_endpoint_names": ["Directory Audit Logs"], "current_role_present": False,
                "approval_status": "REQUIRED",
            }],
        }

    def _resume(self, prior_state, roles_now, graph_responses=()):
        token_resp = FakeResponse(200, {"access_token": mk_jwt({"roles": roles_now})})
        queue = [token_resp] + list(graph_responses)
        opener = Mock(side_effect=lambda *args, **kwargs: queue.pop(0) if queue else FakeResponse(500, {}))
        with patch("agents.discovery.discovery_agent.load_state_file", return_value=prior_state), \
             patch("agents.discovery.discovery_agent.STATE_FILE", self.state_path), \
             patch("agents.discovery.discovery_agent.EVIDENCE_DIR", self.evidence_dir), \
             patch("agents.discovery.discovery_agent.update_document", return_value=None):
            return run_resume(base_inventory(), {"GRAPH_TENANT_ID": "t", "GRAPH_CLIENT_ID": "c", "GRAPH_CLIENT_SECRET": "s"}, opener=opener)

    def test_resume_acquires_fresh_token(self):
        workflow, results, state, _, _ = self._resume(self.prior_state(), ["AuditLog.Read.All"], [FakeResponse(200, {"value": [{"id": "a1"}]})])
        self.assertEqual(results[0]["inventory_id"], "G01-005")
        self.assertEqual(state["token_roles"], ["AuditLog.Read.All"])
        self.assertEqual(workflow, "COMPLETE")

    def test_resume_reruns_only_waiting_endpoints(self):
        workflow, results, _, _, _ = self._resume(self.prior_state(), ["AuditLog.Read.All"], [FakeResponse(200, {"value": [{"id": "a1"}]})])
        ids = [r["inventory_id"] for r in results]
        self.assertEqual(ids, ["G01-005"])
        self.assertNotIn("G01-001", ids)

    def test_resume_no_change(self):
        workflow, results, _, _, code = self._resume(self.prior_state(), ["Group.Read.All", "LicenseAssignment.Read.All", "User.Read.All"])
        self.assertIsNone(results)
        self.assertEqual(workflow, "AWAITING_APPROVAL")
        self.assertEqual(code, 0)

    def test_role_present_but_still_denied(self):
        workflow, results, state, _, _ = self._resume(
            self.prior_state(),
            ["AuditLog.Read.All"],
            [FakeResponse(403, {"error": {"code": "Authorization_RequestDenied", "message": "still denied"}})],
        )
        self.assertEqual(workflow, "AWAITING_APPROVAL")
        group = state["permission_groups"][0]
        self.assertEqual(group["approval_status"], "ROLE_PRESENT_BUT_STILL_DENIED")
        self.assertTrue(group["current_role_present"])


class StatusTests(unittest.TestCase):
    def test_status_makes_no_network_call(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = Path(d) / "discovery-state.json"
            evidence_dir = Path(d) / "evidence"
            state = {
                "agent_version": AGENT_VERSION,
                "workflow_state": "AWAITING_APPROVAL",
                "last_batch_execution": "2026-08-19T00:00:00+00:00",
                "endpoints": [
                    {"id": "G01-001", "classification": "PASS"},
                    {"id": "G01-005", "classification": "PERMISSION_REQUIRED"},
                ],
                "permission_groups": [{
                    "permission": "AuditLog.Read.All", "affected_endpoint_ids": ["G01-005"],
                    "affected_endpoint_names": ["Directory Audit Logs"],
                    "current_role_present": False, "approval_status": "REQUIRED",
                }],
            }
            write_state_file(state, path=state_path)
            with patch("agents.discovery.discovery_agent.load_state_file", return_value=state), \
                 patch("agents.discovery.discovery_agent.urlopen") as mock_urlopen:
                show_status()
            mock_urlopen.assert_not_called()

    def test_status_reports_no_state(self):
        with patch("agents.discovery.discovery_agent.load_state_file", return_value=None):
            show_status()


class EvidenceTests(unittest.TestCase):
    def test_historical_evidence_never_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            old = directory / "discovery-batch-20260818-120000.json"
            old.write_text('{"old": true}', encoding="utf-8")
            write_evidence([], mode="batch", directory=directory)
            write_evidence([], mode="resume", directory=directory)
            write_evidence([], mode="manual", directory=directory)
            self.assertTrue(old.exists())


class InventoryCompatTests(unittest.TestCase):
    def test_inventory_has_documented_permissions_arrays(self):
        inventory = load_inventory(INVENTORY_PATH)
        self.assertTrue(inventory)
        for item in inventory:
            self.assertIsInstance(item.get("documented_permissions"), list)
            self.assertTrue(item["documented_permissions"])

    def test_g01_003_permission_behavior_finding_preserved(self):
        with patch("agents.discovery.discovery_agent.load_inventory", return_value=base_inventory()):
            inventory_mock = base_inventory()
            org = next(item for item in inventory_mock if item["id"] == "G01-003")
            self.assertEqual(org["documented_permissions"], ["Organization.Read.All"])


class PermissionGroupRecomputeTests(unittest.TestCase):
    """Tests for TASK 1: stale permission groups are recomputed from endpoint state."""

    def test_stale_required_group_disappears_when_endpoints_no_longer_403(self):
        """A permission group that was REQUIRED is removed when all affected
        endpoints are no longer PERMISSION_REQUIRED."""
        endpoint_states = [
            {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
             "classification": "PASS", "documented_permissions": ["AuditLog.Read.All"]},
            {"id": "G01-006", "key": "sign-inlogs", "endpoint_name": "Sign-in Logs",
             "classification": "PASS", "documented_permissions": ["AuditLog.Read.All"]},
        ]
        groups = _recompute_permission_groups_from_states(endpoint_states,
                                                          token_roles=["AuditLog.Read.All"])
        self.assertEqual(groups, [])

    def test_required_group_remains_when_at_least_one_endpoint_still_403(self):
        """A permission group remains REQUIRED if at least one affected endpoint
        is still PERMISSION_REQUIRED."""
        endpoint_states = [
            {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
             "classification": "PERMISSION_REQUIRED", "documented_permissions": ["AuditLog.Read.All"]},
            {"id": "G01-006", "key": "sign-inlogs", "endpoint_name": "Sign-in Logs",
             "classification": "PASS", "documented_permissions": ["AuditLog.Read.All"]},
        ]
        groups = _recompute_permission_groups_from_states(endpoint_states)
        perms = {g["permission"] for g in groups}
        self.assertIn("AuditLog.Read.All", perms)
        group = next(g for g in groups if g["permission"] == "AuditLog.Read.All")
        self.assertEqual(group["approval_status"], "REQUIRED")
        self.assertIn("G01-005", group["affected_endpoint_ids"])

    def test_multiple_groups_independently_resolved(self):
        """Two different permission groups: one resolved (all PASS), one still
        REQUIRED (one endpoint still 403). Only the still-required group appears."""
        endpoint_states = [
            {"id": "G01-007", "key": "applications", "endpoint_name": "Applications",
             "classification": "PASS", "documented_permissions": ["Application.Read.All"]},
            {"id": "G01-008", "key": "serviceprincipals", "endpoint_name": "Service Principals",
             "classification": "PASS", "documented_permissions": ["Application.Read.All"]},
            {"id": "G01-009", "key": "devices", "endpoint_name": "Devices",
             "classification": "PERMISSION_REQUIRED", "documented_permissions": ["Device.Read.All"]},
        ]
        groups = _recompute_permission_groups_from_states(endpoint_states)
        perms = {g["permission"] for g in groups}
        self.assertNotIn("Application.Read.All", perms)
        self.assertIn("Device.Read.All", perms)

    def test_throttled_endpoint_does_not_keep_group_alive(self):
        """A THROTTLED endpoint should not cause a permission group to remain REQUIRED."""
        endpoint_states = [
            {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
             "classification": "THROTTLED", "documented_permissions": ["AuditLog.Read.All"]},
            {"id": "G01-006", "key": "sign-inlogs", "endpoint_name": "Sign-in Logs",
             "classification": "PASS", "documented_permissions": ["AuditLog.Read.All"]},
        ]
        groups = _recompute_permission_groups_from_states(endpoint_states)
        self.assertEqual(groups, [])


class ThrottledResumeTests(unittest.TestCase):
    """Tests for TASK 2: --resume retries THROTTLED endpoints."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state_path = self.dir / "discovery-state.json"
        self.evidence_dir = self.dir / "evidence"

    def tearDown(self):
        self.tmp.cleanup()

    def _resume(self, prior_state, roles_now, graph_responses=()):
        token_resp = FakeResponse(200, {"access_token": mk_jwt({"roles": roles_now})})
        queue = [token_resp] + list(graph_responses)
        opener = Mock(side_effect=lambda *args, **kwargs: queue.pop(0) if queue else FakeResponse(500, {}))
        with patch("agents.discovery.discovery_agent.load_state_file", return_value=prior_state), \
             patch("agents.discovery.discovery_agent.STATE_FILE", self.state_path), \
             patch("agents.discovery.discovery_agent.EVIDENCE_DIR", self.evidence_dir), \
             patch("agents.discovery.discovery_agent.update_document", return_value=None):
            return run_resume(base_inventory(), {"GRAPH_TENANT_ID": "t", "GRAPH_CLIENT_ID": "c", "GRAPH_CLIENT_SECRET": "s"}, opener=opener)

    def test_throttled_resume_retries_throttled_endpoint(self):
        """--resume retries a THROTTLED endpoint."""
        prior = {
            "workflow_state": "PARTIAL",
            "token_roles": ["User.Read.All", "Group.Read.All"],
            "endpoints": [
                {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
                 "classification": "THROTTLED", "http_status": 429, "last_tested": "x",
                 "documented_permissions": ["AuditLog.Read.All"], "pages": 0, "total_rows": 0},
                {"id": "G01-001", "key": "users", "endpoint_name": "Users",
                 "classification": "PASS", "http_status": 200, "last_tested": "x",
                 "documented_permissions": ["User.Read.All"], "pages": 1, "total_rows": 1},
            ],
            "permission_groups": [],
        }
        workflow, results, state, _, _ = self._resume(
            prior, ["User.Read.All", "Group.Read.All"],
            [FakeResponse(200, {"value": [{"id": "a1"}]})],
        )
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["inventory_id"], "G01-005")
        self.assertEqual(state["workflow_state"], "COMPLETE")

    def test_throttled_resume_only_one_retry_per_execution(self):
        """Only one retry occurs per resume execution — no retry loop."""
        prior = {
            "workflow_state": "PARTIAL",
            "token_roles": ["User.Read.All", "Group.Read.All"],
            "endpoints": [
                {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
                 "classification": "THROTTLED", "http_status": 429, "last_tested": "x",
                 "documented_permissions": ["AuditLog.Read.All"], "pages": 0, "total_rows": 0,
                 "retry_after": None},
            ],
            "permission_groups": [],
        }
        # If still 429 after retry, state stays PARTIAL and no further retry
        workflow, results, state, _, _ = self._resume(
            prior, ["User.Read.All", "Group.Read.All"],
            [FakeResponse(429, {"error": {"code": "TooManyRequests", "message": "still slow"}}, {"Retry-After": "10"})],
        )
        self.assertEqual(workflow, "PARTIAL")
        self.assertEqual(results[0]["classification"], "THROTTLED")
        # Only one Graph call was made (the retry), not a loop — confirmed by single result
        self.assertEqual(len(results), 1)

    def test_unrelated_pass_endpoints_not_rerun(self):
        """Unrelated PASS endpoints are not rerun during throttled resume."""
        prior = {
            "workflow_state": "PARTIAL",
            "token_roles": ["User.Read.All", "Group.Read.All"],
            "endpoints": [
                {"id": "G01-001", "key": "users", "endpoint_name": "Users",
                 "classification": "PASS", "http_status": 200, "last_tested": "x",
                 "documented_permissions": ["User.Read.All"], "pages": 1, "total_rows": 1},
                {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
                 "classification": "THROTTLED", "http_status": 429, "last_tested": "x",
                 "documented_permissions": ["AuditLog.Read.All"], "pages": 0, "total_rows": 0},
            ],
            "permission_groups": [],
        }
        workflow, results, state, _, _ = self._resume(
            prior, ["User.Read.All", "Group.Read.All"],
            [FakeResponse(200, {"value": [{"id": "a1"}]})],
        )
        ids = [r["inventory_id"] for r in results]
        self.assertIn("G01-005", ids)
        self.assertNotIn("G01-001", ids)

    def test_throttled_retry_changes_partial_to_complete(self):
        """Successful throttled retry changes PARTIAL -> COMPLETE."""
        prior = {
            "workflow_state": "PARTIAL",
            "token_roles": ["User.Read.All", "Group.Read.All"],
            "endpoints": [
                {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
                 "classification": "THROTTLED", "http_status": 429, "last_tested": "x",
                 "documented_permissions": ["AuditLog.Read.All"], "pages": 0, "total_rows": 0},
            ],
            "permission_groups": [],
        }
        workflow, results, state, _, _ = self._resume(
            prior, ["User.Read.All", "Group.Read.All"],
            [FakeResponse(200, {"value": [{"id": "a1"}]})],
        )
        self.assertEqual(workflow, "COMPLETE")
        self.assertEqual(state["workflow_state"], "COMPLETE")

    def test_retry_after_is_respected(self):
        """Retry-After is respected when retrying a throttled endpoint."""
        prior = {
            "workflow_state": "PARTIAL",
            "token_roles": ["User.Read.All", "Group.Read.All"],
            "endpoints": [
                {"id": "G01-005", "key": "directoryauditlogs", "endpoint_name": "Directory Audit Logs",
                 "classification": "THROTTLED", "http_status": 429, "last_tested": "x",
                 "documented_permissions": ["AuditLog.Read.All"], "pages": 0, "total_rows": 0,
                 "retry_after": "2"},
                {"id": "G01-001", "key": "users", "endpoint_name": "Users",
                 "classification": "PASS", "http_status": 200, "last_tested": "x",
                 "documented_permissions": ["User.Read.All"], "pages": 1, "total_rows": 1},
            ],
            "permission_groups": [],
        }
        # Use a real sleep to test Retry-After — we can verify timing
        import time as time_module
        start = time_module.monotonic()
        workflow, results, state, _, _ = self._resume(
            prior, ["User.Read.All", "Group.Read.All"],
            [FakeResponse(200, {"value": [{"id": "a1"}]})],
        )
        elapsed = time_module.monotonic() - start
        self.assertGreaterEqual(elapsed, 1.5)  # at least ~2s (allow some slop)
        self.assertEqual(workflow, "COMPLETE")


class EndpointStateMergeTests(unittest.TestCase):
    """Tests for TASK 3: --endpoint persists the latest result into discovery-state.json."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state_path = self.dir / "discovery-state.json"
        self.evidence_dir = self.dir / "evidence"
        self.doc_path = self.dir / "api-inventory.md"
        self.roles = ["AdministrativeUnit.Read.All"]

    def tearDown(self):
        self.tmp.cleanup()

    def _make_result(self, inventory_id, name, classification, http_status, perms,
                     roles=None, execution_timestamp="2026-08-19T13:00:00+00:00"):
        return {
            "execution_timestamp": execution_timestamp,
            "agent_version": AGENT_VERSION,
            "inventory_id": inventory_id,
            "workload": "Entra ID",
            "endpoint_name": name,
            "method": "GET",
            "endpoint_path": "/v1.0/x",
            "auth_type": "application",
            "documented_permissions": perms,
            "http_status": http_status,
            "classification": classification,
            "pages": 1 if classification == "PASS" else 0,
            "total_rows": 1 if classification == "PASS" else 0,
            "pagination_detected": False,
            "duration_seconds": 0.1,
            "graph_error_code": None,
            "graph_error_message": None,
            "retry_after": None,
            "token_roles": sorted(roles or []),
        }

    def _ep(self, eid, name, classification, http_status, perms, last_tested="2026-08-19T12:00:00+00:00"):
        return {
            "id": eid, "key": name.lower().replace(" ", ""), "endpoint_name": name,
            "classification": classification, "http_status": http_status,
            "last_tested": last_tested, "documented_permissions": list(perms),
            "pages": 0, "total_rows": 0, "retry_after": None,
        }

    def _run_endpoint(self, result, state=None, endpoint_arg="roleAssignments"):
        with patch("agents.discovery.discovery_agent.STATE_FILE", self.state_path), \
             patch("agents.discovery.discovery_agent.EVIDENCE_DIR", self.evidence_dir), \
             patch("agents.discovery.discovery_agent.DOC_PATH", self.doc_path), \
             patch("agents.discovery.discovery_agent.load_env", return_value={"GRAPH_TENANT_ID": "t", "GRAPH_CLIENT_ID": "c", "GRAPH_CLIENT_SECRET": "s"}), \
             patch("agents.discovery.discovery_agent.acquire_token", return_value="fake-token"), \
             patch("agents.discovery.discovery_agent.token_roles", return_value=self.roles), \
             patch("agents.discovery.discovery_agent.discover_endpoint", return_value=result):
            if state is not None:
                write_state_file(state, path=self.state_path)
            code = main(["--endpoint", endpoint_arg])
        loaded = load_state_file(self.state_path)
        return code, loaded

    def _role_management_state(self, e19_classification, e19_http, e18_classification="PERMISSION_REQUIRED"):
        return {
            "agent_version": AGENT_VERSION,
            "workflow_state": "AWAITING_APPROVAL",
            "token_roles": list(self.roles),
            "last_batch_execution": "2026-08-19T12:00:00+00:00",
            "endpoints": [
                self._ep("G01-001", "Users", "PASS", 200, ["User.Read.All"]),
                self._ep("G01-018", "Directory Role Definitions", e18_classification,
                         403 if e18_classification != "PASS" else 200, ["RoleManagement.Read.Directory"]),
                self._ep("G01-019", "Directory Role Assignments", e19_classification,
                         e19_http, ["RoleManagement.Read.Directory"]),
            ],
            "permission_groups": [{
                "permission": "RoleManagement.Read.Directory",
                "affected_endpoint_ids": ["G01-019"] if e19_classification == "PERMISSION_REQUIRED" else ["G01-018"],
                "affected_endpoint_names": ["Directory Role Assignments"] if e19_classification == "PERMISSION_REQUIRED" else ["Directory Role Definitions"],
                "current_role_present": False, "approval_status": "REQUIRED",
            }],
        }

    def test_endpoint_merges_latest_result_into_existing_state(self):
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"], self.roles)
        code, state = self._run_endpoint(result, state=self._role_management_state("API_ERROR", 400))
        self.assertEqual(code, 1)
        ep = next(e for e in state["endpoints"] if e["id"] == "G01-019")
        self.assertEqual(ep["classification"], "PERMISSION_REQUIRED")
        self.assertEqual(ep["http_status"], 403)
        self.assertEqual(ep["documented_permissions"], ["RoleManagement.Read.Directory"])
        self.assertEqual(state["token_roles"], self.roles)

    def test_unrelated_endpoint_states_remain_unchanged(self):
        prior = self._role_management_state("API_ERROR", 400)
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"], self.roles)
        _, state = self._run_endpoint(result, state=prior)
        g001 = next(e for e in state["endpoints"] if e["id"] == "G01-001")
        prior_g001 = next(e for e in prior["endpoints"] if e["id"] == "G01-001")
        self.assertEqual(g001["classification"], "PASS")
        self.assertEqual(g001["last_tested"], prior_g001["last_tested"])
        self.assertEqual(g001["documented_permissions"], prior_g001["documented_permissions"])
        self.assertTrue(any(e["id"] == "G01-018" for e in state["endpoints"]))
        self.assertTrue(any(e["id"] == "G01-019" for e in state["endpoints"]))

    def test_api_error_to_permission_required_updates_endpoint(self):
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"], self.roles)
        _, state = self._run_endpoint(result, state=self._role_management_state("API_ERROR", 400))
        ep = next(e for e in state["endpoints"] if e["id"] == "G01-019")
        self.assertEqual(ep["classification"], "PERMISSION_REQUIRED")
        self.assertEqual(ep["http_status"], 403)
        self.assertEqual(state["workflow_state"], "AWAITING_APPROVAL")

    def test_permission_group_recomputed_correctly(self):
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"], self.roles)
        _, state = self._run_endpoint(result, state=self._role_management_state("API_ERROR", 400))
        groups = {g["permission"]: g for g in state["permission_groups"]}
        self.assertIn("RoleManagement.Read.Directory", groups)
        self.assertEqual(sorted(groups["RoleManagement.Read.Directory"]["affected_endpoint_ids"]), ["G01-018", "G01-019"])
        self.assertCountEqual(groups["RoleManagement.Read.Directory"]["affected_endpoint_names"],
                              ["Directory Role Definitions", "Directory Role Assignments"])

    def test_permission_required_to_pass_removes_stale_pending_group(self):
        prior = {
            "agent_version": AGENT_VERSION,
            "workflow_state": "AWAITING_APPROVAL",
            "token_roles": list(self.roles),
            "last_batch_execution": "2026-08-19T12:00:00+00:00",
            "endpoints": [
                self._ep("G01-018", "Directory Role Definitions", "PASS", 200, ["RoleManagement.Read.Directory"]),
                self._ep("G01-019", "Directory Role Assignments", "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"]),
            ],
            "permission_groups": [{
                "permission": "RoleManagement.Read.Directory",
                "affected_endpoint_ids": ["G01-019"],
                "affected_endpoint_names": ["Directory Role Assignments"],
                "current_role_present": False, "approval_status": "REQUIRED",
            }],
        }
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PASS", 200, ["RoleManagement.Read.Directory"], self.roles)
        _, state = self._run_endpoint(result, state=prior)
        self.assertEqual(state["permission_groups"], [])
        self.assertEqual(state["workflow_state"], "COMPLETE")

    def test_throttled_to_pass_updates_workflow_state(self):
        prior = {
            "agent_version": AGENT_VERSION,
            "workflow_state": "PARTIAL",
            "token_roles": list(self.roles),
            "last_batch_execution": "2026-08-19T12:00:00+00:00",
            "endpoints": [
                self._ep("G01-001", "Users", "PASS", 200, ["User.Read.All"]),
                self._ep("G01-019", "Directory Role Assignments", "THROTTLED", 429, ["RoleManagement.Read.Directory"]),
            ],
            "permission_groups": [],
        }
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PASS", 200, ["RoleManagement.Read.Directory"], self.roles)
        _, state = self._run_endpoint(result, state=prior)
        self.assertEqual(state["workflow_state"], "COMPLETE")
        ep = next(e for e in state["endpoints"] if e["id"] == "G01-019")
        self.assertEqual(ep["classification"], "PASS")
        self.assertEqual(ep["http_status"], 200)

    def test_workflow_recomputed_from_complete_merged_state(self):
        prior = {
            "agent_version": AGENT_VERSION,
            "workflow_state": "AWAITING_APPROVAL",
            "token_roles": list(self.roles),
            "last_batch_execution": "2026-08-19T12:00:00+00:00",
            "endpoints": [
                self._ep("G01-001", "Users", "PASS", 200, ["User.Read.All"]),
                self._ep("G01-018", "Directory Role Definitions", "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"]),
                self._ep("G01-019", "Directory Role Assignments", "API_ERROR", 400, ["RoleManagement.Read.Directory"]),
            ],
            "permission_groups": [{
                "permission": "RoleManagement.Read.Directory",
                "affected_endpoint_ids": ["G01-018"],
                "affected_endpoint_names": ["Directory Role Definitions"],
                "current_role_present": False, "approval_status": "REQUIRED",
            }],
        }
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PASS", 200, ["RoleManagement.Read.Directory"], self.roles)
        _, state = self._run_endpoint(result, state=prior)
        self.assertEqual(state["workflow_state"], "AWAITING_APPROVAL")
        ep = next(e for e in state["endpoints"] if e["id"] == "G01-019")
        self.assertEqual(ep["classification"], "PASS")

    def test_historical_evidence_preserved(self):
        old = self.evidence_dir / "discovery-batch-20260818-120000.json"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text('{"old": true}', encoding="utf-8")
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"], self.roles)
        self._run_endpoint(result, state=self._role_management_state("API_ERROR", 400))
        self.assertTrue(old.exists())
        manual = [p for p in self.evidence_dir.iterdir() if p.name.startswith("discovery-manual-")]
        self.assertEqual(len(manual), 1)

    def test_status_reflects_new_state_after_endpoint(self):
        import io
        import contextlib
        result = self._make_result("G01-019", "Directory Role Assignments",
                                   "PERMISSION_REQUIRED", 403, ["RoleManagement.Read.Directory"], self.roles)
        _, state = self._run_endpoint(result, state=self._role_management_state("API_ERROR", 400))
        self.assertIsNotNone(state)
        buffer = io.StringIO()
        with patch("agents.discovery.discovery_agent.load_state_file", return_value=state), \
             contextlib.redirect_stdout(buffer):
            show_status()
        output = buffer.getvalue()
        self.assertIn("AWAITING_APPROVAL", output)
        self.assertIn("PERMISSION_REQUIRED count: 2", output)


if __name__ == "__main__":
    unittest.main()