"""Deterministic Microsoft Entra MFA registration coverage rule."""
from __future__ import annotations

from typing import Any, Mapping

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-MFA-REG-001"
RULE_CATEGORY = "Authentication / MFA Readiness"
BASELINE_VALUE = "all_enabled_users_mfa_registered"
SOURCE_TYPE = "entra_user_registration_details"
GRAPH_ENDPOINT = "/v1.0/reports/authenticationMethods/userRegistrationDetails"
OPEN_TITLE = "Enabled users have incomplete MFA registration coverage"
OPEN_RISK = (
    "Some enabled user accounts are not recorded as MFA registered. Accounts "
    "without registered MFA methods may have reduced readiness for authentication "
    "controls that require MFA."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=("Review enabled users without MFA registration and complete appropriate "
          "authentication-method registration according to the organization's "
          "authentication policy."),
    steps=("Re-read the authentication methods registration report after registration "
            "changes and verify MFA registration coverage across the enabled-user population.",),
)
FIELDS = (
    "enabled_user_count", "registration_row_count", "matched_enabled_user_count",
    "unexplained_population_gap", "mfa_registered_count", "mfa_not_registered_count",
    "registration_coverage_percent",
)


def mfa_registration_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID, category=RULE_CATEGORY, title=OPEN_TITLE,
        description="Verify MFA registration coverage for all enabled directory users.",
        baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        baseline_value=BASELINE_VALUE, severity=Severity.MEDIUM,
        required_capabilities=("ENTRA_P1",),
        required_graph_permissions=("AuditLog.Read.All",),
    )


def _valid(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    for field in FIELDS[:-1]:
        if isinstance(value.get(field), bool) or not isinstance(value.get(field), int) or value[field] < 0:
            return False
    coverage = value.get("registration_coverage_percent")
    return isinstance(coverage, (int, float)) and not isinstance(coverage, bool) and 0 <= coverage <= 100


def evaluate_mfa_registration(observation: SecurityObservation, baseline: SecurityBaseline) -> SecurityFinding:
    rule = mfa_registration_rule(baseline)
    value = observation.value if _valid(observation.value) else None
    evidence = EvidenceReference(
        source_type=observation.source_type or SOURCE_TYPE,
        graph_endpoint=observation.graph_endpoint or GRAPH_ENDPOINT,
        collection_run_id=observation.collection_run_id, endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "mfa_registration_coverage",
        sanitized_value=value,
    )
    reliable = (observation.source_available and value is not None and
                value["unexplained_population_gap"] == 0 and
                value["matched_enabled_user_count"] == value["enabled_user_count"] and
                value["registration_row_count"] == value["matched_enabled_user_count"] and
                value["mfa_registered_count"] + value["mfa_not_registered_count"] == value["registration_row_count"])
    if not reliable:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=BASELINE_VALUE,
            observed_state="population_incomplete" if value and value.get("unexplained_population_gap", 0) else "dependency_unavailable",
            risk="Not evaluated because the registration source or enabled-user population was incomplete or malformed. This is not a security gap.",
            evidence=evidence, recommendation=Recommendation(action="verify", text="Verify that the complete MFA registration report and enabled-user denominator were collected correctly."),
            dependency_status=DependencyStatus.AVAILABLE if observation.source_available else DependencyStatus.UNAVAILABLE,
            evaluated_at=utcnow_iso(),
        )
    status = FindingStatus.PASS if value["mfa_not_registered_count"] == 0 else FindingStatus.OPEN
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, f"{status.value}:{value['mfa_not_registered_count']}"),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=OPEN_TITLE if status is FindingStatus.OPEN else rule.title,
        severity=rule.severity, status=status, baseline_expectation=BASELINE_VALUE,
        observed_state=f"mfa_not_registered_count:{value['mfa_not_registered_count']}",
        risk=OPEN_RISK if status is FindingStatus.OPEN else "All enabled users are recorded as MFA registered.",
        evidence=evidence,
        recommendation=OPEN_RECOMMENDATION if status is FindingStatus.OPEN else Recommendation(action="no_action", text="No action is required."),
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=utcnow_iso(),
    )


__all__ = ["GRAPH_ENDPOINT", "RULE_CATEGORY", "RULE_ID", "SOURCE_TYPE", "evaluate_mfa_registration", "mfa_registration_rule"]
