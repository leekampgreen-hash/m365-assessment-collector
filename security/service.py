"""Deterministic Security Finding service.

Flow::

    SecurityObservation
        -> resolve baseline/rule
        -> validate dependency
        -> deterministic comparison
        -> SecurityFinding

The same normalized input + the same baseline/version must produce a
semantically identical result.  There is no AI and no network dependency.
"""
from __future__ import annotations

from typing import Callable, Mapping, Optional

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
)
from security.baseline import recommended_baseline
from security.rules.sp_ext_001 import (
    RULE_ID,
    evaluate_external_sharing,
    external_sharing_rule,
)
from security.rules.entra_guest_001 import (
    RULE_ID as ENTRA_GUEST_RULE_ID,
    evaluate_guest_invitation,
    guest_invitation_rule,
)
from security.rules.entra_consent_001 import (
    RULE_ID as ENTRA_CONSENT_RULE_ID,
    evaluate_user_consent,
    user_consent_rule,
)
from security.rules.entra_risky_consent_001 import (
    RULE_ID as ENTRA_RISKY_CONSENT_RULE_ID,
    evaluate_risky_consent,
    risky_consent_rule,
)
from security.rules.entra_global_admin_001 import (
    RULE_ID as ENTRA_GLOBAL_ADMIN_RULE_ID,
    evaluate_global_admin_assignments,
    global_admin_rule,
)
from security.rules.entra_guest_access_001 import (
    RULE_ID as ENTRA_GUEST_ACCESS_RULE_ID,
    evaluate_guest_access,
    guest_access_rule,
)
from security.rules.entra_ca_enforcement_001 import (
    RULE_ID as ENTRA_CA_ENFORCEMENT_RULE_ID,
    conditional_access_enforcement_rule,
    evaluate_conditional_access_enforcement,
)
from security.rules.entra_ca_mfa_001 import (
    RULE_ID as ENTRA_CA_MFA_RULE_ID,
    conditional_access_mfa_rule,
    evaluate_conditional_access_mfa,
)
from security.rules.entra_ca_legacy_auth_001 import (
    RULE_ID as ENTRA_CA_LEGACY_AUTH_RULE_ID,
    conditional_access_legacy_auth_rule,
    evaluate_conditional_access_legacy_auth,
)
from security.rules.entra_mfa_registration_001 import (
    RULE_ID as ENTRA_MFA_REG_RULE_ID, evaluate_mfa_registration, mfa_registration_rule,
)
from security.rules.entra_admin_mfa_registration_001 import (
    RULE_ID as ENTRA_ADMIN_MFA_REG_RULE_ID,
    admin_mfa_registration_rule, evaluate_admin_mfa_registration,
)

#: Mapping of rule_id -> deterministic evaluator callable.
_EVALUATORS: Mapping[str, Callable[[SecurityObservation, SecurityBaseline], SecurityFinding]] = {
    RULE_ID: evaluate_external_sharing,
    ENTRA_GUEST_RULE_ID: evaluate_guest_invitation,
    ENTRA_CONSENT_RULE_ID: evaluate_user_consent,
    ENTRA_RISKY_CONSENT_RULE_ID: evaluate_risky_consent,
    ENTRA_GLOBAL_ADMIN_RULE_ID: evaluate_global_admin_assignments,
    ENTRA_GUEST_ACCESS_RULE_ID: evaluate_guest_access,
    ENTRA_CA_ENFORCEMENT_RULE_ID: evaluate_conditional_access_enforcement,
    ENTRA_CA_MFA_RULE_ID: evaluate_conditional_access_mfa,
    ENTRA_CA_LEGACY_AUTH_RULE_ID: evaluate_conditional_access_legacy_auth,
    ENTRA_MFA_REG_RULE_ID: evaluate_mfa_registration,
    ENTRA_ADMIN_MFA_REG_RULE_ID: evaluate_admin_mfa_registration,
}

