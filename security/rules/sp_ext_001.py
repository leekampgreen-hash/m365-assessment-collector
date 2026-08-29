"""First deterministic baseline rule: SharePoint / OneDrive External Sharing.

rule_id: M365-SP-EXT-001

This rule evaluates normalized SharePoint tenant external-sharing posture
against the product baseline.  It makes NO Microsoft Graph call.

Canonical ordered external-sharing levels (strictest -> most permissive)::

    none
    existing_guests
    new_and_existing_guests
    anyone

Deterministic behavior
----------------------
- actual equal/stricter than baseline          -> PASS
- actual more permissive than baseline         -> OPEN
- source unavailable                           -> NOT_EVALUATED
- unsupported value                            -> NOT_EVALUATED

Severity and the canonical recommendation are deterministic from the rule
definition.  The recommendation may advise administrative remediation but
never executes it.
"""
from __future__ import annotations

from typing import Mapping, Optional

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

RULE_ID = "M365-SP-EXT-001"
RULE_CATEGORY = "SharePoint / OneDrive External Sharing"

# Canonical ordered values: strictest -> most permissive.  A higher index is
# strictly more permissive.
EXTERNAL_SHARING_LEVELS = (
    "none",
    "existing_guests",
    "new_and_existing_guests",
    "anyone",
)

#: Product baseline expectation: only existing guests may be shared with.
BASELINE_VALUE = "existing_guests"

DEFAULT_TITLE = (
    "SharePoint tenant external-sharing configuration is broader than the "
    "configured security baseline"
)

RISK_OPEN = (
    "The tenant external-sharing configuration is broader than the configured "
    "security baseline. Broader sharing increases the risk of unintentional "
    "exposure of content to parties outside the organization."
)

#: Canonical remediation guidance (advises remediation; never executes it).
RECOMMENDATION_OPEN = Recommendation(
    action="remediate",
    text=(
        "Restrict the SharePoint tenant-level external-sharing setting to the "
        "baseline value or stricter. Administrative remediation is advised; "
        "it is not performed by this service."
    ),
    steps=(
        "Confirm the current tenant-level external-sharing setting in the "
        "SharePoint admin center (or equivalent read-only report).",
        "Change the tenant-level external-sharing setting to the baseline value "
        "or a stricter value.",
        "Re-run the M365-SP-EXT-001 evaluation to confirm the finding resolves.",
    ),
)

RECOMMENDATION_PASS = Recommendation(
    action="no_action",
    text="External-sharing posture satisfies the configured security baseline.",
    steps=(),
)


def external_sharing_rule(baseline: SecurityBaseline) -> SecurityRule:
    """Return the deterministic M365-SP-EXT-001 rule definition."""
    return SecurityRule(
        rule_id=RULE_ID,
        category=RULE_CATEGORY,
        title="SharePoint / OneDrive tenant external sharing posture",
        description=(
            "Evaluate normalized SharePoint tenant external-sharing posture "
            "against the product baseline. No Graph call is made."
        ),
        baseline_id=baseline.baseline_id,
        baseline_version=baseline.version,
        supported_values=EXTERNAL_SHARING_LEVELS,
        baseline_value=BASELINE_VALUE,
        enabled=True,
        severity=Severity.MEDIUM,
    )


def _index(level: str) -> Optional[int]:
    """Return the canonical index of a level, or None if unsupported."""
    if level not in EXTERNAL_SHARING_LEVELS:
        return None
    return EXTERNAL_SHARING_LEVELS.index(level)


