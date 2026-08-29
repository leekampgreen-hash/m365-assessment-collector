"""Explicit tenant capability domain contracts."""
from __future__ import annotations

from enum import Enum


class Capability(str, Enum):
    ENTRA_BASIC = "ENTRA_BASIC"
    ENTRA_P1 = "ENTRA_P1"
    ENTRA_P2 = "ENTRA_P2"
    CONDITIONAL_ACCESS = "CONDITIONAL_ACCESS"
    IDENTITY_PROTECTION = "IDENTITY_PROTECTION"
    RISK_BASED_CONDITIONAL_ACCESS = "RISK_BASED_CONDITIONAL_ACCESS"
    EXCHANGE = "EXCHANGE"
    SHAREPOINT = "SHAREPOINT"
    ONEDRIVE = "ONEDRIVE"
    M365_USAGE_REPORTS = "M365_USAGE_REPORTS"


class EntitlementState(str, Enum):
    ENTITLED = "ENTITLED"
    NOT_ENTITLED = "NOT_ENTITLED"
    UNKNOWN = "UNKNOWN"


class RuntimeState(str, Enum):
    READY = "READY"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FeatureStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_LICENSED = "NOT_LICENSED"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


def derive_feature_status(entitlement: EntitlementState, runtime: RuntimeState) -> FeatureStatus:
    """Keep licensing and operational failures semantically distinct."""
    if entitlement is EntitlementState.NOT_ENTITLED:
        return FeatureStatus.NOT_LICENSED
    if entitlement is EntitlementState.UNKNOWN:
        return FeatureStatus.UNKNOWN
    if runtime is RuntimeState.PERMISSION_REQUIRED:
        return FeatureStatus.PERMISSION_REQUIRED
    if runtime is RuntimeState.SOURCE_UNAVAILABLE:
        return FeatureStatus.SOURCE_UNAVAILABLE
    if runtime is RuntimeState.READY:
        return FeatureStatus.AVAILABLE
    return FeatureStatus.UNKNOWN
