"""Deterministic Security Finding domain contracts.

This module defines the explicit, small contracts the Security Findings
foundation is built on.  It deliberately contains NO Microsoft Graph calls,
NO AI, NO database writes and NO credentials.

Architecture (foundation only)::

    M365 configuration/activity
        -> normalized ``SecurityObservation``
        -> deterministic baseline rule
        -> ``SecurityFinding`` (status, severity, risk, evidence, recommendation)

Key invariants
--------------
- ``NO_EVIDENCE != SECURITY_GAP`` -- missing evidence must never become an
  OPEN finding.  It is expressed as ``NOT_EVALUATED``.
- Status, severity, comparison, evidence and the canonical recommendation are
  all derived deterministically from the rule definition and the normalized
  observation.  No AI is involved.
- The service never performs remediation.  A recommendation may *advise*
  administrative remediation but must never execute it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Any, Mapping, Optional

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class FindingStatus(str, Enum):
    """Status of a deterministic security finding.

    ``PASS`` / ``OPEN`` are only produced when valid evidence was evaluated.
    ``NOT_EVALUATED`` is the fail-safe status for missing / ambiguous /
    unsupported / malformed source data -- it is never a security gap.
    """

    PASS = "PASS"
    OPEN = "OPEN"
    NOT_EVALUATED = "NOT_EVALUATED"


class Severity(str, Enum):
    """Ordered severity ladder, assigned deterministically by the rule."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SEVERITY_ORDER = (
    Severity.INFO,
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
)


class DependencyStatus(str, Enum):
    """Dependency availability for a finding evaluation."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceReference:
    """A sanitized, immutable reference to the observation evidence.

    It describes WHERE the evidence came from and the normalized value that
    was used for the comparison.  It never carries tokens, credentials,
    pre-authenticated URLs, raw HTTP responses, or unnecessary user
    identities.
    """

    # collector / source type, e.g. "sharepoint_tenant_settings"
    source_type: str
    # Graph endpoint identifier (path only, no query credentials), or "" when
    # the source is not yet a Graph endpoint.
    graph_endpoint: str = ""
    collection_run_id: str = ""
    endpoint_run_id: str = ""
    observed_at: Optional[str] = None
    # name of the normalized field the rule compared against.
    normalized_field: str = ""
    # sanitized observed value that was compared (never raw / secret).
    sanitized_value: Any = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "source_type": self.source_type,
            "graph_endpoint": self.graph_endpoint,
            "collection_run_id": self.collection_run_id,
            "endpoint_run_id": self.endpoint_run_id,
            "observed_at": self.observed_at,
            "normalized_field": self.normalized_field,
            "sanitized_value": self.sanitized_value,
        }


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Recommendation:
    """Canonical, deterministic remediation guidance.

    ``action`` describes the recommended administrative action.  It may
    advise remediation but the service / rule NEVER executes it.
    """

    # one of: "no_action", "review", "remediate", "verify"
    action: str
    text: str
    # human-readable step-by-step guidance for an administrator.
    steps: tuple[str, ...] = ()

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "action": self.action,
            "text": self.text,
            "steps": list(self.steps),
        }


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityBaseline:
    """A product baseline.

    This is a product baseline, NOT a claim of CIS / NIST / Microsoft Secure
    Score equivalence or regulatory certification.  ``formal_compliance_claim``
    is therefore always ``False``.
    """

    baseline_id: str
    version: str
    display_name: str = ""
    description: str = ""
    formal_compliance_claim: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "formal_compliance_claim": self.formal_compliance_claim,
        }


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityRule:
    """Deterministic baseline rule definition.

    A rule defines how a normalized observation is compared against a
    baseline expectation and what deterministic severity / recommendation to
    emit.  It contains no policy scripting engine -- the comparison is an
    explicit, closed function supplied by the implementing rule.
    """

    rule_id: str
    category: str
    title: str
    description: str
    baseline_id: str
    baseline_version: str
    # canonical ordered set of supported observation values (stricter->more permissive)
    supported_values: tuple[str, ...] = ()
    # baseline expectation expressed as a supported canonical value.
    baseline_value: str = ""
    enabled: bool = True
    severity: Severity = Severity.MEDIUM
    required_capabilities: tuple[str, ...] = ()
    required_graph_permissions: tuple[str, ...] = ()

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "supported_values": list(self.supported_values),
            "baseline_value": self.baseline_value,
            "enabled": self.enabled,
            "severity": self.severity.value,
            "required_capabilities": list(self.required_capabilities),
            "required_graph_permissions": list(self.required_graph_permissions),
        }


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityObservation:
    """A normalized observation fed into a rule.

    ``value`` is the sanitized observed canonical value.  ``source_available``
    indicates whether the source produced usable evidence.  When the source is
    unavailable or the value is unsupported, the evaluation becomes
    ``NOT_EVALUATED`` (never ``OPEN``).
    """

    rule_id: str
    value: Any = None
    source_available: bool = True
    observed_at: Optional[str] = None
    source_type: str = ""
    graph_endpoint: str = ""
    collection_run_id: str = ""
    endpoint_run_id: str = ""
    normalized_field: str = ""

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "rule_id": self.rule_id,
            "value": self.value,
            "source_available": self.source_available,
            "observed_at": self.observed_at,
            "source_type": self.source_type,
            "graph_endpoint": self.graph_endpoint,
            "collection_run_id": self.collection_run_id,
            "endpoint_run_id": self.endpoint_run_id,
            "normalized_field": self.normalized_field,
        }


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityFinding:
    """The deterministic result of evaluating one observation against a rule.

    A stable ``finding_id`` is derived from the rule id, the tenant-independent
    baseline identity and the normalized observed value so that identical
    input produces an identical id.
    """

    finding_id: str
    rule_id: str
    baseline_id: str
    baseline_version: str
    category: str
    title: str
    severity: Severity
    status: FindingStatus
    baseline_expectation: str
    observed_state: str
    risk: str
    evidence: EvidenceReference
    recommendation: Recommendation
    dependency_status: DependencyStatus
    evaluated_at: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "category": self.category,
            "title": self.title,
            "severity": self.severity.value,
            "status": self.status.value,
            "baseline_expectation": self.baseline_expectation,
            "observed_state": self.observed_state,
            "risk": self.risk,
            "evidence": self.evidence.to_dict(),
            "recommendation": self.recommendation.to_dict(),
            "dependency_status": self.dependency_status.value,
            "evaluated_at": self.evaluated_at,
        }


# ---------------------------------------------------------------------------
# Service contract (protocol)
# ---------------------------------------------------------------------------


class SecurityFindingService:
    """Contract for the deterministic Security Finding service.

    Implementations map::

        SecurityObservation -> resolve baseline/rule -> validate dependency
                              -> deterministic comparison -> SecurityFinding

    The same normalized input + the same baseline/version must produce a
    semantically identical result.  The service has no AI / network
    dependency and performs no remediation.
    """

    def evaluate(self, observation: SecurityObservation) -> SecurityFinding:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def make_finding_id(rule_id: str, baseline_id: str, baseline_version: str,
                    observed_key: str) -> str:
    """Stable deterministic finding id for a given observed state."""
    return _stable_digest(rule_id, baseline_id, baseline_version, observed_key)


__all__ = [
    "DependencyStatus",
    "EvidenceReference",
    "FindingStatus",
    "SEVERITY_ORDER",
    "SecurityBaseline",
    "SecurityFinding",
    "SecurityFindingService",
    "SecurityObservation",
    "SecurityRule",
    "Severity",
    "Recommendation",
    "make_finding_id",
    "utcnow_iso",
]
