"""Bounded retry policy and operational recovery hardening for the collector framework.

Implements TD-006 (Retry Recovery Hardening) and CH-2.4 Section 4.
Behavior:
- Distinguishes retryable vs permanent failures.
- Auth and permission failures are NEVER retried.
- Bounded exponential backoff with jitter and Retry-After delay ceiling.
- Bounded retry attempts (default max 3 retries, at most 4 attempts total).
- Structured RecoveryEvidence capturing attempts, final status, and recommended action.
"""
from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import errors


DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_SECONDS = 0.0  # Tests must not actually sleep long.
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_DELAY_SECONDS = 30.0
DEFAULT_MAX_RETRY_AFTER_SECONDS = 60.0

# ---- Recovery Actions (TD-006 Section 4) -----------------------------------

ACTION_NONE = "NONE"
ACTION_RETRY_RUN = "RETRY_RUN"
ACTION_CHECK_GRAPH_PERMISSION = "CHECK_GRAPH_PERMISSION"
ACTION_VERIFY_TENANT_CONTEXT = "VERIFY_TENANT_CONTEXT"
ACTION_INSPECT_INPUT_CONTRACT = "INSPECT_INPUT_CONTRACT"
ACTION_CHECK_DATABASE_AVAILABILITY = "CHECK_DATABASE_AVAILABILITY"

RECOMMENDED_ACTIONS: Tuple[str, ...] = (
    ACTION_NONE,
    ACTION_RETRY_RUN,
    ACTION_CHECK_GRAPH_PERMISSION,
    ACTION_VERIFY_TENANT_CONTEXT,
    ACTION_INSPECT_INPUT_CONTRACT,
    ACTION_CHECK_DATABASE_AVAILABILITY,
)

# ---- Recovery Final Statuses (TD-006 Section 4) ---------------------------

STATUS_PASS = "PASS"
STATUS_RECOVERED = "RECOVERED"
STATUS_FAILED_RETRY_EXHAUSTED = "FAILED_RETRY_EXHAUSTED"
STATUS_FAILED_PERMANENT = "FAILED_PERMANENT"
STATUS_CANCELLED = "CANCELLED"

RECOVERY_STATUSES: Tuple[str, ...] = (
    STATUS_PASS,
    STATUS_RECOVERED,
    STATUS_FAILED_RETRY_EXHAUSTED,
    STATUS_FAILED_PERMANENT,
    STATUS_CANCELLED,
)


def utcnow_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def recommend_recovery_action(classification: Optional[str], final_status: str) -> str:
    """Determine bounded recommended operator action for a failure (TD-006)."""
    if final_status in (STATUS_PASS, STATUS_RECOVERED):
        return ACTION_NONE
    if not classification:
        return ACTION_RETRY_RUN

    if classification in (errors.AUTH_FAILURE, errors.PERMISSION_REQUIRED):
        return ACTION_CHECK_GRAPH_PERMISSION
    if classification == errors.TENANT_MISMATCH:
        return ACTION_VERIFY_TENANT_CONTEXT
    if classification in (errors.MALFORMED_DATA, errors.SCHEMA_CONTRACT_FAILURE, errors.ENTITY_IDENTITY_UNAVAILABLE):
        return ACTION_INSPECT_INPUT_CONTRACT
    if classification == errors.PERSISTENCE_ERROR:
        return ACTION_CHECK_DATABASE_AVAILABILITY
    if errors.is_retryable(classification):
        return ACTION_RETRY_RUN

    return ACTION_RETRY_RUN


