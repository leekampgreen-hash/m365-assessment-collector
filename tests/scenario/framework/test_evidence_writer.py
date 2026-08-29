"""Offline contract tests for the fixed-shape Scenario evidence writer."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from agents.scenario.auth.contracts import ScenarioAuthenticationContext
from agents.scenario.evidence import (
    ScenarioEvidenceBoundary,
    ScenarioEvidenceRecord,
    ScenarioEvidenceWriter,
)
from agents.scenario.models import (
    STATUS_SUCCESS,
    ScenarioExecutionResult,
    ScenarioStepResult,
)


_FIELDS = {
    "execution_id", "correlation_id", "scenario_id", "operation",
    "actor_id_hash", "timestamp", "status", "error_code", "object_count",
}


def _record() -> ScenarioEvidenceRecord:
    return ScenarioEvidenceRecord(
        execution_id="exec-001",
        correlation_id="GA-SCENARIO-exec-001",
        scenario_id="SCN-AUTH-001",
        operation="INTERACTIVE_SIGNIN",
        actor_id_hash="a" * 64,
        timestamp="2026-08-25T12:00:00+00:00",
        status=STATUS_SUCCESS,
        error_code=None,
        object_count=1,
    )


class _CapturingAdapter:
    def __init__(self) -> None:
        self.persisted = None

    def persist(self, **values) -> None:
        self.persisted = values


class ScenarioEvidenceWriterTests(unittest.TestCase):
    def test_writer_accepts_only_evidence_record(self):
        self.assertEqual(ScenarioEvidenceWriter().write(_record())["execution_id"], "exec-001")

    def test_writer_rejects_dict(self):
        with self.assertRaises(TypeError):
            ScenarioEvidenceWriter().write({"execution_id": "exec-001"})

    def test_writer_rejects_execution_result(self):
        result = ScenarioExecutionResult(
            execution_id="exec-001",
            correlation_id="GA-SCENARIO-exec-001",
            scenario_id="SCN-AUTH-001",
            actor_id="actor-001",
        )
        with self.assertRaises(TypeError):
            ScenarioEvidenceWriter().write(result)

    def test_writer_rejects_step_result(self):
        step_result = ScenarioStepResult(
            step_id="step-001",
            action_type="INTERACTIVE_SIGNIN",
            status=STATUS_SUCCESS,
        )
        with self.assertRaises(TypeError):
            ScenarioEvidenceWriter().write(step_result)

    def test_writer_rejects_raw_auth_context(self):
        context = ScenarioAuthenticationContext(
            authenticated=True,
            tenant_id="tenant-001",
            client_id="client-001",
            correlation_id="GA-SCENARIO-exec-001",
        )
        with self.assertRaises(TypeError):
            ScenarioEvidenceWriter().write(context)

    def test_writer_generates_fixed_payload(self):
        adapter = _CapturingAdapter()
        payload = ScenarioEvidenceWriter(adapter).write(_record())
        self.assertEqual(set(payload), _FIELDS)
        self.assertEqual(adapter.persisted, payload)

    def test_writer_never_persists_unknown_fields(self):
        record = _record()
        object.__setattr__(record, "error_message", "do not persist")
        object.__setattr__(record, "raw_payload", {"access_token": "secret"})
        adapter = _CapturingAdapter()
        payload = ScenarioEvidenceWriter(adapter).write(record)
        self.assertEqual(set(payload), _FIELDS)
        self.assertEqual(set(adapter.persisted), _FIELDS)
        self.assertNotIn("error_message", payload)
        self.assertNotIn("raw_payload", payload)

    def test_evidence_record_remains_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            _record().status = "FAILED"

    def test_boundary_remains_required_for_execution_results(self):
        result = ScenarioExecutionResult(
            execution_id="exec-001",
            correlation_id="GA-SCENARIO-exec-001",
            scenario_id="SCN-AUTH-001",
            actor_id="actor-001",
            status=STATUS_SUCCESS,
            completed_at="2026-08-25T12:00:00+00:00",
            step_results=[
                ScenarioStepResult(
                    step_id="step-001",
                    action_type="INTERACTIVE_SIGNIN",
                    status=STATUS_SUCCESS,
                )
            ],
        )
        record = ScenarioEvidenceBoundary.to_record(result)
        self.assertIsInstance(record, ScenarioEvidenceRecord)


if __name__ == "__main__":
    unittest.main()
