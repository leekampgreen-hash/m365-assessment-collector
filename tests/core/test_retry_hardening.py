"""Unit tests for TD-006 (Retry Recovery Hardening and Recovery Evidence).

Validates:
- Failure classification permanence (RETRYABLE vs PERMANENT vs NON_ERROR).
- Bounded retry strategy, exponential backoff, and Retry-After ceiling.
- RecoveryEvidence shape, bounded statuses, and recommended operator guidance.
- BaseCollector integration: RECOVERED on retry success, FAILED_RETRY_EXHAUSTED
  when attempts exhaust, and FAILED_PERMANENT on auth/permission failures.
- Agentic operational analytics functions.
"""
from __future__ import annotations

import unittest
from unittest.mock import Mock

from collectors.core.collector import BaseCollector
from collectors.core.errors import (
    API_ERROR,
    AUTH_FAILURE,
    NETWORK_ERROR,
    PASS,
    PERMISSION_REQUIRED,
    SOURCE_FAILURE,
    TENANT_MISMATCH,
    THROTTLED,
    classify_failure_permanence,
    PERMANENCE_NON_ERROR,
    PERMANENCE_PERMANENT,
    PERMANENCE_RETRYABLE,
)
from collectors.core.models import CollectionResult, EndpointSpec
from collectors.core.operations_analytics import (
    explain_collection_outcome,
    summarize_run_recovery,
    summarize_run_rejections,
)
from collectors.core.rejections import RejectionTracker
from collectors.core.retry import (
    ACTION_CHECK_GRAPH_PERMISSION,
    ACTION_NONE,
    ACTION_RETRY_RUN,
    ACTION_VERIFY_TENANT_CONTEXT,
    RecoveryEvidence,
    RecoveryTracker,
    RetryPolicy,
    STATUS_FAILED_PERMANENT,
    STATUS_FAILED_RETRY_EXHAUSTED,
    STATUS_PASS,
    STATUS_RECOVERED,
    recommend_recovery_action,
)
from collectors.core.transport import GraphHttpError, GraphTransport, Response


import json


def make_response(status: int, payload: dict, headers: dict = None):
    body = json.dumps(payload).encode("utf-8")

    class HttpResponse:
        def __init__(self):
            self.status = status
            self.headers = headers or {}
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return self._body

        def getheader(self, name, default=None):
            return self.headers.get(name, default)

    return HttpResponse()


def make_http_error(status: int, body: dict, headers: dict = None) -> GraphHttpError:
    return GraphHttpError(
        status=status,
        code=body.get("error", {}).get("code", "Unknown"),
        message=body.get("error", {}).get("message", "Unknown error"),
        headers=headers or {},
    )


class FailurePermanenceClassificationTests(unittest.TestCase):
    def test_transient_failures_are_retryable(self):
        for classification in (THROTTLED, API_ERROR, NETWORK_ERROR, SOURCE_FAILURE):
            with self.subTest(classification=classification):
                self.assertEqual(
                    classify_failure_permanence(classification),
                    PERMANENCE_RETRYABLE,
                )

    def test_permission_and_auth_failures_are_permanent(self):
        for classification in (AUTH_FAILURE, PERMISSION_REQUIRED, TENANT_MISMATCH):
            with self.subTest(classification=classification):
                self.assertEqual(
                    classify_failure_permanence(classification),
                    PERMANENCE_PERMANENT,
                )

    def test_pass_is_non_error(self):
        self.assertEqual(classify_failure_permanence(PASS), PERMANENCE_NON_ERROR)


class RetryPolicyHardeningTests(unittest.TestCase):
    def test_retry_after_bounded_by_maximum_ceiling(self):
        # Even if Graph sends a 3600-second Retry-After, cap it at max_retry_after_seconds (default 60s)
        policy = RetryPolicy(max_retries=3, max_retry_after_seconds=60.0)
        decision = policy.should_retry(THROTTLED, retry_after="3600", attempts_so_far=1)
        self.assertTrue(decision.retry)
        self.assertEqual(decision.sleep_seconds, 60.0)
        self.assertEqual(decision.reason, "honor-retry-after")

    def test_retry_after_under_ceiling_honored_exact(self):
        policy = RetryPolicy(max_retries=3, max_retry_after_seconds=60.0)
        decision = policy.should_retry(THROTTLED, retry_after="15", attempts_so_far=1)
        self.assertTrue(decision.retry)
        self.assertEqual(decision.sleep_seconds, 15.0)

    def test_exponential_backoff_progression(self):
        policy = RetryPolicy(
            max_retries=3,
            base_delay_seconds=1.0,
            backoff_factor=2.0,
            max_delay_seconds=10.0,
        )
        # Attempt 1 failed (retries_done=0) -> delay = 1.0 * (2^0) = 1.0
        d1 = policy.should_retry(API_ERROR, attempts_so_far=1)
        self.assertTrue(d1.retry)
        self.assertEqual(d1.sleep_seconds, 1.0)

        # Attempt 2 failed (retries_done=1) -> delay = 1.0 * (2^1) = 2.0
        d2 = policy.should_retry(API_ERROR, attempts_so_far=2)
        self.assertTrue(d2.retry)
        self.assertEqual(d2.sleep_seconds, 2.0)

        # Attempt 3 failed (retries_done=2) -> delay = 1.0 * (2^2) = 4.0
        d3 = policy.should_retry(API_ERROR, attempts_so_far=3)
        self.assertTrue(d3.retry)
        self.assertEqual(d3.sleep_seconds, 4.0)

        # Attempt 4 completed (retries_done=3 >= max_retries=3) -> STOP
        d4 = policy.should_retry(API_ERROR, attempts_so_far=4)
        self.assertFalse(d4.retry)
        self.assertEqual(d4.reason, "max-retries-reached")

    def test_zero_base_delay_remains_instant_for_unit_tests(self):
        policy = RetryPolicy(max_retries=3, base_delay_seconds=0.0)
        decision = policy.should_retry(API_ERROR, attempts_so_far=1)
        self.assertTrue(decision.retry)
        self.assertEqual(decision.sleep_seconds, 0.0)