def evaluate_external_sharing(
    observation: SecurityObservation,
    baseline: SecurityBaseline,
) -> SecurityFinding:
    """Deterministically evaluate one external-sharing observation.

    Fail-safe semantics:
        valid evidence + baseline satisfied  -> PASS
        valid evidence + baseline violated   -> OPEN
        source unavailable / ambiguous / unsupported / malformed
                                            -> NOT_EVALUATED
    """
    rule = external_sharing_rule(baseline)
    rule_id = rule.rule_id
    evaluated_at = utcnow_iso()

    # Source unavailable -> NOT_EVALUATED (never OPEN). NO_EVIDENCE != SECURITY_GAP.
    if not observation.source_available:
        return _not_evaluated(
            rule=rule,
            observed_state="source_unavailable",
            expectation=_expectation(rule),
            dependency=DependencyStatus.UNAVAILABLE,
            reason="source_unavailable",
            evaluated_at=evaluated_at,
            observation=observation,
        )

    # Normalize / sanitize the observed value.
    raw = observation.value
    if isinstance(raw, str):
        level = raw.strip().lower()
    elif isinstance(raw, bool):
        level = None  # booleans are not a supported canonical external-sharing level
    else:
        level = None

    # Unsupported / malformed / ambiguous -> NOT_EVALUATED.
    if level is None or _index(level) is None:
        return _not_evaluated(
            rule=rule,
            observed_state=f"unsupported_value:{_safe_label(raw)}",
            expectation=_expectation(rule),
            dependency=DependencyStatus.AVAILABLE,
            reason="unsupported_value",
            evaluated_at=evaluated_at,
            observation=observation,
        )

    actual_index = _index(level)
    baseline_index = _index(rule.baseline_value)
    assert baseline_index is not None  # baseline value is always supported

    if actual_index <= baseline_index:
        status = FindingStatus.PASS
        dependency = DependencyStatus.AVAILABLE
        observed_state = f"actual:{level}"
        expectation = _expectation(rule)
        title = rule.title
        risk = (
            "External-sharing posture satisfies the configured security baseline; "
            "no broader-than-baseline sharing is indicated."
        )
        recommendation = RECOMMENDATION_PASS
    else:
        status = FindingStatus.OPEN
        dependency = DependencyStatus.AVAILABLE
        observed_state = f"actual:{level}"
        expectation = _expectation(rule)
        title = DEFAULT_TITLE
        risk = RISK_OPEN
        recommendation = RECOMMENDATION_OPEN

    evidence = _evidence(observation, level)

    return SecurityFinding(
        finding_id=make_finding_id(rule_id, baseline.baseline_id,
                                   baseline.version, f"{status.value}:{level}"),
        rule_id=rule_id,
        baseline_id=baseline.baseline_id,
        baseline_version=baseline.version,
        category=rule.category,
        title=title,
        severity=rule.severity,
        status=status,
        baseline_expectation=expectation,
        observed_state=observed_state,
        risk=risk,
        evidence=evidence,
        recommendation=recommendation,
        dependency_status=dependency,
        evaluated_at=evaluated_at,
    )


def _expectation(rule: SecurityRule) -> str:
    return (
        f"tenant external-sharing at or stricter than "
        f"'{rule.baseline_value}'"
    )


def _evidence(observation: SecurityObservation, sanitized_level: str) -> EvidenceReference:
    return EvidenceReference(
        source_type=observation.source_type or "sharepoint_tenant_settings",
        graph_endpoint=observation.graph_endpoint,
        collection_run_id=observation.collection_run_id,
        endpoint_run_id=observation.endpoint_run_id,
        observed_at=observation.observed_at,
        normalized_field=observation.normalized_field or "sharing_capability",
        sanitized_value=sanitized_level,
    )


def _safe_label(value: object) -> str:
    """Render an unsupported observed value as a short, safe label."""
    if value is None:
        return "none"
    text = str(value)
    if len(text) > 32:
        text = text[:32] + "..."
    return text


def _not_evaluated(*, rule: SecurityRule, observed_state: str, expectation: str,
                   dependency: DependencyStatus, reason: str, evaluated_at: str,
                   observation: SecurityObservation) -> SecurityFinding:
    return SecurityFinding(
        finding_id=make_finding_id(rule.rule_id, rule.baseline_id,
                                   rule.baseline_version, f"NOT_EVALUATED:{reason}"),
        rule_id=rule.rule_id,
        baseline_id=rule.baseline_id,
        baseline_version=rule.baseline_version,
        category=rule.category,
        title=rule.title,
        severity=rule.severity,
        status=FindingStatus.NOT_EVALUATED,
        baseline_expectation=expectation,
        observed_state=observed_state,
        risk=(
            "Not evaluated because the source was unavailable, ambiguous, "
            "unsupported, or malformed. This is not a security gap."
        ),
        evidence=_evidence(observation, observation.value),
        recommendation=Recommendation(
            action="verify",
            text=(
                "Source evidence was unavailable or unsupported; verify that the "
                "external-sharing observation is collected correctly."
            ),
            steps=(),
        ),
        dependency_status=dependency,
        evaluated_at=evaluated_at,
    )


__all__ = [
    "BASELINE_VALUE",
    "DEFAULT_TITLE",
    "EXTERNAL_SHARING_LEVELS",
    "RULE_CATEGORY",
    "RULE_ID",
    "evaluate_external_sharing",
    "external_sharing_rule",
]
