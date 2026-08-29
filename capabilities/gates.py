"""Deterministic capability gates used before optional collection/evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .models import Capability, EntitlementState, FeatureStatus, RuntimeState, derive_feature_status


class CollectionDecision(str, Enum):
    COLLECT = "COLLECT"
    SKIP_NOT_LICENSED = "SKIP_NOT_LICENSED"
    SKIP_CAPABILITY_UNKNOWN = "SKIP_CAPABILITY_UNKNOWN"
    SKIP_PERMISSION_REQUIRED = "SKIP_PERMISSION_REQUIRED"


@dataclass(frozen=True)
class CollectionPlan:
    decision: CollectionDecision
    feature_status: FeatureStatus
    collector_status: str


@dataclass(frozen=True)
class SecurityEvaluationPlan:
    feature_status: FeatureStatus
    collector_status: str
    security_evaluation: str


def _combined_entitlement(required: Iterable[Capability | str], entitlements: Mapping[Capability | str, EntitlementState | str]) -> EntitlementState:
    states = [EntitlementState(entitlements.get(Capability(capability), EntitlementState.UNKNOWN)) for capability in required]
    if EntitlementState.NOT_ENTITLED in states:
        return EntitlementState.NOT_ENTITLED
    if EntitlementState.UNKNOWN in states:
        return EntitlementState.UNKNOWN
    return EntitlementState.ENTITLED


def plan_collection(required_capabilities: Iterable[Capability | str], required_graph_permissions: Iterable[str], entitlements: Mapping[Capability | str, EntitlementState | str], granted_graph_permissions: Iterable[str]) -> CollectionPlan:
    """Plan before constructing or using a Graph collector."""
    entitlement = _combined_entitlement(required_capabilities, entitlements)
    if entitlement is EntitlementState.NOT_ENTITLED:
        return CollectionPlan(CollectionDecision.SKIP_NOT_LICENSED, FeatureStatus.NOT_LICENSED, "NOT_EXECUTED")
    if entitlement is EntitlementState.UNKNOWN:
        return CollectionPlan(CollectionDecision.SKIP_CAPABILITY_UNKNOWN, FeatureStatus.UNKNOWN, "NOT_EXECUTED")
    if not set(required_graph_permissions).issubset(set(granted_graph_permissions)):
        return CollectionPlan(CollectionDecision.SKIP_PERMISSION_REQUIRED, FeatureStatus.PERMISSION_REQUIRED, "NOT_EXECUTED")
    return CollectionPlan(CollectionDecision.COLLECT, FeatureStatus.AVAILABLE, "PLANNED")


def plan_security_evaluation(required_capabilities: Iterable[Capability | str], entitlements: Mapping[Capability | str, EntitlementState | str], runtime: RuntimeState = RuntimeState.READY) -> SecurityEvaluationPlan:
    """Avoid invoking SecurityFindingService unless a feature is eligible."""
    entitlement = _combined_entitlement(required_capabilities, entitlements)
    status = derive_feature_status(entitlement, runtime)
    if status is FeatureStatus.AVAILABLE:
        return SecurityEvaluationPlan(status, "READY", "READY")
    return SecurityEvaluationPlan(status, "NOT_EXECUTED", "NOT_EXECUTED")
