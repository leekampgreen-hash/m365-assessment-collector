"""Scenario Agent framework.

The Scenario Agent is the deterministic execution layer for controlled
Microsoft 365 test actions. It sits *below* any AI / LLM reasoning
and *above* any future live Microsoft Graph transport.

Flow:

    ScenarioRequest
        -> ScenarioRegistry
        -> ScenarioDefinition
        -> Safety gate (agents.scenario.safety)
        -> ScenarioAgent.plan(...)
        -> ScenarioPlan
        -> ScenarioAgent.execute(plan, actor=...)
        -> ScenarioExecutionResult (safe evidence only)

Public surface:

    models       -- typed dataclasses for the entire flow
    actions      -- closed action vocabulary + parameter sanitisation
    actors       -- safe, registry-bound identity model
    safety       -- deterministic safety / authorization gate
    registry     -- deterministic scenario_id -> definition map
    executor     -- executor protocol + dry-run implementation
    engine       -- ScenarioAgent orchestrator

Security properties:

* No module imports Microsoft Graph transport.
* No module stores or accepts passwords, tokens, refresh tokens,
  client secrets, or raw ``Authorization`` header values.
* The caller cannot smuggle URL / method / body overrides through the
  action model; the safety gate rejects such inputs deterministically.
* The dry-run executor performs zero network calls and redacts any
  value that looks like a credential before producing evidence.

The optional :class:`LiveScenarioExecutor` (G08-D1) performs the
public-client device-code flow against the Scenario Agent app
**only** when constructed with ``allow_live=True``. The live executor
is action-restricted to ``INTERACTIVE_SIGNIN``; all other write-capable
actions are refused with ``UNSUPPORTED_LIVE_ACTION``. The live
executor performs no I/O on its own; it delegates to
:mod:`agents.scenario.auth` and requires injected transports. Offline
tests substitute the deterministic fakes declared in
:mod:`agents.scenario.auth.transports`.
"""
from __future__ import annotations

from .actions import (
    ACTION_CREATE_CALENDAR_EVENT,
    ACTION_CREATE_FILE,
    ACTION_CREATE_GROUP_CONTENT,
    ACTION_CREATE_TEAMS_MESSAGE,
    ACTION_DELETE_CALENDAR_EVENT,
    ACTION_DELETE_FILE,
    ACTION_INTERACTIVE_SIGNIN,
    ACTION_NOOP_VALIDATION,
    ACTION_SEND_MAIL,
    ACTION_UPDATE_CALENDAR_EVENT,
    ACTION_UPDATE_FILE,
    SUPPORTED_ACTION_TYPES,
    allowed_parameter_keys,
    declared_permissions_for,
    describe_action_type,
    is_supported_action_type,
    sanitize_action_parameters,
)
from .actors import FORBIDDEN_ACTOR_FIELDS, actor_is_authorized
from .catalog_loader import (
    CatalogLoaderError,
    build_catalog_registry,
    evaluate_permission_readiness,
    load_scenario_catalog,
    scenario_ids_in_deterministic_order,
    validate_observability_g01_references,
)
from .catalog_models import (
    CATALOG_ACTION_TO_FRAMEWORK,
    CATALOG_RISK_TO_FRAMEWORK,
    CLEANUP_BEHAVIORS,
    CatalogLoadResult,
    CatalogMetadata,
    CatalogRegistryResult,
    LoadedScenario,
    OBSERVABILITY_CLASSIFICATIONS,
    OBSERVABILITY_DIRECTLY_OBSERVABLE,
    OBSERVABILITY_INDIRECTLY_OBSERVABLE,
    OBSERVABILITY_NOT_COVERED,
    PERMISSION_DISABLED,
    PERMISSION_MISSING,
    PERMISSION_READINESS_STATES,
    PERMISSION_READY,
    PermissionReadiness,
)
from .engine import ScenarioAgent
from .executor import (
    DryRunScenarioExecutor,
    ScenarioActionExecutor,
    action_description,
)
from .live_executor import (
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
    expected_actor_is_usable,
    validate_live_delegated_scopes,
)
from .models import (
    EXECUTION_STATUSES,
    IDENTITY_NOT_REQUIRED,
    IDENTITY_OPTIONAL,
    IDENTITY_REQUIRED,
    IDENTITY_REQUIREMENTS,
    RISK_HIGH,
    RISK_LEVELS,
    RISK_LOW,
    RISK_MEDIUM,
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_PARTIAL_SUCCESS,
    STATUS_PLANNED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    TERMINAL_STATUSES,
    ScenarioActor,
    ScenarioDefinition,
    ScenarioExecutionResult,
    ScenarioPlan,
    ScenarioRequest,
    ScenarioStep,
    ScenarioStepResult,
    correlation_prefix,
    utcnow_iso,
)
from .evidence import (
    ACTOR_MISMATCH,
    AUTH_FAILED,
    AUTH_TIMEOUT,
    EVIDENCE_ERROR_CODES,
    GRAPH_READ_FAILED,
    POLICY_DENIED,
    UNSUPPORTED_OPERATION,
    ScenarioEvidenceBoundary,
    ScenarioEvidenceBoundaryError,
    ScenarioEvidenceRecord,
    ScenarioEvidenceStorageAdapter,
    ScenarioEvidenceWriter,
)
from .registry import ScenarioRegistry
from .safety import (
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
    allowed_action_types,
    evaluate_safety,
)


