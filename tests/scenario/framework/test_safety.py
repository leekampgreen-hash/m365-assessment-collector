"""Offline tests for the actor model and safety gate."""
from __future__ import annotations

import unittest

from agents.scenario.actions import ACTION_SEND_MAIL
from agents.scenario.models import (
    IDENTITY_NOT_REQUIRED,
    IDENTITY_OPTIONAL,
    IDENTITY_REQUIRED,
    RISK_LOW,
    ScenarioActor,
    ScenarioDefinition,
    ScenarioRequest,
)
from agents.scenario.registry import ScenarioRegistry
from agents.scenario.safety import (
    BLOCK_REASON_CODES,
    REASON_ARBITRARY_METHOD_INPUT,
    REASON_ARBITRARY_URL_INPUT,
    REASON_DESTRUCTIVE_DISABLED,
    REASON_DISABLED_SCENARIO,
    REASON_MISSING_ACTOR,
    REASON_PERMISSIONS_UNDECLARED,
    REASON_RAW_BODY_PASSTHROUGH,
    REASON_RAW_TOKEN_INPUT,
    REASON_UNAUTHORIZED_ACTOR,
    REASON_UNKNOWN_SCENARIO,
    REASON_UNSUPPORTED_ACTION,
    ScenarioBlockedError,
    actor_is_authorized,
    evaluate_safety,
)


def _scenario(
    *,
    scenario_id="scenario.test.x",
    action_type=ACTION_SEND_MAIL,
    enabled=True,
    destructive=False,
    identity_requirement=IDENTITY_REQUIRED,
    permissions=("Mail.Send",),
    workload="mail",
):
    return ScenarioDefinition(
        scenario_id=scenario_id,
        name="Test scenario",
        description="For tests.",
        workload=workload,
        action_type=action_type,
        identity_requirement=identity_requirement,
        required_delegated_permissions=list(permissions),
        risk_level=RISK_LOW,
        destructive=destructive,
        enabled=enabled,
    )


def _actor(**overrides):
    defaults = dict(actor_id="test-user-1")
    defaults.update(overrides)
    return ScenarioActor(**defaults)


class ActorModelTests(unittest.TestCase):
    def test_actor_is_authorized_when_enabled_and_no_restrictions(self):
        scenario = _scenario()
        actor = _actor()
        self.assertTrue(actor_is_authorized(actor, scenario))

    def test_disabled_actor_is_not_authorized(self):
        scenario = _scenario()
        actor = _actor(enabled=False)
        self.assertFalse(actor_is_authorized(actor, scenario))

    def test_disabled_scenario_is_not_authorized(self):
        scenario = _scenario(enabled=False)
        actor = _actor()
        self.assertFalse(actor_is_authorized(actor, scenario))

    def test_actor_id_whitelist_enforced(self):
        scenario = _scenario(scenario_id="scenario.mail.send_test_message")
        actor = _actor(allowed_scenario_ids=["scenario.other"])
        self.assertFalse(actor_is_authorized(actor, scenario))

    def test_workload_whitelist_enforced(self):
        scenario = _scenario(workload="mail")
        actor = _actor(allowed_workloads=["calendar"])
        self.assertFalse(actor_is_authorized(actor, scenario))

    def test_actor_authorization_is_actor_id_sensitive(self):
        scenario = _scenario(identity_requirement=IDENTITY_REQUIRED)
        actor = ScenarioActor(actor_id="")
        self.assertFalse(actor_is_authorized(actor, scenario))


