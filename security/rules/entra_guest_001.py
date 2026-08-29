"""Deterministic Microsoft Entra guest invitation policy rule."""
from __future__ import annotations

from typing import Any, Optional

from security.models import (
    DependencyStatus,
    EvidenceReference,
    FindingStatus,
    Recommendation,
    SecurityBaseline,
    SecurityFinding,
    SecurityObservation,
    SecurityRule,
    Severity,
    make_finding_id,
    utcnow_iso,
)

RULE_ID = "M365-ENTRA-GUEST-001"
RULE_CATEGORY = "External Collaboration / Guest Invitations"
GUEST_INVITATION_LEVELS = (
    "none",
    "admins_and_guest_inviters",
    "admins_guest_inviters_and_all_members",
    "everyone",
)
BASELINE_VALUE = "admins_and_guest_inviters"

OPEN_TITLE = "Guest invitation permissions are broader than the recommended baseline"
OPEN_RISK = (
    "Broad guest-invitation permissions increase the number of identities able to "
    "introduce external users into the tenant and can increase unmanaged external "
    "collaboration exposure."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=(
        "Restrict guest invitations to administrators and designated Guest Inviters, "
        "or a stricter approved organizational policy."
    ),
    steps=(
        "Re-read the tenant authorization policy after an administrator changes the "
        "setting and re-evaluate M365-ENTRA-GUEST-001.",
    ),
)


def guest_invitation_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID,
        category=RULE_CATEGORY,
        title="Microsoft Entra guest invitation policy",
        description="Evaluate guest invitation permissions against the product baseline.",
        baseline_id=baseline.baseline_id,
        baseline_version=baseline.version,
        supported_values=GUEST_INVITATION_LEVELS,
        baseline_value=BASELINE_VALUE,
        severity=Severity.MEDIUM,
    )


def evaluate_guest_invitation(
    observation: SecurityObservation, baseline: SecurityBaseline
) -> SecurityFinding:
    rule = guest_invitation_rule(baseline)
    evaluated_at = utcnow_iso()
    value = observation.value if isinstance(observation.value, str) else None
    index = GUEST_INVITATION_LEVELS.index(value) if value in GUEST_INVITATION_LEVELS else None
    evidence = EvidenceReference(
        source_type=observation.source_type or "entra_authorization_policy",
        graph_endpoint=observation.graph_endpoint,
        collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "allow_invites_from",
        sanitized_value=value,
    )
    if not observation.source_available or index is None:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED,
            baseline_expectation=BASELINE_VALUE, observed_state="not_evaluated",
            risk="Not evaluated because the source was unavailable, unsupported, or malformed. This is not a security gap.",
            evidence=evidence,
            recommendation=Recommendation(action="verify", text="Verify that the guest invitation policy observation is collected correctly."),
            dependency_status=(DependencyStatus.UNAVAILABLE if not observation.source_available else DependencyStatus.AVAILABLE),
            evaluated_at=evaluated_at,
        )
    status = FindingStatus.PASS if index <= GUEST_INVITATION_LEVELS.index(BASELINE_VALUE) else FindingStatus.OPEN
    if status is FindingStatus.OPEN:
        title, risk, recommendation = OPEN_TITLE, OPEN_RISK, OPEN_RECOMMENDATION
    else:
        title = rule.title
        risk = "Guest invitation permissions satisfy the recommended product baseline."
        recommendation = Recommendation(action="no_action", text="No action is required.")
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, f"{status.value}:{value}"),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=title, severity=rule.severity, status=status,
        baseline_expectation=BASELINE_VALUE, observed_state=f"actual:{value}", risk=risk,
        evidence=evidence, recommendation=recommendation,
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=evaluated_at,
    )


__all__ = ["BASELINE_VALUE", "GUEST_INVITATION_LEVELS", "RULE_CATEGORY", "RULE_ID", "evaluate_guest_invitation", "guest_invitation_rule"]
