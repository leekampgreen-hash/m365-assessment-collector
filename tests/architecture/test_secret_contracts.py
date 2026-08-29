"""Value-free invariants for runtime secret delivery and cleanup safety."""
from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = REPO_ROOT / "config" / "secret_contracts.json"
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"


class SecretContractInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
        cls.contracts = cls.payload["contracts"]
        cls.compose = COMPOSE_PATH.read_text(encoding="utf-8")

    def test_collector_env_uses_operator_acl_contract(self) -> None:
        contract = self.contracts["collector.env"]
        self.assertEqual(contract["delivery_type"], "COMPOSE_FILE_SECRET")
        self.assertEqual(contract["expected_owner_group"], "1000:1001")
        self.assertEqual(contract["expected_base_mode"], "0640")
        self.assertEqual(contract["expected_acl_entries"], ["user:70:r--"])
        self.assertEqual(contract["status"], "VALID_BY_DESIGN")

    def test_runtime_password_has_independent_db_contract(self) -> None:
        contract = self.contracts["graph-agent-runtime-password"]
        self.assertEqual(contract["expected_owner_group"], "70:70")
        self.assertEqual(contract["expected_base_mode"], "0600")
        self.assertNotEqual(contract["expected_base_mode"], self.contracts["collector.env"]["expected_base_mode"])
        self.assertIn("PostgreSQL", contract["authorized_consumers"])

    def test_contracts_do_not_impose_generic_0600_runtime_ownership(self) -> None:
        self.assertNotEqual({item["expected_owner_group"] for item in self.contracts.values()}, {"70:70"})
        self.assertNotEqual({item["expected_base_mode"] for item in self.contracts.values()}, {"0600"})

    def test_active_compose_secret_sources_are_not_cleanup_targets(self) -> None:
        for name, contract in self.contracts.items():
            with self.subTest(secret=name):
                self.assertTrue(contract["active_compose_references"])
                self.assertTrue(contract["container_mount_read_only"])
                self.assertEqual(contract["status"], "VALID_BY_DESIGN")
                for reference in contract["active_compose_references"]:
                    service, _, secret = reference.partition(".secrets.")
                    self.assertIn(f"  {service}:", self.compose)
                    self.assertIn(secret, self.compose)
                self.assertEqual(self.payload["safe_cleanup"]["active_reference_decision"], "DO_NOT_DELETE")

    def test_cleanup_requires_provenance_and_stops_on_mismatch(self) -> None:
        cleanup = self.payload["safe_cleanup"]
        self.assertEqual(
            cleanup["required_temporary_metadata"],
            ["path", "type", "size", "owner", "group", "mode"],
        )
        self.assertTrue(cleanup["requires_proven_temporary_provenance"])
        self.assertEqual(cleanup["unproven_provenance_decision"], "DO_NOT_DELETE")
        self.assertEqual(cleanup["metadata_mismatch_decision"], "STOP")


if __name__ == "__main__":
    unittest.main()
