"""Small, offline-testable persistence boundary.

No production connection is created here. A caller injects a DB-API-like
connection and a record writer when endpoint persistence SQL is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol, Sequence
from uuid import uuid4

from collectors.core.runtime import NormalizedCollection
from collectors.core.errors import CLASSIFICATIONS
from collectors.workloads.models import NormalizedWorkloadRecord, PersistenceMode
from collectors.workloads.registry import REGISTRY


def _jsonb_parameter(value: Any) -> Any:
    """Wrap a structured value for psycopg 3 JSONB adaptation."""
    if value is None:
        return None
    try:
        from psycopg.types.json import Jsonb
    except ImportError:
        raise PersistenceError("PostgreSQL JSONB adaptation is unavailable") from None
    return Jsonb(value)


def _snapshot_parameters(record: NormalizedWorkloadRecord, columns: tuple[str, ...], row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(
        _jsonb_parameter(row[column]) if column == "service_plans" else row[column]
        for column in columns
    )


class Cursor(Protocol):
    """Minimal cursor surface needed for parameterized statements."""

    def execute(self, sql: str, parameters: Sequence[Any] | Mapping[str, Any]) -> Any:
        """Execute one statement using values bound by the driver."""


class Connection(Protocol):
    """Minimal transactional DB-API connection surface."""

    def cursor(self) -> Cursor:
        """Return a cursor for statement execution."""

    def commit(self) -> Any:
        """Commit the active transaction."""

    def rollback(self) -> Any:
        """Roll back the active transaction."""


class PersistenceError(ValueError):
    """Raised before an unsafe or incomplete SQL execution is attempted."""


class BoundSqlExecutor:
    """Execute SQL only when its parameter values are explicitly bound."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def execute(self, sql: str, parameters: Sequence[Any] | Mapping[str, Any] | None) -> Any:
        if parameters is None:
            raise PersistenceError("SQL execution requires bound parameters")
        return self._connection.cursor().execute(sql, parameters)


RecordWriter = Callable[[BoundSqlExecutor, NormalizedWorkloadRecord], None]


@dataclass(frozen=True)
class AuditBatchResult:
    attempted: int
    inserted: int
    duplicate_skips: int
    failure_classification: str | None = None


