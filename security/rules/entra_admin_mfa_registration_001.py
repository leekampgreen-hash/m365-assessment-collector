"""Deterministic administrator MFA registration coverage rule."""
from __future__ import annotations

from typing import Any, Mapping

from security.models import (
    DependencyStatus, EvidenceReference, FindingStatus, Recommendation,
    SecurityBaseline, SecurityFinding, SecurityObservation, SecurityRule,
    Severity, make_finding_id, utcnow_iso,
)

RULE_ID = "M365-ENTRA-ADMIN-MFA-REG-001"
RULE_CATEGORY = "Authentication / Privileged Access"
BASELINE_VALUE = "all_report_identified_administrators_mfa_registered"
SOURCE_TYPE = "entra_user_registration_details"
GRAPH_ENDPOINT = "/v1.0/reports/authenticationMethods/userRegistrationDetails"
INTERPRETATION_SCOPE = "ADMIN_MFA_REGISTRATION_COVERAGE_ONLY"
OPEN_TITLE = "Administrator accounts have incomplete MFA registration coverage"
OPEN_RISK = (
    "One or more user accounts identified as administrators are not recorded as MFA "
    "registered. Because administrator accounts hold elevated privileges, incomplete "
    "MFA registration readiness increases the potential impact of credential misuse."
)
OPEN_RECOMMENDATION = Recommendation(
    action="remediate",
    text=("Review administrator accounts without MFA registration and complete appropriate "
          "authentication-method registration according to the organization's privileged "
          "access and authentication policy."),
    steps=("Re-read the Microsoft authentication methods registration report and confirm "
           "that all report-identified administrator accounts are MFA registered.",),
)
FIELDS = (
    "admin_user_count", "admin_mfa_registered_count",
    "admin_mfa_not_registered_count", "admin_registration_coverage_percent",
)


def admin_mfa_registration_rule(baseline: SecurityBaseline) -> SecurityRule:
    return SecurityRule(
        rule_id=RULE_ID, category=RULE_CATEGORY, title=OPEN_TITLE,
        description=("Verify MFA registration coverage for user accounts identified as "
                     "administrators by Microsoft's authentication registration report."),
        baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        baseline_value=BASELINE_VALUE, severity=Severity.HIGH,
        required_capabilities=("ENTRA_P1",),
        required_graph_permissions=("AuditLog.Read.All",),
    )


def _valid(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    counts = [value.get(field) for field in FIELDS[:3]]
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts):
        return False
    coverage = value.get(FIELDS[3])
    return (isinstance(coverage, (int, float)) and not isinstance(coverage, bool)
            and 0 <= coverage <= 100)


def evaluate_admin_mfa_registration(observation: SecurityObservation,
                                    baseline: SecurityBaseline) -> SecurityFinding:
    rule = admin_mfa_registration_rule(baseline)
    value = observation.value if _valid(observation.value) else None
    evidence = EvidenceReference(
        source_type=observation.source_type or SOURCE_TYPE,
        graph_endpoint=observation.graph_endpoint or GRAPH_ENDPOINT,
        collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "admin_mfa_registration_coverage",
        sanitized_value=value,
    )
    reliable = (
        observation.source_available and value is not None
        and value["admin_user_count"] > 0
        and value["admin_mfa_registered_count"]
        + value["admin_mfa_not_registered_count"] == value["admin_user_count"]
    )
    if not reliable:
        return SecurityFinding(
            finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version, "NOT_EVALUATED"),
            rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
            category=rule.category, title=rule.title, severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED, baseline_expectation=BASELINE_VALUE,
            observed_state="no_report_identified_administrators" if value and value.get("admin_user_count") == 0 else "dependency_unavailable",
            risk="Not evaluated because the administrator registration source was incomplete, malformed, or contained no report-identified administrators. This is not a security gap.",
            evidence=evidence,
            recommendation=Recommendation(action="verify", text="Verify that the complete administrator registration report was collected correctly."),
            dependency_status=DependencyStatus.AVAILABLE if observation.source_available else DependencyStatus.UNAVAILABLE,
            evaluated_at=utcnow_iso(),
        )
    status = (FindingStatus.PASS if value["admin_mfa_not_registered_count"] == 0
              else FindingStatus.OPEN)
    return SecurityFinding(
        finding_id=make_finding_id(RULE_ID, baseline.baseline_id, baseline.version,
                                   f"{status.value}:{value['admin_mfa_not_registered_count']}"),
        rule_id=RULE_ID, baseline_id=baseline.baseline_id, baseline_version=baseline.version,
        category=rule.category, title=OPEN_TITLE, severity=rule.severity, status=status,
        baseline_expectation=BASELINE_VALUE,
        observed_state=f"admin_mfa_not_registered_count:{value['admin_mfa_not_registered_count']}",
        risk=OPEN_RISK if status is FindingStatus.OPEN else "All report-identified administrator accounts are recorded as MFA registered.",
        evidence=evidence,
        recommendation=OPEN_RECOMMENDATION if status is FindingStatus.OPEN else Recommendation(action="no_action", text="No action is required."),
        dependency_status=DependencyStatus.AVAILABLE, evaluated_at=utcnow_iso(),
    )


__all__ = ["GRAPH_ENDPOINT", "INTERPRETATION_SCOPE", "RULE_ID", "SOURCE_TYPE",
           "admin_mfa_registration_rule", "evaluate_admin_mfa_registration"]
