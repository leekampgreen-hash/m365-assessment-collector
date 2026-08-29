"""Executor interface and dry-run implementation.

The framework only ships a deterministic, network-free executor in
G08-A: :class:`DryRunScenarioExecutor`. A live Microsoft Graph
executor is explicitly out of scope and is referenced in
``docs/g08-scenario-agent-framework.md`` as a future boundary.

The dry-run executor must:

* never import Microsoft Graph transport code
* never make a network call
* return deterministic, safe evidence
* preserve scenario / actor / step identifiers
* redact any value in its parameters that looks like a credential
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Protocol, Set

from .actions import describe_action_type, is_supported_action_type
from .models import (
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    ScenarioActor,
    ScenarioExecutionResult,
    ScenarioPlan,
    ScenarioStep,
    ScenarioStepResult,
    utcnow_iso,
)


# Conservative pattern for "this string resembles a token". Used only
# to redact caller-supplied values inside dry-run evidence; it is NOT
# a substitute for real credential handling.
_TOKEN_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9._\-]+|"
    r"sk-[a-z0-9]{8,}|"
    r"ey[a-z0-9]{20,})"
)


# Evidence accepts a deliberately small metadata vocabulary. Drop fields that
# could carry credentials or unbounded request/response content before evidence
# can be persisted or displayed.
_FORBIDDEN_EVIDENCE_FIELDS: Set[str] = {
    "access_token",
    "authorization",
    "authorization_header",
    "client_secret",
    "device_code",
    "user_code",
    "verification_uri",
    "verification_uri_complete",
    "verification_url",
    "verification",
    "challenge",
    "prompt",
    "message",
    "password",
    "raw_payload",
    "refresh_token",
    "secret",
    "secrets",
}


def _redact(value: Any) -> Any:
    """Recursively redact token-shaped strings from ``value``.

    This helper is internal to the framework. It exists so that dry-run
    evidence can never echo a credential-shaped value back to the
    caller. It is intentionally conservative: when in doubt it replaces
    a value with ``"[REDACTED]"``.
    """
    if isinstance(value, str):
        if _TOKEN_PATTERN.search(value):
            return "[REDACTED]"
        return value
    if isinstance(value, dict):
        return {str(k): _redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def redact_value(value: Any) -> Any:
    """Public redaction helper used by dry-run executors and tests.

    This is a thin alias around :func:`_redact` exposed so that tests
    and downstream code can rely on a single, documented behaviour.
    """
    return _redact(value)


def sanitize_evidence(value: Any) -> Any:
    """Return evidence with sensitive fields removed recursively.

    This complements value redaction: credential and raw-payload fields are
    excluded altogether, so their key names and structure cannot be emitted.
    """
    if isinstance(value, dict):
        return {
            str(key): sanitize_evidence(item)
            for key, item in value.items()
            if str(key).lower() not in _FORBIDDEN_EVIDENCE_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_evidence(item) for item in value]
    return _redact(value)


class ScenarioActionExecutor(Protocol):
    """Executor protocol.

    A live executor will later implement ``execute(step, actor_context,
    plan)`` and call Microsoft Graph. The protocol intentionally does
    not prescribe how that happens; the dry-run implementation below
    proves the contract without performing any I/O.
    """

    def execute(
        self,
        step: ScenarioStep,
        actor: Optional[ScenarioActor],
        plan: ScenarioPlan,
    ) -> ScenarioStepResult:
        ...


class DryRunScenarioExecutor:
    """Deterministic executor that never touches Microsoft Graph.

    The executor records what *would* happen, returns a synthetic
    ``SUCCESS`` step result, and never propagates any caller input that
    resembles a credential.
    """

    def execute(
        self,
        step: ScenarioStep,
        actor: Optional[ScenarioActor],
        plan: ScenarioPlan,
    ) -> ScenarioStepResult:
        started_at = utcnow_iso()
        if not is_supported_action_type(step.action_type):
            completed_at = utcnow_iso()
            return ScenarioStepResult(
                step_id=step.step_id,
                action_type=step.action_type,
                status=STATUS_BLOCKED,
                evidence_labels=(),
                started_at=started_at,
                completed_at=completed_at,
                duration=0.0,
                error_code="ACTION_UNSUPPORTED",
                error_message="DryRun refused unsupported action type.",
            )

        safe_params = _redact(step.safe_parameters)
        evidence = [
            "dry_run:{0}".format(step.action_type),
            "scenario:{0}".format(plan.scenario_id),
            "actor:{0}".format(actor.actor_id if actor is not None else "none"),
            "correlation:{0}".format(plan.correlation_id),
            "params_keys:{0}".format(",".join(sorted(safe_params.keys()))),
        ]
        evidence.extend(step.expected_evidence)

        completed_at = utcnow_iso()
        return ScenarioStepResult(
            step_id=step.step_id,
            action_type=step.action_type,
            status=STATUS_SUCCESS,
            evidence_labels=tuple(evidence),
            started_at=started_at,
            completed_at=completed_at,
            duration=0.0,
        )


def action_description(action_type: str) -> str:
    """Convenience wrapper that re-exports the action description helper."""
    return describe_action_type(action_type)


__all__ = [
    "DryRunScenarioExecutor",
    "ScenarioActionExecutor",
    "action_description",
    "redact_value",
    "sanitize_evidence",
]
