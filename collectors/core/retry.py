"""Bounded retry policy for the collector framework.

Behavior:
- Auth and permission failures are NEVER retried (they cannot resolve
  themselves by retrying).
- 429 honors a Retry-After header (integer seconds) when present.
- Retryable transient server / network errors are retried up to
  ``max_retries`` times (not counting the initial attempt).
- No infinite loops; the policy returns a ``RetryDecision`` describing
  what the caller should do next.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from . import errors


DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_SECONDS = 0.0  # Tests must not actually sleep long.


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
    sleep: Callable[[float], None] = time.sleep

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

        sleep_seconds = self.base_delay_seconds
        reason = "retryable"
        if classification == errors.THROTTLED and retry_after is not None:
            try:
                sleep_seconds = float(int(retry_after))
                reason = "honor-retry-after"
            except (TypeError, ValueError):
                pass

        return RetryDecision(True, sleep_seconds=sleep_seconds, reason=reason, attempts_so_far=attempts_so_far)

    def wait(self, decision: RetryDecision) -> None:
        """Sleep according to the decision. Tests may override ``sleep``."""
        if decision.retry and decision.sleep_seconds > 0:
            self.sleep(decision.sleep_seconds)