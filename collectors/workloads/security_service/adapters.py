"""Workload-specific adapters for G01-005..G01-017 security / governance /
service-health endpoints.

Each adapter function:

  * accepts a list of Graph record dicts and an optional lineage mapping;
  * returns one or more "row dictionaries" shaped exactly to the
    columns declared by ``database/migrations/004_core_security_governance_rbac.sql``
    and ``database/migrations/005_core_service_health_and_change.sql``;
  * preserves ``source_object_id`` (Graph ``id``) and propagates the
    supplied tenant + run lineage onto every produced row.

The adapters are grouped by their storage idiom:

  * **Event streams** (G01-005, G01-006, G01-014):
    append-only fact tables. Each Graph record becomes one row keyed
    by ``(tenant_id, source_object_id[, event_source])``. Event-source
    separation between G01-005 and G01-006 happens via the
    ``event_source`` discriminator (``DIRECTORY_AUDIT`` vs ``SIGN_IN``)
    on ``core.audit_event``; the event timestamp (``event_at``) is the
    Graph ``activityDateTime`` / ``createdDateTime`` value and is
    *distinct* from ``collected_at`` lineage.

  * **Current-state upserts** (G01-012, plus the current arm of
    G01-011, G01-013, G01-015, G01-016, G01-017): one row per Graph id
    keyed by ``(tenant_id, source_object_id)``.

  * **Snapshot rows** (G01-011, G01-013, G01-015): one row per Graph id
    per ``collection_run_id``, keyed by
    ``(tenant_id, source_object_id, collection_run_id)``.

  * **Versioned history** (G01-016, G01-017): one row per *new*
    ``version_identity`` per Graph id. The adapters emit history rows
    along with the current-state rows, but the persistence layer is
    responsible for the ``ON CONFLICT DO NOTHING`` dedup.

The adapters perform **no** database I/O and **no** Microsoft Graph
calls; they only project Graph records onto the curated column shapes.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .lineage import (
    DEFAULT_LINEAGE,
    Lineage,
    normalize_lineage,
)
from .versioning import compute_version_identity


# ---------------------------------------------------------------------------
# Constants / target-table map
# ---------------------------------------------------------------------------


EVENT_SOURCE_DIRECTORY_AUDIT = "DIRECTORY_AUDIT"
EVENT_SOURCE_SIGN_IN = "SIGN_IN"

# Table identities that downstream writers persist to. The values are the
# canonical ``schema.table`` strings used by the migration files. These
# are safe identifiers, not credentials.
ENDPOINT_TABLE_MAP: Dict[str, Mapping[str, Any]] = {
    "G01-005": {
        "endpoint_id": "G01-005",
        "endpoint_name": "Directory Audit Logs",
        "current_table": "core.audit_event",
        "history_table": None,
        "snapshot_table": None,
        "pattern": "EVENT_LOG",
        "event_source": EVENT_SOURCE_DIRECTORY_AUDIT,
    },
    "G01-006": {
        "endpoint_id": "G01-006",
        "endpoint_name": "Sign-in Logs",
        "current_table": "core.audit_event",
        "history_table": None,
        "snapshot_table": None,
        "pattern": "EVENT_LOG",
        "event_source": EVENT_SOURCE_SIGN_IN,
    },
    "G01-011": {
        "endpoint_id": "G01-011",
        "endpoint_name": "Conditional Access Policies",
        "current_table": "core.conditional_access_policy",
        "history_table": None,
        "snapshot_table": "core.conditional_access_policy_snapshot",
        "pattern": "HISTORICAL_WITH_SNAPSHOT",
    },
    "G01-012": {
        "endpoint_id": "G01-012",
        "endpoint_name": "Conditional Access Named Locations",
        "current_table": "core.named_location",
        "history_table": None,
        "snapshot_table": None,
        "pattern": "CURRENT_ONLY",
    },
    "G01-013": {
        "endpoint_id": "G01-013",
        "endpoint_name": "Risky Users",
        "current_table": "core.risky_user",
        "history_table": None,
        "snapshot_table": "core.risky_user_snapshot",
        "pattern": "HISTORICAL_WITH_SNAPSHOT",
    },
    "G01-014": {
        "endpoint_id": "G01-014",
        "endpoint_name": "Risk Detections",
        "current_table": "core.risk_detection",
        "history_table": None,
        "snapshot_table": None,
        "pattern": "EVENT_LOG",
    },
    "G01-015": {
        "endpoint_id": "G01-015",
        "endpoint_name": "Service Health Overview",
        "current_table": "core.service_health_overview",
        "history_table": None,
        "snapshot_table": "core.service_health_overview_snapshot",
        "pattern": "HISTORICAL_WITH_SNAPSHOT",
    },
    "G01-016": {
        "endpoint_id": "G01-016",
        "endpoint_name": "Service Health Issues",
        "current_table": "core.service_health_issue",
        "history_table": "core.service_health_issue_history",
        "snapshot_table": None,
        "pattern": "INCREMENTAL_HISTORICAL",
    },
    "G01-017": {
        "endpoint_id": "G01-017",
        "endpoint_name": "Service Update Messages",
        "current_table": "core.service_update_message",
        "history_table": "core.service_update_message_history",
        "snapshot_table": None,
        "pattern": "INCREMENTAL_HISTORICAL",
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping")
    if "id" not in record or record["id"] in (None, ""):
        raise ValueError("Graph record missing required 'id' field")
    return record


def _as_text(value: Any) -> Optional[str]:
    """Return ``value`` if it is a non-empty string, else ``None``."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return None


