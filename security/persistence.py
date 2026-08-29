"""Atomic, bounded PostgreSQL persistence for deterministic Security findings."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from security.models import SecurityFinding, SecurityObservation


class SecurityPersistenceError(ValueError):
    """Raised when a Security persistence input or database operation is invalid."""


def _digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _timestamp(value: str | None, field: str) -> datetime:
    if not value:
        raise SecurityPersistenceError(field + " is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise SecurityPersistenceError(field + " is not a valid timestamp") from None
    if parsed.tzinfo is None:
        raise SecurityPersistenceError(field + " must include timezone")
    return parsed.astimezone(timezone.utc)


def _lineage(value: str, field: str) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise SecurityPersistenceError(field + " must be an existing numeric id") from None
    if parsed <= 0:
        raise SecurityPersistenceError(field + " must be positive")
    return parsed


class SecurityPersistenceWriter:
    """Persist one evaluated observation and its projection in one transaction.

    Evaluation remains exclusively owned by ``SecurityFindingService``. This
    writer only stores the supplied normalized observation and finding.
    """

    def __init__(self, connection: Any):
        self.connection = connection

    def persist_authenticated(self, *, config: Any, observation: SecurityObservation,
                               finding: SecurityFinding) -> dict[str, int | bool]:
        """Resolve the authenticated tenant through the Collector contract, then write."""
        from collectors.core.tenant import resolve_trusted_tenant

        tenant_id = resolve_trusted_tenant(config, self.connection)
        return self.persist(tenant_id=tenant_id, observation=observation, finding=finding)

    def persist(self, *, tenant_id: int, observation: SecurityObservation,
                finding: SecurityFinding) -> dict[str, int | bool]:
        if isinstance(tenant_id, bool) or not isinstance(tenant_id, int) or tenant_id <= 0:
            raise SecurityPersistenceError("tenant_id is missing or malformed")
        if finding.rule_id != observation.rule_id:
            raise SecurityPersistenceError("finding and observation rules do not match")
        observed_at = _timestamp(observation.observed_at, "observed_at")
        evaluated_at = _timestamp(finding.evaluated_at, "evaluated_at")
        collection_run_id = _lineage(observation.collection_run_id, "collection_run_id")
        endpoint_run_id = _lineage(observation.endpoint_run_id, "endpoint_run_id")
        # Aggregate observations are sanitized domain data, not raw Graph JSON.
        normalized_value = observation.value if isinstance(observation.value, str) else (
            json.dumps(observation.value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            if observation.value is not None else None
        )
        # Sanitized aggregate observations may contain several bounded counters.
        if normalized_value is not None and len(normalized_value) > 1024:
            raise SecurityPersistenceError("normalized value is too long")
        observation_payload = {
            "tenant_id": tenant_id, "rule_id": observation.rule_id,
            "source_type": observation.source_type, "source_endpoint": observation.graph_endpoint,
            "normalized_field": observation.normalized_field,
            "normalized_value": normalized_value,
            "dependency_status": finding.dependency_status.value,
            "observed_at": observed_at.isoformat(),
            "collection_run_id": collection_run_id, "endpoint_run_id": endpoint_run_id,
        }
        observation_digest = _digest(observation_payload)
        evaluation_payload = {
            "tenant_id": tenant_id, "finding_id": finding.finding_id,
            "observation_digest": observation_digest, "rule_id": finding.rule_id,
            "baseline_id": finding.baseline_id, "baseline_version": finding.baseline_version,
            "category": finding.category, "status": finding.status.value,
            "severity": finding.severity.value, "baseline_expectation": finding.baseline_expectation,
            "observed_state": finding.observed_state, "risk": finding.risk,
            "recommendation": finding.recommendation.text,
            "validation_guidance": " ".join(finding.recommendation.steps),
            "dependency_status": finding.dependency_status.value,
        }
        evaluation_digest = _digest(evaluation_payload)
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO security.observation "
                "(tenant_id, rule_id, source_type, source_endpoint, normalized_field, normalized_value, "
                "dependency_status, observed_at, collection_run_id, endpoint_run_id, observation_digest) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (observation_digest) DO NOTHING RETURNING observation_id",
                (tenant_id, observation.rule_id, observation.source_type, observation.graph_endpoint,
                 observation.normalized_field, normalized_value, finding.dependency_status.value,
                 observed_at, collection_run_id, endpoint_run_id, observation_digest),
            )
            row = cursor.fetchone()
            observation_inserted = row is not None
            if row is None:
                cursor.execute("SELECT observation_id FROM security.observation WHERE observation_digest = %s", (observation_digest,))
                row = cursor.fetchone()
            if not row:
                raise SecurityPersistenceError("observation id was not returned")
            observation_id = row[0]
            cursor.execute(
                "INSERT INTO security.finding_evaluation "
                "(tenant_id, finding_id, observation_id, rule_id, baseline_id, baseline_version, category, status, severity, "
                "baseline_expectation, observed_state, risk, recommendation, validation_guidance, dependency_status, evaluated_at, evaluation_digest) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (evaluation_digest) DO NOTHING RETURNING evaluation_id",
                (tenant_id, finding.finding_id, observation_id, finding.rule_id, finding.baseline_id,
                 finding.baseline_version, finding.category, finding.status.value, finding.severity.value,
                 finding.baseline_expectation, finding.observed_state, finding.risk, finding.recommendation.text,
                 " ".join(finding.recommendation.steps), finding.dependency_status.value, evaluated_at, evaluation_digest),
            )
            row = cursor.fetchone()
            evaluation_inserted = row is not None
            if row is None:
                cursor.execute("SELECT evaluation_id FROM security.finding_evaluation WHERE evaluation_digest = %s", (evaluation_digest,))
                row = cursor.fetchone()
            if not row:
                raise SecurityPersistenceError("evaluation id was not returned")
            evaluation_id = row[0]
            cursor.execute(
                "INSERT INTO security.finding_current "
                "(tenant_id, finding_id, rule_id, baseline_id, baseline_version, latest_evaluation_id, status, severity, observed_state, evaluated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, rule_id, baseline_id, baseline_version) DO UPDATE SET "
                "finding_id = EXCLUDED.finding_id, latest_evaluation_id = EXCLUDED.latest_evaluation_id, "
                "status = EXCLUDED.status, severity = EXCLUDED.severity, observed_state = EXCLUDED.observed_state, "
                "evaluated_at = EXCLUDED.evaluated_at, updated_at = now() "
                "WHERE security.finding_current.evaluated_at <= EXCLUDED.evaluated_at",
                (tenant_id, finding.finding_id, finding.rule_id, finding.baseline_id, finding.baseline_version,
                 evaluation_id, finding.status.value, finding.severity.value, finding.observed_state, evaluated_at),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return {"observation_id": observation_id, "evaluation_id": evaluation_id,
                "observation_inserted": observation_inserted,
                "evaluation_inserted": evaluation_inserted,
                "evaluation_digest": evaluation_digest}


__all__ = ["SecurityPersistenceError", "SecurityPersistenceWriter"]
