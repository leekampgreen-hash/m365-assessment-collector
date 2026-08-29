"""Deterministic Conditional Access enforcement-presence rule."""
from __future__ import annotations

from typing import Any, Mapping

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-CA-ENFORCEMENT-001"
RULE_CATEGORY = "Authentication / Conditional Access"
OPEN_TITLE = "No Conditional Access policy is actively enforced"
BASELINE_VALUE = "at_least_one_enabled_CA_policy"
SOURCE_TYPE = "conditional_access_policies"
GRAPH_ENDPOINT = "/v1.0/identity/conditionalAccess/policies"
OPEN_RISK = (
    "The tenant is entitled to Conditional Access, but no policy is currently in "
    "an enabled enforcement state. Report-only and disabled policies do not "
    "actively apply Conditional Access controls during sign-in."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=("Review the tenant's authentication requirements and deploy appropriate "
          "Conditional Access policies using staged testing and report-only "
          "validation before enforcement."),
    steps=("Re-read Conditional Access policies after administrative changes and "
           "confirm that at least one intended policy is in the enabled state.",),
)


def conditional_access_enforcement_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID,
        category=RULE_CATEGORY,
        title=OPEN_TITLE,
        description="Verify that at least one Conditional Access policy is enabled.",
        baseline_id=baseline.baseline_id,
        baseline_version=baseline.version,
        baseline_value=BASELINE_VALUE,
        severity=Severity.MEDIUM,
        required_capabilities=("ENTRA_P1",),
        required_graph_permissions=("Policy.Read.All",),
    )


def _counts(value: Any) -> Mapping[str, int] | None:
    if not isinstance(value, Mapping):
        return None
    fields = ("total_policy_count", "enabled_policy_count", "report_only_policy_count", "disabled_policy_count")
    if any(isinstance(value.get(field), bool) or not isinstance(value.get(field), int) or value[field] < 0 for field in fields):
        return None
    unknown = value.get("unknown_state_count", 0)
    if isinstance(unknown, bool) or not isinstance(unknown, int) or unknown < 0:
        return None
    if sum(value[field] for field in fields[1:]) + unknown != value["total_policy_count"]:
        return None
    return {field: value[field] for field in fields} | {"unknown_state_count": unknown}


def evaluate_conditional_access_enforcement(
    observation: SecurityObservation, baseline: SecurityBaseline
) -> SecurityFinding:
    rule = conditional_access_enforcement_rule(baseline)
    counts = _counts(observation.value)
    evidence_value = None
    if counts is not None:
        evidence_value = {field: counts[field] for field in (
            "total_policy_count", "enabled_policy_count", "report_only_policy_count", "disabled_policy_count")}
    evidence = EvidenceReference(
        source_type=observation.source_type or SOURCE_TYPE,
        graph_endpoint=observation.graph_endpoint or GRAPH_ENDPOINT,
        collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "conditional_access_policy_counts",
        sanitized_value=evidence_value,
    )
    if not observation.source_available or counts is None or counts["unknown_state_count"]:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=BASELINE_VALUE,
            observed_state="dependency_unavailable" if not observation.source_available else "unknown_state",
            risk="Not evaluated because the Conditional Access source was unavailable or ambiguous. This is not a security gap.",
            evidence=evidence, recommendation=Recommendation(
                action="verify", text="Verify that the complete Conditional Access policy inventory was collected correctly."),
            dependency_status=DependencyStatus.UNAVAILABLE if not observation.source_available else DependencyStatus.AVAILABLE,
            evaluated_at=utcnow_iso(),
        )
    enabled = counts["enabled_policy_count"]
    status = FindingStatus.PASS if enabled >= 1 else FindingStatus.OPEN
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, f"{status.value}:{enabled}"),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=OPEN_TITLE if status is FindingStatus.OPEN else rule.title,
        severity=rule.severity, status=status, baseline_expectation=BASELINE_VALUE,
        observed_state=f"enabled_policy_count:{enabled}",
        risk=OPEN_RISK if status is FindingStatus.OPEN else "At least one Conditional Access policy is actively enforced.",
        evidence=evidence,
        recommendation=OPEN_RECOMMENDATION if status is FindingStatus.OPEN else Recommendation(action="no_action", text="No action is required."),
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=utcnow_iso(),
    )


__all__ = ["BASELINE_VALUE", "GRAPH_ENDPOINT", "RULE_CATEGORY", "RULE_ID", "SOURCE_TYPE", "conditional_access_enforcement_rule", "evaluate_conditional_access_enforcement"]
