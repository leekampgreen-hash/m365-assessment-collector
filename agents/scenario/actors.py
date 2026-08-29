"""Safe actor / identity model for the Scenario Agent.

The Scenario Agent never accepts raw credentials. This module provides:

* :class:`ScenarioActor` -- a safe, registry-bound test identity
  carrying identifiers and an explicit allow-list of scenarios /
  workloads it may drive. It never carries a password, token, refresh
  token, client secret, or any other secret material.
* :func:`actor_is_authorized` -- deterministic authorization check
  used by the safety gate.

All helpers in this module are pure; they perform no I/O and no
network access.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .models import ScenarioActor, ScenarioDefinition


# Field names that are NEVER allowed on an actor. Even if a caller
# constructs :class:`ScenarioActor` directly with these set, the safety
# gate treats their presence as a hard block.
FORBIDDEN_ACTOR_FIELDS = (
    "password",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization_header",
    "secret",
    "api_key",
)


def _norm_list(values: Optional[Iterable[str]]) -> Optional[List[str]]:
    if values is None:
        return None
    return [str(v) for v in values]


def actor_is_authorized(actor: ScenarioActor, scenario: ScenarioDefinition) -> bool:
    """Return ``True`` if ``actor`` is authorized to drive ``scenario``.

    Authorization is determined strictly from the actor's allow-list
    and enabled flag. The check is deterministic and side-effect free.
    """
    if not actor.enabled:
        return False
    if not scenario.enabled:
        return False
    if scenario.identity_requirement == "REQUIRED" and not actor.actor_id:
        return False

    allowed_ids = _norm_list(actor.allowed_scenario_ids)
    if allowed_ids is not None and scenario.scenario_id not in allowed_ids:
        return False

    allowed_workloads = _norm_list(actor.allowed_workloads)
    if allowed_workloads is not None and scenario.workload not in allowed_workloads:
        return False

    return True


__all__ = [
    "FORBIDDEN_ACTOR_FIELDS",
    "actor_is_authorized",
]