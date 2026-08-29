"""Database-agnostic persistence transaction primitives.

This package deliberately contains no database driver, connection factory, or
endpoint-specific SQL. Callers provide a DB-API-like connection at the edge.
"""
from .core import (
    BoundSqlExecutor,
    AuditBatchResult,
    CollectionWriter,
    PersistenceError,
    RecordWriter,
    dispatch_persistence,
    get_onedrive_audit_checkpoint,
    advance_onedrive_audit_checkpoint,
    persist_onedrive_high_value_audit_batch,
    persist_sharepoint_high_value_audit_batch,
    write_current_record,
    write_event_record,
    write_history_record,
    write_onedrive_high_value_audit_batch,
    write_reference_record,
    write_snapshot_record,
    write_users_with_assignments,
)
from .runtime import open_database_connection

__all__ = [
    "AuditBatchResult",
    "BoundSqlExecutor",
    "CollectionWriter",
    "PersistenceError",
    "RecordWriter",
    "dispatch_persistence",
    "get_onedrive_audit_checkpoint",
    "advance_onedrive_audit_checkpoint",
    "persist_onedrive_high_value_audit_batch",
    "persist_sharepoint_high_value_audit_batch",
    "write_current_record",
    "write_event_record",
    "write_history_record",
    "write_reference_record",
    "write_snapshot_record",
    "write_users_with_assignments",
    "open_database_connection",
]
