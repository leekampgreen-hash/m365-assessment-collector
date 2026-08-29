"""Capability-gated Conditional Access enforcement collection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from capabilities.gates import CollectionDecision, CollectionPlan
from collectors.core.collector import BaseCollector
from collectors.core.models import EndpointSpec
from collectors.core.retry import RetryPolicy
from collectors.core.transport import GraphTransport
from security import DeterministicSecurityFindingService, SecurityFinding, SecurityObservation
from security.rules.entra_ca_enforcement_001 import (
    GRAPH_ENDPOINT, RULE_ID, SOURCE_TYPE,
)
from security.rules.entra_ca_mfa_001 import RULE_ID as MFA_RULE_ID
from security.rules.entra_ca_legacy_auth_001 import RULE_ID as LEGACY_AUTH_RULE_ID

ENFORCEMENT_ENDPOINT_ID = "G01-011"


def normalize_policy_state(state: Any) -> str:
    return {
        "enabled": "enabled",
        "enabledForReportingButNotEnforced": "report_only",
        "disabled": "disabled",
    }.get(state, "unknown_state")


def aggregate_policy_states(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "total_policy_count": 0,
        "enabled_policy_count": 0,
        "report_only_policy_count": 0,
        "disabled_policy_count": 0,
        "unknown_state_count": 0,
    }
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(record.get("state"), str):
            counts["unknown_state_count"] += 1
        else:
            normalized = normalize_policy_state(record["state"])
            key = "unknown_state_count" if normalized == "unknown_state" else f"{normalized}_policy_count"
            counts[key] += 1
        counts["total_policy_count"] += 1
    return counts


def aggregate_policy_security_counts(records: Iterable[Mapping[str, Any]]) -> tuple[dict[str, int], bool]:
    """Return sanitized MFA/authentication-strength counts and source validity."""
    counts = {field: 0 for field in (
        "total_policy_count", "enabled_policy_count", "explicit_mfa_policy_count",
        "enabled_explicit_mfa_policy_count", "report_only_explicit_mfa_policy_count",
        "disabled_explicit_mfa_policy_count", "enabled_authentication_strength_policy_count",
    )}
    reliable = True
    for record in records:
        counts["total_policy_count"] += 1
        if not isinstance(record, Mapping) or not isinstance(record.get("state"), str):
            reliable = False
            continue
        state = normalize_policy_state(record["state"])
        if state == "unknown_state":
            reliable = False
            continue
        controls = record.get("grantControls")
        if not isinstance(controls, Mapping):
            reliable = False
            continue
        built_in = controls.get("builtInControls", [])
        if not isinstance(built_in, list) or any(not isinstance(item, str) for item in built_in):
            reliable = False
            continue
        explicit_mfa = "mfa" in built_in
        auth_strength = "authenticationStrength" in controls
        if state == "enabled":
            counts["enabled_policy_count"] += 1
        if explicit_mfa:
            counts["explicit_mfa_policy_count"] += 1
            counts[f"{state}_explicit_mfa_policy_count"] += 1
        if state == "enabled" and auth_strength:
            counts["enabled_authentication_strength_policy_count"] += 1
    return counts, reliable


@dataclass(frozen=True)
class ConditionalAccessEnforcementResult:
    plan: CollectionPlan
    collection: Any = None
    observation: Optional[SecurityObservation] = None
    finding: Optional[SecurityFinding] = None


class ConditionalAccessEnforcementCollector:
    """Run G01-011 only after the caller's capability/permission gate allows it."""

    def __init__(self, transport: GraphTransport, *, finding_service=None, rule_id: str = RULE_ID):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()
        self.rule_id = rule_id

    def collect(
        self,
        spec: EndpointSpec,
        plan: CollectionPlan,
        *,
        retry_policy: Optional[RetryPolicy] = None,
        observed_at: Optional[str] = None,
        collection_run_id: str = "",
        endpoint_run_id: str = "",
    ) -> ConditionalAccessEnforcementResult:
        if plan.decision is not CollectionDecision.COLLECT:
            return ConditionalAccessEnforcementResult(plan=plan)
        run = BaseCollector(spec, self.transport, retry_policy=retry_policy).collect()
        complete = run.result.status == "PASS"
        if complete and self.rule_id == MFA_RULE_ID:
            counts, reliable = aggregate_policy_security_counts(run.records)
            complete = reliable
        else:
            counts = aggregate_policy_states(run.records) if complete else None
        if complete and self.rule_id == LEGACY_AUTH_RULE_ID:
            policies = []
            for record in run.records:
                if not isinstance(record, Mapping):
                    policies.append({"security_evidence_complete": False})
                    continue
                conditions = record.get("conditions")
                client_types = conditions.get("clientAppTypes") if isinstance(conditions, Mapping) else None
                controls = record.get("grantControls")
                built_in = controls.get("builtInControls") if isinstance(controls, Mapping) else None
                valid = isinstance(client_types, list) and all(isinstance(x, str) for x in client_types) and isinstance(built_in, list) and all(isinstance(x, str) for x in built_in)
                policies.append({"policy_id": str(record.get("id", "")), "display_name": record.get("displayName") if isinstance(record.get("displayName"), str) else None,
                                 "state": normalize_policy_state(record.get("state")), "client_app_types": list(client_types) if valid else [],
                                 "grant_built_in_controls": list(built_in) if valid else [], "security_evidence_complete": valid})
            counts = {"policies": policies, "collection_complete": True}
        observation = SecurityObservation(
            rule_id=self.rule_id,
            value=counts,
            source_available=complete,
            observed_at=observed_at or run.result.completed_at,
            source_type=SOURCE_TYPE,
            graph_endpoint=GRAPH_ENDPOINT,
            collection_run_id=collection_run_id,
            endpoint_run_id=endpoint_run_id,
            normalized_field=("conditional_access_legacy_auth_policies"
                              if self.rule_id == LEGACY_AUTH_RULE_ID
                              else "conditional_access_policy_counts"),
        )
        finding = self.finding_service.evaluate(observation)
        return ConditionalAccessEnforcementResult(plan, run, observation, finding)


__all__ = [
    "ConditionalAccessEnforcementCollector", "ConditionalAccessEnforcementResult",
    "ENFORCEMENT_ENDPOINT_ID", "aggregate_policy_states", "aggregate_policy_security_counts", "normalize_policy_state",
]
