"""Offline fail-closed tests for Scenario evidence persistence."""
from __future__ import annotations

import unittest

from agents.scenario.evidence import (
    AUTH_FAILED,
    ScenarioEvidenceBoundary,
    ScenarioEvidenceBoundaryError,
    ScenarioEvidenceRecord,
    ScenarioEvidenceWriter,
)
from agents.scenario.models import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    ScenarioExecutionResult,
    ScenarioStepResult,
)


def _result(**overrides):
    defaults = {
        "execution_id": "exec-001",
        "correlation_id": "GA-SCENARIO-exec-001",
        "scenario_id": "SCN-AUTH-001",
        "actor_id": "test-user-01",
        "status": STATUS_SUCCESS,
        "completed_at": "2026-08-25T12:00:00+00:00",
        "step_results": [
            ScenarioStepResult(
                step_id="step-001",
                action_type="INTERACTIVE_SIGNIN",
                status=STATUS_SUCCESS,
            )
        ],
    }
    defaults.update(overrides)
    return ScenarioExecutionResult(**defaults)


class ScenarioEvidenceBoundaryTests(unittest.TestCase):
    def test_scenario_execution_result_requires_boundary_before_persist(self):
        with self.assertRaises(TypeError):
            ScenarioEvidenceWriter().write(_result())

    def test_unknown_evidence_fields_rejected(self):
        payload = ScenarioEvidenceBoundary.to_record(_result()).to_persistence_payload()
        payload["unexpected"] = "value"
        with self.assertRaises(ScenarioEvidenceBoundaryError):
            ScenarioEvidenceRecord.from_payload(payload)

    def test_token_field_removed_before_persist(self):
        result = _result()
        result.access_token = "bearer abcdefghijklmnopqrstuvwxyz"
        payload = ScenarioEvidenceWriter().write(ScenarioEvidenceBoundary.to_record(result))
        self.assertNotIn("access_token", payload)
        self.assertNotIn("bearer", repr(payload).lower())

    def test_dynamic_client_secret_is_not_leaked(self):
        result = _result()
        result.client_secret = "my-app-secret-not-token-shaped"

        record = ScenarioEvidenceBoundary.to_record(result)
        payload = ScenarioEvidenceWriter().write(record)

        self.assertFalse(hasattr(record, "client_secret"))
        self.assertEqual(set(payload), {
            "execution_id", "correlation_id", "scenario_id", "operation",
            "actor_id_hash", "timestamp", "status", "error_code", "object_count",
        })
        self.assertNotIn("client_secret", payload)
        self.assertNotIn("my-app-secret-not-token-shaped", repr(record))
        self.assertNotIn("my-app-secret-not-token-shaped", repr(payload))

    def test_device_code_removed_before_persist(self):
        result = _result()
        result.device_code = "device-code-value"
        result.user_code = "ABCD-EFGH"
        result.verification_uri = "https://microsoft.com/devicelogin"
        payload = ScenarioEvidenceWriter().write(ScenarioEvidenceBoundary.to_record(result))
        self.assertNotIn("device_code", payload)
        self.assertNotIn("user_code", payload)
        self.assertNotIn("verification_uri", payload)

    def test_raw_payload_rejected(self):
        result = _result()
        result.raw_payload = {"value": "untrusted Graph response"}
        with self.assertRaises(ScenarioEvidenceBoundaryError):
            ScenarioEvidenceBoundary.to_record(result)

    def test_error_message_not_persisted(self):
        result = _result(
            status=STATUS_FAILED,
            step_results=[
                ScenarioStepResult(
                    step_id="step-001",
                    action_type="INTERACTIVE_SIGNIN",
                    status=STATUS_FAILED,
                    error_code="AUTH_TOKEN_ERROR",
                    error_message="token exchange failed: bearer secret-value",
                )
            ],
        )
        payload = ScenarioEvidenceWriter().write(ScenarioEvidenceBoundary.to_record(result))
        self.assertEqual(payload["error_code"], AUTH_FAILED)
        self.assertNotIn("error_message", payload)
        self.assertNotIn("secret-value", repr(payload))

    def test_only_allowlisted_fields_written(self):
        payload = ScenarioEvidenceWriter().write(ScenarioEvidenceBoundary.to_record(_result()))
        self.assertEqual(set(payload), {
            "execution_id", "correlation_id", "scenario_id", "operation",
            "actor_id_hash", "timestamp", "status", "error_code", "object_count",
        })
        self.assertNotEqual(payload["actor_id_hash"], "test-user-01")

    def test_writer_accepts_only_evidence_record(self):
        writer = ScenarioEvidenceWriter()
        with self.assertRaises(TypeError):
            writer.write({"execution_id": "exec-001"})
        record = ScenarioEvidenceBoundary.to_record(_result())
        self.assertEqual(writer.write(record)["execution_id"], "exec-001")

    def test_unknown_error_classification_fails_closed(self):
        result = _result(
            status=STATUS_FAILED,
            step_results=[
                ScenarioStepResult(
                    step_id="step-001",
                    action_type="INTERACTIVE_SIGNIN",
                    status=STATUS_FAILED,
                    error_code="UNCLASSIFIED_FAILURE",
                )
            ],
        )
        with self.assertRaises(ScenarioEvidenceBoundaryError):
            ScenarioEvidenceBoundary.to_record(result)


if __name__ == "__main__":
    unittest.main()