_RULE_FACTORIES = {
    RULE_ID: external_sharing_rule,
    ENTRA_GUEST_RULE_ID: guest_invitation_rule,
    ENTRA_CONSENT_RULE_ID: user_consent_rule,
    ENTRA_RISKY_CONSENT_RULE_ID: risky_consent_rule,
    ENTRA_GLOBAL_ADMIN_RULE_ID: global_admin_rule,
    ENTRA_GUEST_ACCESS_RULE_ID: guest_access_rule,
    ENTRA_CA_ENFORCEMENT_RULE_ID: conditional_access_enforcement_rule,
    ENTRA_CA_MFA_RULE_ID: conditional_access_mfa_rule,
    ENTRA_CA_LEGACY_AUTH_RULE_ID: conditional_access_legacy_auth_rule,
    ENTRA_MFA_REG_RULE_ID: mfa_registration_rule,
    ENTRA_ADMIN_MFA_REG_RULE_ID: admin_mfa_registration_rule,
}


class DeterministicSecurityFindingService:
    """Resolve a rule and deterministically evaluate an observation."""

    def __init__(self, baseline: Optional[SecurityBaseline] = None):
        self.baseline = baseline or recommended_baseline()

    def resolve_rule(self, rule_id: str) -> Optional[SecurityRule]:
        """Resolve a rule definition for a rule id (or None if unknown)."""
        factory = _RULE_FACTORIES.get(rule_id)
        return factory(self.baseline) if factory else None

    def evaluate(self, observation: SecurityObservation) -> SecurityFinding:
        """Evaluate a single normalized observation into a SecurityFinding.

        Fail-safe: an unknown rule id or a missing dependency resolves to a
        ``NOT_EVALUATED`` finding and never to ``OPEN``.
        """
        rule = self.resolve_rule(observation.rule_id)
        if rule is None or not rule.enabled:
            return self._unknown_or_disabled(observation)
        evaluator = _EVALUATORS.get(observation.rule_id)
        if evaluator is None:
            return self._unknown_or_disabled(observation)
        return evaluator(observation, self.baseline)

    def evaluate_many(self, observations: list[SecurityObservation]) -> list[SecurityFinding]:
        """Evaluate several observations; order and content are preserved."""
        return [self.evaluate(observation) for observation in observations]

    def _unknown_or_disabled(self, observation: SecurityObservation) -> SecurityFinding:
        rule = self.resolve_rule(observation.rule_id)
        if rule is None:
            rule_id = observation.rule_id
            baseline = self.baseline
            return SecurityFinding(
                finding_id="unknown-rule",
                rule_id=rule_id,
                baseline_id=baseline.baseline_id,
                baseline_version=baseline.version,
                category="",
                title="Rule not recognized",
                severity=Severity.INFO,
                status=FindingStatus.NOT_EVALUATED,
                baseline_expectation="",
                observed_state="unknown_rule",
                risk=(
                    "Not evaluated because the rule is unknown. This is not a "
                    "security gap."
                ),
                evidence=_empty_evidence(),
                recommendation=Recommendation(
                    action="verify",
                    text="Rule id was not recognized; verify the observation.",
                    steps=(),
                ),
                dependency_status=DependencyStatus.NOT_APPLICABLE,
                evaluated_at="",
            )
        # Disabled rule -> never OPEN; emit NOT_EVALUATED with clear state.
        return SecurityFinding(
            finding_id="disabled-rule",
            rule_id=rule.rule_id,
            baseline_id=rule.baseline_id,
            baseline_version=rule.baseline_version,
            category=rule.category,
            title=rule.title,
            severity=rule.severity,
            status=FindingStatus.NOT_EVALUATED,
            baseline_expectation=_expectation_for(rule),
            observed_state="rule_disabled",
            risk=(
                "Not evaluated because the rule is disabled. This is not a "
                "security gap."
            ),
            evidence=_empty_evidence(),
            recommendation=Recommendation(
                action="no_action",
                text="The rule is disabled and was not evaluated.",
                steps=(),
            ),
            dependency_status=DependencyStatus.NOT_APPLICABLE,
            evaluated_at="",
        )


def _expectation_for(rule: SecurityRule) -> str:
    return rule.baseline_value


def _empty_evidence() -> EvidenceReference:
    return EvidenceReference(
        source_type="",
        sanitized_value=None,
    )


__all__ = [
    "DeterministicSecurityFindingService",
]
