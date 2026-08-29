"""Single-shot live entrypoint for the allowlisted SCN-AUTH-001 flow.

This command intentionally has no dry-run fallback.  It cannot contact
Microsoft until an operator supplies ``--live`` and the required environment
variables.  It neither reads collector configuration nor accepts credentials.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from typing import Optional

# Direct execution places ``scripts/`` rather than the project root on sys.path.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.scenario import (
    LiveScenarioConfig,
    LiveScenarioExecutor,
    ScenarioActor,
    ScenarioPlan,
    ScenarioStep,
    correlation_prefix,
)
from agents.scenario.auth import ExpectedActor, MicrosoftDeviceCodeHttpsTransport


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError("{0} must be set".format(name))
    return value


def _expected_actor_from_environment() -> ExpectedActor:
    object_id = os.environ.get("SCENARIO_EXPECTED_ACTOR_OBJECT_ID") or None
    upn = os.environ.get("SCENARIO_EXPECTED_ACTOR_UPN") or None
    expected = ExpectedActor(object_id=object_id, user_principal_name=upn)
    if expected.is_empty():
        raise ValueError(
            "set SCENARIO_EXPECTED_ACTOR_OBJECT_ID and/or SCENARIO_EXPECTED_ACTOR_UPN"
        )
    return expected


def _display_prompt(prompt) -> None:
    # Device-code prompt data is the sole operator-visible pre-completion data.
    print("verification_uri={0}".format(prompt.verification_uri))
    print("user_code={0}".format(prompt.user_code))
    print("expires_in_seconds={0}".format(prompt.expires_in_seconds))
    print("interval_seconds={0}".format(prompt.interval_seconds))
    sys.stdout.flush()


def _await_login_completed(_prompt) -> bool:
    """Accept only an exact, local operator confirmation before polling."""
    print("confirmation_required=LOGIN COMPLETED")
    sys.stdout.flush()
    try:
        confirmation = sys.stdin.readline()
    except (EOFError, KeyboardInterrupt):
        return False
    return confirmation == "LOGIN COMPLETED\n" or confirmation == "LOGIN COMPLETED"


def _safe_result(result) -> None:
    print("status={0}".format(result.status))
    if result.error_code:
        print("error_code={0}".format(result.error_code))
    for label in result.evidence_labels:
        print("evidence={0}".format(label))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run only SCN-AUTH-001 device-code sign-in")
    parser.add_argument("--live", action="store_true", help="explicitly permit the real HTTPS sign-in flow")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; no network operation was started")

    try:
        tenant_id = _required_environment("SCENARIO_TENANT_ID")
        client_id = _required_environment("SCENARIO_CLIENT_ID")
        expected = _expected_actor_from_environment()
        transport = MicrosoftDeviceCodeHttpsTransport(tenant_id=tenant_id)
        execution_id = str(uuid.uuid4())
        actor_id = expected.object_id or expected.user_principal_name or "expected-actor"
        plan = ScenarioPlan(
            plan_id="scn-auth-001-" + execution_id,
            execution_id=execution_id,
            scenario_id="SCN-AUTH-001",
            actor_id=actor_id,
            correlation_id=correlation_prefix(execution_id),
            declared_permissions=["User.Read"],
            steps=[ScenarioStep("interactive-signin", "INTERACTIVE_SIGNIN", ["User.Read"])],
        )
        executor = LiveScenarioExecutor(
            allow_live=True,
            config=LiveScenarioConfig(
                scenario_app_client_id=client_id,
                scenario_app_tenant_id=tenant_id,
                expected_actor=expected,
            ),
            device_code_request_transport=transport.request_device_code,
            device_code_poll_transport=transport.poll_token,
            graph_me_transport=transport.get_me,
            prompt_callback=_display_prompt,
            confirmation_callback=_await_login_completed,
        )
        result = executor.execute(plan.steps[0], ScenarioActor(actor_id=actor_id), plan)
    except ValueError as error:
        print("configuration_error={0}".format(error), file=sys.stderr)
        return 2
    _safe_result(result)
    return 0 if result.status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
