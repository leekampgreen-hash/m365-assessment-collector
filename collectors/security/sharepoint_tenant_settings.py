"""Bounded read-only SharePoint tenant security configuration collector.

This module owns exactly one settings endpoint. It deliberately does not use
the collection paginator because the endpoint returns a singleton object,
not a Graph collection. It also has no persistence or write capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from collectors.core.errors import API_ERROR, PASS, PERMISSION_REQUIRED
from collectors.core.models import utcnow_iso
from collectors.core.transport import GraphHttpError, GraphNetworkError, GraphTransport
from security import (
    DeterministicSecurityFindingService,
    FindingStatus,
    SecurityFinding,
    SecurityObservation,
)

SHAREPOINT_SETTINGS_ENDPOINT = "/admin/sharepoint/settings"
SHAREPOINT_SETTINGS_PATH = "/v1.0/admin/sharepoint/settings"
SHAREPOINT_SETTINGS_PERMISSION = "SharePointTenantSettings.Read.All"
SOURCE_TYPE = "sharepoint_tenant_settings"
NORMALIZED_FIELD = "sharing_capability"

_SHARING_CAPABILITY_MAP = {
    "disabled": "none",
    "existingExternalUserSharingOnly": "existing_guests",
    "externalUserSharingOnly": "new_and_existing_guests",
    "externalUserAndGuestSharing": "anyone",
}


def normalize_sharing_capability(value: Any) -> Optional[str]:
    """Map only documented Graph enum values; unknown values fail closed."""
    if not isinstance(value, str):
        return None
    return _SHARING_CAPABILITY_MAP.get(value)


@dataclass(frozen=True)
class SharePointTenantSettingsResult:
    """In-memory collector output; no raw Graph payload is retained."""

    http_status: Optional[int]
    raw_sharing_capability: Optional[str]
    default_sharing_link_type: Optional[str]
    external_user_expiration_required: Optional[bool]
    external_user_expiration_in_days: Optional[int]
    file_anonymous_link_type: Optional[str]
    folder_anonymous_link_type: Optional[str]
    require_anonymous_links_expire_in_days: Optional[int]
    allow_guest_user_sharing: Optional[bool]
    observation: SecurityObservation
    finding: SecurityFinding
    error_classification: Optional[str] = None


class SharePointTenantSettingsCollector:
    """Collect and evaluate SharePoint tenant external-sharing posture once."""

    def __init__(self, transport: GraphTransport, *, finding_service=None):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()

    def collect(self) -> SharePointTenantSettingsResult:
        """Perform one bounded GET and feed its sanitized observation to CH8."""
        observed_at = utcnow_iso()
        raw_value: Optional[str] = None
        source_available = False
        error_classification: Optional[str] = None
        http_status: Optional[int] = None

        default_sharing_link_type: Optional[str] = None
        external_user_expiration_required: Optional[bool] = None
        external_user_expiration_in_days: Optional[int] = None
        file_anonymous_link_type: Optional[str] = None
        folder_anonymous_link_type: Optional[str] = None
        require_anonymous_links_expire_in_days: Optional[int] = None
        allow_guest_user_sharing: Optional[bool] = None

        try:
            response = self.transport.get(SHAREPOINT_SETTINGS_PATH)
            http_status = response.status
            payload = response.payload
            if isinstance(payload, dict):
                if isinstance(payload.get("sharingCapability"), str):
                    raw_value = payload["sharingCapability"]
                    source_available = normalize_sharing_capability(raw_value) is not None
                default_sharing_link_type = payload.get("defaultSharingLinkType")
                external_user_expiration_required = payload.get("externalUserExpirationRequired")
                external_user_expiration_in_days = payload.get("externalUserExpirationInDays")
                file_anonymous_link_type = payload.get("fileAnonymousLinkType")
                folder_anonymous_link_type = payload.get("folderAnonymousLinkType")
                require_anonymous_links_expire_in_days = payload.get("requireAnonymousLinksExpireInDays")
                allow_guest_user_sharing = payload.get("allowGuestUserSharing")
            else:
                error_classification = API_ERROR
        except GraphHttpError as error:
            http_status = error.status
            error_classification = PERMISSION_REQUIRED if error.status == 403 else API_ERROR
        except GraphNetworkError:
            error_classification = "NETWORK_ERROR"

        normalized = normalize_sharing_capability(raw_value)
        observation = SecurityObservation(
            rule_id="M365-SP-EXT-001",
            value=normalized,
            source_available=source_available,
            observed_at=observed_at,
            source_type=SOURCE_TYPE,
            graph_endpoint=SHAREPOINT_SETTINGS_ENDPOINT,
            normalized_field=NORMALIZED_FIELD,
        )
        finding = self.finding_service.evaluate(observation)
        return SharePointTenantSettingsResult(
            http_status=http_status,
            raw_sharing_capability=raw_value,
            default_sharing_link_type=default_sharing_link_type,
            external_user_expiration_required=external_user_expiration_required,
            external_user_expiration_in_days=external_user_expiration_in_days,
            file_anonymous_link_type=file_anonymous_link_type,
            folder_anonymous_link_type=folder_anonymous_link_type,
            require_anonymous_links_expire_in_days=require_anonymous_links_expire_in_days,
            allow_guest_user_sharing=allow_guest_user_sharing,
            observation=observation,
            finding=finding,
            error_classification=error_classification,
        )


__all__ = [
    "SHAREPOINT_SETTINGS_ENDPOINT",
    "SHAREPOINT_SETTINGS_PERMISSION",
    "SharePointTenantSettingsCollector",
    "SharePointTenantSettingsResult",
    "normalize_sharing_capability",
]
