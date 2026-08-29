"""Live Scenario Agent executor (G08-D1).

This module ships the first LIVE-capable Scenario Agent executor.
It supports exactly one action:

    ActionType.INTERACTIVE_SIGNIN

Everything else is refused with a controlled ``UNSUPPORTED_LIVE_ACTION``
classification.

Design principles:

* The executor implements the same
  :class:`~agents.scenario.executor.ScenarioActionExecutor` protocol as
  :class:`DryRunScenarioExecutor`. The framework engine cannot tell
  the difference; the contract is the contract.
* The executor **never** runs by default. It requires
  ``allow_live=True`` at construction. When ``allow_live`` is
  ``False`` every call returns a controlled ``BLOCKED`` /
  ``LIVE_EXECUTION_DISABLED`` result. This means a test that
  instantiates the executor by accident cannot accidentally sign in
  a real user.
* The executor does NOT call Microsoft Graph or the Microsoft
  identity platform directly. It delegates to the abstractions in
  :mod:`agents.scenario.auth`. Production wiring will use
  :class:`DeviceCodeFlow` and :class:`GraphMeValidator`; offline
  tests use the fake transports in
  :mod:`agents.scenario.auth.transports`.
* The executor is action-restricted. Anything other than
  ``INTERACTIVE_SIGNIN`` is refused with ``UNSUPPORTED_LIVE_ACTION``.
  No arbitrary Graph URL, no arbitrary HTTP method, no arbitrary body.
* The executor never writes tokens to disk. The token is held in a
  single private attribute of the executor instance and is wiped
  after use. The executor's ``__repr__`` never echoes the token.
* Evidence labels are safe. They never include access or refresh tokens,
  authorization headers, device-code challenge material, client secrets, or
  passwords. Device-code prompts are delivered only through the transient
  operator callback. Evidence includes the authenticated object-id, actor
  correlation metadata, and expected observable endpoint label (``G01-006``).
* Failures are classified using a closed vocabulary:

      LIVE_EXECUTION_DISABLED
      UNSUPPORTED_LIVE_ACTION
      LIVE_CONFIGURATION_INVALID
      AUTH_DEVICE_CODE_ERROR
      AUTH_TIMEOUT
      AUTH_DECLINED
      AUTH_TOKEN_ERROR
      ACTOR_IDENTITY_MISMATCH
      GRAPH_ME_VALIDATION_FAILED

  See :data:`LIVE_FAILURE_CLASSIFICATIONS`.
* The delegated scope set is **pinned**. Every allow_live=True
  construction/execution path requests exactly ``("User.Read",)``.
  Any extra, missing, duplicate, or variant scope fails closed at the
  config boundary (``ValueError``) and again at the execution
  boundary (``LIVE_CONFIGURATION_INVALID``) before any network or
  auth operation can start. See
  :func:`validate_live_delegated_scopes` and :data:`LIVE_REQUIRED_DELEGATED_SCOPES`.
* Actor verification is **mandatory**. For every allow_live=True
  ``INTERACTIVE_SIGNIN`` execution the config must carry an
  ``ExpectedActor`` with at least one verifiable identity field
  (object id and/or UPN). A missing or empty expected actor fails
  closed with ``LIVE_CONFIGURATION_INVALID`` before authentication
  starts. After authentication the executor always performs a single
  ``GET /me``; there is no successful live path that skips actor
  verification, and no evidence label ever claims it was skipped.

This task ends with implementation + offline tests. No real device-code
login is performed in this task; the live acceptance step is G08-D2.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Mapping, Optional, Tuple

from .actions import (
    ACTION_INTERACTIVE_SIGNIN,
    SUPPORTED_ACTION_TYPES,
    declared_permissions_for,
    is_supported_action_type,
)
from .auth import (
    DelegatedScenarioAuthenticationProvider,
    DeviceCodeError,
    DeviceCodePrompt,
    ExpectedActor,
    GraphMeError,
    ScenarioIdentityConfig,
    TokenTransportResponse,
)
from .auth.transports import (
    DeviceCodePollTransport,
    DeviceCodeRequestTransport,
    GraphMeTransport,
)
from .executor import ScenarioActionExecutor
from .models import (
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    ScenarioActor,
    ScenarioExecutionResult,
    ScenarioPlan,
    ScenarioStep,
    ScenarioStepResult,
    utcnow_iso,
)


# ---------------------------------------------------------------------------
# Closed failure-classification vocabulary
# ---------------------------------------------------------------------------


LIVE_EXECUTION_DISABLED = "LIVE_EXECUTION_DISABLED"
UNSUPPORTED_LIVE_ACTION = "UNSUPPORTED_LIVE_ACTION"
LIVE_CONFIGURATION_INVALID = "LIVE_CONFIGURATION_INVALID"
AUTH_DEVICE_CODE_ERROR = "AUTH_DEVICE_CODE_ERROR"
AUTH_TIMEOUT = "AUTH_TIMEOUT"
AUTH_DECLINED = "AUTH_DECLINED"
AUTH_TOKEN_ERROR = "AUTH_TOKEN_ERROR"
ACTOR_IDENTITY_MISMATCH = "ACTOR_IDENTITY_MISMATCH"
GRAPH_ME_VALIDATION_FAILED = "GRAPH_ME_VALIDATION_FAILED"

LIVE_FAILURE_CLASSIFICATIONS: Tuple[str, ...] = (
    LIVE_EXECUTION_DISABLED,
    UNSUPPORTED_LIVE_ACTION,
    LIVE_CONFIGURATION_INVALID,
    AUTH_DEVICE_CODE_ERROR,
    AUTH_TIMEOUT,
    AUTH_DECLINED,
    AUTH_TOKEN_ERROR,
    ACTOR_IDENTITY_MISMATCH,
    GRAPH_ME_VALIDATION_FAILED,
)


# ---------------------------------------------------------------------------
# Runtime / config
# ---------------------------------------------------------------------------


# The only action the live executor performs. Hard-coded allowlist.
LIVE_SUPPORTED_ACTIONS: Tuple[str, ...] = (ACTION_INTERACTIVE_SIGNIN,)

# The immutable delegated-scope allowlist for every live path. The
# effective scope set MUST be exactly this tuple: one scope, User.Read.
# This is the G08-D1 acceptance contract (zero permission expansion).
LIVE_REQUIRED_DELEGATED_SCOPES: Tuple[str, ...] = ("User.Read",)


def validate_live_delegated_scopes(
    scopes: Any,
) -> Tuple[str, ...]:
    """Validate that ``scopes`` is exactly the live scope allowlist.

    The live boundary requests exactly one delegated scope:
    ``User.Read``. This function fails closed on everything else:

    * non tuple/list input is rejected,
    * an empty sequence is rejected,
    * any entry that is not a non-empty string is rejected,
    * any extra scope (``Mail.Send``, ``Calendars.ReadWrite``,
      ``Files.ReadWrite``, wildcards, arbitrary values) is rejected,
    * duplicates are rejected -- a duplicate does not broaden access
      but it is not the exact contract either and must not be
      silently normalized into acceptance,
    * variants are rejected -- entries are compared **exactly**; no
      whitespace stripping, no case folding, no other normalization
      that could silently turn a variant into ``User.Read``.

    Returns the canonical immutable tuple
    :data:`LIVE_REQUIRED_DELEGATED_SCOPES` when the candidate matches.
    Raises ``ValueError`` otherwise. No network or auth operation may
    start before this validation passes.
    """
    if not isinstance(scopes, (tuple, list)):
        raise ValueError(
            "delegated_scopes must be a tuple/list containing exactly "
            "('User.Read',)"
        )
    if not scopes:
        raise ValueError(
            "delegated_scopes must not be empty; the live executor "
            "requires exactly ('User.Read',)"
        )
    for scope in scopes:
        if not isinstance(scope, str) or not scope:
            raise ValueError(
                "delegated_scopes entries must be non-empty strings"
            )
    if tuple(scopes) != LIVE_REQUIRED_DELEGATED_SCOPES:
        raise ValueError(
            "delegated_scopes must be exactly ('User.Read',); "
            "got {0!r}. Extra, missing, duplicate, or variant scopes "
            "are not permitted on the live boundary.".format(
                tuple(str(item) for item in scopes),
            )
        )
    return LIVE_REQUIRED_DELEGATED_SCOPES


def expected_actor_is_usable(expected_actor: Any) -> bool:
    """Return True when ``expected_actor`` carries at least one
    verifiable identity field.

    A usable expected actor is a non-None :class:`ExpectedActor`
    whose ``object_id`` or ``user_principal_name`` is set to a
    non-blank value. Blank/whitespace-only fields do not count.
    """
    return expected_actor is not None and not expected_actor.is_empty()


@dataclass
class LiveScenarioConfig:
    """Runtime configuration for the live executor.

    The config object holds only identifiers, host names, and a
    timeout. It NEVER holds a client secret, access token, refresh
    token, or password. The expected actor identity is supplied
    externally so it never enters a file under version control.

    The fields:

    * ``scenario_app_client_id`` -- the application (client) ID of the
      Scenario Agent app (``graph-agent-scenario-dev``).
    * ``scenario_app_tenant_id`` -- the tenant ID used to build the
      Microsoft identity platform endpoints.
    * ``delegated_scopes`` -- the delegated scopes to request. This is
      **pinned** to exactly ``("User.Read",)``. Any extra, missing,
      duplicate, or variant scope raises ``ValueError`` at
      construction (the config boundary) -- fail closed before any
      executor can be built around it.
    * ``expected_actor`` -- the :class:`ExpectedActor` used to verify
      the ``/me`` response. The live executor requires a usable
      expected actor for every ``INTERACTIVE_SIGNIN`` execution: an
      object ID, a UPN, or both. If it is missing/empty the execution
      fails closed with ``LIVE_CONFIGURATION_INVALID`` before any
      authentication or network operation starts.
    * ``timeout_seconds`` -- the absolute time budget for the entire
      device-code flow. Default is conservative.
    """

    scenario_app_client_id: str
    scenario_app_tenant_id: str
    delegated_scopes: Tuple[str, ...] = LIVE_REQUIRED_DELEGATED_SCOPES
    expected_actor: Optional[ExpectedActor] = None
    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_app_client_id, str) or not self.scenario_app_client_id:
            raise ValueError("scenario_app_client_id must be a non-empty string")
        if not isinstance(self.scenario_app_tenant_id, str) or not self.scenario_app_tenant_id:
            raise ValueError("scenario_app_tenant_id must be a non-empty string")
        # Config-boundary scope pinning: exactly ("User.Read",) or
        # refuse construction. The validated value is stored as the
        # canonical immutable tuple so list inputs cannot leak a
        # mutable scope set into later execution paths.
        self.delegated_scopes = validate_live_delegated_scopes(
            self.delegated_scopes,
        )
        if float(self.timeout_seconds) <= 0:
            raise ValueError("timeout_seconds must be positive")


# ---------------------------------------------------------------------------
# Live executor
# ---------------------------------------------------------------------------


@dataclass
class LiveScenarioExecutor:
    """The first LIVE-capable Scenario Agent executor.

    Construction:

    * ``allow_live`` must be ``True`` for the executor to ever run
      an action. The default is ``False``; the executor is safe to
      instantiate in a test without ever performing a real action.
    * ``config`` is a :class:`LiveScenarioConfig`. Required when
      ``allow_live=True``.
    * ``device_code_request_transport`` -- the request transport.
      Production wiring uses a real HTTP transport; offline tests
      use :class:`~agents.scenario.auth.transports.FakeDeviceCodeTransport`.
    * ``device_code_poll_transport`` -- the poll transport.
    * ``graph_me_transport`` -- the ``GET /me`` transport.

    The executor is **not** a long-running object. It is constructed
    per scenario execution; one scenario -> one executor instance ->
    one device-code flow (if the action is supported).
    """

    allow_live: bool = False
    config: Optional[LiveScenarioConfig] = None
    device_code_request_transport: Optional[DeviceCodeRequestTransport] = None
    device_code_poll_transport: Optional[DeviceCodePollTransport] = None
    graph_me_transport: Optional[GraphMeTransport] = None
    prompt_callback: Optional[Callable[[DeviceCodePrompt], None]] = field(
        default=None, repr=False
    )
    confirmation_callback: Optional[Callable[[DeviceCodePrompt], bool]] = field(
        default=None, repr=False
    )
    sleep: Callable[[float], None] = field(default=time.sleep)
    clock: Callable[[], float] = field(default=time.monotonic)

    def __post_init__(self) -> None:
        if self.allow_live and self.config is None:
            raise ValueError(
                "LiveScenarioExecutor requires a LiveScenarioConfig "
                "when allow_live=True"
            )
        if self.allow_live:
            if self.device_code_request_transport is None:
                raise ValueError(
                    "device_code_request_transport is required when allow_live=True"
                )
            if self.device_code_poll_transport is None:
                raise ValueError(
                    "device_code_poll_transport is required when allow_live=True"
                )
            if self.graph_me_transport is None:
                raise ValueError(
                    "graph_me_transport is required when allow_live=True"
                )

    # ---- Properties --------------------------------------------------

    @property
    def is_live_enabled(self) -> bool:
        return bool(self.allow_live)

    @property
    def supported_actions(self) -> Tuple[str, ...]:
        """The closed allowlist of live actions for this build."""
        return LIVE_SUPPORTED_ACTIONS

    @property
    def declared_permissions(self) -> Tuple[str, ...]:
        """The union of declared permissions for all live actions."""
        out: List[str] = []
        for action in LIVE_SUPPORTED_ACTIONS:
            for perm in declared_permissions_for(action):
                if perm not in out:
                    out.append(perm)
        return tuple(out)

    # ---- Executor protocol ------------------------------------------

    def execute(
        self,
        step: ScenarioStep,
        actor: Optional[ScenarioActor],
        plan: ScenarioPlan,
    ) -> ScenarioStepResult:
        """Run ``step`` and return a safe :class:`ScenarioStepResult`.

        The executor is the live boundary; nothing outside this method
        performs a network call. When ``allow_live`` is ``False``
        the method short-circuits with a controlled
        ``LIVE_EXECUTION_DISABLED`` block.

        For ``INTERACTIVE_SIGNIN`` the method delegates to the canonical
        authentication provider, which owns the transient access-token
        lifecycle and never returns it.
        """
        started_at = utcnow_iso()

        if not self.allow_live:
            return self._blocked_result(
                step=step,
                started_at=started_at,
                error_code=LIVE_EXECUTION_DISABLED,
                error_message=(
                    "LiveScenarioExecutor is constructed with allow_live=False; "
                    "refusing to perform any live action."
                ),
            )

        if not is_supported_action_type(step.action_type):
            return self._blocked_result(
                step=step,
                started_at=started_at,
                error_code=UNSUPPORTED_LIVE_ACTION,
                error_message=(
                    "LiveScenarioExecutor refused unsupported action type: "
                    "{0!r}".format(step.action_type)
                ),
            )

        if step.action_type not in LIVE_SUPPORTED_ACTIONS:
            return self._blocked_result(
                step=step,
                started_at=started_at,
                error_code=UNSUPPORTED_LIVE_ACTION,
                error_message=(
                    "LiveScenarioExecutor refused action {0!r}; "
                    "only INTERACTIVE_SIGNIN is allowed in this build."
                ).format(step.action_type),
            )

        if step.action_type == ACTION_INTERACTIVE_SIGNIN:
            return self._execute_interactive_signin(step, actor, plan, started_at)

        # Unreachable: the allowlist above has exactly one entry.
        return self._blocked_result(
            step=step,
            started_at=started_at,
            error_code=UNSUPPORTED_LIVE_ACTION,
            error_message=(
                "LiveScenarioExecutor has no live implementation for "
                "{0!r}".format(step.action_type)
            ),
        )

    # ---- Action implementations -------------------------------------

    def _execute_interactive_signin(
        self,
        step: ScenarioStep,
        actor: Optional[ScenarioActor],
        plan: ScenarioPlan,
        started_at: str,
    ) -> ScenarioStepResult:
        config = self.config
        assert config is not None  # guarded by allow_live + __post_init__

        # ---- Pre-flight configuration gate --------------------------
        # Fail closed BEFORE any network or auth operation can start.
        # Both checks are repeated at this boundary even though the
        # config constructor validates them: dataclass fields are
        # mutable after construction and the executor is the last
        # line of defence in front of the transports.
        try:
            scopes = validate_live_delegated_scopes(config.delegated_scopes)
        except ValueError as error:
            return self._blocked_result(
                step=step,
                started_at=started_at,
                error_code=LIVE_CONFIGURATION_INVALID,
                error_message=(
                    "Live delegated scope configuration is invalid and "
                    "the live boundary refuses to authenticate: "
                    "{0}".format(error),
                ),
            )

        expected = config.expected_actor
        if not expected_actor_is_usable(expected):
            return self._blocked_result(
                step=step,
                started_at=started_at,
                error_code=LIVE_CONFIGURATION_INVALID,
                error_message=(
                    "expected_actor is mandatory for live INTERACTIVE_SIGNIN; "
                    "supply an ExpectedActor with at least one verifiable "
                    "identity field (object_id and/or user_principal_name). "
                    "The live executor refuses to authenticate without it."
                ),
            )
        assert expected is not None

        actor_id = actor.actor_id if actor is not None else None
        correlation_id = plan.correlation_id
        evidence_prefix: List[str] = [
            "live:INTERACTIVE_SIGNIN",
            "scenario:{0}".format(plan.scenario_id),
            "actor:{0}".format(actor_id if actor_id is not None else "none"),
            "correlation:{0}".format(correlation_id),
            "expected_observable_endpoint:G01-006",
            "authentication_started",
        ]

        # Steps 1-3: canonical delegated device-code authentication and
        # mandatory /me actor verification. The provider returns safe metadata
        # only and disposes of the bearer token before returning.
        try:
            authentication = DelegatedScenarioAuthenticationProvider(
                identity_config=ScenarioIdentityConfig(
                    tenant_id=config.scenario_app_tenant_id,
                    client_id=config.scenario_app_client_id,
                ),
                expected_actor=expected,
                correlation_id=correlation_id,
                delegated_scopes=scopes,
                device_code_request_transport=self.device_code_request_transport,
                device_code_poll_transport=self.device_code_poll_transport,
                graph_me_transport=self.graph_me_transport,
                prompt_callback=self.prompt_callback,
                confirmation_callback=self.confirmation_callback,
                sleep=self.sleep,
                timeout_seconds=config.timeout_seconds,
                clock=self.clock,
            ).authenticate()
        except DeviceCodeError as error:
            completed_at = utcnow_iso()
            return self._failed_result(
                step=step,
                started_at=started_at,
                completed_at=completed_at,
                error_code=error.classification,
                error_message=error.message,
                evidence=evidence_prefix,
            )
        except GraphMeError as error:
            completed_at = utcnow_iso()
            evidence = list(evidence_prefix)
            evidence.append("authentication_completed")
            evidence.append("actor_verification_failed:{0}".format(
                error.classification,
            ))
            return self._failed_result(
                step=step,
                started_at=started_at,
                completed_at=completed_at,
                error_code=error.classification,
                error_message=error.message,
                evidence=evidence,
            )
        except Exception as error:  # pragma: no cover - defensive
            completed_at = utcnow_iso()
            return self._failed_result(
                step=step,
                started_at=started_at,
                completed_at=completed_at,
                error_code=AUTH_DEVICE_CODE_ERROR,
                error_message=(
                    "Device-code flow raised unexpected error: {0}".format(
                        type(error).__name__,
                    )
                ),
                evidence=evidence_prefix,
            )

        # Step 4: emit safe evidence. The authentication provider has already
        # discarded the bearer token, and device-code prompt material never
        # crosses its result boundary.
        completed_at = utcnow_iso()
        evidence: List[str] = list(evidence_prefix)
        evidence.append("authentication_completed")
        evidence.append("actor_verified")
        evidence.append("authenticated_object_id:{0}".format(authentication.context.actor.object_id))
        if authentication.context.actor.user_principal_name:
            evidence.append("authenticated_upn_hash:{0}".format(
                _short_hash(authentication.context.actor.user_principal_name)
            ))

        # Correlation note: GA-SCENARIO-* is recorded in the plan, but
        # is NOT embedded into the actual Microsoft sign-in event. We
        # document this explicitly so the evidence does not falsely
        # claim the marker is present in the upstream telemetry.
        evidence.append("scenario_correlation:plan_correlation_only")
        evidence.append("expected_observable_window_start:{0}".format(started_at))
        evidence.append("expected_observable_window_end:{0}".format(completed_at))

        return ScenarioStepResult(
            step_id=step.step_id,
            action_type=step.action_type,
            status=STATUS_SUCCESS,
            evidence_labels=tuple(evidence),
            started_at=started_at,
            completed_at=completed_at,
            duration=0.0,
        )

    # ---- Helpers ----------------------------------------------------

    def _blocked_result(
        self,
        *,
        step: ScenarioStep,
        started_at: str,
        error_code: str,
        error_message: str,
    ) -> ScenarioStepResult:
        completed_at = utcnow_iso()
        return ScenarioStepResult(
            step_id=step.step_id,
            action_type=step.action_type,
            status=STATUS_BLOCKED,
            evidence_labels=("live:refused", "reason:{0}".format(error_code)),
            started_at=started_at,
            completed_at=completed_at,
            duration=0.0,
            error_code=error_code,
            error_message=error_message,
        )

    def _failed_result(
        self,
        *,
        step: ScenarioStep,
        started_at: str,
        completed_at: str,
        error_code: str,
        error_message: str,
        evidence: Optional[List[str]] = None,
    ) -> ScenarioStepResult:
        labels: List[str] = list(evidence or [])
        labels.append("live:failed")
        labels.append("reason:{0}".format(error_code))
        return ScenarioStepResult(
            step_id=step.step_id,
            action_type=step.action_type,
            status=STATUS_FAILED,
            evidence_labels=tuple(labels),
            started_at=started_at,
            completed_at=completed_at,
            duration=0.0,
            error_code=error_code,
            error_message=error_message,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _short_hash(value: str) -> str:
    """Return a short, non-reversible hash of ``value``.

    Used to record that an authenticated UPN was observed without
    exposing the UPN itself in evidence. The function is deterministic
    and does not collide with the device-code / token values.
    """
    import hashlib

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:12]


__all__ = [
    "ACTOR_IDENTITY_MISMATCH",
    "AUTH_DECLINED",
    "AUTH_DEVICE_CODE_ERROR",
    "AUTH_TIMEOUT",
    "AUTH_TOKEN_ERROR",
    "GRAPH_ME_VALIDATION_FAILED",
    "LIVE_CONFIGURATION_INVALID",
    "LIVE_EXECUTION_DISABLED",
    "LIVE_FAILURE_CLASSIFICATIONS",
    "LIVE_REQUIRED_DELEGATED_SCOPES",
    "LIVE_SUPPORTED_ACTIONS",
    "LiveScenarioConfig",
    "LiveScenarioExecutor",
    "UNSUPPORTED_LIVE_ACTION",
    "expected_actor_is_usable",
    "validate_live_delegated_scopes",
]
