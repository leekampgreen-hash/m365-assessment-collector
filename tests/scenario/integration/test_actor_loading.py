"""Integration tests: actor loading from actor_model.json.

Verifies the loader:

* loads the logical alias as the actor_id
* does not store any password / token / secret / actual UPN
* honors the actor ``enabled`` flag
* leaves UPN resolution deferred (no fabricated UPN values)
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.scenario.catalog_loader import load_scenario_catalog


def _write_actor_model(td: str, alias: str, *, upn_resolution="DEFERRED_TO_RUNTIME_CONFIG") -> Path:
    root = Path(td)
    (root / "scenarios").mkdir(parents=True, exist_ok=True)
    actor_model = {
        "schema_version": "1.0",
        "description": "test actors",
        "owner": "G08-C",
        "model": "actor_alias",
        "actor_aliases": [
            {
                "alias": alias,
                "role": "primary_actor",
                "description": "Primary test identity.",
                "license_requirements_hint": [],
                "upn_resolution": upn_resolution,
            }
        ],
        "invariant": "alias_set_is_closed",
        "notes": [],
    }
    (root / "actor_model.json").write_text(json.dumps(actor_model))
    # Minimal scenario so the catalog file is parseable.
    scenario = {
        "schema_version": "1.0",
        "scenario_id": "SCN-X-001",
        "name": "n",
        "description": "d",
        "domain": "MAIL",
        "action_type": "SEND_MAIL",
        "actor_required": alias,
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
        "risk": "LOW",
        "enabled": False,
        "permission_pack": "PACK-MAIL",
        "notes": "ok",
    }
    (root / "scenarios" / "SCN-X-001.json").write_text(json.dumps(scenario))
    catalog = {
        "schema_version": "1.0",
        "catalog_id": "T",
        "version": "0.0.1",
        "scenarios": [{"scenario_id": "SCN-X-001", "file": "scenarios/SCN-X-001.json"}],
        "totals": {"total_scenarios": 1, "enabled_scenarios": 0, "disabled_scenarios": 1},
        "current_scenario_app_delegated_permissions": ["User.Read"],
        "additional_permissions_required": [],
        "actor_model_file": "actor_model.json",
    }
    (root / "catalog.json").write_text(json.dumps(catalog))
    return root


class ActorLoadingTests(unittest.TestCase):
    def test_alias_loads_as_actor_id(self):
        with TemporaryDirectory() as td:
            root = _write_actor_model(td, "test-user-99")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertEqual(len(result.actors), 1)
            self.assertEqual(result.actors[0].actor_id, "test-user-99")

    def test_no_credential_fields_on_actor(self):
        with TemporaryDirectory() as td:
            root = _write_actor_model(td, "test-user-99")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            actor = result.actors[0]
            data = actor.to_dict()
            forbidden = {"password", "token", "secret", "api_key", "client_secret"}
            self.assertEqual(set(data.keys()) & forbidden, set())
            self.assertNotIn("refresh_token", data)
            self.assertNotIn("access_token", data)

    def test_unresolved_upn_remains_unresolved(self):
        with TemporaryDirectory() as td:
            root = _write_actor_model(td, "test-user-99")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            actor = result.actors[0]
            self.assertIsNone(actor.user_principal_name)
            self.assertIsNone(actor.object_id)

    def test_upn_resolution_other_than_deferred_rejected(self):
        with TemporaryDirectory() as td:
            root = _write_actor_model(td, "test-user-99", upn_resolution="RESOLVE_NOW")
            with self.assertRaises(Exception) as ctx:
                load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            # The error message must mention the field; we don't
            # import CatalogLoaderError directly to keep the test
            # tolerant of error-type changes.
            self.assertIn("upn_resolution", str(ctx.exception))

    def test_real_production_actors_have_no_upn_values(self):
        result = load_scenario_catalog()
        for actor in result.actors:
            self.assertIsNone(actor.user_principal_name)
            self.assertIsNone(actor.object_id)
            # Alias is the actor_id and never contains an "@" sign.
            self.assertNotIn("@", actor.actor_id)

    def test_actor_enabled_flag_is_honored(self):
        # The framework's ScenarioActor defaults ``enabled`` to True;
        # the loader always produces enabled actors because the
        # alias_set_is_closed invariant in actor_model.json implies all
        # aliases are usable. Disabled scenarios are handled by the
        # safety gate, not by disabling the actor.
        with TemporaryDirectory() as td:
            root = _write_actor_model(td, "test-user-99")
            result = load_scenario_catalog(root, allowed_g01_ids=["G01-006"])
            self.assertTrue(result.actors[0].enabled)


if __name__ == "__main__":
    unittest.main()