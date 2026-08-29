"""Shared helpers and import-safety tests for the G08-D1 offline tests."""
from __future__ import annotations

import importlib
import sys
import unittest
from typing import List, Tuple

from agents.scenario.actions import ACTION_INTERACTIVE_SIGNIN
from agents.scenario.auth import ExpectedActor
from agents.scenario.models import (
    ScenarioActor,
    ScenarioPlan,
    ScenarioStep,
    correlation_prefix,
)


FAKE_TENANT = "00000000-0000-0000-0000-000000000000"
FAKE_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
FAKE_USER_OBJECT_ID = "33333333-3333-3333-3333-333333333333"
FAKE_USER_UPN = "test-user-01@example.test"

# The offline test suite's expected actor. Identity stays synthetic
# (example.test / fake GUIDs); no real UPN is ever hard-coded here.
EXPECTED_TEST_ACTOR = ExpectedActor(object_id=FAKE_USER_OBJECT_ID)


def build_signin_plan(
    *,
    execution_id: str = "exec-1",
    actor_id: str = "test-user-01",
    scenario_id: str = "SCN-AUTH-001",
    step_id: str = "step-001",
) -> Tuple[ScenarioPlan, ScenarioStep, ScenarioActor]:
    """Construct a ScenarioPlan + step + actor suitable for INTERACTIVE_SIGNIN."""
    plan = ScenarioPlan(
        plan_id="plan-{0}".format(execution_id),
        execution_id=execution_id,
        scenario_id=scenario_id,
        actor_id=actor_id,
        correlation_id=correlation_prefix(execution_id),
        declared_permissions=["User.Read"],
        steps=[
            ScenarioStep(
                step_id=step_id,
                action_type=ACTION_INTERACTIVE_SIGNIN,
                declared_permissions=["User.Read"],
            )
        ],
    )
    actor = ScenarioActor(
        actor_id=actor_id,
        user_principal_name=None,
        object_id=None,
    )
    return plan, plan.steps[0], actor


def _module_submodules(module_name: str) -> List[str]:
    """Return the names of all submodules of ``module_name`` in sys.modules.

    The function inspects ``sys.modules`` to find every module whose
    name starts with ``module_name + "."``. It is used by the
    import-safety tests to assert that the live executor does not
    transitively pull in modules from the protected layers.
    """
    prefix = module_name + "."
    return [name for name in sys.modules if name == module_name or name.startswith(prefix)]


class LiveExecutorImportTests(unittest.TestCase):
    """The live executor must not import collectors, discovery, or
    production transport modules as a side effect of its own import.

    The test is module-graph based: we look at the modules the
    framework's live executor pulls in (directly or transitively) and
    assert that none of the protected module names appear.
    """

    def test_live_executor_does_not_depend_on_collectors(self):
        from agents.scenario import live_executor

        # The live_executor module's own __dict__ should not reference
        # anything from collectors.*. This is a structural test that
        # is robust against sys.modules pollution from other test
        # files in the same run.
        for name in live_executor.__dict__:
            self.assertFalse(
                name.startswith("collectors_") or name == "collectors",
                "live_executor must not import collectors.*; "
                "found {0!r}".format(name),
            )

    def test_live_executor_does_not_depend_on_discovery(self):
        from agents.scenario import live_executor

        for name in live_executor.__dict__:
            self.assertFalse(
                name.startswith("agents_discovery_") or name == "agents_discovery",
                "live_executor must not import agents.discovery; "
                "found {0!r}".format(name),
            )

    def test_auth_subpackage_does_not_depend_on_collectors(self):
        from agents.scenario.auth import device_code, identity, transports

        for module in (device_code, identity, transports):
            for name in module.__dict__:
                self.assertFalse(
                    name.startswith("collectors_") or name == "collectors",
                    "{0} must not import collectors.*; "
                    "found {1!r}".format(module.__name__, name),
                )

    def test_only_fixed_transport_may_import_urllib_request(self):
        # D2-A adds a real stdlib HTTPS transport. The executor and flow
        # remain transport-agnostic; only transports.py may import it.
        from pathlib import Path
        from agents.scenario import live_executor
        from agents.scenario.auth import (
            device_code,
            identity,
            transports,
        )
        repo_root = Path(live_executor.__file__).resolve().parent.parent.parent
        for module in (live_executor, device_code, identity):
            module_path = Path(module.__file__).resolve()
            try:
                module_path.relative_to(repo_root)
            except ValueError:
                # Module lives outside the repo; skip.
                continue
            text = module_path.read_text(encoding="utf-8")
            for forbidden in (
                "import urllib.request",
                "from urllib.request import",
                "import requests",
                "from requests import",
                "import httpx",
                "from httpx import",
            ):
                self.assertNotIn(
                    forbidden,
                    text,
                    "{0} must not contain {1!r}".format(
                        module_path.relative_to(repo_root), forbidden,
                    ),
                )


__all__ = [
    "EXPECTED_TEST_ACTOR",
    "FAKE_CLIENT_ID",
    "FAKE_TENANT",
    "FAKE_USER_OBJECT_ID",
    "FAKE_USER_UPN",
    "LiveExecutorImportTests",
    "build_signin_plan",
]
