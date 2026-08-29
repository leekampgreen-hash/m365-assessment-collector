"""Bounded read-only collector for the Entra authorization policy setting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from collectors.core.errors import API_ERROR, PERMISSION_REQUIRED
from collectors.core.models import utcnow_iso
from collectors.core.transport import GraphHttpError, GraphNetworkError, GraphTransport
from security import DeterministicSecurityFindingService, SecurityFinding, SecurityObservation
from security.rules.entra_guest_access_001 import RULE_ID as GUEST_ACCESS_RULE_ID

AUTHORIZATION_POLICY_ENDPOINT = "/policies/authorizationPolicy"
AUTHORIZATION_POLICY_PATH = "/v1.0/policies/authorizationPolicy"
AUTHORIZATION_POLICY_PERMISSION = "Policy.Read.All"
SOURCE_TYPE = "entra_authorization_policy"
NORMALIZED_FIELD = "allow_invites_from"
GUEST_ACCESS_ENDPOINT = AUTHORIZATION_POLICY_ENDPOINT
GUEST_ACCESS_PATH = AUTHORIZATION_POLICY_PATH
GUEST_ACCESS_PERMISSION = AUTHORIZATION_POLICY_PERMISSION
GUEST_ACCESS_NORMALIZED_FIELD = "guest_directory_access_level"
GUEST_ROLE_IDS = {
    "a0b1b346-4d3e-4e8b-98f8-753987be4970": "same_as_members",
    "10dae51f-b6af-4016-8d66-8c2a99b929b3": "limited_guest",
    "2af84b1e-32c8-42b7-82bc-daa82404023b": "restricted_guest",
}
_VALUES = {
    "none": "none",
    "adminsAndGuestInviters": "admins_and_guest_inviters",
    "adminsGuestInvitersAndAllMembers": "admins_guest_inviters_and_all_members",
    "everyone": "everyone",
}


def normalize_allow_invites_from(value: Any) -> Optional[str]:
    return _VALUES.get(value) if isinstance(value, str) else None


def normalize_guest_directory_access(value: Any) -> str:
    if value is None:
        return "dependency_unavailable"
    if not isinstance(value, str):
        return "custom_or_unknown"
    return GUEST_ROLE_IDS.get(value.lower(), "custom_or_unknown")


@dataclass(frozen=True)
class EntraAuthorizationPolicyResult:
    http_status: Optional[int]
    raw_allow_invites_from: Optional[str]
    observation: SecurityObservation
    finding: SecurityFinding
    error_classification: Optional[str] = None


class EntraAuthorizationPolicyCollector:
    def __init__(self, transport: GraphTransport, *, finding_service=None):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()

    def collect(self) -> EntraAuthorizationPolicyResult:
        observed_at = utcnow_iso()
        raw = None
        available = False
        status = None
        error = None
        try:
            response = self.transport.get(AUTHORIZATION_POLICY_PATH, params={"$select": "allowInvitesFrom"})
            status = response.status
            payload = response.payload
            if isinstance(payload, dict) and isinstance(payload.get("allowInvitesFrom"), str):
                raw = payload["allowInvitesFrom"]
                available = normalize_allow_invites_from(raw) is not None
            else:
                error = API_ERROR
        except GraphHttpError as exc:
            status, error = exc.status, (PERMISSION_REQUIRED if exc.status == 403 else API_ERROR)
        except GraphNetworkError:
            error = "NETWORK_ERROR"
        observation = SecurityObservation(
            rule_id="M365-ENTRA-GUEST-001", value=normalize_allow_invites_from(raw),
            source_available=available, observed_at=observed_at, source_type=SOURCE_TYPE,
            graph_endpoint=AUTHORIZATION_POLICY_ENDPOINT, normalized_field=NORMALIZED_FIELD,
        )
        return EntraAuthorizationPolicyResult(status, raw, observation, self.finding_service.evaluate(observation), error)


class EntraGuestDirectoryAccessCollector:
    """Bounded read-only collector for guestUserRoleId."""
    def __init__(self, transport: GraphTransport, *, finding_service=None):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()

    def collect(self) -> EntraAuthorizationPolicyResult:
        observed_at = utcnow_iso()
        raw = None
        source_available = False
        status = None
        error = None
        try:
            response = self.transport.get(GUEST_ACCESS_PATH, params={"$select": "guestUserRoleId"})
            status = response.status
            payload = response.payload
            if isinstance(payload, dict) and "guestUserRoleId" in payload:
                raw = payload.get("guestUserRoleId")
                source_available = raw is not None
            else:
                error = API_ERROR
        except GraphHttpError as exc:
            status, error = exc.status, (PERMISSION_REQUIRED if exc.status == 403 else API_ERROR)
        except GraphNetworkError:
            error = "NETWORK_ERROR"
        normalized = normalize_guest_directory_access(raw)
        observation = SecurityObservation(
            rule_id=GUEST_ACCESS_RULE_ID, value=normalized,
            source_available=source_available, observed_at=observed_at,
            source_type="authorization_policy", graph_endpoint=GUEST_ACCESS_ENDPOINT,
            normalized_field=GUEST_ACCESS_NORMALIZED_FIELD,
        )
        return EntraAuthorizationPolicyResult(status, raw, observation,
                                               self.finding_service.evaluate(observation), error)


__all__ = ["AUTHORIZATION_POLICY_ENDPOINT", "AUTHORIZATION_POLICY_PATH", "AUTHORIZATION_POLICY_PERMISSION", "EntraAuthorizationPolicyCollector", "EntraAuthorizationPolicyResult", "normalize_allow_invites_from", "EntraGuestDirectoryAccessCollector", "GUEST_ACCESS_ENDPOINT", "GUEST_ACCESS_PATH", "GUEST_ACCESS_PERMISSION", "GUEST_ACCESS_NORMALIZED_FIELD", "normalize_guest_directory_access"]
