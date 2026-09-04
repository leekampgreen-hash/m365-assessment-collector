"""Unit tests for TD-005 (Collector Rejection Metrics and Tracing).

Validates:
- Controlled rejection categories, reasons, and severities.
- Input validation and exception raising on invalid categories/reasons.
- Sensitive data scrubbing and redaction in evidence fields.
- Prometheus-style rejection counter (records_rejected_total).
- Fail-closed record validation integration in normalize_records.
- Rejection metrics summary and queryability for agentic analytics.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict

from collectors.core.rejections import (
    ALL_REJECTION_REASONS,
    CATEGORY_REASONS_MAP,
    REASON_FORBIDDEN_FIELD,
    REASON_INVALID_STRUCTURE,
    REASON_INVALID_TYPE,
    REASON_MALFORMED_FORMAT,
    REASON_MISSING_REQUIRED_FIELD,
    REASON_PERSISTENCE_FAILURE,
    REASON_TENANT_MISMATCH,
    REASON_TRANSACTION_FAILURE,
    REASON_UNAUTHORIZED_SOURCE,
    REJECTION_CATEGORIES,
    REJECTION_CATEGORY_DATA_VALIDATION,
    REJECTION_CATEGORY_SECURITY_VALIDATION,
    REJECTION_CATEGORY_SYSTEM,
    SEVERITIES,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    RejectionEvidence,
    RejectionTracker,
    get_rejection_tracker,
    sanitize_field_name,
    sanitize_source_object_id,
)
from collectors.core.models import CollectionResult
from collectors.workloads.registry import LineageContext, normalize_records


class RejectionVocabularyTests(unittest.TestCase):
    def test_controlled_categories_are_defined(self):
        self.assertIn("DATA_VALIDATION", REJECTION_CATEGORIES)
        self.assertIn("SECURITY_VALIDATION", REJECTION_CATEGORIES)
        self.assertIn("SYSTEM", REJECTION_CATEGORIES)
        self.assertEqual(len(REJECTION_CATEGORIES), 3)

    def test_category_reasons_mapping(self):
        data_reasons = CATEGORY_REASONS_MAP[REJECTION_CATEGORY_DATA_VALIDATION]
        self.assertIn(REASON_MISSING_REQUIRED_FIELD, data_reasons)
        self.assertIn(REASON_INVALID_TYPE, data_reasons)
        self.assertIn(REASON_MALFORMED_FORMAT, data_reasons)
        self.assertIn(REASON_INVALID_STRUCTURE, data_reasons)

        sec_reasons = CATEGORY_REASONS_MAP[REJECTION_CATEGORY_SECURITY_VALIDATION]
        self.assertIn(REASON_TENANT_MISMATCH, sec_reasons)
        self.assertIn(REASON_FORBIDDEN_FIELD, sec_reasons)
        self.assertIn(REASON_UNAUTHORIZED_SOURCE, sec_reasons)

        sys_reasons = CATEGORY_REASONS_MAP[REJECTION_CATEGORY_SYSTEM]
        self.assertIn(REASON_PERSISTENCE_FAILURE, sys_reasons)
        self.assertIn(REASON_TRANSACTION_FAILURE, sys_reasons)

    def test_severities_are_bounded(self):
        self.assertIn("INFO", SEVERITIES)
        self.assertIn("WARNING", SEVERITIES)
        self.assertIn("ERROR", SEVERITIES)
        self.assertEqual(len(SEVERITIES), 3)


class RejectionEvidenceValidationTests(unittest.TestCase):
    def test_valid_evidence_creation(self):
        ev = RejectionEvidence(
            endpoint="G01-001",
            rejection_category=REJECTION_CATEGORY_DATA_VALIDATION,
            rejection_reason=REASON_MISSING_REQUIRED_FIELD,
            affected_field="userPrincipalName",
            source_object_id="user-123",
            severity=SEVERITY_ERROR,
        )
        self.assertEqual(ev.endpoint, "G01-001")
        self.assertEqual(ev.rejection_category, "DATA_VALIDATION")
        self.assertEqual(ev.rejection_reason, "MISSING_REQUIRED_FIELD")
        self.assertEqual(ev.affected_field, "userPrincipalName")
        self.assertEqual(ev.source_object_id, "user-123")
        self.assertEqual(ev.severity, "ERROR")
        self.assertTrue(bool(ev.timestamp))

    def test_invalid_category_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            RejectionEvidence(
                endpoint="G01-001",
                rejection_category="ARBITRARY_CATEGORY",
                rejection_reason=REASON_MISSING_REQUIRED_FIELD,
            )
        self.assertIn("Invalid rejection_category", str(cm.exception))

    def test_invalid_reason_for_category_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            RejectionEvidence(
                endpoint="G01-001",
                rejection_category=REJECTION_CATEGORY_DATA_VALIDATION,
                rejection_reason=REASON_TENANT_MISMATCH,  # TENANT_MISMATCH is SECURITY_VALIDATION
            )
        self.assertIn("Invalid rejection_reason", str(cm.exception))

    def test_invalid_severity_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            RejectionEvidence(
                endpoint="G01-001",
                rejection_category=REJECTION_CATEGORY_DATA_VALIDATION,
                rejection_reason=REASON_MISSING_REQUIRED_FIELD,
                severity="CRITICAL",  # Not in bounded SEVERITIES
            )
        self.assertIn("Invalid severity", str(cm.exception))


class SanitizationAndRedactionTests(unittest.TestCase):
    def test_source_id_scrubs_bearer_token(self):
        raw_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token"
        sanitized = sanitize_source_object_id(raw_token)
        self.assertEqual(sanitized, "[REDACTED]")

    def test_source_id_scrubs_password_strings(self):
        raw_secret = "client_secret_xyz123"
        sanitized = sanitize_source_object_id(raw_secret)
        self.assertEqual(sanitized, "[REDACTED]")

    def test_source_id_preserves_safe_identifier(self):
        safe_guid = "00000000-0000-0000-0000-000000000001"
        sanitized = sanitize_source_object_id(safe_guid)
        self.assertEqual(sanitized, safe_guid)

    def test_field_name_scrubs_sensitive_names(self):
        bad_field = "password_hash"
        sanitized = sanitize_field_name(bad_field)
        self.assertEqual(sanitized, "[REDACTED_FIELD]")

    def test_field_name_preserves_safe_attribute(self):
        safe_field = "displayName"
        sanitized = sanitize_field_name(safe_field)
        self.assertEqual(sanitized, "displayName")

    def test_evidence_auto_sanitizes_attributes(self):
        ev = RejectionEvidence(
            endpoint="G01-001",
            rejection_category=REJECTION_CATEGORY_SECURITY_VALIDATION,
            rejection_reason=REASON_FORBIDDEN_FIELD,
            source_object_id="access_token=secret123",
            affected_field="client_secret",
        )
        self.assertEqual(ev.source_object_id, "[REDACTED]")
        self.assertEqual(ev.affected_field, "[REDACTED_FIELD]")


class RejectionTrackerMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tracker = RejectionTracker()

    def test_tracker_records_and_increments_counters(self):
        ev1 = RejectionEvidence(
            endpoint="G01-001",
            rejection_category=REJECTION_CATEGORY_DATA_VALIDATION,
            rejection_reason=REASON_MISSING_REQUIRED_FIELD,
            affected_field="id",
            severity=SEVERITY_ERROR,
        )
        ev2 = RejectionEvidence(
            endpoint="G01-001",
            rejection_category=REJECTION_CATEGORY_DATA_VALIDATION,
            rejection_reason=REASON_MISSING_REQUIRED_FIELD,
            affected_field="userPrincipalName",
            severity=SEVERITY_ERROR,
        )
        ev3 = RejectionEvidence(
            endpoint="G01-005",
            rejection_category=REJECTION_CATEGORY_SECURITY_VALIDATION,
            rejection_reason=REASON_TENANT_MISMATCH,
            severity=SEVERITY_WARNING,
        )

        self.tracker.record(ev1)
        self.tracker.record(ev2)
        self.tracker.record(ev3)

        self.assertEqual(self.tracker.total_rejections, 3)

        metrics = self.tracker.get_metrics()
        self.assertEqual(len(metrics), 2)

        # G01-001 DATA_VALIDATION had 2 occurrences
        g01_metric = next(m for m in metrics if m["labels"]["endpoint"] == "G01-001")
        self.assertEqual(g01_metric["value"], 2)
        self.assertEqual(g01_metric["labels"]["rejection_category"], "DATA_VALIDATION")

        # G01-005 SECURITY_VALIDATION had 1 occurrence
        g05_metric = next(m for m in metrics if m["labels"]["endpoint"] == "G01-005")
        self.assertEqual(g05_metric["value"], 1)
        self.assertEqual(g05_metric["labels"]["rejection_category"], "SECURITY_VALIDATION")

    def test_tracker_summary_aggregations(self):
        self.tracker.record_raw(
            endpoint="G01-002",
            category=REJECTION_CATEGORY_DATA_VALIDATION,
            reason=REASON_INVALID_TYPE,
            affected_field="accountEnabled",
        )
        self.tracker.record_raw(
            endpoint="G01-002",
            category=REJECTION_CATEGORY_DATA_VALIDATION,
            reason=REASON_MALFORMED_FORMAT,
            affected_field="createdDateTime",
        )
        summary = self.tracker.summary()
        self.assertEqual(summary["total_rejected"], 2)
        self.assertEqual(summary["by_endpoint"]["G01-002"], 2)
        self.assertEqual(summary["by_category"]["DATA_VALIDATION"], 2)
        self.assertEqual(summary["by_reason"]["INVALID_TYPE"], 1)
        self.assertEqual(summary["by_reason"]["MALFORMED_FORMAT"], 1)

    def test_query_evidence_filtering(self):
        self.tracker.record_raw(
            endpoint="G01-001",
            category=REJECTION_CATEGORY_DATA_VALIDATION,
            reason=REASON_INVALID_TYPE,
        )
        self.tracker.record_raw(
            endpoint="G01-003",
            category=REJECTION_CATEGORY_SECURITY_VALIDATION,
            reason=REASON_UNAUTHORIZED_SOURCE,
        )
        filtered = self.tracker.get_evidence(endpoint="G01-001")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].endpoint, "G01-001")


class FailClosedRejectionIntegrationTests(unittest.TestCase):
    def setUp(self):
        get_rejection_tracker().clear()

    def tearDown(self):
        get_rejection_tracker().clear()

    def test_malformed_record_records_evidence_and_strictly_fails_closed(self):
        tracker = get_rejection_tracker()
        initial_count = tracker.total_rejections

        # Pass a non-dict record which fails type assertion in G01-001 adapter
        invalid_records = ["not-a-dict-record"]
        lineage = LineageContext(tenant_id=1, collection_run_id=42)

        with self.assertRaises(TypeError):
            normalize_records("G01-001", invalid_records, lineage)

        # Fail-closed verified: an exception was raised, and rejection was traced
        self.assertEqual(tracker.total_rejections, initial_count + 1)
        evidence = tracker.get_evidence(endpoint="G01-001")
        self.assertTrue(len(evidence) >= 1)
        latest = evidence[-1]
        self.assertEqual(latest.endpoint, "G01-001")
        self.assertEqual(latest.rejection_category, REJECTION_CATEGORY_DATA_VALIDATION)
        self.assertEqual(latest.rejection_reason, REASON_INVALID_TYPE)
        self.assertEqual(latest.collection_run_id, 42)


class CollectionResultModelTests(unittest.TestCase):
    def test_collection_result_has_rejection_fields(self):
        res = CollectionResult(endpoint_id="G01-001")
        self.assertEqual(res.rejected_rows, 0)
        self.assertEqual(res.rejections, [])

        res.rejected_rows = 5
        res.rejections.append({"reason": "MALFORMED_FORMAT"})
        as_dict = res.to_dict()
        self.assertEqual(as_dict["rejected_rows"], 5)
        self.assertEqual(len(as_dict["rejections"]), 1)


if __name__ == "__main__":
    unittest.main()