# These are a closed subset of the accepted G01 CURRENT tables.  Identifiers
# never originate from a normalized row, so records cannot select a table.
_CURRENT_ENDPOINTS: Mapping[str, tuple[str, tuple[str, ...], tuple[str, ...], str]] = {
    "G01-001": (
        'core."user"',
        (
            "tenant_id",
            "source_object_id",
            "user_principal_name",
            "display_name",
            "user_type",
            "account_enabled",
            "created_date_time",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "user_principal_name = EXCLUDED.user_principal_name, "
        "display_name = EXCLUDED.display_name, user_type = EXCLUDED.user_type, "
        "account_enabled = EXCLUDED.account_enabled, "
        "created_date_time = EXCLUDED.created_date_time, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
    "G01-002": (
        'core."group"',
        (
            "tenant_id",
            "source_object_id",
            "display_name",
            "mail",
            "mail_enabled",
            "security_enabled",
            "group_types",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "display_name = EXCLUDED.display_name, mail = EXCLUDED.mail, "
        "mail_enabled = EXCLUDED.mail_enabled, "
        "security_enabled = EXCLUDED.security_enabled, "
        "group_types = EXCLUDED.group_types, "
        "last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
    ),
    "G01-003": (
        "core.organization",
        (
            "tenant_id",
            "source_object_id",
            "display_name",
            "country_letter_code",
            "tenant_type",
            "verified_domains",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id",),
        "source_object_id = EXCLUDED.source_object_id, "
        "display_name = EXCLUDED.display_name, "
        "country_letter_code = EXCLUDED.country_letter_code, "
        "tenant_type = EXCLUDED.tenant_type, "
        "verified_domains = EXCLUDED.verified_domains, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
    "G01-007": (
        "core.application",
        (
            "tenant_id",
            "source_object_id",
            "app_id",
            "display_name",
            "sign_in_audience",
            "created_date_time",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "app_id = EXCLUDED.app_id, display_name = EXCLUDED.display_name, "
        "sign_in_audience = EXCLUDED.sign_in_audience, "
        "created_date_time = EXCLUDED.created_date_time, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
    "G01-008": (
        "core.service_principal",
        (
            "tenant_id",
            "source_object_id",
            "app_id",
            "display_name",
            "account_enabled",
            "service_principal_type",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "app_id = EXCLUDED.app_id, display_name = EXCLUDED.display_name, "
        "account_enabled = EXCLUDED.account_enabled, "
        "service_principal_type = EXCLUDED.service_principal_type, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
    "G01-009": (
        "core.device",
        (
            "tenant_id",
            "source_object_id",
            "device_graph_id",
            "account_enabled",
            "operating_system",
            "operating_system_version",
            "trust_type",
            "approximate_last_sign_in_date_time",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "device_graph_id = EXCLUDED.device_graph_id, "
        "account_enabled = EXCLUDED.account_enabled, "
        "operating_system = EXCLUDED.operating_system, "
        "operating_system_version = EXCLUDED.operating_system_version, "
        "trust_type = EXCLUDED.trust_type, "
        "approximate_last_sign_in_date_time = EXCLUDED.approximate_last_sign_in_date_time, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
    "G01-010": (
        "core.administrative_unit",
        (
            "tenant_id",
            "source_object_id",
            "display_name",
            "description",
            "visibility",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "display_name = EXCLUDED.display_name, "
        "description = EXCLUDED.description, "
        "visibility = EXCLUDED.visibility, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
    "G01-012": (
        "core.named_location",
        (
            "tenant_id",
            "source_object_id",
            "display_name",
            "created_date_time",
            "modified_date_time",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "display_name = EXCLUDED.display_name, "
        "created_date_time = EXCLUDED.created_date_time, "
        "modified_date_time = EXCLUDED.modified_date_time, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
}


def write_users_with_assignments(
    executor: BoundSqlExecutor,
    records: Sequence[NormalizedWorkloadRecord],
) -> None:
    """Replace one tenant's user-license set after user upserts succeed.

    The assignment property is optional in Graph responses. Missing property
    means the entitlement dependency is unavailable, so existing assignments
    are preserved rather than incorrectly cleared.
    """
    if not records:
        return
    tenant_ids = {record.current_row.get("tenant_id") for record in records if record.current_row}
    if len(tenant_ids) != 1:
        raise PersistenceError("Users assignment refresh requires one tenant")
    tenant_id = next(iter(tenant_ids))
    if not all(record.current_row and record.current_row.get("_assigned_licenses_available") for record in records):
        for record in records:
            write_current_record(executor, record)
        return
    executor.execute('DELETE FROM core.user_license_assignment WHERE tenant_id = %s', (tenant_id,))
    for record in records:
        write_current_record(executor, record)
        row = record.current_row or {}
        for sku_id in row.get("_assigned_licenses", ()): 
            executor.execute(
                "INSERT INTO core.user_license_assignment "
                "(tenant_id, user_id, sku_id, first_observed_at, last_observed_at) "
                "SELECT u.tenant_id, u.user_id, %s, %s, %s "
                "FROM core.\"user\" u "
                "JOIN core.subscribed_sku s ON s.tenant_id = u.tenant_id AND s.sku_id = %s "
                "WHERE u.tenant_id = %s AND u.source_object_id = %s "
                "ON CONFLICT (tenant_id, user_id, sku_id) DO UPDATE SET "
                "last_observed_at = EXCLUDED.last_observed_at",
                (sku_id, row["last_observed_at"], row["last_observed_at"], sku_id,
                 row["tenant_id"], row["source_object_id"]),
            )


# Closed accepted REFERENCE endpoint set. The normalized record cannot select
# a target table and only the destination DDL columns are bound.
_REFERENCE_ENDPOINTS: Mapping[str, tuple[str, tuple[str, ...], tuple[str, ...], str]] = {
    "G01-018": (
        "core.directory_role_definition",
        (
            "tenant_id",
            "source_object_id",
            "display_name",
            "description",
            "is_built_in",
            "last_observed_at",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
        "display_name = EXCLUDED.display_name, description = EXCLUDED.description, "
        "is_built_in = EXCLUDED.is_built_in, "
        "last_observed_at = EXCLUDED.last_observed_at, "
        "retention_class = EXCLUDED.retention_class",
    ),
}


# Accepted EVENT endpoints. G01-005 and G01-006 share core.audit_event; the
# event_source discriminator keeps their conflict targets disjoint. G01-014
# uses its dedicated core.risk_detection event table.
_AUDIT_EVENT_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "event_source",
    "source_object_id",
    "event_at",
    "collected_at",
    "collection_run_id",
    "endpoint_run_id",
    "actor_user_id",
    "actor_app_id",
    "activity",
    "category",
    "result",
    "is_interactive",
    "risk_level",
    "extension",
    "retention_class",
)
_AUDIT_EVENT_CONFLICT: tuple[str, ...] = ("tenant_id", "event_source", "source_object_id")

_ONEDRIVE_AUDIT_COLUMNS: tuple[str, ...] = (
    "tenant_id", "audit_record_id", "event_time", "operation", "workload",
    "event_category", "external_flag", "anonymous_flag", "collected_at",
    "client_ip", "object_id", "site_url", "source_relative_url", "source_file_name",
    "unique_sharing_id", "target_user_or_group_name", "target_user_or_group_type",
    "collection_run_id", "endpoint_run_id", "retention_class",
)
_ONEDRIVE_AUDIT_REQUIRED: tuple[str, ...] = (
    "tenant_id", "audit_record_id", "event_time", "operation", "workload",
    "event_category", "external_flag", "anonymous_flag", "collected_at",
)
_ONEDRIVE_AUDIT_OPERATIONS = {"AnonymousLinkCreated", "SharingInvitationCreated", "SharingSet", "FileMalwareDetected"}


def _validate_onedrive_audit_row(row: Mapping[str, Any], trusted_tenant_id: int | None) -> None:
    missing = tuple(column for column in _ONEDRIVE_AUDIT_REQUIRED if column not in row)
    if missing:
        raise PersistenceError("OneDrive audit row is missing required columns: {}".format(", ".join(missing)))
    tenant_id = row["tenant_id"]
    if isinstance(tenant_id, bool) or not isinstance(tenant_id, int) or tenant_id <= 0:
        raise PersistenceError("OneDrive audit row tenant_id is missing or malformed")
    if trusted_tenant_id is not None and tenant_id != trusted_tenant_id:
        raise PersistenceError("OneDrive audit row tenant_id does not match trusted tenant_id")
    if row["workload"] != "OneDrive":
        raise PersistenceError("OneDrive audit row workload is not OneDrive")
    operation = row["operation"]
    if operation not in _ONEDRIVE_AUDIT_OPERATIONS:
        raise PersistenceError("OneDrive audit operation is outside the locked filter contract")
    for field in ("event_time", "collected_at"):
        value = row[field]
        if isinstance(value, datetime):
            continue
        if not isinstance(value, str):
            raise PersistenceError("OneDrive audit {} is missing or malformed".format(field))
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise PersistenceError("OneDrive audit {} is missing or malformed".format(field)) from None
    if operation == "AnonymousLinkCreated":
        expected = ("EXTERNAL_SHARING", True, True)
    elif operation == "FileMalwareDetected":
        expected = ("MALWARE_DETECTED", False, False)
    else:
        if row.get("target_user_or_group_type") != "Guest":
            raise PersistenceError("OneDrive audit sharing target is not proven Guest")
        expected = ("EXTERNAL_SHARING", True, False)
    if (row["event_category"], row["external_flag"], row["anonymous_flag"]) != expected:
        raise PersistenceError("OneDrive audit classification does not match the locked filter contract")


def persist_onedrive_high_value_audit_batch(
    connection: Connection,
    rows: Sequence[Mapping[str, Any]],
    *,
    trusted_tenant_id: int,
) -> AuditBatchResult:
    try:
        connection.cursor().execute("BEGIN", ())
        result = write_onedrive_high_value_audit_batch(
            BoundSqlExecutor(connection), rows, trusted_tenant_id=trusted_tenant_id
        )
        connection.commit()
        return result
    except PersistenceError:
        connection.rollback()
        raise
    except Exception as exc:
        connection.rollback()
        raise PersistenceError("OneDrive audit batch failed: PERSISTENCE_ERROR") from exc


def write_onedrive_high_value_audit_batch(
    executor: BoundSqlExecutor,
    rows: Sequence[Mapping[str, Any]],
    *,
    trusted_tenant_id: int | None = None,
) -> AuditBatchResult:
    for row in rows:
        _validate_onedrive_audit_row(row, trusted_tenant_id)
    sql = "INSERT INTO core.onedrive_high_value_audit_event ({}) VALUES ({}) ON CONFLICT (tenant_id, audit_record_id) DO NOTHING".format(
        ", ".join(_ONEDRIVE_AUDIT_COLUMNS), ", ".join("%s" for _ in _ONEDRIVE_AUDIT_COLUMNS)
    )
    inserted = 0
    for row in rows:
        cursor = executor.execute(sql, tuple(row.get(column) for column in _ONEDRIVE_AUDIT_COLUMNS))
        inserted += int(getattr(cursor, "rowcount", 0) == 1)
    return AuditBatchResult(
        attempted=len(rows),
        inserted=inserted,
        duplicate_skips=len(rows) - inserted,
    )


# Accepted EVENT endpoints. G01-005 and G01-006 share core.audit_event; the
_EVENT_ENDPOINTS: Mapping[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "G01-005": (
        "core.audit_event",
        _AUDIT_EVENT_COLUMNS,
        _AUDIT_EVENT_CONFLICT,
    ),
    "G01-006": (
        "core.audit_event",
        _AUDIT_EVENT_COLUMNS,
        _AUDIT_EVENT_CONFLICT,
    ),
    "G01-014": (
        "core.risk_detection",
        (
            "tenant_id",
            "source_object_id",
            "detected_at",
            "activity_at",
            "collected_at",
            "collection_run_id",
            "endpoint_run_id",
            "risk_event_type",
            "risk_level",
            "risk_state",
            "risk_detail",
            "detection_timing_type",
            "activity",
            "affected_user_id",
            "retention_class",
        ),
        ("tenant_id", "source_object_id"),
    ),
}

_G01_016_CURRENT_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "source_object_id",
    "service",
    "status",
    "classification",
    "start_date_time",
    "end_date_time",
    "last_modified_date_time",
    "is_resolved",
    "last_observed_at",
    "retention_class",
)
_G01_016_CURRENT_CONFLICT: tuple[str, ...] = ("tenant_id", "source_object_id")
_G01_016_CURRENT_ASSIGNMENTS: str = (
    "service = EXCLUDED.service, status = EXCLUDED.status, "
    "classification = EXCLUDED.classification, start_date_time = EXCLUDED.start_date_time, "
    "end_date_time = EXCLUDED.end_date_time, "
    "last_modified_date_time = EXCLUDED.last_modified_date_time, "
    "is_resolved = EXCLUDED.is_resolved, last_observed_at = EXCLUDED.last_observed_at, "
    "retention_class = EXCLUDED.retention_class"
)
_G01_016_HISTORY_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "source_object_id",
    "version_identity",
    "service",
    "status",
    "classification",
    "start_date_time",
    "end_date_time",
    "last_modified_date_time",
    "is_resolved",
    "observed_at",
    "collected_at",
    "collection_run_id",
    "endpoint_run_id",
    "retention_class",
)
_G01_016_HISTORY_CONFLICT: tuple[str, ...] = ("tenant_id", "source_object_id", "version_identity")

_G01_017_CURRENT_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "source_object_id",
    "category",
    "severity",
    "start_date_time",
    "end_date_time",
    "last_modified_date_time",
    "is_major_change",
    "action_required_by_date_time",
    "services",
    "last_observed_at",
    "retention_class",
)
_G01_017_CURRENT_CONFLICT: tuple[str, ...] = ("tenant_id", "source_object_id")
_G01_017_CURRENT_ASSIGNMENTS: str = (
    "category = EXCLUDED.category, severity = EXCLUDED.severity, "
    "start_date_time = EXCLUDED.start_date_time, end_date_time = EXCLUDED.end_date_time, "
    "last_modified_date_time = EXCLUDED.last_modified_date_time, "
    "is_major_change = EXCLUDED.is_major_change, "
    "action_required_by_date_time = EXCLUDED.action_required_by_date_time, "
    "services = EXCLUDED.services, last_observed_at = EXCLUDED.last_observed_at, "
    "retention_class = EXCLUDED.retention_class"
)
_G01_017_HISTORY_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "source_object_id",
    "version_identity",
    "category",
    "severity",
    "start_date_time",
    "end_date_time",
    "last_modified_date_time",
    "is_major_change",
    "action_required_by_date_time",
    "services",
    "observed_at",
    "collected_at",
    "collection_run_id",
    "endpoint_run_id",
    "retention_class",
)
_G01_017_HISTORY_CONFLICT: tuple[str, ...] = ("tenant_id", "source_object_id", "version_identity")

_HISTORY_ENDPOINTS: Mapping[str, tuple[str, tuple[str, ...], tuple[str, ...], str, str, tuple[str, ...], tuple[str, ...]]] = {
    "G01-016": (
        "core.service_health_issue",
        _G01_016_CURRENT_COLUMNS,
        _G01_016_CURRENT_CONFLICT,
        _G01_016_CURRENT_ASSIGNMENTS,
        "core.service_health_issue_history",
        _G01_016_HISTORY_COLUMNS,
        _G01_016_HISTORY_CONFLICT,
    ),
    "G01-017": (
        "core.service_update_message",
        _G01_017_CURRENT_COLUMNS,
        _G01_017_CURRENT_CONFLICT,
        _G01_017_CURRENT_ASSIGNMENTS,
        "core.service_update_message_history",
        _G01_017_HISTORY_COLUMNS,
        _G01_017_HISTORY_CONFLICT,
    ),
}


_SNAPSHOT_ENDPOINTS: Mapping[str, tuple[str, tuple[str, ...], tuple[str, ...], str, tuple[str, ...], tuple[str, ...], str]] = {
    "G01-004": (
        "core.subscribed_sku_snapshot",
        ("tenant_id", "source_object_id", "collection_run_id", "endpoint_run_id", "snapshot_at", "consumed_units", "prepaid_units", "capability_status", "service_plans", "retention_class"),
        ("tenant_id", "source_object_id", "collection_run_id"),
        "core.subscribed_sku",
        ("tenant_id", "source_object_id", "sku_id", "sku_part_number", "capability_status", "consumed_units", "prepaid_units", "service_plans", "last_observed_at", "retention_class"),
        ("tenant_id", "source_object_id"),
        "sku_id = EXCLUDED.sku_id, sku_part_number = EXCLUDED.sku_part_number, capability_status = EXCLUDED.capability_status, consumed_units = EXCLUDED.consumed_units, prepaid_units = EXCLUDED.prepaid_units, service_plans = EXCLUDED.service_plans, last_observed_at = EXCLUDED.last_observed_at, retention_class = EXCLUDED.retention_class",
    ),
    "G01-011": ("core.conditional_access_policy_snapshot", ("tenant_id", "source_object_id", "collection_run_id", "endpoint_run_id", "snapshot_at", "display_name", "state", "created_date_time", "modified_date_time", "client_app_types", "grant_built_in_controls", "security_evidence_complete", "retention_class"), ("tenant_id", "source_object_id", "collection_run_id"), "core.conditional_access_policy", ("tenant_id", "source_object_id", "display_name", "state", "created_date_time", "modified_date_time", "client_app_types", "grant_built_in_controls", "security_evidence_complete", "last_observed_at", "retention_class"), ("tenant_id", "source_object_id"), "display_name = EXCLUDED.display_name, state = EXCLUDED.state, created_date_time = EXCLUDED.created_date_time, modified_date_time = EXCLUDED.modified_date_time, client_app_types = EXCLUDED.client_app_types, grant_built_in_controls = EXCLUDED.grant_built_in_controls, security_evidence_complete = EXCLUDED.security_evidence_complete, last_observed_at = EXCLUDED.last_observed_at, retention_class = EXCLUDED.retention_class"),
    "G01-013": ("core.risky_user_snapshot", ("tenant_id", "source_object_id", "collection_run_id", "endpoint_run_id", "snapshot_at", "risk_level", "risk_state", "risk_detail", "is_deleted", "is_processing", "risk_last_updated_at", "retention_class"), ("tenant_id", "source_object_id", "collection_run_id"), "core.risky_user", ("tenant_id", "source_object_id", "risk_level", "risk_state", "risk_detail", "is_deleted", "is_processing", "risk_last_updated_at", "last_observed_at", "retention_class"), ("tenant_id", "source_object_id"), "risk_level = EXCLUDED.risk_level, risk_state = EXCLUDED.risk_state, risk_detail = EXCLUDED.risk_detail, is_deleted = EXCLUDED.is_deleted, is_processing = EXCLUDED.is_processing, risk_last_updated_at = EXCLUDED.risk_last_updated_at, last_observed_at = EXCLUDED.last_observed_at, retention_class = EXCLUDED.retention_class"),
    "G01-015": ("core.service_health_overview_snapshot", ("tenant_id", "source_object_id", "collection_run_id", "endpoint_run_id", "snapshot_at", "service", "status", "retention_class"), ("tenant_id", "source_object_id", "collection_run_id"), "core.service_health_overview", ("tenant_id", "source_object_id", "service", "status", "last_observed_at", "retention_class"), ("tenant_id", "source_object_id"), "service = EXCLUDED.service, status = EXCLUDED.status, last_observed_at = EXCLUDED.last_observed_at, retention_class = EXCLUDED.retention_class"),
    "G01-019": ("core.directory_role_assignment_snapshot", ("tenant_id", "source_object_id", "collection_run_id", "endpoint_run_id", "snapshot_at", "role_definition_id", "principal_id", "directory_scope_id", "retention_class"), ("tenant_id", "source_object_id", "collection_run_id"), "core.directory_role_assignment", ("tenant_id", "source_object_id", "role_definition_id", "principal_id", "directory_scope_id", "last_observed_at", "retention_class"), ("tenant_id", "source_object_id"), "role_definition_id = EXCLUDED.role_definition_id, principal_id = EXCLUDED.principal_id, directory_scope_id = EXCLUDED.directory_scope_id, last_observed_at = EXCLUDED.last_observed_at, retention_class = EXCLUDED.retention_class"),
}


def _validate_record_tenants(record: NormalizedWorkloadRecord, trusted_tenant_id: int | None = None) -> None:
    for row in record.rows():
        record_tenant_id = row.get("tenant_id")
        if isinstance(record_tenant_id, bool) or not isinstance(record_tenant_id, int) or record_tenant_id <= 0:
            raise PersistenceError("Normalized record tenant_id is missing or malformed")
        if trusted_tenant_id is not None and record_tenant_id != trusted_tenant_id:
            raise PersistenceError("Normalized record tenant_id does not match trusted tenant_id")


def write_snapshot_record(executor: BoundSqlExecutor, record: NormalizedWorkloadRecord) -> None:
    if record.persistence_mode != PersistenceMode.CURRENT_WITH_SNAPSHOT:
        raise PersistenceError("Only CURRENT_WITH_SNAPSHOT records are supported")
    endpoint = _SNAPSHOT_ENDPOINTS.get(record.endpoint_id)
    if endpoint is None or record.current_row is None or record.snapshot_row is None:
        raise PersistenceError("Snapshot record is incomplete or unsupported")
    _validate_record_tenants(record)
    snapshot_table, snapshot_columns, snapshot_conflict, current_table, current_columns, current_conflict, assignments = endpoint
    for label, columns, row in (("current", current_columns, record.current_row), ("snapshot", snapshot_columns, record.snapshot_row)):
        missing = tuple(column for column in columns if column not in row)
        if missing:
            raise PersistenceError("{} row is missing required columns: {}".format(label.title(), ", ".join(missing)))
    current_sql = "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}".format(current_table, ", ".join(current_columns), ", ".join("%s" for _ in current_columns), ", ".join(current_conflict), assignments)
    snapshot_sql = "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING".format(snapshot_table, ", ".join(snapshot_columns), ", ".join("%s" for _ in snapshot_columns), ", ".join(snapshot_conflict))
    executor.execute(current_sql, _snapshot_parameters(record, current_columns, record.current_row))
    executor.execute(snapshot_sql, _snapshot_parameters(record, snapshot_columns, record.snapshot_row))


def write_current_record(executor: BoundSqlExecutor, record: NormalizedWorkloadRecord) -> None:
    """Write one supported G01 CURRENT row with a deterministic upsert."""
    if record.persistence_mode != PersistenceMode.CURRENT:
        raise PersistenceError("Only CURRENT records are supported")
    endpoint = _CURRENT_ENDPOINTS.get(record.endpoint_id)
    if endpoint is None:
        raise PersistenceError("Unsupported CURRENT endpoint: {}".format(record.endpoint_id))
    if record.current_row is None:
        raise PersistenceError("CURRENT record requires current_row")

    _validate_record_tenants(record)
    table, columns, conflict_columns, assignments = endpoint
    missing = tuple(column for column in columns if column not in record.current_row)
    if missing:
        raise PersistenceError("CURRENT row is missing required columns: {}".format(", ".join(missing)))
    placeholders = ", ".join("%s" for _ in columns)
    sql = (
        "INSERT INTO {} ({}) VALUES ({}) "
        "ON CONFLICT ({}) DO UPDATE SET {}"
    ).format(table, ", ".join(columns), placeholders, ", ".join(conflict_columns), assignments)
    executor.execute(sql, tuple(record.current_row[column] for column in columns))


def write_reference_record(executor: BoundSqlExecutor, record: NormalizedWorkloadRecord) -> None:
    """Write one supported G01 REFERENCE row with a deterministic upsert."""
    if record.persistence_mode != PersistenceMode.REFERENCE:
        raise PersistenceError("Only REFERENCE records are supported")
    endpoint = _REFERENCE_ENDPOINTS.get(record.endpoint_id)
    if endpoint is None:
        raise PersistenceError("Unsupported REFERENCE endpoint: {}".format(record.endpoint_id))
    if record.reference_row is None:
        raise PersistenceError("REFERENCE record requires reference_row")

    _validate_record_tenants(record)
    table, columns, conflict_columns, assignments = endpoint
    missing = tuple(column for column in columns if column not in record.reference_row)
    if missing:
        raise PersistenceError("REFERENCE row is missing required columns: {}".format(
            ", ".join(missing)
        ))
    placeholders = ", ".join("%s" for _ in columns)
    sql = (
        "INSERT INTO {} ({}) VALUES ({}) "
        "ON CONFLICT ({}) DO UPDATE SET {}"
    ).format(table, ", ".join(columns), placeholders, ", ".join(conflict_columns), assignments)
    executor.execute(sql, tuple(record.reference_row[column] for column in columns))


def write_event_record(executor: BoundSqlExecutor, record: NormalizedWorkloadRecord) -> None:
    """Append one supported G01 EVENT row with deterministic idempotency."""
    if record.persistence_mode != PersistenceMode.EVENT:
        raise PersistenceError("Only EVENT records are supported")
    endpoint = _EVENT_ENDPOINTS.get(record.endpoint_id)
    if endpoint is None:
        raise PersistenceError("Unsupported EVENT endpoint: {}".format(record.endpoint_id))
    if record.event_row is None:
        raise PersistenceError("EVENT record requires event_row")

    _validate_record_tenants(record)
    table, columns, conflict_columns = endpoint
    if "event_source" in columns:
        registered_source = REGISTRY[record.endpoint_id].event_source
        supplied_source = record.event_row.get("event_source")
        if registered_source is None:
            raise PersistenceError("EVENT endpoint has no registered event source: {}".format(record.endpoint_id))
        if supplied_source != registered_source:
            raise PersistenceError(
                "EVENT source does not match endpoint {}: expected {}, got {}".format(
                    record.endpoint_id, registered_source, supplied_source
                )
            )
    missing = tuple(column for column in columns if column not in record.event_row)
    if missing:
        raise PersistenceError("EVENT row is missing required columns: {}".format(
            ", ".join(missing)
        ))
    placeholders = ", ".join("%s" for _ in columns)
    sql = "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING".format(
        table, ", ".join(columns), placeholders, ", ".join(conflict_columns)
    )
    executor.execute(sql, tuple(record.event_row[column] for column in columns))


def write_history_record(executor: BoundSqlExecutor, record: NormalizedWorkloadRecord) -> None:
    if record.persistence_mode != PersistenceMode.CURRENT_WITH_HISTORY:
        raise PersistenceError("Only CURRENT_WITH_HISTORY records are supported")
    endpoint = _HISTORY_ENDPOINTS.get(record.endpoint_id)
    if endpoint is None:
        raise PersistenceError("Unsupported CURRENT_WITH_HISTORY endpoint: {}".format(record.endpoint_id))
    if record.current_row is None:
        raise PersistenceError("CURRENT_WITH_HISTORY record requires current_row")
    if record.history_row is None:
        raise PersistenceError("CURRENT_WITH_HISTORY record requires history_row")

    _validate_record_tenants(record)
    current_table, current_columns, current_conflict, current_assignments, history_table, history_columns, history_conflict = endpoint

    missing_current = tuple(column for column in current_columns if column not in record.current_row)
    if missing_current:
        raise PersistenceError("Current row is missing required columns: {}".format(", ".join(missing_current)))
    missing_history = tuple(column for column in history_columns if column not in record.history_row)
    if missing_history:
        raise PersistenceError("History row is missing required columns: {}".format(", ".join(missing_history)))

    distinct_columns = tuple(column for column in current_columns if column not in current_conflict)
    placeholders_current = ", ".join("%s" for _ in current_columns)
    if distinct_columns:
        old_tuple = ", ".join("{}.{}".format(current_table, col) for col in distinct_columns)
        new_tuple = ", ".join("EXCLUDED.{}".format(col) for col in distinct_columns)
        where_clause = " WHERE ({}) IS DISTINCT FROM ({})".format(old_tuple, new_tuple)
    else:
        where_clause = ""
    sql_current = (
        "INSERT INTO {} ({}) VALUES ({}) "
        "ON CONFLICT ({}) DO UPDATE SET {}{}"
    ).format(current_table, ", ".join(current_columns), placeholders_current, ", ".join(current_conflict), current_assignments, where_clause)
    executor.execute(sql_current, tuple(record.current_row[column] for column in current_columns))

    placeholders_history = ", ".join("%s" for _ in history_columns)
    sql_history = "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING".format(
        history_table, ", ".join(history_columns), placeholders_history, ", ".join(history_conflict)
    )
    executor.execute(sql_history, tuple(record.history_row[column] for column in history_columns))


def dispatch_persistence(
    executor: BoundSqlExecutor,
    endpoint_id: str,
    records: Sequence[NormalizedWorkloadRecord],
) -> None:
    entry = REGISTRY.get(endpoint_id)
    if entry is None:
        raise PersistenceError("Unknown endpoint: {}".format(endpoint_id))
    mode = entry.persistence_mode
    writers = {
        PersistenceMode.CURRENT: write_current_record,
        PersistenceMode.REFERENCE: write_reference_record,
        PersistenceMode.EVENT: write_event_record,
        PersistenceMode.CURRENT_WITH_SNAPSHOT: write_snapshot_record,
        PersistenceMode.CURRENT_WITH_HISTORY: write_history_record,
    }
    writer = writers.get(mode)
    if writer is None:
        raise PersistenceError("Unknown persistence mode for {}".format(endpoint_id))
    for record in records:
        _validate_record_dispatch(record, endpoint_id, mode)
    if endpoint_id == "G01-001":
        write_users_with_assignments(executor, records)
    else:
        for record in records:
            writer(executor, record)


def _validate_record_dispatch(
    record: NormalizedWorkloadRecord,
    endpoint_id: str,
    mode: PersistenceMode,
) -> None:
    if record.endpoint_id != endpoint_id:
        raise PersistenceError("Record endpoint does not match dispatch endpoint")
    if record.persistence_mode != mode:
        raise PersistenceError("Persistence mode does not match registry for {}".format(endpoint_id))


class CollectionWriter:
    """Persist one normalized collection within exactly one transaction.

    ``record_writer`` is intentionally injected: persistence-mode SQL belongs
    to later work, while this boundary owns transaction behavior now.
    """

    def __init__(self, connection: Connection, record_writer: RecordWriter | None = None) -> None:
        self._connection = connection
        self._record_writer = record_writer

    def begin_collection_run(self, *, tenant_id: int, endpoint_ids: Sequence[str]) -> int:
        """Create and commit the canonical control row for one runtime call."""
        if isinstance(tenant_id, bool) or not isinstance(tenant_id, int) or tenant_id <= 0:
            raise PersistenceError("Collection run tenant_id is missing or malformed")
        if not endpoint_ids:
            raise PersistenceError("Collection run requires at least one endpoint")
        now = datetime.now(timezone.utc)
        cursor = self._connection.cursor()
        cursor.execute(
            "INSERT INTO control.collection_run "
            "(run_uuid, tenant_id, started_at, status, trigger_source, "
            "collector_version, selected_endpoint_ids, endpoints_total) "
            "VALUES (%s, %s, %s, 'RUNNING', %s, %s, %s, %s) "
            "RETURNING collection_run_id",
            (uuid4(), tenant_id, now, "runtime", "collector", list(endpoint_ids), len(endpoint_ids)),
        )
        result = cursor.fetchone()
        collection_run_id = result[0] if result else None
        if isinstance(collection_run_id, bool) or not isinstance(collection_run_id, int) or collection_run_id <= 0:
            self._connection.rollback()
            raise PersistenceError("Collection run creation returned no valid collection_run_id")
        self._connection.commit()
        return collection_run_id

    def begin_endpoint_run(self, *, collection_run_id: int, tenant_id: int, spec: Any) -> int:
        """Create the database-owned lineage row for one endpoint attempt."""
        if not isinstance(collection_run_id, int) or collection_run_id <= 0:
            raise PersistenceError("Endpoint run collection_run_id is missing or malformed")
        if not isinstance(tenant_id, int) or tenant_id <= 0:
            raise PersistenceError("Endpoint run tenant_id is missing or malformed")
        now = datetime.now(timezone.utc)
        cursor = self._connection.cursor()
        cursor.execute(
            "INSERT INTO control.endpoint_run "
            "(collection_run_id, endpoint_id, endpoint_name, tenant_id, started_at, status) "
            "VALUES (%s, %s, %s, %s, %s, 'ERROR') RETURNING endpoint_run_id",
            (collection_run_id, spec.endpoint_id, spec.name, tenant_id, now),
        )
        result = cursor.fetchone()
        endpoint_run_id = result[0] if result else None
        if not isinstance(endpoint_run_id, int) or endpoint_run_id <= 0:
            self._connection.rollback()
            raise PersistenceError("Endpoint run creation returned no valid endpoint_run_id")
        self._connection.commit()
        return endpoint_run_id

    def complete_endpoint_run(self, *, endpoint_run_id: int, result: Any) -> None:
        """Persist the terminal endpoint result in its own control transaction."""
        status = "PASS" if result.status == "PASS" else "ERROR"
        allowed_classifications = set(CLASSIFICATIONS)
        classification = result.error_classification or "UNKNOWN"
        if classification not in allowed_classifications:
            raise PersistenceError("Unknown endpoint error classification")
        self._connection.cursor().execute(
            "UPDATE control.endpoint_run SET completed_at = %s, status = %s, "
            "pages = %s, rows = %s, http_status = %s, error_classification = %s, "
            "error_message_safe = %s, retry_count = %s, graph_error_code = %s "
            "WHERE endpoint_run_id = %s",
            (datetime.now(timezone.utc), status, result.pages, result.rows,
             result.http_status, classification,
             classification if status == "ERROR" else None,
             result.retry_count, result.graph_error_code, endpoint_run_id),
        )
        self._connection.commit()

    def complete_collection_run(self, *, collection_run_id: int, results: Sequence[Any]) -> None:
        """Set the collection terminal state after all selected endpoints finish."""
        failed = sum(result.status != "PASS" for result in results)
        passed = len(results) - failed
        status = "SUCCESS" if failed == 0 else ("PARTIAL_SUCCESS" if passed else "FAILED")
        self._connection.cursor().execute(
            "UPDATE control.collection_run SET completed_at = %s, status = %s, "
            "endpoints_passed = %s, endpoints_failed = %s, rows_total = %s, "
            "error_summary = %s WHERE collection_run_id = %s",
            (datetime.now(timezone.utc), status, passed, failed,
             sum(getattr(result, "rows", 0) for result in results),
             _jsonb_parameter(None if not failed else {"failed_endpoints": [
                 result.endpoint_id for result in results if result.status != "PASS"
             ]}), collection_run_id),
        )
        self._connection.commit()

    def recover_orphaned_collection_run(self, *, collection_run_id: int) -> None:
        """Close one legacy RUNNING collection without creating endpoint history.

        The status predicate makes recovery conditional and prevents rewriting a
        run that became terminal concurrently.
        """
        if isinstance(collection_run_id, bool) or not isinstance(collection_run_id, int) or collection_run_id <= 0:
            raise PersistenceError("Collection run recovery id is missing or malformed")
        cursor = self._connection.cursor()
        cursor.execute(
            "UPDATE control.collection_run SET completed_at = %s, status = 'FAILED', "
            "error_summary = %s WHERE collection_run_id = %s AND status = 'RUNNING'",
            (
                datetime.now(timezone.utc),
                _jsonb_parameter({"classification": "LEGACY_STALE_ORPHAN"}),
                collection_run_id,
            ),
        )
        if cursor.rowcount != 1:
            self._connection.rollback()
            raise PersistenceError("Collection run recovery did not update exactly one RUNNING row")
        self._connection.commit()

    def write(self, collection: NormalizedCollection) -> None:
        self._validate_tenant_boundary(collection)
        self._validate_dispatch_boundary(collection)
        try:
            self._begin()
            if collection.records:
                if self._record_writer is None:
                    raise PersistenceError("No record writer is configured")
                executor = BoundSqlExecutor(self._connection)
                if self._record_writer is dispatch_persistence:
                    dispatch_persistence(executor, collection.endpoint_id, collection.records)
                else:
                    for record in collection.records:
                        self._record_writer(executor, record)
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def write_usage_report(self, key: str, rows, *, tenant_id: int, complete: bool = True) -> None:
        """Persist a fully normalized usage report in one transaction."""
        from collectors.usage_reports.persistence import write_report_rows

        if isinstance(tenant_id, bool) or not isinstance(tenant_id, int) or tenant_id <= 0:
            raise PersistenceError("Collection trusted tenant_id is missing or malformed")
        for current, snapshot in rows:
            if current.get("tenant_id") != tenant_id or snapshot.get("tenant_id") != tenant_id:
                raise PersistenceError("Usage report record tenant does not match trusted tenant")
        try:
            self._begin()
            write_report_rows(BoundSqlExecutor(self._connection), key, rows, complete=complete)
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    @staticmethod
    def _validate_tenant_boundary(collection: NormalizedCollection) -> None:
        trusted_tenant_id = collection.tenant_id
        if isinstance(trusted_tenant_id, bool) or not isinstance(trusted_tenant_id, int) or trusted_tenant_id <= 0:
            raise PersistenceError("Collection trusted tenant_id is missing or malformed")

        for record in collection.records:
            _validate_record_tenants(record, trusted_tenant_id)

    @staticmethod
    def _validate_dispatch_boundary(collection: NormalizedCollection) -> None:
        entry = REGISTRY.get(collection.endpoint_id)
        if entry is None:
            raise PersistenceError("Unknown endpoint: {}".format(collection.endpoint_id))
        for record in collection.records:
            _validate_record_dispatch(record, collection.endpoint_id, entry.persistence_mode)

    def _begin(self) -> None:
        self._connection.cursor().execute("BEGIN", ())
