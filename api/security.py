"""Read-only query service and HTTP helpers for persisted Security findings.

This module is deliberately an API adapter over the persisted deterministic
projection. It does not evaluate rules, call Graph, or write to PostgreSQL.
"""
from __future__ import annotations

from typing import Any, Mapping


VALID_STATUSES = ("OPEN", "PASS", "NOT_EVALUATED")
VALID_SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


class SecurityFindingQueryService:
    """Bounded reads over the current finding projection and its evidence."""

    def __init__(self, connection: Any, tenant_id: int):
        self.connection = connection
        self.tenant_id = tenant_id

    def _fetchall(self, query: str, parameters: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        cursor = self.connection.cursor()
        cursor.execute(query, parameters)
        return list(cursor.fetchall())

    def _fetchone(self, query: str, parameters: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
        cursor = self.connection.cursor()
        cursor.execute(query, parameters)
        return cursor.fetchone()

    @classmethod
    def from_connection(cls, connection: Any, tenant_id: int) -> "SecurityFindingQueryService":
        return cls(connection, tenant_id)

    @staticmethod
    def _finding(row: tuple[Any, ...]) -> dict[str, Any]:
        names = (
            "finding_id", "rule_id", "category", "title", "status", "severity",
            "baseline_id", "baseline_version", "baseline_expectation", "observed_state",
            "risk", "recommendation", "validation_guidance", "dependency_status", "evaluated_at",
        )
        return dict(zip(names, row))

    def findings(self, *, status: str | None = None, severity: str | None = None) -> list[dict[str, Any]]:
        clauses = ["c.tenant_id = %s"]
        parameters: list[Any] = [self.tenant_id]
        if status is not None:
            clauses.append("c.status = %s")
            parameters.append(status)
        if severity is not None:
            clauses.append("c.severity = %s")
            parameters.append(severity)
        query = """SELECT c.finding_id, e.rule_id, e.category, e.category,
                          c.status, c.severity, c.baseline_id, c.baseline_version,
                          e.baseline_expectation, c.observed_state, e.risk,
                          e.recommendation, e.validation_guidance, e.dependency_status,
                          c.evaluated_at
                   FROM security.finding_current c
                   JOIN security.finding_evaluation e
                     ON e.evaluation_id = c.latest_evaluation_id
                    AND e.tenant_id = c.tenant_id
                   WHERE """ + " AND ".join(clauses) + " ORDER BY c.evaluated_at DESC, c.finding_id"
        return [self._finding(row) for row in self._fetchall(query, tuple(parameters))]

    def summary(self) -> dict[str, Any]:
        row = self._fetchone(
            """SELECT count(*)::int,
                      count(*) FILTER (WHERE status = 'OPEN')::int,
                      count(*) FILTER (WHERE status = 'PASS')::int,
                      count(*) FILTER (WHERE status = 'NOT_EVALUATED')::int,
                      max(evaluated_at)
               FROM security.finding_current WHERE tenant_id = %s""",
            (self.tenant_id,),
        ) or (0, 0, 0, 0, None)
        severity_rows = self._fetchall(
            """SELECT severity, count(*)::int FROM security.finding_current
               WHERE tenant_id = %s AND status = 'OPEN' GROUP BY severity ORDER BY severity""",
            (self.tenant_id,),
        )
        return {
            "total_findings": row[0],
            "status_counts": {"OPEN": row[1], "PASS": row[2], "NOT_EVALUATED": row[3]},
            "open_severity_distribution": {item[0]: item[1] for item in severity_rows},
            "latest_evaluated_at": row[4],
        }

    def detail(self, finding_id: str) -> dict[str, Any] | None:
        rows = self._fetchall(
            """SELECT c.finding_id, e.rule_id, e.category, e.category,
                      c.status, c.severity, c.baseline_id, c.baseline_version,
                      e.baseline_expectation, c.observed_state, e.risk,
                      e.recommendation, e.validation_guidance, e.dependency_status,
                      c.evaluated_at, o.source_type, o.source_endpoint,
                      o.normalized_field, o.normalized_value, o.observed_at,
                      o.collection_run_id, o.endpoint_run_id
               FROM security.finding_current c
               JOIN security.finding_evaluation e
                 ON e.evaluation_id = c.latest_evaluation_id AND e.tenant_id = c.tenant_id
               JOIN security.observation o
                 ON o.observation_id = e.observation_id AND o.tenant_id = c.tenant_id
               WHERE c.tenant_id = %s AND c.finding_id = %s""",
            (self.tenant_id, finding_id),
        )
        if not rows:
            return None
        finding = self._finding(rows[0][:15])
        finding["evidence"] = {
            "source_type": rows[0][15],
            "source_endpoint": rows[0][16],
            "normalized_field": rows[0][17],
            "normalized_value": rows[0][18],
            "observed_at": rows[0][19],
            "collection_run_id": rows[0][20],
            "endpoint_run_id": rows[0][21],
        }
        return finding

    def data_quality(self) -> dict[str, Any]:
        row = self._fetchone(
            """SELECT count(*)::int,
                      count(*) FILTER (WHERE status = 'NOT_EVALUATED')::int,
                      count(DISTINCT rule_id)::int, max(evaluated_at)
               FROM security.finding_current WHERE tenant_id = %s""",
            (self.tenant_id,),
        ) or (0, 0, 0, None)
        baselines = self._fetchall(
            """SELECT DISTINCT baseline_id, baseline_version FROM security.finding_current
               WHERE tenant_id = %s ORDER BY baseline_id, baseline_version""",
            (self.tenant_id,),
        )
        observations = self._fetchone(
            """SELECT EXISTS (SELECT 1 FROM security.observation WHERE tenant_id = %s)""",
            (self.tenant_id,),
        )
        return {
            "deterministic_engine_status": "READY",
            "persisted_observation_available": bool(observations and observations[0]),
            "latest_evaluation_timestamp": row[3],
            "not_evaluated_count": row[1],
            "current_rule_count": row[2],
            "current_baselines": [{"baseline_id": item[0], "version": item[1]} for item in baselines],
            "known_source_limitations": ["Security findings reflect persisted collector observations only."],
        }


def validate_filters(status: str | None, severity: str | None) -> str | None:
    if status is not None and status not in VALID_STATUSES:
        return "INVALID_STATUS_FILTER"
    if severity is not None and severity not in VALID_SEVERITIES:
        return "INVALID_SEVERITY_FILTER"
    return None


__all__ = ["SecurityFindingQueryService", "VALID_STATUSES", "VALID_SEVERITIES", "validate_filters"]
