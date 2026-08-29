"""Deterministic Microsoft Entra guest directory access rule."""
from __future__ import annotations

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-GUEST-ACCESS-001"
RULE_CATEGORY = "External Collaboration / Guest Directory Access"
BASELINE_VALUE = "guest_not_same_as_members"
ACCESS_LEVELS = (
    "restricted_guest", "limited_guest", "same_as_members",
    "custom_or_unknown", "dependency_unavailable",
)

OPEN_TITLE = "Guest users have member-equivalent directory access"
OPEN_RISK = (
    "Guest identities with member-equivalent directory permissions can discover "
    "substantially more users, groups, and directory information than required for "
    "normal external collaboration, increasing information exposure if a guest "
    "account is compromised or misused."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=(
        "Use the standard Guest User access level or the Restricted Guest User "
        "access level unless broader directory visibility is explicitly required "
        "and approved."
    ),
    steps=(
        "Re-read the tenant authorization policy after an administrator changes "
        "the guest access level and re-evaluate M365-ENTRA-GUEST-ACCESS-001.",
    ),
)


def guest_access_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID, category=RULE_CATEGORY,
        title="Microsoft Entra guest directory access level",
        description="Evaluate guest directory access against the product baseline.",
        baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        supported_values=ACCESS_LEVELS, baseline_value=BASELINE_VALUE,
        severity=Severity.HIGH,
    )


def evaluate_guest_access(observation: SecurityObservation,
                          baseline: SecurityBaseline) -> SecurityFinding:
    rule = guest_access_rule(baseline)
    value = observation.value if isinstance(observation.value, str) else None
    evidence = EvidenceReference(
        source_type=observation.source_type or "authorization_policy",
        graph_endpoint=observation.graph_endpoint,
        collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "guest_directory_access_level",
        sanitized_value=value,
    )
    if not observation.source_available or value not in ACCESS_LEVELS or value in {
        "custom_or_unknown", "dependency_unavailable",
    }:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version,
                                       "NOT_EVALUATED:" + str(value)),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id,
            baseline_version=baseline.version, category=rule.category,
            title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=BASELINE_VALUE,
            observed_state="not_evaluated",
            risk="Not evaluated because the source was unavailable or the guest access semantics were unknown. This is not a security gap.",
            evidence=evidence,
            recommendation=Recommendation(
                action="verify",
                text="Verify that the Entra guest directory access observation is collected correctly.",
            ),
            dependency_status=(DependencyStatus.AVAILABLE if observation.source_available
                               else DependencyStatus.UNAVAILABLE),
            evaluated_at=utcnow_iso(),
        )
    status = FindingStatus.OPEN if value == "same_as_members" else FindingStatus.PASS
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version,
                                   status.value + ":" + value),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id,
        baseline_version=baseline.version, category=rule.category,
        title=OPEN_TITLE if status is FindingStatus.OPEN else rule.title,
        severity=Severity.HIGH, status=status, baseline_expectation=BASELINE_VALUE,
        observed_state="actual:" + value,
        risk=OPEN_RISK if status is FindingStatus.OPEN else "Guest directory access satisfies the recommended product baseline.",
        evidence=evidence,
        recommendation=(OPEN_RECOMMENDATION if status is FindingStatus.OPEN
                        else Recommendation(action="no_action", text="No action is required.")),
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=utcnow_iso(),
    )


__all__ = ["ACCESS_LEVELS", "BASELINE_VALUE", "RULE_CATEGORY", "RULE_ID",
           "evaluate_guest_access", "guest_access_rule"]
