"""Fail-closed persistence boundary for Scenario execution evidence.

Scenario execution objects are runtime objects and must never be handed to a
persistence implementation.  This module is the sole supported conversion
path to the deliberately narrow :class:`ScenarioEvidenceRecord` contract.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from hashlib import sha256
import re
from typing import Any, Dict, Mapping, Optional, Protocol, Tuple

from .models import EXECUTION_STATUSES, ScenarioExecutionResult


AUTH_FAILED = "AUTH_FAILED"
AUTH_TIMEOUT = "AUTH_TIMEOUT"
ACTOR_MISMATCH = "ACTOR_MISMATCH"
POLICY_DENIED = "POLICY_DENIED"
GRAPH_READ_FAILED = "GRAPH_READ_FAILED"
UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"

EVIDENCE_ERROR_CODES: Tuple[str, ...] = (
    AUTH_FAILED,
    AUTH_TIMEOUT,
    ACTOR_MISMATCH,
    POLICY_DENIED,
    GRAPH_READ_FAILED,
    UNSUPPORTED_OPERATION,
)

_FORBIDDEN_FIELDS = frozenset({
    "access_token", "refresh_token", "authorization", "headers", "secret", "client_secret",
    "password", "device_code", "user_code", "verification_uri", "verification_uri_complete", "prompt",
    "message", "raw_payload", "exception", "error_message",
})
_REJECTED_FIELDS = frozenset({"raw_payload", "exception"})
_TOKEN_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9._\-]+|sk-[a-z0-9]{8,}|ey[a-z0-9]{20,})"
)
_ERROR_CODE_MAP = {
    "AUTH_FAILED": AUTH_FAILED,
    "AUTH_TIMEOUT": AUTH_TIMEOUT,
    "ACTOR_MISMATCH": ACTOR_MISMATCH,
    "POLICY_DENIED": POLICY_DENIED,
    "GRAPH_READ_FAILED": GRAPH_READ_FAILED,
    "UNSUPPORTED_OPERATION": UNSUPPORTED_OPERATION,
    "AUTH_DEVICE_CODE_ERROR": AUTH_FAILED,
    "AUTH_DECLINED": AUTH_FAILED,
    "AUTH_TOKEN_ERROR": AUTH_FAILED,
    "ACTOR_IDENTITY_MISMATCH": ACTOR_MISMATCH,
    "ACTOR_UNAUTHORIZED": ACTOR_MISMATCH,
    "GRAPH_ME_VALIDATION_FAILED": GRAPH_READ_FAILED,
    "LIVE_EXECUTION_DISABLED": POLICY_DENIED,
    "LIVE_CONFIGURATION_INVALID": POLICY_DENIED,
    "UNSUPPORTED_LIVE_ACTION": UNSUPPORTED_OPERATION,
    "ACTION_UNSUPPORTED": UNSUPPORTED_OPERATION,
}


class ScenarioEvidenceBoundaryError(ValueError):
    """Raised when runtime data cannot safely cross into evidence storage."""


@dataclass(frozen=True)
class ScenarioEvidenceRecord:
    """The only Scenario evidence shape accepted by persistence writers."""

    execution_id: str
    correlation_id: str
    scenario_id: str
    operation: str
    actor_id_hash: Optional[str]
    timestamp: str
    status: str
    error_code: Optional[str]
    object_count: int

    def __post_init__(self) -> None:
        for name in (
            "execution_id", "correlation_id", "scenario_id", "operation",
            "timestamp", "status",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ScenarioEvidenceBoundaryError("{0} must be a non-empty string".format(name))
        if self.actor_id_hash is not None and (
            not isinstance(self.actor_id_hash, str) or not self.actor_id_hash
        ):
            raise ScenarioEvidenceBoundaryError("actor_id_hash must be a non-empty string or None")
        if self.status not in EXECUTION_STATUSES:
            raise ScenarioEvidenceBoundaryError("status is not in the closed execution vocabulary")
        if self.error_code is not None and self.error_code not in EVIDENCE_ERROR_CODES:
            raise ScenarioEvidenceBoundaryError("error_code is not in the closed evidence vocabulary")
        if isinstance(self.object_count, bool) or not isinstance(self.object_count, int) or self.object_count < 0:
            raise ScenarioEvidenceBoundaryError("object_count must be a non-negative integer")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ScenarioEvidenceRecord":
        """Construct a record only from the exact allowlisted payload shape."""
        if not isinstance(payload, Mapping):
            raise TypeError("Scenario evidence payload must be a mapping")
        allowed = {item.name for item in fields(cls)}
        unknown = set(payload) - allowed
        missing = allowed - set(payload)
        if unknown or missing:
            raise ScenarioEvidenceBoundaryError(
                "Scenario evidence payload must contain exactly the allowlisted fields"
            )
        return cls(**dict(payload))

    def to_persistence_payload(self) -> Dict[str, Any]:
        """Return a fresh, fixed-shape payload for the persistence adapter."""
        return {
            "execution_id": self.execution_id,
            "correlation_id": self.correlation_id,
            "scenario_id": self.scenario_id,
            "operation": self.operation,
            "actor_id_hash": self.actor_id_hash,
            "timestamp": self.timestamp,
            "status": self.status,
            "error_code": self.error_code,
            "object_count": self.object_count,
        }


def _inspect_runtime_value(value: Any, field_name: Optional[str] = None) -> None:
    """Reject raw payloads and credential-shaped values before projection.

    Credential and free-text fields are intentionally excluded from evidence,
    while raw payloads and exceptions are never safe to silently accept.
    """
    normalized_name = field_name.lower() if isinstance(field_name, str) else None
    if normalized_name in _REJECTED_FIELDS:
        raise ScenarioEvidenceBoundaryError("{0} is forbidden in Scenario evidence".format(field_name))
    if normalized_name in _FORBIDDEN_FIELDS:
        return
    if isinstance(value, str):
        if _TOKEN_PATTERN.search(value):
            raise ScenarioEvidenceBoundaryError("credential-shaped value is forbidden in Scenario evidence")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _inspect_runtime_value(item, str(key))
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _inspect_runtime_value(item)
        return
    if is_dataclass(value):
        for item in fields(value):
            _inspect_runtime_value(getattr(value, item.name), item.name)


class ScenarioEvidenceBoundary:
    """Mandatory conversion from runtime execution results to persistence data."""

    @staticmethod
    def to_record(result: ScenarioExecutionResult) -> ScenarioEvidenceRecord:
        if type(result) is not ScenarioExecutionResult:
            raise TypeError("Scenario evidence boundary accepts ScenarioExecutionResult only")
        _inspect_runtime_value(result)
        # Detect dynamically attached runtime fields as well as dataclass fields.
        for name, value in vars(result).items():
            _inspect_runtime_value(value, name)

        step_results = result.step_results
        operation = step_results[0].action_type if step_results else "NONE"
        error_codes = [step.error_code for step in step_results if step.error_code is not None]
        if len(set(error_codes)) > 1:
            raise ScenarioEvidenceBoundaryError("multiple Scenario error classifications are not persistable")
        error_code = None
        if error_codes:
            error_code = _ERROR_CODE_MAP.get(error_codes[0])
            if error_code is None:
                raise ScenarioEvidenceBoundaryError("unknown Scenario error classification")
        actor_id_hash = None
        if result.actor_id is not None:
            actor_id_hash = sha256(result.actor_id.encode("utf-8")).hexdigest()
        timestamp = result.completed_at or result.started_at
        return ScenarioEvidenceRecord(
            execution_id=result.execution_id,
            correlation_id=result.correlation_id,
            scenario_id=result.scenario_id,
            operation=operation,
            actor_id_hash=actor_id_hash,
            timestamp=timestamp or "",
            status=result.status,
            error_code=error_code,
            object_count=len(step_results),
        )


class ScenarioEvidenceStorageAdapter(Protocol):
    """Storage contract for the fixed Scenario evidence schema only.

    This is intentionally a contract, not a database implementation.  Each
    field is named explicitly so callers cannot pass arbitrary payloads into
    Scenario evidence storage.
    """

    def persist(
        self,
        *,
        execution_id: str,
        correlation_id: str,
        scenario_id: str,
        operation: str,
        actor_id_hash: Optional[str],
        timestamp: str,
        status: str,
        error_code: Optional[str],
        object_count: int,
    ) -> None:
        """Persist one fixed-schema Scenario evidence record."""


class ScenarioEvidenceWriter:
    """Persistence boundary accepting only sanitized evidence records."""

    def __init__(self, storage_adapter: Optional[ScenarioEvidenceStorageAdapter] = None) -> None:
        self._storage_adapter = storage_adapter

    def write(self, record: ScenarioEvidenceRecord) -> Dict[str, Any]:
        if type(record) is not ScenarioEvidenceRecord:
            raise TypeError("ScenarioEvidenceWriter accepts ScenarioEvidenceRecord only")
        # Do not serialize the dataclass: this is the complete storage schema.
        payload = {
            "execution_id": record.execution_id,
            "correlation_id": record.correlation_id,
            "scenario_id": record.scenario_id,
            "operation": record.operation,
            "actor_id_hash": record.actor_id_hash,
            "timestamp": record.timestamp,
            "status": record.status,
            "error_code": record.error_code,
            "object_count": record.object_count,
        }
        if self._storage_adapter is not None:
            self._storage_adapter.persist(
                execution_id=record.execution_id,
                correlation_id=record.correlation_id,
                scenario_id=record.scenario_id,
                operation=record.operation,
                actor_id_hash=record.actor_id_hash,
                timestamp=record.timestamp,
                status=record.status,
                error_code=record.error_code,
                object_count=record.object_count,
            )
        return payload


__all__ = [
    "ACTOR_MISMATCH", "AUTH_FAILED", "AUTH_TIMEOUT", "EVIDENCE_ERROR_CODES",
    "GRAPH_READ_FAILED", "POLICY_DENIED", "ScenarioEvidenceBoundary",
    "ScenarioEvidenceBoundaryError", "ScenarioEvidenceRecord", "ScenarioEvidenceStorageAdapter",
    "ScenarioEvidenceWriter",
    "UNSUPPORTED_OPERATION",
]
