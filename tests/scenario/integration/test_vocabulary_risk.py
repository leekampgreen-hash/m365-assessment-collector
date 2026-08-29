"""Integration tests: risk vocabulary normalization (catalog -> framework).

The catalog uses LOW / MODERATE / HIGH. The framework runtime
vocabulary is LOW / MEDIUM / HIGH. The loader must map MODERATE to
MEDIUM, leave LOW and HIGH untouched, and reject unknown values.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.scenario.catalog_loader import load_scenario_catalog


def _write_one_scenario_catalog(td: str, risk_value: str) -> Path:
    """Write a catalog with one scenario at the given risk level."""
    root = Path(td)
    (root / "scenarios").mkdir(parents=True, exist_ok=True)
    scenario = {
        "schema_version": "1.0",
        "scenario_id": "SCN-T-001",
        "name": "n",
        "description": "d",
        "domain": "MAIL",
        "action_type": "SEND_MAIL",
        "actor_required": "x",
        "peer_actor_required": None,
        "no_recipient": True,
        "required_delegated_permissions": ["Mail.Send"],
        "expected_observable_sources": ["G01-006"],
        "observability_classification": "INDIRECTLY_OBSERVABLE",
        "correlation_strategy": "x",
        "correlation_token_field": "y",
        "cleanup_required": False,
        "cleanup_behavior": "NO_CLEANUP_REQUIRED",
        "destructive": False,
        "risk": risk_value,
        "enabled": False,
        "permission_pack": "PACK-MAIL",
        "notes": "ok",
    }
    (root / "scenarios" / "SCN-T-001.json").write_text(json.dumps(scenario))
    catalog = {
        "schema_version": "1.0",
        "catalog_id": "T",
        "version": "0.0.1",
        "scenarios": [{"scenario_id": "SCN-T-001", "file": "scenarios/SCN-T-001.json"}],
        "totals": {"total_scenarios": 1, "enabled_scenarios": 0, "disabled_scenarios": 1},
        "current_scenario_app_delegated_permissions": ["User.Read"],
        "additional_permissions_required": [],
    }
    (root / "catalog.json").write_text(json.dumps(catalog))
    return root


class RiskNormalizationTests(unittest.TestCase):
    def test_low_remains_low(self):
        with TemporaryDirectory() as td:
            root = _write_one_scenario_catalog(td, "LOW")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(result.loaded_scenarios[0].definition.risk_level, "LOW")
            self.assertEqual(result.loaded_scenarios[0].catalog_metadata.risk, "LOW")

    def test_moderate_maps_to_medium(self):
        with TemporaryDirectory() as td:
            root = _write_one_scenario_catalog(td, "MODERATE")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(result.loaded_scenarios[0].definition.risk_level, "MEDIUM")
            self.assertEqual(result.loaded_scenarios[0].catalog_metadata.risk, "MODERATE")

    def test_high_remains_high(self):
        with TemporaryDirectory() as td:
            root = _write_one_scenario_catalog(td, "HIGH")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(result.loaded_scenarios[0].definition.risk_level, "HIGH")
            self.assertEqual(result.loaded_scenarios[0].catalog_metadata.risk, "HIGH")

    def test_unknown_risk_is_rejected(self):
        with TemporaryDirectory() as td:
            root = _write_one_scenario_catalog(td, "ELEVATED")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(result.malformed, ("SCN-T-001",))
            self.assertEqual(result.loaded_scenarios, ())

    def test_case_sensitive_rejection(self):
        for bad in ("low", "moderate", "Medium", "high"):
            with TemporaryDirectory() as td:
                root = _write_one_scenario_catalog(td, bad)
                result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
                self.assertEqual(result.malformed, ("SCN-T-001",))
                self.assertEqual(result.loaded_scenarios, ())

    def test_no_arbitrary_aliases_supported(self):
        for bad in ("MOD", "M", "medium", "INTERMEDIATE", "MED"):
            with TemporaryDirectory() as td:
                root = _write_one_scenario_catalog(td, bad)
                result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
                self.assertEqual(result.malformed, ("SCN-T-001",))
                self.assertEqual(result.loaded_scenarios, ())


if __name__ == "__main__":
    unittest.main()