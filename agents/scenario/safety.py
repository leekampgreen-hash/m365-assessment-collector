"""Deterministic safety / authorization gates for the Scenario Agent.

Every scenario request flows through :func:`evaluate_safety` before any
plan is built or executed. The gate enforces the closed vocabularies
from :mod:`agents.scenario.models` and
:mod:`agents.scenario.actions`, plus a small set of explicit safety
checks:

* only registered ``scenario_id`` values are accepted
* only registered action types are accepted
* disabled scenarios are blocked
* destructive scenarios are blocked unless explicitly opted in
* required delegated permissions are declared on the scenario
* an actor is required when the scenario requires one
* raw token-shaped input strings are rejected and never propagated
* arbitrary URLs, HTTP methods, and body passthroughs cannot enter
  the action model

A blocked request raises :class:`ScenarioBlockedError`. The error
carries a stable, closed ``reason_code`` so callers and tests can
assert against it without parsing messages.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .actions import (
    SUPPORTED_ACTION_TYPES,
    is_supported_action_type,
)
from .actors import actor_is_authorized
from .models import (
    IDENTITY_REQUIRED,
    ScenarioActor,
    ScenarioDefinition,
    ScenarioRequest,
)


# ---------------------------------------------------------------------------
# Reason codes (closed vocabulary)
# ---------------------------------------------------------------------------

REASON_UNKNOWN_SCENARIO = "SCENARIO_UNKNOWN"
REASON_DISABLED_SCENARIO = "SCENARIO_DISABLED"
REASON_DESTRUCTIVE_DISABLED = "SCENARIO_DESTRUCTIVE_DISABLED"
REASON_UNSUPPORTED_ACTION = "ACTION_UNSUPPORTED"
REASON_MISSING_ACTOR = "ACTOR_MISSING"
REASON_UNAUTHORIZED_ACTOR = "ACTOR_UNAUTHORIZED"
REASON_RAW_TOKEN_INPUT = "RAW_TOKEN_INPUT_REJECTED"
REASON_ARBITRARY_URL_INPUT = "ARBITRARY_URL_INPUT_REJECTED"
REASON_ARBITRARY_METHOD_INPUT = "ARBITRARY_METHOD_INPUT_REJECTED"
REASON_RAW_BODY_PASSTHROUGH = "RAW_BODY_PASSTHROUGH_REJECTED"
REASON_PERMISSIONS_UNDECLARED = "PERMISSIONS_UNDECLARED"

BLOCK_REASON_CODES = (
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
)


# Patterns we never want to see as a value in caller input. These are
# matched conservatively and are NOT a substitute for full validation;
# they exist so that obviously dangerous strings cannot be smuggled into
# the action model.
_TOKEN_LIKE_KEYS = (
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "bearer",
    "password",
    "client_secret",
    "secret",
    "api_key",
)


class ScenarioBlockedError(Exception):
    """Raised when the safety gate refuses a scenario request.

    The exception carries a stable ``reason_code`` from
    :data:`BLOCK_REASON_CODES` so that callers and tests can assert
    against the failure category without inspecting message text.
    """

    def __init__(self, reason_code: str, message: str) -> None:
        if reason_code not in BLOCK_REASON_CODES:
            raise ValueError(
                "Unknown block reason code: {0!r}".format(reason_code)
            )
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message

    def __repr__(self) -> str:
        return "ScenarioBlockedError(reason_code={0!r})".format(self.reason_code)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _value_looks_like_token(value: object) -> bool:
    """Return True if a single caller value is obviously credential-shaped."""
    if not isinstance(value, str):
        return False
    lowered = value.lower().lstrip()
    if lowered.startswith("bearer "):
        return True
    if lowered.startswith("basic "):
        return True
    return False


def _mapping_contains_token_shaped_values(mapping) -> bool:
    if not mapping:
        return False
    for key, value in mapping.items():
        if not isinstance(key, str):
            continue
        lowered_key = key.lower()
        if any(token in lowered_key for token in _TOKEN_LIKE_KEYS):
            return True
        if _value_looks_like_token(value):
            return True
        if isinstance(value, (list, tuple)):
            for item in value:
                if _value_looks_like_token(item):
                    return True
    return False


def _mapping_contains_raw_transport_overrides(mapping) -> Optional[str]:
    """Return a reason code if a mapping smuggles raw transport overrides.

    Returns one of ``REASON_ARBITRARY_URL_INPUT``,
    ``REASON_ARBITRARY_METHOD_INPUT``, ``REASON_RAW_BODY_PASSTHROUGH``,
    or ``None`` if no override was detected.

    Order of precedence: URL > METHOD > BODY. Callers should treat any
    of these three reason codes as "raw transport override detected".
    """
    if not mapping:
        return None
    url_keys = {"url", "endpoint", "path"}
    method_keys = {"method", "http_method"}
    body_keys = {"body", "raw_body", "payload"}
    for key in mapping.keys():
        if not isinstance(key, str):
            continue
        lowered = key.lower()
        if lowered in url_keys:
            return REASON_ARBITRARY_URL_INPUT
        if lowered in method_keys:
            return REASON_ARBITRARY_METHOD_INPUT
        if lowered in body_keys:
            return REASON_RAW_BODY_PASSTHROUGH
    return None


def evaluate_safety(
    request: ScenarioRequest,
    *,
    registry,
    allow_destructive: bool = False,
) -> None:
    """Apply all safety gates to ``request``.

    ``registry`` is an object that exposes ``get(scenario_id) ->
    Optional[ScenarioDefinition]`` (see :class:`ScenarioRegistry`).

    The function raises :class:`ScenarioBlockedError` if the request is
    refused. It returns ``None`` on success.
    """
    scenario = registry.get(request.scenario_id)
    if scenario is None:
        raise ScenarioBlockedError(
            REASON_UNKNOWN_SCENARIO,
            "Unknown scenario_id: {0!r}".format(request.scenario_id),
        )

    if not scenario.enabled:
        raise ScenarioBlockedError(
            REASON_DISABLED_SCENARIO,
            "Scenario is disabled: {0!r}".format(request.scenario_id),
        )

    if scenario.destructive and not allow_destructive:
        raise ScenarioBlockedError(
            REASON_DESTRUCTIVE_DISABLED,
            "Destructive scenario blocked by default: {0!r}".format(
                request.scenario_id
            ),
        )

    if not is_supported_action_type(scenario.action_type):
        raise ScenarioBlockedError(
            REASON_UNSUPPORTED_ACTION,
            "Scenario references unsupported action type: {0!r}".format(
                scenario.action_type
            ),
        )

    if not scenario.required_delegated_permissions:
        raise ScenarioBlockedError(
            REASON_PERMISSIONS_UNDECLARED,
            "Scenario does not declare required delegated permissions: "
            "{0!r}".format(request.scenario_id),
        )

    actor = request.actor
    if scenario.identity_requirement == IDENTITY_REQUIRED and actor is None:
        raise ScenarioBlockedError(
            REASON_MISSING_ACTOR,
            "Scenario requires an explicit actor: {0!r}".format(
                request.scenario_id
            ),
        )

    if actor is not None and not actor_is_authorized(actor, scenario):
        raise ScenarioBlockedError(
            REASON_UNAUTHORIZED_ACTOR,
            "Actor is not authorized for scenario: {0!r}".format(
                request.scenario_id
            ),
        )

    if _mapping_contains_token_shaped_values(request.metadata):
        raise ScenarioBlockedError(
            REASON_RAW_TOKEN_INPUT,
            "Request metadata contains token-shaped values.",
        )

    transport_reason = _mapping_contains_raw_transport_overrides(request.metadata)
    if transport_reason is not None:
        raise ScenarioBlockedError(
            transport_reason,
            "Request metadata contains raw transport overrides.",
        )


def allowed_action_types() -> List[str]:
    """Return the list of supported action types (read-only copy)."""
    return list(SUPPORTED_ACTION_TYPES)


__all__ = [
    "BLOCK_REASON_CODES",
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
    "ScenarioBlockedError",
    "allowed_action_types",
    "evaluate_safety",
]