class SafetyGateRegisteredScenarioTests(unittest.TestCase):
    def setUp(self):
        self.registry = ScenarioRegistry()

    def test_registered_scenario_passes_safety(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
        )
        # No exception raised.
        evaluate_safety(request, registry=self.registry)

    def test_unknown_scenario_is_blocked(self):
        request = ScenarioRequest(
            scenario_id="scenario.does.not.exist",
            actor=_actor(),
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_UNKNOWN_SCENARIO)

    def test_disabled_scenario_is_blocked(self):
        definition = _scenario(
            scenario_id="scenario.test.disabled",
            enabled=False,
        )
        registry = ScenarioRegistry(extra=[definition])
        request = ScenarioRequest(
            scenario_id="scenario.test.disabled",
            actor=_actor(),
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=registry)
        self.assertEqual(ctx.exception.reason_code, REASON_DISABLED_SCENARIO)

    def test_destructive_scenario_blocked_by_default(self):
        definition = _scenario(
            scenario_id="scenario.test.destructive",
            destructive=True,
        )
        registry = ScenarioRegistry(extra=[definition])
        request = ScenarioRequest(
            scenario_id="scenario.test.destructive",
            actor=_actor(),
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=registry)
        self.assertEqual(ctx.exception.reason_code, REASON_DESTRUCTIVE_DISABLED)

    def test_destructive_scenario_allowed_with_opt_in(self):
        definition = _scenario(
            scenario_id="scenario.test.destructive",
            destructive=True,
        )
        registry = ScenarioRegistry(extra=[definition])
        request = ScenarioRequest(
            scenario_id="scenario.test.destructive",
            actor=_actor(),
        )
        # No exception when allow_destructive=True.
        evaluate_safety(request, registry=registry, allow_destructive=True)

    def test_unsupported_action_is_blocked(self):
        definition = _scenario(
            scenario_id="scenario.test.bad_action",
            action_type="NUKE_TENANT",
        )
        registry = ScenarioRegistry(extra=[definition])
        request = ScenarioRequest(
            scenario_id="scenario.test.bad_action",
            actor=_actor(),
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=registry)
        self.assertEqual(ctx.exception.reason_code, REASON_UNSUPPORTED_ACTION)

    def test_undeclared_permissions_blocked(self):
        # The registry already blocks scenarios without permissions at
        # construction time; we exercise the safety gate independently
        # using a minimal stub registry.
        definition = _scenario(
            scenario_id="scenario.test.no_perms",
            permissions=(),
        )

        class StubRegistry:
            def get(self, scenario_id):
                if scenario_id == definition.scenario_id:
                    return definition
                return None

        request = ScenarioRequest(
            scenario_id="scenario.test.no_perms",
            actor=_actor(),
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=StubRegistry())
        self.assertEqual(ctx.exception.reason_code, REASON_PERMISSIONS_UNDECLARED)

    def test_missing_actor_blocked_for_required_scenario(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=None,
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_MISSING_ACTOR)

    def test_unauthorized_actor_blocked(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(allowed_scenario_ids=["scenario.other"]),
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_UNAUTHORIZED_ACTOR)

    def test_optional_identity_does_not_require_actor(self):
        definition = _scenario(
            scenario_id="scenario.framework.noop_validation",
            identity_requirement=IDENTITY_OPTIONAL,
            permissions=("User.Read",),
        )
        registry = ScenarioRegistry(extra=[definition])
        request = ScenarioRequest(
            scenario_id="scenario.framework.noop_validation",
            actor=None,
        )
        evaluate_safety(request, registry=registry)

    def test_not_required_identity_allows_no_actor(self):
        definition = _scenario(
            scenario_id="scenario.framework.not_required",
            identity_requirement=IDENTITY_NOT_REQUIRED,
            permissions=("User.Read",),
        )
        registry = ScenarioRegistry(extra=[definition])
        request = ScenarioRequest(
            scenario_id="scenario.framework.not_required",
            actor=None,
        )
        evaluate_safety(request, registry=registry)


class SafetyGateInputHardeningTests(unittest.TestCase):
    def setUp(self):
        self.registry = ScenarioRegistry()

    def test_raw_token_input_in_metadata_is_blocked(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"token": "bearer abcdef"},
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_RAW_TOKEN_INPUT)

    def test_bearer_string_in_metadata_is_blocked(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"note": "bearer abcdef"},
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_RAW_TOKEN_INPUT)

    def test_arbitrary_url_key_in_metadata_is_blocked(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"url": "https://graph.microsoft.com/v1.0/me/sendMail"},
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_ARBITRARY_URL_INPUT)

    def test_arbitrary_method_key_in_metadata_is_blocked(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"method": "POST"},
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_ARBITRARY_METHOD_INPUT)

    def test_raw_body_key_in_metadata_is_blocked(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"body": "<raw body passthrough>"},
        )
        with self.assertRaises(ScenarioBlockedError) as ctx:
            evaluate_safety(request, registry=self.registry)
        self.assertEqual(ctx.exception.reason_code, REASON_RAW_BODY_PASSTHROUGH)

    def test_clean_metadata_passes(self):
        request = ScenarioRequest(
            scenario_id="scenario.mail.send_test_message",
            actor=_actor(),
            metadata={"parameters": {"subject": "hello"}},
        )
        evaluate_safety(request, registry=self.registry)


class BlockedErrorTests(unittest.TestCase):
    def test_blocked_error_rejects_unknown_reason(self):
        with self.assertRaises(ValueError):
            ScenarioBlockedError("NOT_A_CODE", "msg")

    def test_block_reason_codes_are_closed(self):
        # Sanity check that every documented reason is registered.
        self.assertEqual(
            set(BLOCK_REASON_CODES),
            {
                REASON_UNKNOWN_SCENARIO,
                REASON_DISABLED_SCENARIO,
                REASON_DESTRUCTIVE_DISABLED,
                REASON_UNSUPPORTED_ACTION,
                REASON_MISSING_ACTOR,
                REASON_UNAUTHORIZED_ACTOR,
                REASON_RAW_TOKEN_INPUT,
                REASON_ARBITRARY_URL_INPUT,
                REASON_ARBITRARY_METHOD_INPUT,
                REASON_RAW_BODY_PASSTHROUGH,
                REASON_PERMISSIONS_UNDECLARED,
            },
        )


if __name__ == "__main__":
    unittest.main()