def _as_text_or_number(value: Any) -> Optional[str]:
    """Render Graph scalar status codes without copying structured data."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    return _as_text(value)


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    return None


def _as_timestamp(value: Any) -> Optional[str]:
    """Return the Graph timestamp string verbatim if non-blank."""
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    return None


def _envelope(
    lineage: Lineage,
    *,
    source_object_id: str,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply common envelope fields to a produced row dict."""
    row: Dict[str, Any] = dict(extra or {})
    row["tenant_id"] = lineage.tenant_id
    row["source_object_id"] = source_object_id
    if lineage.collection_run_id is not None:
        row["collection_run_id"] = lineage.collection_run_id
    if lineage.endpoint_run_id is not None:
        row["endpoint_run_id"] = lineage.endpoint_run_id
    if lineage.collected_at is not None:
        row["collected_at"] = lineage.collected_at
    if lineage.retention_class is not None:
        row["retention_class"] = lineage.retention_class
    return row


# ---------------------------------------------------------------------------
# Event-stream adapters: G01-005 / G01-006 / G01-014
# ---------------------------------------------------------------------------


def adapt_directory_audit_logs(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-005 Directory Audit Logs -> ``core.audit_event`` rows.

    ``event_source`` is forced to ``DIRECTORY_AUDIT`` and
    ``event_at`` comes from ``activityDateTime``. ``collected_at`` is
    taken from the lineage envelope.
    """
    lineage = normalize_lineage(lineage)
    out: List[Dict[str, Any]] = []
    for raw in records:
        record = _require_record(raw)
        row = _envelope(
            lineage,
            source_object_id=str(record["id"]),
            extra={
                "event_source": EVENT_SOURCE_DIRECTORY_AUDIT,
                "event_at": _as_timestamp(record.get("activityDateTime")),
                "activity": _as_text(record.get("activityDisplayName")),
                "category": _as_text(record.get("category")),
                "result": _as_text(record.get("result")),
                "actor_user_id": _as_text(record.get("loggedByService")),
            },
        )
        # G01-005 maps ``loggedByService`` into actor_user_id per the
        # catalog Notes ("actor references for audits"); other actor
        # fields stay null for these selected columns.
        if lineage.collected_at is not None:
            row["collected_at"] = lineage.collected_at
        out.append(row)
    return out


def adapt_sign_in_logs(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-006 Sign-in Logs -> ``core.audit_event`` rows.

    ``event_source`` is forced to ``SIGN_IN`` and ``event_at`` comes
    from ``createdDateTime``. ``collected_at`` is taken from the
    lineage envelope.
    """
    lineage = normalize_lineage(lineage)
    out: List[Dict[str, Any]] = []
    for raw in records:
        record = _require_record(raw)
        status = record.get("status") if isinstance(record.get("status"), Mapping) else None
        row = _envelope(
            lineage,
            source_object_id=str(record["id"]),
            extra={
                "event_source": EVENT_SOURCE_SIGN_IN,
                "event_at": _as_timestamp(record.get("createdDateTime")),
                "actor_user_id": _as_text(record.get("userId")),
                "actor_app_id": _as_text(record.get("appId")),
                "activity": _as_text(record.get("clientAppUsed")),
                "category": _as_text_or_number(
                    (status or {}).get("errorCode") if status else None
                ),
                "result": _as_text(
                    (status or {}).get("failureReason") if status else None
                )
                or _as_text((status or {}).get("additionalDetails") if status else None),
                "is_interactive": _as_bool(record.get("isInteractive")),
            },
        )
        if lineage.collected_at is not None:
            row["collected_at"] = lineage.collected_at
        out.append(row)
    return out


def adapt_risk_detections(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-014 Risk Detections -> ``core.risk_detection`` rows.

    Append-only. ``detected_at`` is the Graph ``detectedDateTime``;
    ``activity_at`` is the Graph ``activityDateTime``; ``collected_at``
    comes from lineage.
    """
    lineage = normalize_lineage(lineage)
    out: List[Dict[str, Any]] = []
    for raw in records:
        record = _require_record(raw)
        row = _envelope(
            lineage,
            source_object_id=str(record["id"]),
            extra={
                "detected_at": _as_timestamp(record.get("detectedDateTime")),
                "activity_at": _as_timestamp(record.get("activityDateTime")),
                "risk_event_type": _as_text(record.get("riskEventType")),
                "risk_level": _as_text(record.get("riskLevel")),
                "risk_state": _as_text(record.get("riskState")),
                "risk_detail": _as_text(record.get("riskDetail")),
                "detection_timing_type": _as_text(record.get("detectionTimingType")),
                "activity": _as_text(record.get("activity")),
            },
        )
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Current-state + snapshot adapters: G01-011 / G01-013 / G01-015
# ---------------------------------------------------------------------------


def _adapt_conditional_access(
    records: Sequence[Mapping[str, Any]],
    lineage: Lineage,
) -> List[Dict[str, Any]]:
    """G01-011 Conditional Access Policies -> current + snapshot rows.

    Curated fields include policy metadata and the minimum sanitized security
    evidence needed by Conditional Access rules. Policy targeting bodies are
    excluded; malformed evidence is marked incomplete rather than coerced.
    """
    out: List[Dict[str, Any]] = []
    for raw in records:
        record = _require_record(raw)
        source_object_id = str(record["id"])
        common = {
            "display_name": _as_text(record.get("displayName")),
            "state": _as_text(record.get("state")),
            "created_date_time": _as_timestamp(record.get("createdDateTime")),
            "modified_date_time": _as_timestamp(record.get("modifiedDateTime")),
        }
        conditions = record.get("conditions")
        client_app_types = conditions.get("clientAppTypes") if isinstance(conditions, Mapping) else None
        controls = record.get("grantControls")
        built_in_controls = controls.get("builtInControls") if isinstance(controls, Mapping) else [] if controls is None else None
        client_types_valid = isinstance(client_app_types, list) and all(isinstance(item, str) for item in client_app_types)
        controls_valid = isinstance(built_in_controls, list) and all(isinstance(item, str) for item in built_in_controls)
        common.update({
            "client_app_types": list(client_app_types) if client_types_valid else None,
            "grant_built_in_controls": list(built_in_controls) if controls_valid else None,
            "security_evidence_complete": client_types_valid and controls_valid,
        })
        current_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        current_row["last_observed_at"] = lineage.collected_at
        out.append(current_row)

        snapshot_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        snapshot_row["snapshot_at"] = lineage.collected_at
        snapshot_row.pop("last_observed_at", None)
        out.append(snapshot_row)
    return out


def conditional_access_policies(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-011 Conditional Access Policies -> current + snapshot rows."""
    return _adapt_conditional_access(list(records), normalize_lineage(lineage))


def risky_users(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-013 Risky Users -> current + snapshot rows.

    Curated fields per ``docs/data-catalog.md`` and migration 004:
    ``risk_level``, ``risk_state``, ``risk_detail``, ``is_deleted``,
    ``is_processing``, ``risk_last_updated_at``.
    """
    lineage = normalize_lineage(lineage)
    materialized: Sequence[Mapping[str, Any]] = list(records)
    rows: List[Dict[str, Any]] = []
    for raw in materialized:
        record = _require_record(raw)
        source_object_id = str(record["id"])
        common = {
            "risk_level": _as_text(record.get("riskLevel")),
            "risk_state": _as_text(record.get("riskState")),
            "risk_detail": _as_text(record.get("riskDetail")),
            "is_deleted": _as_bool(record.get("isDeleted")),
            "is_processing": _as_bool(record.get("isProcessing")),
            "risk_last_updated_at": _as_timestamp(record.get("riskLastUpdatedDateTime")),
        }
        current_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        current_row["last_observed_at"] = lineage.collected_at
        rows.append(current_row)
        snapshot_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        snapshot_row["snapshot_at"] = lineage.collected_at
        snapshot_row.pop("last_observed_at", None)
        rows.append(snapshot_row)
    return rows


def service_health_overview(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-015 Service Health Overview -> current + snapshot rows.

    Curated fields per migration 005: ``service``, ``status``.
    """
    lineage = normalize_lineage(lineage)
    materialized: Sequence[Mapping[str, Any]] = list(records)
    rows: List[Dict[str, Any]] = []
    for raw in materialized:
        record = _require_record(raw)
        source_object_id = str(record["id"])
        common = {
            "service": _as_text(record.get("service")),
            "status": _as_text(record.get("status")),
        }
        current_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        current_row["last_observed_at"] = lineage.collected_at
        rows.append(current_row)
        snapshot_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        snapshot_row["snapshot_at"] = lineage.collected_at
        snapshot_row.pop("last_observed_at", None)
        rows.append(snapshot_row)
    return rows


# ---------------------------------------------------------------------------
# Current-state only: G01-012
# ---------------------------------------------------------------------------


def named_locations(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-012 Named Locations -> current-state rows only.

    Curated fields per migration 003: ``display_name``,
    ``created_date_time``, ``modified_date_time``. Raw IP / country
    ranges are excluded.
    """
    lineage = normalize_lineage(lineage)
    out: List[Dict[str, Any]] = []
    for raw in records:
        record = _require_record(raw)
        row = _envelope(
            lineage,
            source_object_id=str(record["id"]),
            extra={
                "display_name": _as_text(record.get("displayName")),
                "created_date_time": _as_timestamp(record.get("createdDateTime")),
                "modified_date_time": _as_timestamp(record.get("modifiedDateTime")),
            },
        )
        row["last_observed_at"] = lineage.collected_at
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# INCREMENTAL + HISTORICAL: G01-016 / G01-017
# ---------------------------------------------------------------------------


def service_health_issues(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-016 Service Health Issues -> current + history rows.

    Each Graph record yields:

      * one current-state row for ``core.service_health_issue``;
      * one versioned history row for
        ``core.service_health_issue_history`` carrying the
        deterministic ``version_identity``.

    The ``observed_at`` and ``collected_at`` columns on the history
    row are populated from the lineage ``collected_at`` value, so the
    history timeline is reconstructed chronologically via
    ``(tenant_id, source_object_id, observed_at DESC)``.
    """
    lineage = normalize_lineage(lineage)
    out: List[Dict[str, Any]] = []
    for raw in records:
        record = _require_record(raw)
        source_object_id = str(record["id"])
        common = {
            "service": _as_text(record.get("service")),
            "status": _as_text(record.get("status")),
            "classification": _as_text(record.get("classification")),
            "start_date_time": _as_timestamp(record.get("startDateTime")),
            "end_date_time": _as_timestamp(record.get("endDateTime")),
            "last_modified_date_time": _as_timestamp(record.get("lastModifiedDateTime")),
            "is_resolved": _as_bool(record.get("isResolved")),
        }
        current_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        current_row["last_observed_at"] = lineage.collected_at
        out.append(current_row)

        history_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        history_row["observed_at"] = lineage.collected_at
        history_row["collected_at"] = lineage.collected_at
        history_row["version_identity"] = compute_version_identity(
            "G01-016",
            tenant_id=lineage.tenant_id,
            source_object_id=source_object_id,
            record=record,
        )
        out.append(history_row)
    return out


def service_update_messages(
    records: Iterable[Mapping[str, Any]],
    lineage: Any = None,
) -> List[Dict[str, Any]]:
    """G01-017 Service Update Messages -> current + history rows.

    Each Graph record yields:

      * one current-state row for ``core.service_update_message``;
      * one versioned history row for
        ``core.service_update_message_history`` carrying the
        deterministic ``version_identity``.

    ``services`` is the Graph ``services`` array; it is preserved
    verbatim (empty / null allowed).
    """
    lineage = normalize_lineage(lineage)
    out: List[Dict[str, Any]] = []
    for raw in records:
        record = _require_record(raw)
        source_object_id = str(record["id"])
        services = record.get("services")
        if services is not None and not isinstance(services, list):
            services = None
        common = {
            "category": _as_text(record.get("category")),
            "severity": _as_text(record.get("severity")),
            "start_date_time": _as_timestamp(record.get("startDateTime")),
            "end_date_time": _as_timestamp(record.get("endDateTime")),
            "last_modified_date_time": _as_timestamp(record.get("lastModifiedDateTime")),
            "is_major_change": _as_bool(record.get("isMajorChange")),
            "action_required_by_date_time": _as_timestamp(
                record.get("actionRequiredByDateTime")
            ),
            "services": services,
        }
        current_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        current_row["last_observed_at"] = lineage.collected_at
        out.append(current_row)

        history_row = _envelope(lineage, source_object_id=source_object_id, extra=common)
        history_row["observed_at"] = lineage.collected_at
        history_row["collected_at"] = lineage.collected_at
        history_row["version_identity"] = compute_version_identity(
            "G01-017",
            tenant_id=lineage.tenant_id,
            source_object_id=source_object_id,
            record=record,
        )
        out.append(history_row)
    return out


# ---------------------------------------------------------------------------
# Backwards-compatible ``adapt_*`` aliases.
# ---------------------------------------------------------------------------


adapt_directory_audit_logs = adapt_directory_audit_logs
adapt_sign_in_logs = adapt_sign_in_logs
adapt_risk_detections = adapt_risk_detections
adapt_risky_users = risky_users
adapt_named_locations = named_locations
adapt_service_health_overview = service_health_overview
adapt_service_health_issues = service_health_issues
adapt_service_update_messages = service_update_messages


__all__ = [
    "ENDPOINT_TABLE_MAP",
    "EVENT_SOURCE_DIRECTORY_AUDIT",
    "EVENT_SOURCE_SIGN_IN",
    "adapt_directory_audit_logs",
    "adapt_named_locations",
    "adapt_risk_detections",
    "adapt_risky_users",
    "adapt_service_health_issues",
    "adapt_service_health_overview",
    "adapt_service_update_messages",
    "adapt_sign_in_logs",
    "conditional_access_policies",
    "named_locations",
    "risky_users",
    "service_health_issues",
    "service_health_overview",
    "service_update_messages",
]
