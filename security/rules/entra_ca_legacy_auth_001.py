"""Deterministic Conditional Access legacy-authentication block presence rule."""
from __future__ import annotations

from typing import Any, Mapping

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-CA-LEGACY-AUTH-001"
RULE_CATEGORY = "Authentication / Conditional Access"
TITLE = "Conditional Access legacy authentication block presence"
BASELINE_VALUE = "enabled_legacy_authentication_block_policy"
SOURCE_TYPE = "conditional_access_policies"
GRAPH_ENDPOINT = "/v1.0/identity/conditionalAccess/policies"
LEGACY_SPECIFIC_VALUES = ("exchangeActiveSync", "easSupported", "easUnsupported", "other")
OPEN_RISK = (
    "No enabled Conditional Access policy with complete evidence was found that "
    "blocks legacy authentication. This presence-only rule does not prove tenant-wide coverage."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=("Review and deploy an enabled Conditional Access policy that blocks legacy "
          "authentication, validating report-only impact first. This presence-only "
          "finding does not prove all users, applications, or resources are covered "
          "and does not assess exclusions or Security Defaults equivalence."),
    steps=("Confirm the policy uses the intended legacy client types (or all client apps), "
           "contains the block grant control, and is enabled.",),
)


def conditional_access_legacy_auth_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID, category=RULE_CATEGORY, title=TITLE,
        description="Verify presence of an enabled Conditional Access legacy-authentication block policy.",
        baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        baseline_value=BASELINE_VALUE, severity=Severity.HIGH,
        required_capabilities=("ENTRA_P1",), required_graph_permissions=("Policy.Read.All",),
    )


def _evidence(observation: SecurityObservation, value: Any) -> EvidenceReference:
    return EvidenceReference(
        source_type=observation.source_type or SOURCE_TYPE,
        graph_endpoint=observation.graph_endpoint or GRAPH_ENDPOINT,
        collection_run_id=observation.collection_run_id, endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "conditional_access_legacy_auth_policies",
        sanitized_value=value,
    )


def evaluate_conditional_access_legacy_auth(
    observation: SecurityObservation, baseline: SecurityBaseline
) -> SecurityFinding:
    rule = conditional_access_legacy_auth_rule(baseline)
    value = observation.value
    policies = value.get("policies") if isinstance(value, Mapping) else None
    complete = value.get("collection_complete") if isinstance(value, Mapping) else False
    valid = isinstance(policies, list) and isinstance(complete, bool)
    sanitized = policies if valid else None
    evidence = _evidence(observation, sanitized)
    if not observation.source_available or not valid:
        state = "source_unavailable" if not observation.source_available else "malformed_observation"
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=BASELINE_VALUE,
            observed_state=state,
            risk="Not evaluated because Conditional Access evidence was unavailable or malformed. This is not a security gap.",
            evidence=evidence, recommendation=Recommendation(action="verify", text="Verify that the complete current Conditional Access policy evidence was collected."),
            dependency_status=DependencyStatus.UNAVAILABLE if not observation.source_available else DependencyStatus.AVAILABLE,
            evaluated_at=utcnow_iso(),
        )
    qualifying = []
    for policy in policies:
        if not isinstance(policy, Mapping):
            continue
        client_types = policy.get("client_app_types")
        controls = policy.get("grant_built_in_controls")
        if (policy.get("state") == "enabled" and policy.get("security_evidence_complete") is True
                and isinstance(client_types, list) and all(isinstance(t, str) for t in client_types)
                and isinstance(controls, list) and "block" in controls
                and (set(client_types) & set(LEGACY_SPECIFIC_VALUES) or "all" in client_types)):
            qualifying.append(policy)
    if qualifying:
        matches = []
        for policy in qualifying:
            types = list(policy["client_app_types"])
            matches.append({"policy_id": policy.get("policy_id"), "display_name": policy.get("display_name"),
                            "matching_client_types": [t for t in types if t in LEGACY_SPECIFIC_VALUES or t == "all"],
                            "coverage_mode": "ALL_CLIENT_APPS" if "all" in types else "LEGACY_SPECIFIC"})
        status = FindingStatus.PASS
        state = "qualifying_enabled_policy_present"
        risk = "An enabled policy blocks legacy authentication for the explicitly identified client-app coverage mode; this rule does not claim tenant-wide coverage."
        recommendation = Recommendation(action="no_action", text="No action is required for this presence-only check.")
    elif not complete or any(not isinstance(p, Mapping) or p.get("security_evidence_complete") is not True for p in policies):
        status, state = FindingStatus.NOT_EVALUATED, "incomplete_absence_evidence"
        risk = "Not evaluated because evidence required to establish absence of a qualifying policy is incomplete. This is not a security gap."
        recommendation = Recommendation(action="verify", text="Collect complete Conditional Access security evidence before determining absence.")
        matches = []
    else:
        status, state, risk, recommendation = FindingStatus.OPEN, "no_qualifying_enabled_policy", OPEN_RISK, OPEN_RECOMMENDATION
        matches = []
    if valid:
        evidence = _evidence(observation, matches if status is FindingStatus.PASS else {"policy_count": len(policies), "qualifying": matches})
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, state),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=rule.title, severity=rule.severity, status=status,
        baseline_expectation=BASELINE_VALUE, observed_state=state, risk=risk,
        evidence=evidence, recommendation=recommendation, dependency_status=DependencyStatus.AVAILABLE,
        evaluated_at=utcnow_iso(),
    )


__all__ = ["BASELINE_VALUE", "GRAPH_ENDPOINT", "LEGACY_SPECIFIC_VALUES", "RULE_ID", "SOURCE_TYPE", "conditional_access_legacy_auth_rule", "evaluate_conditional_access_legacy_auth"]
