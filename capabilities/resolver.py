"""Resolve tenant capabilities from persisted subscribed-SKU service plans."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import Capability, EntitlementState, FeatureStatus, RuntimeState, derive_feature_status


# These are stable Graph servicePlanName identifiers, not product/SKU names.
# A capability is resolved only where a plan name is explicit and its
# provisioning status is Success. Unknown plans intentionally provide no
# negative entitlement evidence.
_PLAN_CAPABILITIES = {
    "AAD_PREMIUM": (Capability.ENTRA_P1,),
    "AAD_PREMIUM_P2": (Capability.ENTRA_P1, Capability.ENTRA_P2),
    "EXCHANGE_S_ENTERPRISE": (Capability.EXCHANGE,),
    "EXCHANGE_S_STANDARD": (Capability.EXCHANGE,),
    "SHAREPOINTENTERPRISE": (Capability.SHAREPOINT,),
    "SHAREPOINTSTANDARD": (Capability.SHAREPOINT,),
    "ONEDRIVESTANDARD": (Capability.ONEDRIVE,),
}


@dataclass(frozen=True)
class TenantCapability:
    capability: Capability
    entitlement: EntitlementState
    runtime: RuntimeState
    feature_status: FeatureStatus

    def to_dict(self) -> dict[str, str]:
        return {
            "capability": self.capability.value,
            "entitlement": self.entitlement.value,
            "runtime": self.runtime.value,
            "feature_status": self.feature_status.value,
        }


class CapabilityResolver:
    """Derive tenant-wide availability from current ``core.subscribed_sku`` rows."""

    def __init__(self, subscribed_skus: Iterable[Mapping[str, Any]] | None):
        self._skus = list(subscribed_skus or [])
        self._plans_available = bool(self._skus) and all(
            isinstance(sku.get("service_plans"), list) for sku in self._skus
        )
        self._has_unknown_plan = False
        self._entitlements = self._resolve_entitlements()

    def resolve(self, capability: Capability | str, runtime: RuntimeState = RuntimeState.READY) -> TenantCapability:
        capability = Capability(capability)
        entitlement = self._entitlements[capability]
        return TenantCapability(capability, entitlement, runtime, derive_feature_status(entitlement, runtime))

    def all(self, runtime_by_capability: Mapping[Capability | str, RuntimeState] | None = None) -> list[TenantCapability]:
        runtime_by_capability = runtime_by_capability or {}
        return [
            self.resolve(capability, RuntimeState(runtime_by_capability.get(capability, RuntimeState.READY)))
            for capability in Capability
        ]

    def _resolve_entitlements(self) -> dict[Capability, EntitlementState]:
        if not self._plans_available:
            return {capability: EntitlementState.UNKNOWN for capability in Capability}
        enabled: set[Capability] = {Capability.ENTRA_BASIC}
        for sku in self._skus:
            for plan in sku["service_plans"]:
                if not isinstance(plan, Mapping) or plan.get("provisioningStatus") != "Success":
                    continue
                capabilities = _PLAN_CAPABILITIES.get(plan.get("servicePlanName"))
                if capabilities is None:
                    self._has_unknown_plan = True
                    continue
                for capability in capabilities:
                    enabled.add(capability)
        unresolved = EntitlementState.UNKNOWN if self._has_unknown_plan else EntitlementState.NOT_ENTITLED
        result = {capability: unresolved for capability in Capability}
        for capability in enabled:
            result[capability] = EntitlementState.ENTITLED
        # No supported persisted mapping has been accepted for these derived
        # capabilities or M365 reporting. Never infer them from a SKU name.
        for capability in (
            Capability.CONDITIONAL_ACCESS,
            Capability.IDENTITY_PROTECTION,
            Capability.RISK_BASED_CONDITIONAL_ACCESS,
            Capability.M365_USAGE_REPORTS,
        ):
            result[capability] = EntitlementState.UNKNOWN
        return result
