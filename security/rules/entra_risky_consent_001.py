"""Deterministic Microsoft Entra risky-application consent rule."""
from __future__ import annotations

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-RISKY-CONSENT-001"
RULE_CATEGORY = "Application Security / Risky Application Consent"
DISABLED_STATE = "risky_app_user_consent_disabled"
ENABLED_STATE = "risky_app_user_consent_enabled"
DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
BASELINE_VALUE = DISABLED_STATE

OPEN_TITLE = "User consent for risky applications is enabled"
OPEN_RISK = (
    "Allowing users to consent to applications classified as risky can increase "
    "the likelihood that risky or potentially malicious applications obtain "
    "delegated access to organizational data."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=(
        "Disable user consent for risky applications and require the organization's "
        "approved administrative consent process for applications requiring review."
    ),
    steps=(
        "Re-read the tenant authorization policy after an administrator changes the "
        "setting and re-evaluate M365-ENTRA-RISKY-CONSENT-001.",
    ),
)


def risky_consent_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID,
        category=RULE_CATEGORY,
        title="Microsoft Entra risky application consent policy",
        description="Evaluate user consent for risky applications against the product baseline.",
        baseline_id=baseline.baseline_id,
        baseline_version=baseline.version,
        supported_values=(DISABLED_STATE, ENABLED_STATE, DEPENDENCY_UNAVAILABLE),
        baseline_value=BASELINE_VALUE,
        severity=Severity.HIGH,
    )


def evaluate_risky_consent(
    observation: SecurityObservation, baseline: SecurityBaseline
) -> SecurityFinding:
    rule = risky_consent_rule(baseline)
    value = observation.value if isinstance(observation.value, str) else None
    evidence = EvidenceReference(
        source_type=observation.source_type or "authorization_policy",
        graph_endpoint=observation.graph_endpoint,
        collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "allow_user_consent_for_risky_apps",
        sanitized_value=value,
    )
    if not observation.source_available or value == DEPENDENCY_UNAVAILABLE or value not in {
        DISABLED_STATE, ENABLED_STATE,
    }:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=BASELINE_VALUE,
            observed_state=DEPENDENCY_UNAVAILABLE,
            risk="Not evaluated because the source was unavailable or malformed. This is not a security gap.",
            evidence=evidence,
            recommendation=Recommendation(action="verify", text="Verify that the risky application consent policy observation is collected correctly."),
            dependency_status=DependencyStatus.UNAVAILABLE,
            evaluated_at=utcnow_iso(),
        )
    status = FindingStatus.OPEN if value == ENABLED_STATE else FindingStatus.PASS
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, status.value + ":" + value),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category,
        title=OPEN_TITLE if status is FindingStatus.OPEN else rule.title,
        severity=rule.severity, status=status, baseline_expectation=BASELINE_VALUE,
        observed_state="actual:" + value,
        risk=OPEN_RISK if status is FindingStatus.OPEN else "User consent for risky applications is disabled as required by the product baseline.",
        evidence=evidence,
        recommendation=OPEN_RECOMMENDATION if status is FindingStatus.OPEN else Recommendation(action="no_action", text="No action is required."),
        dependency_status=DependencyStatus.AVAILABLE,
        evaluated_at=utcnow_iso(),
    )


__all__ = [
    "BASELINE_VALUE", "DEPENDENCY_UNAVAILABLE", "DISABLED_STATE", "ENABLED_STATE",
    "RULE_CATEGORY", "RULE_ID", "evaluate_risky_consent", "risky_consent_rule",
]
