"""Controlled rejection vocabulary, evidence structure, and metrics tracing.

Implements TD-005 (Rejection Metrics and Tracing) and CH-2.4 Section 3.
Provides bounded operational visibility into rejected and malformed records
while strictly preserving fail-closed validation, tenant isolation, and
sensitive data exclusion (no tokens, credentials, secrets, or raw payloads).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


# ---- Controlled Rejection Categories -------------------------------------

REJECTION_CATEGORY_DATA_VALIDATION = "DATA_VALIDATION"
REJECTION_CATEGORY_SECURITY_VALIDATION = "SECURITY_VALIDATION"
REJECTION_CATEGORY_SYSTEM = "SYSTEM"

REJECTION_CATEGORIES: Tuple[str, ...] = (
    REJECTION_CATEGORY_DATA_VALIDATION,
    REJECTION_CATEGORY_SECURITY_VALIDATION,
    REJECTION_CATEGORY_SYSTEM,
)

# ---- Controlled Rejection Reasons -----------------------------------------

# DATA_VALIDATION reasons
REASON_MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
REASON_INVALID_TYPE = "INVALID_TYPE"
REASON_MALFORMED_FORMAT = "MALFORMED_FORMAT"
REASON_INVALID_STRUCTURE = "INVALID_STRUCTURE"

# SECURITY_VALIDATION reasons
REASON_TENANT_MISMATCH = "TENANT_MISMATCH"
REASON_FORBIDDEN_FIELD = "FORBIDDEN_FIELD"
REASON_UNAUTHORIZED_SOURCE = "UNAUTHORIZED_SOURCE"

# SYSTEM reasons
REASON_PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
REASON_TRANSACTION_FAILURE = "TRANSACTION_FAILURE"

CATEGORY_REASONS_MAP: Mapping[str, Tuple[str, ...]] = {
    REJECTION_CATEGORY_DATA_VALIDATION: (
        REASON_MISSING_REQUIRED_FIELD,
        REASON_INVALID_TYPE,
        REASON_MALFORMED_FORMAT,
        REASON_INVALID_STRUCTURE,
    ),
    REJECTION_CATEGORY_SECURITY_VALIDATION: (
        REASON_TENANT_MISMATCH,
        REASON_FORBIDDEN_FIELD,
        REASON_UNAUTHORIZED_SOURCE,
    ),
    REJECTION_CATEGORY_SYSTEM: (
        REASON_PERSISTENCE_FAILURE,
        REASON_TRANSACTION_FAILURE,
    ),
}

ALL_REJECTION_REASONS: Tuple[str, ...] = tuple(
    reason
    for reasons in CATEGORY_REASONS_MAP.values()
    for reason in reasons
)

# ---- Controlled Severities -----------------------------------------------

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_ERROR = "ERROR"

SEVERITIES: Tuple[str, ...] = (
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ERROR,
)


def utcnow_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


# Patterns for detecting potentially sensitive strings
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(secret|token|password|cred|auth|bearer|key|cert|private)",
    re.IGNORECASE,
)
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.\:\@]{1,128}$")


def sanitize_source_object_id(value: Any) -> Optional[str]:
    """Sanitize and bounded-redact a source_object_id.

    Ensures the ID does not contain raw payload fragments or sensitive tokens.
    """
    if value is None:
        return None
    str_val = str(value).strip()
    if not str_val:
        return None
    # If the value resembles a token or sensitive key name, redact it.
    if _SENSITIVE_KEY_PATTERN.search(str_val):
        return "[REDACTED]"
    if _SAFE_ID_PATTERN.match(str_val):
        return str_val[:64]
    return "[REDACTED_FORMAT]"


def sanitize_field_name(field_name: Any) -> Optional[str]:
    """Ensure an affected field name is a safe, non-sensitive identifier."""
    if field_name is None:
        return None
    str_val = str(field_name).strip()
    if not str_val:
        return None
    if _SENSITIVE_KEY_PATTERN.search(str_val):
        return "[REDACTED_FIELD]"
    # Only allow safe identifier names
    if re.match(r"^[a-zA-Z0-9_\-\.]{1,64}$", str_val):
        return str_val
    return "[REDACTED_FIELD]"


@dataclass(frozen=True)
class RejectionEvidence:
    """Structured, redacted evidence of a rejected record.

    Adheres strictly to TD-005 Section 4:
    - timestamp in UTC;
    - endpoint identity;
    - collection_run_id (optional);
    - source_object_id (scrubbed);
    - rejection_category (controlled);
    - rejection_reason (controlled);
    - affected_field (scrubbed);
    - severity (controlled).
    """

    endpoint: str
    rejection_category: str
    rejection_reason: str
    timestamp: str = field(default_factory=utcnow_iso)
    collection_run_id: Optional[int] = None
    source_object_id: Optional[str] = None
    affected_field: Optional[str] = None
    severity: str = SEVERITY_ERROR

    def __post_init__(self) -> None:
        if self.rejection_category not in REJECTION_CATEGORIES:
            raise ValueError(
                f"Invalid rejection_category '{self.rejection_category}'. "
                f"Must be one of {REJECTION_CATEGORIES}"
            )
        allowed_reasons = CATEGORY_REASONS_MAP.get(self.rejection_category, ())
        if self.rejection_reason not in allowed_reasons:
            raise ValueError(
                f"Invalid rejection_reason '{self.rejection_reason}' for category "
                f"'{self.rejection_category}'. Must be one of {allowed_reasons}"
            )
        if self.severity not in SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. Must be one of {SEVERITIES}"
            )
        # Apply sanitization to mutable inputs via object.__setattr__
        object.__setattr__(
            self,
            "source_object_id",
            sanitize_source_object_id(self.source_object_id),
        )
        object.__setattr__(
            self,
            "affected_field",
            sanitize_field_name(self.affected_field),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RejectionTracker:
    """In-memory collector and metrics accumulator for record rejections.

    Maintains:
    - Prometheus-style counter:
      ``records_rejected_total{endpoint, rejection_category, rejection_reason, severity}``
    - Redacted rejection evidence log for queryability.
    """

    def __init__(self, max_rejections: int = 1000) -> None:
        self._max_rejections = max_rejections
        self._counters: Dict[Tuple[str, str, str, str], int] = {}
        self._evidence_log: List[RejectionEvidence] = []

    def record(self, evidence: RejectionEvidence) -> None:
        """Record a rejection event and increment metric counters."""
        key = (
            evidence.endpoint,
            evidence.rejection_category,
            evidence.rejection_reason,
            evidence.severity,
        )
        self._counters[key] = self._counters.get(key, 0) + 1

        if len(self._evidence_log) < self._max_rejections:
            self._evidence_log.append(evidence)

    def record_raw(
        self,
        *,
        endpoint: str,
        category: str,
        reason: str,
        source_object_id: Optional[str] = None,
        affected_field: Optional[str] = None,
        collection_run_id: Optional[int] = None,
        severity: str = SEVERITY_ERROR,
    ) -> RejectionEvidence:
        """Create, sanitize, and record rejection evidence."""
        evidence = RejectionEvidence(
            endpoint=endpoint,
            rejection_category=category,
            rejection_reason=reason,
            source_object_id=source_object_id,
            affected_field=affected_field,
            collection_run_id=collection_run_id,
            severity=severity,
        )
        self.record(evidence)
        return evidence

    @property
    def total_rejections(self) -> int:
        return sum(self._counters.values())

    def get_evidence(
        self,
        endpoint: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[RejectionEvidence]:
        """Query stored rejection evidence."""
        results = self._evidence_log
        if endpoint is not None:
            results = [e for e in results if e.endpoint == endpoint]
        if category is not None:
            results = [e for e in results if e.rejection_category == category]
        return list(results)

    def get_metrics(self) -> List[Dict[str, Any]]:
        """Return metric series for ``records_rejected_total``."""
        metrics: List[Dict[str, Any]] = []
        for (ep, cat, reason, sev), count in sorted(self._counters.items()):
            metrics.append({
                "metric": "records_rejected_total",
                "labels": {
                    "endpoint": ep,
                    "rejection_category": cat,
                    "rejection_reason": reason,
                    "severity": sev,
                },
                "value": count,
            })
        return metrics

    def summary(self) -> Dict[str, Any]:
        """Aggregate summary for agentic analytics."""
        by_endpoint: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        by_reason: Dict[str, int] = {}

        for (ep, cat, reason, _), count in self._counters.items():
            by_endpoint[ep] = by_endpoint.get(ep, 0) + count
            by_category[cat] = by_category.get(cat, 0) + count
            by_reason[reason] = by_reason.get(reason, 0) + count

        return {
            "total_rejected": self.total_rejections,
            "by_endpoint": by_endpoint,
            "by_category": by_category,
            "by_reason": by_reason,
            "sample_evidence_count": len(self._evidence_log),
        }

    def clear(self) -> None:
        self._counters.clear()
        self._evidence_log.clear()


# Default singleton instance for convenience
_GLOBAL_REJECTION_TRACKER = RejectionTracker()


def get_rejection_tracker() -> RejectionTracker:
    return _GLOBAL_REJECTION_TRACKER
