"""Deterministic Microsoft Entra Global Administrator exposure rule."""
from __future__ import annotations

from typing import Any

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-GA-001"
RULE_CATEGORY = "Privileged Access / Global Administrators"
BASELINE_VALUE = "global_admin_assignments_less_than_5"
OPEN_TITLE = "Global Administrator assignments exceed the recommended baseline"
OPEN_RISK = (
    "Global Administrators have broad control over Microsoft Entra ID and Microsoft 365. "
    "Excessive assignments increase the number of high-value privileged identities that "
    "could be abused if compromised."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=("Review Global Administrator assignments and reduce the number to fewer than "
          "five where operationally feasible, delegating narrower roles for routine "
          "administrative duties."),
    steps=("Re-read Global Administrator role assignments after administrative review "
            "and re-evaluate M365-ENTRA-GA-001.",),
)


def global_admin_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID, category=RULE_CATEGORY,
        title="Microsoft Entra Global Administrator assignment count",
        description="Evaluate the Global Administrator assignment count against the product baseline.",
        baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        baseline_value=BASELINE_VALUE, severity=Severity.HIGH,
    )


def evaluate_global_admin_assignments(observation: SecurityObservation,
                                      baseline: SecurityBaseline) -> SecurityFinding:
    rule = global_admin_rule(baseline)
    value = observation.value if isinstance(observation.value, dict) else None
    count = value.get("global_admin_assignment_count") if value else None
    principals = value.get("distinct_global_admin_principals") if value else None
    valid = (isinstance(count, int) and not isinstance(count, bool) and count >= 0 and
             isinstance(principals, int) and not isinstance(principals, bool) and principals >= 0)
    evidence = EvidenceReference(
        source_type=observation.source_type or "entra_directory_role_assignments",
        graph_endpoint=observation.graph_endpoint, collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id, observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "global_admin_assignment_count",
        sanitized_value=(value if valid else None),
    )
    if not observation.source_available or not valid:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=BASELINE_VALUE,
            observed_state="not_evaluated",
            risk="Not evaluated because the source was unavailable or malformed. This is not a security gap.",
            evidence=evidence, recommendation=Recommendation(
                action="verify", text="Verify that the Global Administrator assignment observation is collected correctly."),
            dependency_status=(DependencyStatus.UNAVAILABLE if not observation.source_available else DependencyStatus.AVAILABLE),
            evaluated_at=utcnow_iso(),
        )
    status = FindingStatus.PASS if count < 5 else FindingStatus.OPEN
    if status is FindingStatus.OPEN:
        title, risk, recommendation = OPEN_TITLE, OPEN_RISK, OPEN_RECOMMENDATION
    else:
        title, risk, recommendation = rule.title, "Global Administrator assignments satisfy the recommended product baseline.", Recommendation(action="no_action", text="No action is required.")
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, f"{status.value}:{count}"),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=title, severity=rule.severity, status=status,
        baseline_expectation=BASELINE_VALUE, observed_state=f"actual:{count}", risk=risk,
        evidence=evidence, recommendation=recommendation,
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=utcnow_iso(),
    )


__all__ = ["BASELINE_VALUE", "RULE_CATEGORY", "RULE_ID", "evaluate_global_admin_assignments", "global_admin_rule"]
