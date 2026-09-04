"""Operational analytics and diagnostic explanation helpers for collector runs.

Implements agentic operations queries defined in:
- TD-005 Section 6 (Rejection Analytics)
- TD-006 Section 5 (Recovery Analytics)
- CH-2.4 Section 6 (Agentic Operations Readiness)
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .errors import classify_failure_permanence
from .models import CollectionResult
from .rejections import RejectionTracker, get_rejection_tracker
from .retry import (
    ACTION_NONE,
    STATUS_FAILED_PERMANENT,
    STATUS_FAILED_RETRY_EXHAUSTED,
    STATUS_PASS,
    STATUS_RECOVERED,
    recommend_recovery_action,
)


def explain_collection_outcome(result: CollectionResult) -> Dict[str, Any]:
    """Provide a structured explanation of an endpoint collection outcome.

    Answers the operational questions:
    - Why did collection fail?
    - Was retry attempted?
    - Is manual intervention required?
    """
    error_cls = result.error_classification
    status = result.status
    permanence = classify_failure_permanence(error_cls or "PASS")
    attempts = max(1, result.retry_count + 1) if result.retry_count else 1

    recovery_ev = result.recovery_evidence or {}
    final_status = recovery_ev.get("final_status")
    if not final_status:
        if status == "PASS":
            final_status = STATUS_RECOVERED if result.retry_count > 0 else STATUS_PASS
        else:
            final_status = STATUS_FAILED_RETRY_EXHAUSTED if result.retry_count > 0 else STATUS_FAILED_PERMANENT

    action = recovery_ev.get("recommended_action") or recommend_recovery_action(error_cls, final_status)
    manual_intervention = final_status == STATUS_FAILED_PERMANENT or action != ACTION_NONE

    return {
        "endpoint_id": result.endpoint_id,
        "status": status,
        "final_status": final_status,
        "error_classification": error_cls,
        "permanence": permanence,
        "retry_count": result.retry_count,
        "total_attempts": attempts,
        "recommended_action": action,
        "manual_intervention_required": manual_intervention,
        "rejected_rows": result.rejected_rows,
        "rejection_sample_count": len(result.rejections),
    }


def summarize_run_recovery(results: Sequence[CollectionResult]) -> Dict[str, Any]:
    """Aggregate recovery metrics across an entire collection run (TD-006)."""
    total = len(results)
    passed_initial = 0
    recovered = 0
    failed_retry_exhausted = 0
    failed_permanent = 0
    by_action: Dict[str, int] = {}
    by_classification: Dict[str, int] = {}

    for r in results:
        explanation = explain_collection_outcome(r)
        fs = explanation["final_status"]
        if fs == STATUS_PASS:
            passed_initial += 1
        elif fs == STATUS_RECOVERED:
            recovered += 1
        elif fs == STATUS_FAILED_RETRY_EXHAUSTED:
            failed_retry_exhausted += 1
        elif fs == STATUS_FAILED_PERMANENT:
            failed_permanent += 1

        action = explanation["recommended_action"]
        by_action[action] = by_action.get(action, 0) + 1

        cls_val = explanation["error_classification"] or "PASS"
        by_classification[cls_val] = by_classification.get(cls_val, 0) + 1

    denominator = recovered + failed_retry_exhausted
    recovery_rate = (recovered / denominator) if denominator > 0 else 1.0

    return {
        "total_endpoints": total,
        "passed_initial": passed_initial,
        "recovered": recovered,
        "failed_retry_exhausted": failed_retry_exhausted,
        "failed_permanent": failed_permanent,
        "recovery_rate": round(recovery_rate, 4),
        "by_recommended_action": by_action,
        "by_classification": by_classification,
    }


def summarize_run_rejections(
    results: Optional[Sequence[CollectionResult]] = None,
    tracker: Optional[RejectionTracker] = None,
) -> Dict[str, Any]:
    """Aggregate rejection metrics across endpoints and tracker evidence (TD-005)."""
    active_tracker = tracker or get_rejection_tracker()
    tracker_summary = active_tracker.summary()

    total_rows = 0
    total_rejected = tracker_summary["total_rejected"]
    endpoint_rejections: Dict[str, int] = dict(tracker_summary["by_endpoint"])

    if results:
        for r in results:
            total_rows += getattr(r, "rows", 0) + getattr(r, "rejected_rows", 0)
            if getattr(r, "rejected_rows", 0) > 0:
                ep = r.endpoint_id
                endpoint_rejections[ep] = max(
                    endpoint_rejections.get(ep, 0),
                    r.rejected_rows,
                )

    rejection_rate = (total_rejected / total_rows) if total_rows > 0 else 0.0

    return {
        "total_rejected": total_rejected,
        "total_rows_evaluated": total_rows,
        "rejection_rate": round(rejection_rate, 4),
        "by_endpoint": endpoint_rejections,
        "by_category": tracker_summary["by_category"],
        "by_reason": tracker_summary["by_reason"],
        "sample_evidence_count": tracker_summary["sample_evidence_count"],
    }
