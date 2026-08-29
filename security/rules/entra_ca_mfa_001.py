"""Deterministic Conditional Access explicit built-in MFA rule."""
from __future__ import annotations

from typing import Any, Mapping

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-CA-MFA-001"
RULE_CATEGORY = "Authentication / Conditional Access"
OPEN_TITLE = "No enabled Conditional Access policy with explicit MFA enforcement"
BASELINE_VALUE = "at_least_one_enabled_CA_policy_with_builtin_mfa"
SOURCE_TYPE = "conditional_access_policies"
GRAPH_ENDPOINT = "/v1.0/identity/conditionalAccess/policies"
OPEN_RISK = (
    "Conditional Access policies containing MFA controls exist only if they are "
    "actively enabled. Report-only and disabled policies do not enforce their MFA "
    "grant controls during sign-in."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=("Review the existing Conditional Access MFA policies and validate their "
          "intended scope and exclusions. Use report-only results to confirm "
          "expected impact before enabling an appropriate policy."),
    steps=("Re-read Conditional Access policies after administrative changes and "
           "confirm that at least one intended enabled policy contains the explicit "
           "MFA grant control.",),
)

FIELDS = (
    "total_policy_count", "enabled_policy_count", "explicit_mfa_policy_count",
    "enabled_explicit_mfa_policy_count", "report_only_explicit_mfa_policy_count",
    "disabled_explicit_mfa_policy_count", "enabled_authentication_strength_policy_count",
)


def conditional_access_mfa_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID, category=RULE_CATEGORY, title=OPEN_TITLE,
        description="Verify that an enabled Conditional Access policy explicitly contains the built-in MFA grant control.",
        baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        baseline_value=BASELINE_VALUE, severity=Severity.MEDIUM,
        required_capabilities=("ENTRA_P1",), required_graph_permissions=("Policy.Read.All",),
    )


def _counts(value: Any) -> Mapping[str, int] | None:
    if not isinstance(value, Mapping):
        return None
    if any(isinstance(value.get(field), bool) or not isinstance(value.get(field), int) or value[field] < 0 for field in FIELDS):
        return None
    if value["explicit_mfa_policy_count"] > value["total_policy_count"]:
        return None
    return {field: value[field] for field in FIELDS}


def evaluate_conditional_access_mfa(observation: SecurityObservation, baseline: SecurityBaseline) -> SecurityFinding:
    rule = conditional_access_mfa_rule(baseline)
    counts = _counts(observation.value)
    evidence = EvidenceReference(
        source_type=observation.source_type or SOURCE_TYPE,
        graph_endpoint=observation.graph_endpoint or GRAPH_ENDPOINT,
        collection_run_id=observation.collection_run_id, endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at, normalized_field=observation.normalized_field or "conditional_access_mfa_counts",
        sanitized_value=dict(counts) if counts is not None else None,
    )
    if not observation.source_available or counts is None:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity, status=FindingStatus.NOT_EVALUATED,
            baseline_expectation=BASELINE_VALUE, observed_state="source_unavailable" if not observation.source_available else "malformed_observation",
            risk="Not evaluated because the Conditional Access source was unavailable or malformed. This is not a security gap.",
            evidence=evidence, recommendation=Recommendation(action="verify", text="Verify that the complete Conditional Access policy inventory and grant controls were collected correctly."),
            dependency_status=DependencyStatus.UNAVAILABLE if not observation.source_available else DependencyStatus.AVAILABLE,
            evaluated_at=utcnow_iso(),
        )
    if counts["enabled_explicit_mfa_policy_count"]:
        status, state = FindingStatus.PASS, "enabled_explicit_mfa_policy_count:1+"
        risk, recommendation = "At least one enabled Conditional Access policy explicitly enforces the built-in MFA grant control.", Recommendation(action="no_action", text="No action is required.")
    elif counts["enabled_authentication_strength_policy_count"]:
        status, state = FindingStatus.NOT_EVALUATED, "authentication_strength_policy_present"
        risk, recommendation = "Not evaluated because an enabled authentication strength policy was observed; this rule does not resolve authentication strength semantics.", Recommendation(action="verify", text="Verify the intended authentication strength requirements separately.")
    else:
        status, state = FindingStatus.OPEN, "enabled_explicit_mfa_policy_count:0"
        risk, recommendation = OPEN_RISK, OPEN_RECOMMENDATION
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, state),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=OPEN_TITLE if status is FindingStatus.OPEN else rule.title,
        severity=rule.severity, status=status, baseline_expectation=BASELINE_VALUE,
        observed_state=state, risk=risk, evidence=evidence, recommendation=recommendation,
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=utcnow_iso(),
    )


__all__ = ["FIELDS", "GRAPH_ENDPOINT", "OPEN_TITLE", "RULE_ID", "SOURCE_TYPE", "conditional_access_mfa_rule", "evaluate_conditional_access_mfa"]
