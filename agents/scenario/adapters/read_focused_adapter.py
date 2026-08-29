"""Allowlisted, read-only Microsoft Graph adapter for Scenario Agent.

The adapter deliberately exposes operations rather than URLs.  A caller can
request only ``USER_LIST`` or ``GROUP_LIST``; the transport owns the fixed
Graph endpoint and always uses GET.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import FrozenSet, Mapping, Protocol

from ..auth.contracts import ScenarioAuthenticationContext
from ..auth.transports import TokenTransportResponse


class OperationType(str, Enum):
    """Closed registry of Graph read operations implemented by this adapter."""

    USER_LIST = "USER_LIST"
    GROUP_LIST = "GROUP_LIST"


class PolicyDecision(str, Enum):
    """The adapter accepts only an explicit policy allow decision."""

    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class AuthorizationContext:
    """Operation-specific authorization produced after actor verification."""

    authorized_operations: FrozenSet[OperationType] = field(default_factory=frozenset)

    def authorizes(self, operation: OperationType) -> bool:
        return operation in self.authorized_operations


@dataclass(frozen=True)
class OperationMetadata:
    """The complete persistable result shape for a Graph read."""

    operation: str
    timestamp: str
    status: str
    object_count: int
    correlation_id: str


class GraphReadTransport(Protocol):
    """Fixed-operation transport.  It intentionally has no generic request API."""

    def get_users(self, access_token: str) -> TokenTransportResponse: ...

    def get_groups(self, access_token: str) -> TokenTransportResponse: ...


class PolicyChecker:
    """Small deterministic policy gate used by the read adapter runtime."""

    def __init__(self, allowed_operations=()) -> None:
        self._allowed_operations = frozenset(allowed_operations)

    def decision_for(self, operation: OperationType) -> PolicyDecision:
        if operation.value in self._allowed_operations:
            return PolicyDecision.ALLOW
        return PolicyDecision.DENY


class ReadFocusedAdapter:
    """Execute only allowlisted Graph collection reads through all gates."""

    _REGISTERED_OPERATIONS = frozenset(OperationType)

    def __init__(self, transport: GraphReadTransport, policy_checker: PolicyChecker) -> None:
        if transport is None:
            raise ValueError("transport is required")
        if policy_checker is None:
            raise ValueError("policy_checker is required; policy approval is mandatory")
        self._transport = transport
        self._policy_checker = policy_checker

    def read_users(
        self,
        authentication: ScenarioAuthenticationContext,
        authorization: AuthorizationContext,
        correlation_id: str,
        *,
        _access_token: str | None = None,
    ) -> OperationMetadata:
        return self._execute(OperationType.USER_LIST, authentication, authorization, correlation_id, _access_token)

    def read_groups(
        self,
        authentication: ScenarioAuthenticationContext,
        authorization: AuthorizationContext,
        correlation_id: str,
        *,
        _access_token: str | None = None,
    ) -> OperationMetadata:
        return self._execute(OperationType.GROUP_LIST, authentication, authorization, correlation_id, _access_token)

    def _execute(
        self,
        operation: OperationType,
        authentication: ScenarioAuthenticationContext,
        authorization: AuthorizationContext,
        correlation_id: str,
        access_token: str | None = None,
    ) -> OperationMetadata:
        if operation not in self._REGISTERED_OPERATIONS:
            raise ValueError("Operation is not registered")
        if not isinstance(authentication, ScenarioAuthenticationContext) or not authentication.is_valid():
            raise ValueError("Valid authenticated Scenario Agent identity is required")
        if not isinstance(authorization, AuthorizationContext) or not authorization.authorizes(operation):
            raise ValueError("Operation is not authorized for the authenticated identity")
        if self._policy_checker.decision_for(operation) is not PolicyDecision.ALLOW:
            raise ValueError("Policy rejection: explicit ALLOW is required")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise ValueError("correlation_id is required")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Transient Scenario authentication token is required")

        # Dispatch is closed and owns method/endpoint selection in the transport.
        if operation is OperationType.USER_LIST:
            response = self._transport.get_users(access_token)
        else:
            response = self._transport.get_groups(access_token)
        return self._metadata_from_response(operation, response, correlation_id)

    @staticmethod
    def _metadata_from_response(
        operation: OperationType,
        response: TokenTransportResponse,
        correlation_id: str,
    ) -> OperationMetadata:
        if not isinstance(response, TokenTransportResponse):
            raise ValueError("Graph transport returned an invalid response")
        values = response.body.get("value") if isinstance(response.body, Mapping) else None
        object_count = len(values) if isinstance(values, list) else 0
        return OperationMetadata(
            operation=operation.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="SUCCESS" if not response.is_error and response.status < 400 else "ERROR",
            object_count=object_count,
            correlation_id=correlation_id,
        )


__all__ = [
    "ScenarioAuthenticationContext",
    "AuthorizationContext",
    "GraphReadTransport",
    "OperationMetadata",
    "OperationType",
    "PolicyChecker",
    "PolicyDecision",
    "ReadFocusedAdapter",
]
