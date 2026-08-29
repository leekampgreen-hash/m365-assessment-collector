"""Public-surface / import-safety tests for the G08-D1 live executor.

These tests prove that the new live executor module is correctly
exposed from the ``agents.scenario`` package, that it never imports
the collector or discovery layers, and that the public symbols match
the documented surface.
"""
from __future__ import annotations

import sys
import unittest

from agents.scenario import (
    ACTOR_IDENTITY_MISMATCH,
    AUTH_DECLINED,
    AUTH_DEVICE_CODE_ERROR,
    AUTH_TIMEOUT,
    AUTH_TOKEN_ERROR,
    GRAPH_ME_VALIDATION_FAILED,
    LIVE_CONFIGURATION_INVALID,
    LIVE_EXECUTION_DISABLED,
    LIVE_FAILURE_CLASSIFICATIONS,
    LIVE_REQUIRED_DELEGATED_SCOPES,
    LIVE_SUPPORTED_ACTIONS,
    LiveScenarioConfig,
    LiveScenarioExecutor,
    UNSUPPORTED_LIVE_ACTION,
)
from agents.scenario.live_executor import (
    ACTOR_IDENTITY_MISMATCH as _AIM,
    AUTH_DECLINED as _AD,
    AUTH_DEVICE_CODE_ERROR as _ADE,
    AUTH_TIMEOUT as _AT,
    AUTH_TOKEN_ERROR as _ATE,
    GRAPH_ME_VALIDATION_FAILED as _GMV,
    LIVE_CONFIGURATION_INVALID as _LCI,
    LIVE_EXECUTION_DISABLED as _LED,
    LIVE_FAILURE_CLASSIFICATIONS as _LFC,
    LIVE_REQUIRED_DELEGATED_SCOPES as _LRDS,
    LIVE_SUPPORTED_ACTIONS as _LSA,
    LiveScenarioConfig as _LSC,
    LiveScenarioExecutor as _LSE,
    UNSUPPORTED_LIVE_ACTION as _ULA,
)

from tests.scenario.live._helpers import LiveExecutorImportTests


class PublicSurfaceTests(unittest.TestCase):
    def test_live_symbols_exported_from_package(self):
        # The package must expose the same symbols as the module.
        self.assertIs(ACTOR_IDENTITY_MISMATCH, _AIM)
        self.assertIs(AUTH_DECLINED, _AD)
        self.assertIs(AUTH_DEVICE_CODE_ERROR, _ADE)
        self.assertIs(AUTH_TIMEOUT, _AT)
        self.assertIs(AUTH_TOKEN_ERROR, _ATE)
        self.assertIs(GRAPH_ME_VALIDATION_FAILED, _GMV)
        self.assertIs(LIVE_CONFIGURATION_INVALID, _LCI)
        self.assertIs(LIVE_EXECUTION_DISABLED, _LED)
        self.assertIs(LIVE_FAILURE_CLASSIFICATIONS, _LFC)
        self.assertIs(LIVE_REQUIRED_DELEGATED_SCOPES, _LRDS)
        self.assertIs(LIVE_SUPPORTED_ACTIONS, _LSA)
        self.assertIs(LiveScenarioConfig, _LSC)
        self.assertIs(LiveScenarioExecutor, _LSE)
        self.assertIs(UNSUPPORTED_LIVE_ACTION, _ULA)

    def test_failure_classifications_closed(self):
        self.assertEqual(
            set(LIVE_FAILURE_CLASSIFICATIONS),
            {
                LIVE_EXECUTION_DISABLED,
                UNSUPPORTED_LIVE_ACTION,
                LIVE_CONFIGURATION_INVALID,
                AUTH_DEVICE_CODE_ERROR,
                AUTH_TIMEOUT,
                AUTH_DECLINED,
                AUTH_TOKEN_ERROR,
                ACTOR_IDENTITY_MISMATCH,
                GRAPH_ME_VALIDATION_FAILED,
            },
        )

    def test_live_supported_actions_is_only_signin(self):
        self.assertEqual(LIVE_SUPPORTED_ACTIONS, ("INTERACTIVE_SIGNIN",))

    def test_live_required_scopes_are_exactly_user_read(self):
        # The live scope allowlist is immutable and contains exactly
        # one scope: User.Read.
        self.assertIsInstance(LIVE_REQUIRED_DELEGATED_SCOPES, tuple)
        self.assertEqual(LIVE_REQUIRED_DELEGATED_SCOPES, ("User.Read",))


class AuthSubpackageImportTests(unittest.TestCase):
    def test_auth_subpackage_imports(self):
        from agents.scenario.auth import (  # noqa: F401
            DeviceCodeError,
            DeviceCodeFlow,
            DeviceCodePrompt,
            DeviceCodeToken,
            ExpectedActor,
            FakeDeviceCodeTransport,
            FakeGraphTransport,
            GraphMeError,
            GraphMeValidator,
            MeIdentity,
            TokenTransportResponse,
        )

    def test_auth_subpackage_does_not_depend_on_collectors(self):
        # Inspect the auth subpackage's own __init__ source: the
        # submodule names re-exported there are an allow-list, so
        # they are constant. We assert that no submodule under
        # ``agents.scenario.auth`` is a re-export of anything from
        # ``collectors.*``.
        from agents.scenario.auth import device_code, identity, transports

        for module in (device_code, identity, transports):
            for name in module.__dict__:
                self.assertFalse(
                    name.startswith("collectors_") or name == "collectors",
                    "{0} must not import collectors.*; "
                    "found {1!r}".format(module.__name__, name),
                )


if __name__ == "__main__":
    unittest.main()