class RecoveryEvidenceAndActionTests(unittest.TestCase):
    def test_recommend_action_for_auth_and_permission(self):
        self.assertEqual(
            recommend_recovery_action(AUTH_FAILURE, STATUS_FAILED_PERMANENT),
            ACTION_CHECK_GRAPH_PERMISSION,
        )
        self.assertEqual(
            recommend_recovery_action(PERMISSION_REQUIRED, STATUS_FAILED_PERMANENT),
            ACTION_CHECK_GRAPH_PERMISSION,
        )

    def test_recommend_action_for_tenant_mismatch(self):
        self.assertEqual(
            recommend_recovery_action(TENANT_MISMATCH, STATUS_FAILED_PERMANENT),
            ACTION_VERIFY_TENANT_CONTEXT,
        )

    def test_recommend_action_for_retryable_exhausted(self):
        self.assertEqual(
            recommend_recovery_action(THROTTLED, STATUS_FAILED_RETRY_EXHAUSTED),
            ACTION_RETRY_RUN,
        )
        self.assertEqual(
            recommend_recovery_action(API_ERROR, STATUS_FAILED_RETRY_EXHAUSTED),
            ACTION_RETRY_RUN,
        )

    def test_recommend_action_for_recovered_and_pass(self):
        self.assertEqual(recommend_recovery_action(None, STATUS_PASS), ACTION_NONE)
        self.assertEqual(recommend_recovery_action(THROTTLED, STATUS_RECOVERED), ACTION_NONE)

    def test_recovery_evidence_creation(self):
        ev = RecoveryEvidence(
            endpoint="G01-001",
            failure_category=THROTTLED,
            retry_attempts=2,
            final_status=STATUS_RECOVERED,
            recommended_action=ACTION_NONE,
            collection_run_id=10,
        )
        self.assertEqual(ev.endpoint, "G01-001")
        self.assertEqual(ev.failure_category, "THROTTLED")
        self.assertEqual(ev.retry_attempts, 2)
        self.assertEqual(ev.final_status, "RECOVERED")
        self.assertEqual(ev.collection_run_id, 10)
        self.assertTrue(bool(ev.timestamp))


