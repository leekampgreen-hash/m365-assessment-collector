"""Tenant license capability resolution and pre-execution gates.

This package is deliberately offline: it resolves product eligibility from
persisted subscribed-SKU service plans and never calls Microsoft Graph.
"""
from .gates import (
    CollectionDecision,
    CollectionPlan,
    SecurityEvaluationPlan,
    plan_collection,
    plan_security_evaluation,
)
from .models import Capability, EntitlementState, FeatureStatus, RuntimeState
from .resolver import CapabilityResolver, TenantCapability

__all__ = [
    "Capability",
    "CapabilityResolver",
    "CollectionDecision",
    "CollectionPlan",
    "EntitlementState",
    "FeatureStatus",
    "RuntimeState",
    "SecurityEvaluationPlan",
    "TenantCapability",
    "plan_collection",
    "plan_security_evaluation",
]
