"""Bounded read-only collector for Entra user application consent policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from collectors.core.errors import API_ERROR, PERMISSION_REQUIRED
from collectors.core.models import utcnow_iso
from collectors.core.transport import GraphHttpError, GraphNetworkError, GraphTransport
from security import DeterministicSecurityFindingService, SecurityFinding, SecurityObservation
from security.rules.entra_consent_001 import RULE_ID

AUTHORIZATION_POLICY_ENDPOINT = "/policies/authorizationPolicy"
AUTHORIZATION_POLICY_PATH = "/v1.0/policies/authorizationPolicy"
AUTHORIZATION_POLICY_PERMISSION = "Policy.Read.All"
NORMALIZED_FIELD = "user_app_consent_policy"
SOURCE_TYPE = "authorization_policy"
_PREFIX = "managepermissiongrantsforself."
_RECOMMENDED = "managepermissiongrantsforself.microsoft-user-default-recommended"
_LOW = "managepermissiongrantsforself.microsoft-user-default-low"
_LEGACY = "managepermissiongrantsforself.microsoft-user-default-legacy"


def _normalize_user_consent_policy(value: Any) -> tuple[Optional[str], list[str]]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        return None, []
    relevant = [item.strip() for item in value if item.strip().lower().startswith(_PREFIX)]
    lowered = {item.lower() for item in relevant}
    if _LEGACY in lowered:
        return "legacy_broad_consent", relevant
    if any(item not in {_RECOMMENDED, _LOW} for item in lowered):
        return "custom_or_unknown", relevant
    if not relevant:
        return "user_consent_disabled", relevant
    return ("microsoft_recommended" if _RECOMMENDED in lowered else "limited_low_risk"), relevant


def normalize_user_consent_policy(value: Any) -> Optional[str]:
    """Return the canonical user-consent state for assigned policy IDs."""
    return _normalize_user_consent_policy(value)[0]


@dataclass(frozen=True)
class EntraUserConsentResult:
    http_status: Optional[int]
    relevant_policy_ids: tuple[str, ...]
    normalized_state: Optional[str]
    observation: SecurityObservation
    finding: SecurityFinding
    error_classification: Optional[str] = None


class EntraUserConsentCollector:
    def __init__(self, transport: GraphTransport, *, finding_service=None):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()

    def collect(self) -> EntraUserConsentResult:
        observed_at, status, error = utcnow_iso(), None, None
        state, relevant = None, []
        try:
            response = self.transport.get(AUTHORIZATION_POLICY_PATH, params={"$select": "defaultUserRolePermissions"})
            status = response.status
            payload = response.payload
            permissions = payload.get("defaultUserRolePermissions") if isinstance(payload, dict) else None
            assigned = permissions.get("permissionGrantPoliciesAssigned") if isinstance(permissions, dict) else None
            state, relevant = _normalize_user_consent_policy(assigned)
            if state is None:
                error = API_ERROR
        except GraphHttpError as exc:
            status, error = exc.status, (PERMISSION_REQUIRED if exc.status == 403 else API_ERROR)
        except GraphNetworkError:
            error = "NETWORK_ERROR"
        observation = SecurityObservation(
            rule_id=RULE_ID, value=state, source_available=state is not None,
            observed_at=observed_at, source_type=SOURCE_TYPE,
            graph_endpoint=AUTHORIZATION_POLICY_ENDPOINT, normalized_field=NORMALIZED_FIELD,
        )
        return EntraUserConsentResult(status, tuple(relevant), state, observation, self.finding_service.evaluate(observation), error)


__all__ = ["AUTHORIZATION_POLICY_ENDPOINT", "AUTHORIZATION_POLICY_PATH", "AUTHORIZATION_POLICY_PERMISSION", "EntraUserConsentCollector", "EntraUserConsentResult", "normalize_user_consent_policy"]
