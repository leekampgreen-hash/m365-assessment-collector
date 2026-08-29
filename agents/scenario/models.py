"""Typed models for the Scenario Agent framework.

These dataclasses describe a deterministic scenario execution contract:

    ScenarioDefinition  - the registry-level description of an action pattern
    ScenarioRequest     - caller input that names a scenario_id (+ actor)
    ScenarioPlan        - a deterministic, immutable execution plan
    ScenarioStep        - one controllable action inside a plan
    ScenarioExecutionResult
                         - the safe, evidence-only result of one execute(...)
    ScenarioStepResult  - per-step safe evidence
    ScenarioExecutionStatus
                         - closed vocabulary (PLANNED/RUNNING/SUCCESS/...)

The models intentionally contain NO credentials, tokens, secrets, raw
``Authorization`` header values, or arbitrary Graph URLs. Caller input
is never mutated by ``to_dict``/``asdict``/planning helpers.

This module is import-time safe: importing it triggers no I/O and no
network access.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Closed status vocabulary
# ---------------------------------------------------------------------------

STATUS_PLANNED = "PLANNED"
STATUS_RUNNING = "RUNNING"
STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_BLOCKED = "BLOCKED"

EXECUTION_STATUSES = (
    STATUS_PLANNED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_PARTIAL_SUCCESS,
    STATUS_FAILED,
    STATUS_BLOCKED,
)

TERMINAL_STATUSES = (
    STATUS_SUCCESS,
    STATUS_PARTIAL_SUCCESS,
    STATUS_FAILED,
    STATUS_BLOCKED,
)


# ---------------------------------------------------------------------------
# Risk vocabulary
# ---------------------------------------------------------------------------

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

RISK_LEVELS = (RISK_LOW, RISK_MEDIUM, RISK_HIGH)


# ---------------------------------------------------------------------------
# Identity requirement vocabulary
# ---------------------------------------------------------------------------

IDENTITY_NOT_REQUIRED = "NOT_REQUIRED"
IDENTITY_OPTIONAL = "OPTIONAL"
IDENTITY_REQUIRED = "REQUIRED"

IDENTITY_REQUIREMENTS = (
    IDENTITY_NOT_REQUIRED,
    IDENTITY_OPTIONAL,
    IDENTITY_REQUIRED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def correlation_prefix(execution_id: str) -> str:
    """Build the canonical correlation marker for a scenario execution.

    The marker is intentionally simple and stable so collectors can later
    prove that observed telemetry corresponds to a specific scenario
    action. It contains no caller-supplied data.
    """
    return "GA-SCENARIO-{0}".format(execution_id)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class ScenarioDefinition:
    """Registry-level definition of an executable scenario.

    A scenario is a *pattern* of actions the Scenario Agent may execute
    against a test user. It is registered ahead of time and looked up by
    ``scenario_id``; callers cannot construct raw Graph operations at
    request time.
    """

    scenario_id: str
    name: str
    description: str
    workload: str
    action_type: str
    identity_requirement: str = IDENTITY_REQUIRED
    required_delegated_permissions: List[str] = field(default_factory=list)
    expected_observable_evidence: List[str] = field(default_factory=list)
    cleanup_required: bool = False
    risk_level: str = RISK_LOW
    destructive: bool = False
    enabled: bool = True
    cleanup_scenario_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioRequest:
    """Caller-supplied request to plan/execute a scenario.

    Only ``scenario_id`` and ``actor`` are required. The request is
    validated against the registry; arbitrary URLs, methods, or bodies
    cannot be supplied here.
    """

    scenario_id: str
    actor: Optional["ScenarioActor"] = None
    correlation_tag: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "actor": self.actor.to_dict() if self.actor is not None else None,
            "correlation_tag": self.correlation_tag,
            "metadata": dict(self.metadata),
        }


@dataclass
class ScenarioStep:
    """One controllable action inside a :class:`ScenarioPlan`.

    Steps are deterministic data: an action type, a correlation id,
    and a fixed set of safe, declared parameters. They never contain
    Graph URLs, HTTP methods, or arbitrary caller-supplied bodies.
    """

    step_id: str
    action_type: str
    declared_permissions: List[str] = field(default_factory=list)
    safe_parameters: Dict[str, Any] = field(default_factory=dict)
    expected_evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioPlan:
    """A deterministic, immutable plan produced by ``ScenarioAgent.plan``.

    The plan records the scenario that was selected, the actor that
    will act on its behalf, and the ordered steps that will be
    executed. It carries NO credentials and NO Graph URLs.
    """

    plan_id: str
    execution_id: str
    scenario_id: str
    actor_id: Optional[str]
    correlation_id: str
    declared_permissions: List[str] = field(default_factory=list)
    steps: List[ScenarioStep] = field(default_factory=list)
    expected_evidence: List[str] = field(default_factory=list)
    cleanup_required: bool = False
    cleanup_scenario_id: Optional[str] = None
    risk_level: str = RISK_LOW
    status: str = STATUS_PLANNED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "execution_id": self.execution_id,
            "scenario_id": self.scenario_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "declared_permissions": list(self.declared_permissions),
            "steps": [s.to_dict() for s in self.steps],
            "expected_evidence": list(self.expected_evidence),
            "cleanup_required": self.cleanup_required,
            "cleanup_scenario_id": self.cleanup_scenario_id,
            "risk_level": self.risk_level,
            "status": self.status,
        }


@dataclass
class ScenarioStepResult:
    """Per-step safe evidence produced by an executor.

    Executors MUST return only safe evidence. Token-shaped strings,
    Authorization headers, passwords, secrets, and arbitrary Graph
    response bodies must never appear here.
    """

    step_id: str
    action_type: str
    status: str
    evidence_labels: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioExecutionResult:
    """Safe, evidence-only result of one ``ScenarioAgent.execute(...)``.

    This object is a runtime execution artifact. It is never passed directly
    to persistence; ``ScenarioEvidenceBoundary`` projects the narrow typed
    evidence record. It never contains:
      - Microsoft Graph access tokens
      - ``Authorization`` header values
      - passwords or client secrets
      - raw, unfiltered Graph response bodies
      - device-code prompts, user codes, verification URIs, or prompt messages
    """

    execution_id: str
    correlation_id: str
    scenario_id: str
    actor_id: Optional[str]
    status: str = STATUS_PLANNED
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    step_results: List[ScenarioStepResult] = field(default_factory=list)
    final_evidence: List[str] = field(default_factory=list)
    declared_permissions: List[str] = field(default_factory=list)
    cleanup_required: bool = False
    cleanup_scenario_id: Optional[str] = None
    risk_level: str = RISK_LOW
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "correlation_id": self.correlation_id,
            "scenario_id": self.scenario_id,
            "actor_id": self.actor_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "step_results": [s.to_dict() for s in self.step_results],
            "final_evidence": list(self.final_evidence),
            "declared_permissions": list(self.declared_permissions),
            "cleanup_required": self.cleanup_required,
            "cleanup_scenario_id": self.cleanup_scenario_id,
            "risk_level": self.risk_level,
            "blocked_reason": self.blocked_reason,
        }


@dataclass
class ScenarioActor:
    """Safe, registry-bound test identity.

    The actor carries only identifiers and a whitelist of scenarios /
    workloads the identity is allowed to drive. It NEVER carries
    credentials, tokens, refresh tokens, client secrets, or any other
    secret material.
    """

    actor_id: str
    user_principal_name: Optional[str] = None
    object_id: Optional[str] = None
    allowed_scenario_ids: Optional[List[str]] = None
    allowed_workloads: Optional[List[str]] = None
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "user_principal_name": self.user_principal_name,
            "object_id": self.object_id,
            "allowed_scenario_ids": (
                list(self.allowed_scenario_ids)
                if self.allowed_scenario_ids is not None
                else None
            ),
            "allowed_workloads": (
                list(self.allowed_workloads)
                if self.allowed_workloads is not None
                else None
            ),
            "enabled": self.enabled,
            "description": self.description,
        }


__all__ = [
    "EXECUTION_STATUSES",
    "IDENTITY_NOT_REQUIRED",
    "IDENTITY_OPTIONAL",
    "IDENTITY_REQUIRED",
    "IDENTITY_REQUIREMENTS",
    "RISK_HIGH",
    "RISK_LEVELS",
    "RISK_LOW",
    "RISK_MEDIUM",
    "STATUS_BLOCKED",
    "STATUS_FAILED",
    "STATUS_PARTIAL_SUCCESS",
    "STATUS_PLANNED",
    "STATUS_RUNNING",
    "STATUS_SUCCESS",
    "ScenarioActor",
    "ScenarioDefinition",
    "ScenarioExecutionResult",
    "ScenarioPlan",
    "ScenarioRequest",
    "ScenarioStep",
    "ScenarioStepResult",
    "TERMINAL_STATUSES",
    "correlation_prefix",
    "utcnow_iso",
]
