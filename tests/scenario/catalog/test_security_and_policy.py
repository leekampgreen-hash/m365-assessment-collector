"""Offline security and policy tests for G08-B.

These tests verify:

* no scenario file contains credential substrings,
* no scenario declares a destructive action as enabled,
* all enabled scenarios are LOW risk,
* permission packs are not broad wildcard bundles,
* the catalog does not declare a single "all-purpose" pack.

No live Graph calls are made. No credentials are loaded.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_DIR = REPO_ROOT / "config" / "scenarios"
CATALOG_PATH = SCENARIOS_DIR / "catalog.json"
SCENARIOS_SUBDIR = SCENARIOS_DIR / "scenarios"
PERMISSION_PACKS_PATH = SCENARIOS_DIR / "permission_packs.json"
ACTOR_MODEL_PATH = SCENARIOS_DIR / "actor_model.json"
OBSERVABILITY_MAP_PATH = SCENARIOS_DIR / "observability_map.json"


CREDENTIAL_SUBSTRINGS = (
    "password=",
    "Password=",
    "secret=",
    "Secret=",
    "client_secret",
    "clientSecret",
    "Bearer ",
    "eyJ",
    "tenant_id=",
    "tenantId=",
    "client_id=",
    "clientId=",
)


EMAIL_LIKE_PATTERN = re.compile(r"@[\w.-]+\.[a-z]{2,}")


UPN_VALUE_PATTERN = re.compile(
    r"\"upn\"\s*:\s*\"[^\"]+\"|upn\s*=\s*\"[^\"]+\"|upn\s*=\s*[A-Za-z0-9._-]+@"
)


def _iter_all_scenario_files():
    for path in SCENARIOS_DIR.glob("*.json"):
        yield path
    for path in SCENARIOS_SUBDIR.glob("*.json"):
        yield path


def _load_scenarios():
    catalog = json.loads(CATALOG_PATH.read_text())
    items = []
    for entry in catalog["scenarios"]:
        path = SCENARIOS_DIR / entry["file"]
        items.append((entry["scenario_id"], json.loads(path.read_text()), path))
    return items


class SecurityAndCredentialTests(unittest.TestCase):
    """No file in the catalog may carry credentials, secrets, or UPNs."""

    def test_no_credential_substrings_in_scenario_files(self):
        for path in _iter_all_scenario_files():
            text = path.read_text()
            for substring in CREDENTIAL_SUBSTRINGS:
                self.assertNotIn(
                    substring,
                    text,
                    "file {} contains forbidden substring {}".format(path.name, substring),
                )

    def test_no_email_like_upn_in_scenario_files(self):
        # No file in the catalog should embed a real UPN. Actor aliases
        # are logical only.
        for path in _iter_all_scenario_files():
            text = path.read_text()
            self.assertIsNone(
                EMAIL_LIKE_PATTERN.search(text),
                "file {} contains email-like UPN pattern".format(path.name),
            )

    def test_no_actual_upn_value_in_actor_model(self):
        # The actor model must declare the UPN resolution as deferred;
        # it must not contain an actual UPN value.
        text = ACTOR_MODEL_PATH.read_text()
        self.assertIsNone(
            UPN_VALUE_PATTERN.search(text),
            "actor_model.json contains an actual UPN value",
        )

    def test_no_actual_upn_value_in_scenarios(self):
        for path in SCENARIOS_SUBDIR.glob("*.json"):
            self.assertIsNone(
                UPN_VALUE_PATTERN.search(path.read_text()),
                "scenario {} contains an actual UPN value".format(path.name),
            )

    def test_actor_model_aliases_are_closed(self):
        actor_model = json.loads(ACTOR_MODEL_PATH.read_text())
        self.assertIn("actor_aliases", actor_model)
        aliases = {entry["alias"] for entry in actor_model["actor_aliases"]}
        # The actor_model is closed; no extra aliases may appear in the
        # catalog that are not declared here.
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIn(
                payload["actor_required"],
                aliases,
                "scenario {} references undeclared actor {}".format(
                    scenario_id, payload["actor_required"]
                ),
            )
            if payload.get("peer_actor_required"):
                self.assertIn(
                    payload["peer_actor_required"],
                    aliases,
                    "scenario {} references undeclared peer {}".format(
                        scenario_id, payload["peer_actor_required"]
                    ),
                )


class PolicyAndRiskTests(unittest.TestCase):
    """Risk, destructive-flag, and enabled-state policy enforcement."""

    def test_no_destructive_scenario_is_enabled(self):
        for scenario_id, payload, _path in _load_scenarios():
            if payload["destructive"]:
                self.assertFalse(
                    payload["enabled"],
                    "destructive scenario {} must not be enabled".format(scenario_id),
                )

    def test_every_enabled_scenario_is_low_risk(self):
        for scenario_id, payload, _path in _load_scenarios():
            if payload["enabled"]:
                self.assertEqual(
                    payload["risk"],
                    "LOW",
                    "enabled scenario {} is not LOW risk".format(scenario_id),
                )

    def test_no_high_risk_scenarios_in_catalog(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertNotEqual(
                payload["risk"],
                "HIGH",
                "scenario {} is HIGH risk".format(scenario_id),
            )

    def test_destructive_flag_is_boolean(self):
        for scenario_id, payload, _path in _load_scenarios():
            self.assertIsInstance(payload["destructive"], bool)

    def test_no_tenant_admin_scenario(self):
        # No scenario should claim to mutate tenant-level resources.
        forbidden_actions = (
            "CREATE_USER",
            "DELETE_USER",
            "ASSIGN_ROLE",
            "REMOVE_ROLE",
            "CREATE_POLICY",
            "DELETE_POLICY",
            "INVITE_GUEST",
            "RESET_PASSWORD",
        )
        for scenario_id, payload, _path in _load_scenarios():
            self.assertNotIn(payload["action_type"], forbidden_actions)


class PackExpansionTests(unittest.TestCase):
    """No single pack is a broad wildcard bundle."""

    def test_no_pack_contains_wildcard_permission(self):
        packs = json.loads(PERMISSION_PACKS_PATH.read_text())
        for pack in packs["packs"]:
            for perm in pack["delegated_permissions"]:
                self.assertNotIn(
                    "*",
                    perm,
                    "pack {} contains wildcard permission {}".format(pack["pack_id"], perm),
                )

    def test_no_pack_combines_unrelated_workloads(self):
        # Packs must not bundle Mail + Calendar + Files permissions
        # together. Each pack is independent. Two Teams-related
        # permissions (ChatMessage.Send and ChannelMessage.Send) are
        # allowed in the same Teams pack because they target the same
        # workload.
        packs = json.loads(PERMISSION_PACKS_PATH.read_text())
        workload_groups = {
            "Mail": ("Mail.",),
            "Calendar": ("Calendars.",),
            "Files": ("Files.",),
            "Teams": ("ChatMessage.", "ChannelMessage."),
        }
        for pack in packs["packs"]:
            groups_present = {
                group
                for group, prefixes in workload_groups.items()
                for perm in pack["delegated_permissions"]
                for prefix in prefixes
                if perm.startswith(prefix)
            }
            self.assertLessEqual(
                len(groups_present),
                1,
                "pack {} combines multiple workload permissions: {}".format(
                    pack["pack_id"], sorted(groups_present)
                ),
            )

    def test_no_all_purpose_scenario_pack(self):
        # The catalog must not declare a single pack that covers all
        # scenarios.
        packs = json.loads(PERMISSION_PACKS_PATH.read_text())
        scenario_count = len(json.loads(CATALOG_PATH.read_text())["scenarios"])
        for pack in packs["packs"]:
            self.assertLess(
                len(pack["scenarios_enabled"]),
                scenario_count,
                "pack {} is an all-purpose pack".format(pack["pack_id"]),
            )

    def test_current_scenario_app_state_in_packs(self):
        packs = json.loads(PERMISSION_PACKS_PATH.read_text())
        self.assertEqual(
            packs["current_scenario_app_delegated_permissions"],
            ["User.Read"],
        )

    def test_teams_pack_has_no_enabled_scenarios(self):
        # The Teams pack is reserved; it must not enable any scenario
        # because observability for Teams activity is not supported by
        # G01.
        packs = json.loads(PERMISSION_PACKS_PATH.read_text())
        teams_pack = next(p for p in packs["packs"] if p["pack_id"] == "PACK-TEAMS")
        self.assertEqual(teams_pack["scenarios_enabled"], [])
        self.assertEqual(teams_pack["current_status"], "DEFERRED")

    def test_auth_pack_has_no_extra_permission(self):
        packs = json.loads(PERMISSION_PACKS_PATH.read_text())
        auth_pack = next(p for p in packs["packs"] if p["pack_id"] == "PACK-AUTH")
        self.assertEqual(auth_pack["delegated_permissions"], [])
        self.assertEqual(auth_pack["current_status"], "NO_EXPANSION_REQUIRED")


if __name__ == "__main__":
    unittest.main()