__all__ = [
    "ACTION_CREATE_CALENDAR_EVENT",
    "ACTION_CREATE_FILE",
    "ACTION_CREATE_GROUP_CONTENT",
    "ACTION_CREATE_TEAMS_MESSAGE",
    "ACTION_DELETE_CALENDAR_EVENT",
    "ACTION_DELETE_FILE",
    "ACTION_INTERACTIVE_SIGNIN",
    "ACTION_NOOP_VALIDATION",
    "ACTION_SEND_MAIL",
    "ACTION_UPDATE_CALENDAR_EVENT",
    "ACTION_UPDATE_FILE",
    "ACTOR_IDENTITY_MISMATCH",
    "AUTH_DECLINED",
    "AUTH_FAILED",
    "AUTH_DEVICE_CODE_ERROR",
    "AUTH_TIMEOUT",
    "ACTOR_MISMATCH",
    "AUTH_TOKEN_ERROR",
    "BLOCK_REASON_CODES",
    "CATALOG_ACTION_TO_FRAMEWORK",
    "CATALOG_RISK_TO_FRAMEWORK",
    "CLEANUP_BEHAVIORS",
    "CatalogLoadResult",
    "CatalogLoaderError",
    "CatalogMetadata",
    "CatalogRegistryResult",
    "DryRunScenarioExecutor",
    "EXECUTION_STATUSES",
    "EVIDENCE_ERROR_CODES",
    "FORBIDDEN_ACTOR_FIELDS",
    "GRAPH_ME_VALIDATION_FAILED",
    "GRAPH_READ_FAILED",
    "IDENTITY_NOT_REQUIRED",
    "IDENTITY_OPTIONAL",
    "IDENTITY_REQUIRED",
    "IDENTITY_REQUIREMENTS",
    "LIVE_CONFIGURATION_INVALID",
    "LIVE_EXECUTION_DISABLED",
    "LIVE_FAILURE_CLASSIFICATIONS",
    "LIVE_REQUIRED_DELEGATED_SCOPES",
    "LIVE_SUPPORTED_ACTIONS",
    "LoadedScenario",
    "LiveScenarioConfig",
    "LiveScenarioExecutor",
    "OBSERVABILITY_CLASSIFICATIONS",
    "OBSERVABILITY_DIRECTLY_OBSERVABLE",
    "OBSERVABILITY_INDIRECTLY_OBSERVABLE",
    "OBSERVABILITY_NOT_COVERED",
    "PERMISSION_DISABLED",
    "PERMISSION_MISSING",
    "PERMISSION_READINESS_STATES",
    "PERMISSION_READY",
    "POLICY_DENIED",
    "PermissionReadiness",
    "REASON_ARBITRARY_METHOD_INPUT",
    "REASON_ARBITRARY_URL_INPUT",
    "REASON_DESTRUCTIVE_DISABLED",
    "REASON_DISABLED_SCENARIO",
    "REASON_MISSING_ACTOR",
    "REASON_PERMISSIONS_UNDECLARED",
    "REASON_RAW_BODY_PASSTHROUGH",
    "REASON_RAW_TOKEN_INPUT",
    "REASON_UNAUTHORIZED_ACTOR",
    "REASON_UNKNOWN_SCENARIO",
    "REASON_UNSUPPORTED_ACTION",
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
    "ScenarioActionExecutor",
    "ScenarioActor",
    "ScenarioAgent",
    "ScenarioBlockedError",
    "ScenarioDefinition",
    "ScenarioExecutionResult",
    "ScenarioEvidenceBoundary",
    "ScenarioEvidenceBoundaryError",
    "ScenarioEvidenceRecord",
    "ScenarioEvidenceStorageAdapter",
    "ScenarioEvidenceWriter",
    "ScenarioPlan",
    "ScenarioRegistry",
    "ScenarioRequest",
    "ScenarioStep",
    "ScenarioStepResult",
    "SUPPORTED_ACTION_TYPES",
    "TERMINAL_STATUSES",
    "UNSUPPORTED_LIVE_ACTION",
    "UNSUPPORTED_OPERATION",
    "action_description",
    "actor_is_authorized",
    "allowed_action_types",
    "allowed_parameter_keys",
    "build_catalog_registry",
    "correlation_prefix",
    "declared_permissions_for",
    "describe_action_type",
    "expected_actor_is_usable",
    "evaluate_permission_readiness",
    "evaluate_safety",
    "is_supported_action_type",
    "load_scenario_catalog",
    "sanitize_action_parameters",
    "scenario_ids_in_deterministic_order",
    "utcnow_iso",
    "validate_live_delegated_scopes",
    "validate_observability_g01_references",
]
