"""Scenario identity contracts.

This module intentionally defines configuration only. Device-code token
acquisition remains owned by the existing live-executor boundary; Scenario
configuration must never contain a client secret or Collector credential.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable
from enum import Enum


class IdentityType(str, Enum):
    """Canonical, non-interchangeable workload identity types."""

    COLLECTOR_APP_ONLY = "collector_app_only"
    SCENARIO_DELEGATED_USER = "scenario_delegated_user"


@dataclass(frozen=True)
class ScenarioIdentityConfig:
    """Public-client metadata for the future delegated Scenario runtime.

    This contract deliberately has no secret, token, password, or Collector
    identity field. A scenario identity must be a dedicated test user using
    device-code authentication and delegated permissions.
    """

    tenant_id: str
    client_id: str
    identity_type: IdentityType = IdentityType.SCENARIO_DELEGATED_USER

    def __post_init__(self) -> None:
        if self.identity_type is not IdentityType.SCENARIO_DELEGATED_USER:
            raise ValueError("Scenario identity_type must be scenario_delegated_user")
        for name in ("tenant_id", "client_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("ScenarioIdentityConfig.{} must be a non-empty string".format(name))


@dataclass(frozen=True)
class ScenarioActorMetadata:
    """Verified delegated actor metadata safe to retain with a run.

    This deliberately contains identity attributes only. OAuth artifacts such
    as access tokens, refresh tokens, and authorization headers never cross
    the authentication boundary.
    """

    object_id: str
    user_principal_name: str = ""
    display_name: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not self.object_id:
            raise ValueError("ScenarioActorMetadata.object_id must be a non-empty string")


@dataclass(frozen=True, repr=False)
class ScenarioAuthenticationContext:
    """Safe Scenario authentication metadata passed to approved operations."""

    authenticated: bool
    tenant_id: str
    client_id: str
    correlation_id: str
    actor: ScenarioActorMetadata | None = None
    expires_at_epoch: int | None = None
    identity_type: IdentityType = IdentityType.SCENARIO_DELEGATED_USER

    def is_valid(self, clock: Callable[[], float] = time.time) -> bool:
        return (
            self.authenticated
            and self.identity_type is IdentityType.SCENARIO_DELEGATED_USER
            and bool(self.tenant_id)
            and bool(self.client_id)
            and bool(self.correlation_id)
            and isinstance(self.actor, ScenarioActorMetadata)
            and isinstance(self.expires_at_epoch, int)
            and self.expires_at_epoch > int(clock())
        )


__all__ = [
    "IdentityType",
    "ScenarioActorMetadata",
    "ScenarioAuthenticationContext",
    "ScenarioIdentityConfig",
]