@dataclass(frozen=True)
class RecoveryEvidence:
    """Structured, redacted recovery evidence for one endpoint execution (TD-006).

    Contains:
    - endpoint: stable endpoint identity from registry/spec;
    - collection_run_id: optional integer lineage run ID;
    - failure_category: controlled failure classification;
    - retry_attempts: total completed attempts;
    - final_status: outcome (PASS, RECOVERED, FAILED_RETRY_EXHAUSTED, FAILED_PERMANENT);
    - recommended_action: bounded operator guidance;
    - timestamp: UTC ISO timestamp.
    """

    endpoint: str
    failure_category: Optional[str] = None
    retry_attempts: int = 0
    final_status: str = STATUS_PASS
    recommended_action: str = ACTION_NONE
    collection_run_id: Optional[int] = None
    timestamp: str = field(default_factory=utcnow_iso)

    def __post_init__(self) -> None:
        if self.final_status not in RECOVERY_STATUSES:
            raise ValueError(
                f"Invalid final_status '{self.final_status}'. Must be one of {RECOVERY_STATUSES}"
            )
        if self.recommended_action not in RECOMMENDED_ACTIONS:
            raise ValueError(
                f"Invalid recommended_action '{self.recommended_action}'. "
                f"Must be one of {RECOMMENDED_ACTIONS}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetryDecision:
    retry: bool
    sleep_seconds: float = 0.0
    reason: str = ""
    attempts_so_far: int = 0


@dataclass
class RetryPolicy:
    max_retries: int = DEFAULT_MAX_RETRIES
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS
    max_retry_after_seconds: float = DEFAULT_MAX_RETRY_AFTER_SECONDS
    use_jitter: bool = False
    sleep: Callable[[float], None] = time.sleep
    jitter_func: Callable[[], float] = field(default_factory=lambda: random.random)

    def should_retry(
        self,
        classification: str,
        *,
        retry_after: Optional[str] = None,
        attempts_so_far: int = 0,
    ) -> RetryDecision:
        """Decide whether to retry after a failed attempt.

        ``attempts_so_far`` is the number of attempts that have already
        been COMPLETED before this decision is requested (0 before the
        first attempt, 1 after the first attempt returned). ``max_retries``
        counts RETRIES ONLY -- not the initial attempt. So with
        ``max_retries=2`` the policy permits the initial attempt plus
        two retries (three attempts total).
        """
        if attempts_so_far < 0:
            attempts_so_far = 0

        if classification == errors.PASS:
            return RetryDecision(False, reason="pass", attempts_so_far=attempts_so_far)

        if not errors.is_retryable(classification):
            return RetryDecision(False, reason="non-retryable", attempts_so_far=attempts_so_far)

        # Retries done so far = attempts - 1 (initial attempt is not a retry).
        retries_done = max(0, attempts_so_far - 1)
        if retries_done >= self.max_retries:
            return RetryDecision(False, reason="max-retries-reached", attempts_so_far=attempts_so_far)

        # Compute delay: honor Retry-After if throttled, otherwise exponential backoff.
        sleep_seconds = self.base_delay_seconds
        reason = "retryable"
        if classification == errors.THROTTLED and retry_after is not None:
            try:
                parsed_after = float(int(retry_after))
                # Bound Retry-After to max_retry_after_seconds ceiling (TD-006 Section 3)
                sleep_seconds = min(parsed_after, self.max_retry_after_seconds)
                reason = "honor-retry-after"
            except (TypeError, ValueError):
                pass
        elif self.base_delay_seconds > 0.0:
            # Bounded exponential backoff with optional jitter
            backoff_multiplier = self.backoff_factor ** retries_done
            computed_delay = min(self.base_delay_seconds * backoff_multiplier, self.max_delay_seconds)
            if self.use_jitter:
                jitter = self.jitter_func() * (computed_delay * 0.25)
                computed_delay = min(computed_delay + jitter, self.max_delay_seconds)
            sleep_seconds = computed_delay

        return RetryDecision(True, sleep_seconds=sleep_seconds, reason=reason, attempts_so_far=attempts_so_far)

    def wait(self, decision: RetryDecision) -> None:
        """Sleep according to the decision. Tests may override ``sleep``."""
        if decision.retry and decision.sleep_seconds > 0:
            self.sleep(decision.sleep_seconds)


class RecoveryTracker:
    """Accumulates recovery statistics across multiple collector executions."""

    def __init__(self) -> None:
        self._history: List[RecoveryEvidence] = []

    def record(self, evidence: RecoveryEvidence) -> None:
        self._history.append(evidence)

    def summary(self) -> Dict[str, Any]:
        total = len(self._history)
        passed = sum(1 for e in self._history if e.final_status == STATUS_PASS)
        recovered = sum(1 for e in self._history if e.final_status == STATUS_RECOVERED)
        retry_exhausted = sum(1 for e in self._history if e.final_status == STATUS_FAILED_RETRY_EXHAUSTED)
        permanent_failed = sum(1 for e in self._history if e.final_status == STATUS_FAILED_PERMANENT)

        by_action: Dict[str, int] = {}
        for e in self._history:
            by_action[e.recommended_action] = by_action.get(e.recommended_action, 0) + 1

        recovery_rate = (recovered / (recovered + retry_exhausted)) if (recovered + retry_exhausted) > 0 else 1.0

        return {
            "total_executions": total,
            "pass_initial": passed,
            "recovered": recovered,
            "failed_retry_exhausted": retry_exhausted,
            "failed_permanent": permanent_failed,
            "recovery_rate": round(recovery_rate, 4),
            "by_recommended_action": by_action,
        }

    def clear(self) -> None:
        self._history.clear()