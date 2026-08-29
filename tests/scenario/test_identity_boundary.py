"""Offline tests for Collector and Scenario identity separation."""
from __future__ import annotations

import unittest
from pathlib import Path

from agents.scenario.auth import (
    IdentityType,
    ScenarioActorMetadata,
    ScenarioAuthenticationContext,
    ScenarioIdentityConfig,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class ScenarioIdentityBoundaryTests(unittest.TestCase):
    def test_scenario_contract_has_no_client_secret_or_collector_identity(self):
        config = ScenarioIdentityConfig(tenant_id="scenario-tenant", client_id="scenario-client")

        self.assertEqual(config.identity_type, IdentityType.SCENARIO_DELEGATED_USER)
        self.assertNotIn("secret", vars(config))
        self.assertNotIn("collector", vars(config))

    def test_collector_identity_type_is_rejected_for_scenario_configuration(self):
        with self.assertRaisesRegex(ValueError, "scenario_delegated_user"):
            ScenarioIdentityConfig(
                tenant_id="scenario-tenant",
                client_id="scenario-client",
                identity_type=IdentityType.COLLECTOR_APP_ONLY,
            )

    def test_expired_authentication_context_rejected(self):
        context = ScenarioAuthenticationContext(
            authenticated=True,
            tenant_id="scenario-tenant",
            client_id="scenario-client",
            correlation_id="corr-1",
            actor=ScenarioActorMetadata(object_id="actor-id"),
            expires_at_epoch=1,
        )
        self.assertFalse(context.is_valid())

        invalid = ScenarioAuthenticationContext(
            authenticated=True,
            tenant_id="scenario-tenant",
            client_id="scenario-client",
            correlation_id="corr-1",
            actor=ScenarioActorMetadata(object_id="actor-id"),
            expires_at_epoch=1,
            identity_type=IdentityType.COLLECTOR_APP_ONLY,
        )
        self.assertFalse(invalid.is_valid())

    def test_scenario_compose_service_has_no_secret_mount(self):
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        scenario_section = compose.split("  scenario:\n", 1)[1].split("\n  postgres:", 1)[0]

        self.assertNotIn("secrets", scenario_section)
        self.assertNotIn("collector", scenario_section.lower())


if __name__ == "__main__":
    unittest.main()
