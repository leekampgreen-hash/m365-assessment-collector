"""Bounded read-only collector for Entra risky-application consent policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from collectors.core.errors import API_ERROR, PERMISSION_REQUIRED
from collectors.core.models import utcnow_iso
from collectors.core.transport import GraphHttpError, GraphNetworkError, GraphTransport
from security import DeterministicSecurityFindingService, SecurityFinding, SecurityObservation
from security.rules.entra_risky_consent_001 import RULE_ID

AUTHORIZATION_POLICY_ENDPOINT = "/policies/authorizationPolicy"
AUTHORIZATION_POLICY_PATH = "/v1.0/policies/authorizationPolicy"
AUTHORIZATION_POLICY_PERMISSION = "Policy.Read.All"
NORMALIZED_FIELD = "allow_user_consent_for_risky_apps"
SOURCE_TYPE = "authorization_policy"
DISABLED_STATE = "risky_app_user_consent_disabled"
ENABLED_STATE = "risky_app_user_consent_enabled"
DEPENDENCY_UNAVAILABLE = "dependency_unavailable"


def normalize_risky_app_consent(value: Any) -> Optional[str]:
    if type(value) is not bool:
        return DEPENDENCY_UNAVAILABLE
    return ENABLED_STATE if value else DISABLED_STATE


@dataclass(frozen=True)
class EntraRiskyConsentResult:
    http_status: Optional[int]
    property_present: bool
    raw_allow_user_consent_for_risky_apps: Optional[bool]
    observation: SecurityObservation
    finding: SecurityFinding
    error_classification: Optional[str] = None


class EntraRiskyConsentCollector:
    def __init__(self, transport: GraphTransport, *, finding_service=None):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()

    def collect(self) -> EntraRiskyConsentResult:
        observed_at, status, error = utcnow_iso(), None, None
        raw, present = None, False
        state = DEPENDENCY_UNAVAILABLE
        try:
            response = self.transport.get(AUTHORIZATION_POLICY_PATH, params={"$select": "allowUserConsentForRiskyApps"})
            status = response.status
            payload = response.payload
            if isinstance(payload, dict) and "allowUserConsentForRiskyApps" in payload:
                raw = payload["allowUserConsentForRiskyApps"]
                present = True
                state = normalize_risky_app_consent(raw)
            else:
                error = API_ERROR
        except GraphHttpError as exc:
            status, error = exc.status, (PERMISSION_REQUIRED if exc.status == 403 else API_ERROR)
        except GraphNetworkError:
            error = "NETWORK_ERROR"
        available = present and state != DEPENDENCY_UNAVAILABLE
        observation = SecurityObservation(
            rule_id=RULE_ID, value=state, source_available=available,
            observed_at=observed_at, source_type=SOURCE_TYPE,
            graph_endpoint=AUTHORIZATION_POLICY_ENDPOINT, normalized_field=NORMALIZED_FIELD,
        )
        return EntraRiskyConsentResult(
            status, present, raw, observation, self.finding_service.evaluate(observation), error,
        )


__all__ = [
    "AUTHORIZATION_POLICY_ENDPOINT", "AUTHORIZATION_POLICY_PATH", "AUTHORIZATION_POLICY_PERMISSION",
    "EntraRiskyConsentCollector", "EntraRiskyConsentResult", "normalize_risky_app_consent",
]