class BaseCollectorRecoveryIntegrationTests(unittest.TestCase):
    def _make_collector(self, opener, max_retries: int = 3):
        spec = EndpointSpec(
            endpoint_id="G01-001",
            name="users",
            path="/users",
            data_domain="Users",
        )
        transport = GraphTransport(
            token_provider=lambda: "token",
            url_open=opener,
        )
        retry = RetryPolicy(max_retries=max_retries, base_delay_seconds=0.0, sleep=lambda s: None)
        return BaseCollector(spec, transport, retry_policy=retry), spec

    def test_first_attempt_pass_records_pass_status(self):
        opener = Mock(return_value=make_response(200, {"value": [{"id": "1"}]}))
        collector, _ = self._make_collector(opener)
        run = collector.collect()
        self.assertEqual(run.result.status, "PASS")
        self.assertEqual(run.result.retry_count, 0)
        self.assertIsNotNone(run.result.recovery_evidence)
        ev = run.result.recovery_evidence
        self.assertEqual(ev["final_status"], "PASS")
        self.assertEqual(ev["retry_attempts"], 1)
        self.assertEqual(ev["recommended_action"], "NONE")

    def test_retry_recovery_success_records_recovered_status(self):
        # Attempt 1 fails with 429, Attempt 2 succeeds with 200
        opener = Mock(side_effect=[
            make_http_error(429, {"error": {"code": "TooManyRequests", "message": "Throttled"}}),
            make_response(200, {"value": [{"id": "1"}]}),
        ])
        collector, _ = self._make_collector(opener)
        run = collector.collect()
        self.assertEqual(run.result.status, "PASS")
        self.assertEqual(run.result.retry_count, 1)
        self.assertIsNotNone(run.result.recovery_evidence)
        ev = run.result.recovery_evidence
        self.assertEqual(ev["final_status"], "RECOVERED")
        self.assertEqual(ev["retry_attempts"], 2)
        self.assertEqual(ev["recommended_action"], "NONE")

    def test_retry_exhausted_records_failed_retry_exhausted(self):
        # All attempts fail with 503 API_ERROR
        opener = Mock(side_effect=make_http_error(
            503, {"error": {"code": "ServiceUnavailable", "message": "Outage"}},
        ))
        collector, _ = self._make_collector(opener, max_retries=2)
        run = collector.collect()
        self.assertEqual(run.result.status, "ERROR")
        self.assertEqual(run.result.error_classification, API_ERROR)  # root cause preserved
        self.assertEqual(run.result.retry_count, 2)
        self.assertIsNotNone(run.result.recovery_evidence)
        ev = run.result.recovery_evidence
        self.assertEqual(ev["final_status"], "FAILED_RETRY_EXHAUSTED")
        self.assertEqual(ev["retry_attempts"], 3)  # initial + 2 retries
        self.assertEqual(ev["failure_category"], API_ERROR)
        self.assertEqual(ev["recommended_action"], "RETRY_RUN")

    def test_permanent_failure_records_failed_permanent(self):
        # 403 Forbidden is not retryable
        opener = Mock(side_effect=make_http_error(
            403, {"error": {"code": "Authorization_RequestDenied", "message": "Denied"}},
        ))
        collector, _ = self._make_collector(opener)
        run = collector.collect()
        self.assertEqual(run.result.status, "ERROR")
        self.assertEqual(run.result.error_classification, PERMISSION_REQUIRED)
        self.assertEqual(run.result.retry_count, 0)
        self.assertIsNotNone(run.result.recovery_evidence)
        ev = run.result.recovery_evidence
        self.assertEqual(ev["final_status"], "FAILED_PERMANENT")
        self.assertEqual(ev["retry_attempts"], 1)
        self.assertEqual(ev["recommended_action"], "CHECK_GRAPH_PERMISSION")


class AgenticOperationsAnalyticsTests(unittest.TestCase):
    def test_explain_collection_outcome(self):
        res = CollectionResult(
            endpoint_id="G01-006",
            status="ERROR",
            error_classification=PERMISSION_REQUIRED,
            retry_count=0,
            recovery_evidence={
                "final_status": "FAILED_PERMANENT",
                "recommended_action": "CHECK_GRAPH_PERMISSION",
            },
        )
        explanation = explain_collection_outcome(res)
        self.assertEqual(explanation["endpoint_id"], "G01-006")
        self.assertEqual(explanation["status"], "ERROR")
        self.assertEqual(explanation["final_status"], "FAILED_PERMANENT")
        self.assertEqual(explanation["permanence"], "PERMANENT")
        self.assertEqual(explanation["recommended_action"], "CHECK_GRAPH_PERMISSION")
        self.assertTrue(explanation["manual_intervention_required"])

    def test_summarize_run_recovery(self):
        results = [
            CollectionResult(endpoint_id="G01-001", status="PASS", retry_count=0),
            CollectionResult(endpoint_id="G01-002", status="PASS", retry_count=1),
            CollectionResult(
                endpoint_id="G01-003",
                status="ERROR",
                error_classification=API_ERROR,
                retry_count=3,
            ),
            CollectionResult(
                endpoint_id="G01-004",
                status="ERROR",
                error_classification=AUTH_FAILURE,
                retry_count=0,
            ),
        ]
        summary = summarize_run_recovery(results)
        self.assertEqual(summary["total_endpoints"], 4)
        self.assertEqual(summary["passed_initial"], 1)
        self.assertEqual(summary["recovered"], 1)
        self.assertEqual(summary["failed_retry_exhausted"], 1)
        self.assertEqual(summary["failed_permanent"], 1)
        self.assertEqual(summary["recovery_rate"], 0.5)  # 1 recovered / (1 recovered + 1 exhausted)

    def test_summarize_run_rejections(self):
        tracker = RejectionTracker()
        tracker.record_raw(
            endpoint="G01-001",
            category="DATA_VALIDATION",
            reason="MISSING_REQUIRED_FIELD",
        )
        results = [
            CollectionResult(endpoint_id="G01-001", rows=9, rejected_rows=1),
        ]
        summary = summarize_run_rejections(results, tracker=tracker)
        self.assertEqual(summary["total_rejected"], 1)
        self.assertEqual(summary["total_rows_evaluated"], 10)
        self.assertEqual(summary["rejection_rate"], 0.1)


if __name__ == "__main__":
    unittest.main()
