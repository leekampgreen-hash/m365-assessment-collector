"""Deterministic Microsoft Entra user application consent policy rule."""
from __future__ import annotations

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-CONSENT-001"
RULE_CATEGORY = "Application Security / User Consent"
CONSENT_STATES = (
    "user_consent_disabled", "microsoft_recommended", "limited_low_risk",
    "legacy_broad_consent", "custom_or_unknown", "dependency_unavailable",
)
OPEN_TITLE = "User application consent is broader than the recommended baseline"
OPEN_RISK = (
    "Users can grant consent to applications under a broad legacy policy, increasing "
    "the risk that applications obtain delegated access without sufficient administrative review."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=(
        "Move user consent to the approved organizational policy, such as Microsoft-recommended "
        "or restricted low-risk consent, or disable ordinary user consent if required by "
        "organizational policy."
    ),
    steps=(
        "Re-read authorizationPolicy after an administrator changes the user consent configuration, "
        "then re-evaluate M365-ENTRA-CONSENT-001.",
    ),
)


def user_consent_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID, category=RULE_CATEGORY,
        title="Microsoft Entra user application consent policy",
        description="Evaluate user application consent against the product baseline.",
        baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        supported_values=CONSENT_STATES, baseline_value="microsoft_recommended",
        severity=Severity.HIGH,
    )


def evaluate_user_consent(observation: SecurityObservation, baseline: SecurityBaseline) -> SecurityFinding:
    rule = user_consent_rule(baseline)
    value = observation.value if isinstance(observation.value, str) else None
    evidence = EvidenceReference(
        source_type=observation.source_type or "authorization_policy",
        graph_endpoint=observation.graph_endpoint,
        collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "user_app_consent_policy",
        sanitized_value=value,
    )
    if not observation.source_available or value not in CONSENT_STATES or value in {
        "custom_or_unknown", "dependency_unavailable"
    }:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED:" + str(value)),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=rule.baseline_value,
            observed_state="not_evaluated",
            risk="Not evaluated because the source was unavailable or the policy semantics were unknown. This is not a security gap.",
            evidence=evidence,
            recommendation=Recommendation(action="verify", text="Verify that the Entra user consent policy observation is collected correctly."),
            dependency_status=(DependencyStatus.AVAILABLE if observation.source_available else DependencyStatus.UNAVAILABLE),
            evaluated_at=utcnow_iso(),
        )
    status = FindingStatus.OPEN if value == "legacy_broad_consent" else FindingStatus.PASS
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, status.value + ":" + value),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=OPEN_TITLE if status is FindingStatus.OPEN else rule.title,
        severity=Severity.HIGH, status=status, baseline_expectation=rule.baseline_value,
        observed_state="actual:" + value,
        risk=OPEN_RISK if status is FindingStatus.OPEN else "User application consent satisfies the recommended product baseline.",
        evidence=evidence,
        recommendation=OPEN_RECOMMENDATION if status is FindingStatus.OPEN else Recommendation(action="no_action", text="No action is required."),
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=utcnow_iso(),
    )


__all__ = ["CONSENT_STATES", "RULE_CATEGORY", "RULE_ID", "evaluate_user_consent", "user_consent_rule"]
