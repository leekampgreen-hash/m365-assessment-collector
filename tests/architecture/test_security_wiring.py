"""Registry-driven Security production wiring invariants.

These tests intentionally inspect registrations rather than individual rule
ids, so a future execution registration receives the same coverage.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from capabilities import Capability
from collectors.core.inventory import load_inventory
from collectors.core.models import ENDPOINT_TYPE_SECURITY_ONLY, ENDPOINT_TYPE_WORKLOAD
from collectors.security.orchestration import SecurityOrchestrator, _EXECUTIONS
from collectors.workloads import REGISTRY as WORKLOAD_REGISTRY
from security import DeterministicSecurityFindingService
from security.service import _EVALUATORS


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "config" / "api_inventory.json"
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile.collector"


def tearDownModule() -> None:
    """Keep Scenario import-isolation tests independent of discovery order."""
    for name in (
        "collectors.core.auth", "collectors.core.config",
        "collectors.core.transport", "urllib.request",
    ):
        sys.modules.pop(name, None)


class SecurityProductionWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = {spec.endpoint_id: spec for spec in load_inventory(INVENTORY_PATH)}
        self.service = DeterministicSecurityFindingService()

    def test_registered_security_executions_resolve_all_production_dependencies(self) -> None:
        self.assertTrue(_EXECUTIONS, "at least one production Security execution must be registered")
        for rule_id, execution in _EXECUTIONS.items():
            with self.subTest(rule_id=rule_id):
                self.assertEqual(execution.rule_id, rule_id)
                rule = self.service.resolve_rule(rule_id)
                self.assertIsNotNone(rule, "execution must resolve a declared Security rule")
                self.assertIn(rule_id, _EVALUATORS, "execution must resolve a deterministic evaluator")
                self.assertTrue(callable(_EVALUATORS[rule_id]))
                self.assertTrue(callable(execution.collector_factory))
                self.assertTrue(rule.required_graph_permissions, "production rules require Graph permissions")
                self.assertTrue(all(permission for permission in rule.required_graph_permissions))
                self.assertTrue(all(capability in Capability._value2member_map_ for capability in rule.required_capabilities))

                endpoint = self.inventory.get(execution.endpoint_id)
                self.assertIsNotNone(endpoint, "execution endpoint must be in canonical inventory")
                self.assertIn(endpoint.endpoint_type, (ENDPOINT_TYPE_WORKLOAD, ENDPOINT_TYPE_SECURITY_ONLY))
                self.assertEqual(endpoint.method, "GET", "Security collectors are read-only")
                self.assertEqual(endpoint.auth_type, "application", "Security execution is app-only")
                self.assertTrue(endpoint.documented_permissions)
                self.assertTrue(set(rule.required_graph_permissions) & set(endpoint.documented_permissions))
                orchestrator = SecurityOrchestrator.__new__(SecurityOrchestrator)
                self.assertEqual(orchestrator.execution_spec(rule_id), execution)

    def test_inventory_endpoint_type_has_the_right_registry_obligation(self) -> None:
        for endpoint_id, endpoint in self.inventory.items():
            with self.subTest(endpoint_id=endpoint_id):
                if (
                    endpoint.endpoint_type == ENDPOINT_TYPE_WORKLOAD
                    and endpoint.transport_type == "NORMAL_GRAPH_JSON"
                    and (endpoint.collector_type != "specialized" or endpoint_id in WORKLOAD_REGISTRY)
                ):
                    self.assertIn(endpoint_id, WORKLOAD_REGISTRY)
                if endpoint.endpoint_type == ENDPOINT_TYPE_SECURITY_ONLY or (
                    endpoint.collector_type == "specialized" and endpoint_id not in WORKLOAD_REGISTRY
                ):
                    self.assertNotIn(endpoint_id, WORKLOAD_REGISTRY)

    def test_security_executions_reference_canonical_read_only_allowlist(self) -> None:
        raw_inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        allowed_ids = {item["id"] for item in raw_inventory if item.get("enabled", True)}
        for execution in _EXECUTIONS.values():
            endpoint = self.inventory[execution.endpoint_id]
            self.assertIn(execution.endpoint_id, allowed_ids)
            self.assertEqual(endpoint.method.upper(), "GET")

    def test_collector_image_copies_all_runtime_packages(self) -> None:
        copied_packages = set()
        for line in DOCKERFILE_PATH.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) == 3 and fields[0] == "COPY" and fields[2].startswith("/workspace/"):
                copied_packages.add(fields[1])
        self.assertTrue({"collectors", "capabilities", "security"}.issubset(copied_packages))
