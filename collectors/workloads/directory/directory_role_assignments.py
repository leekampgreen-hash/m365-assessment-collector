"""G01-019 -- Directory Role Assignments -- HISTORICAL_WITH_SNAPSHOT.

Emits TWO row-shaped dicts per Graph record:
  1. ``core.directory_role_assignment``           -- current-state row
  2. ``core.directory_role_assignment_snapshot``  -- per-run snapshot row

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-019 SNAPSHOT HISTORICAL_WITH_SNAPSHOT,
  HIGH_SENSITIVITY, LONG)
- ``docs/database-schema-design.md`` Section 7.6
- ``database/migrations/004_core_security_governance_rbac.sql``

Schema columns (current-state row):
    tenant_id, source_object_id, role_definition_id, principal_id,
    directory_scope_id, last_observed_at, retention_class

Schema columns (snapshot row):
    tenant_id, source_object_id, collection_run_id, endpoint_run_id,
    snapshot_at, role_definition_id, principal_id, directory_scope_id,
    retention_class

Security note:
- ``role_definition_id`` / ``principal_id`` / ``directory_scope_id``
  are stored as TEXT (soft Graph references). Per the schema comment
  no DB-level FK is enforced.
- No principal display data is retained.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from .common import (
    AdapterSpec,
    HISTORY_MODE_HISTORICAL_WITH_SNAPSHOT,
    _ensure_lineage,
    _get_text,
    _require_mapping,
    _wrap_snapshot,
)


ENDPOINT_ID = "G01-019"
TARGET_TABLE = "core.directory_role_assignment"
SNAPSHOT_TABLE = "core.directory_role_assignment_snapshot"
RETENTION_CLASS = "LONG"
HISTORY_MODE = HISTORY_MODE_HISTORICAL_WITH_SNAPSHOT


@_wrap_snapshot(
    ENDPOINT_ID,
    TARGET_TABLE,
    SNAPSHOT_TABLE,
    RETENTION_CLASS,
    description="Directory Role Assignments -- current + per-run snapshot",
)
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Normalise one Graph
    ``/v1.0/roleManagement/directory/roleAssignments`` record into a
    ``(current_row, snapshot_row)`` pair.

    The Graph ``$select`` covers only the three Graph-side reference
    ids. The schema adds nothing on top; the adapter copies those
    three ids plus lineage.
    """
    _require_mapping(record, ENDPOINT_ID)
    lineage, source_object_id = _ensure_lineage(
        ENDPOINT_ID,
        record,
        tenant_id=tenant_id,
        collection_run_id=collection_run_id,
        endpoint_run_id=endpoint_run_id,
        observed_at=observed_at,
    )

    role_definition_id = _get_text(record, "roleDefinitionId")
    principal_id = _get_text(record, "principalId")
    directory_scope_id = _get_text(record, "directoryScopeId")

    current_row: Dict[str, Any] = dict(lineage)
    current_row["role_definition_id"] = role_definition_id
    current_row["principal_id"] = principal_id
    current_row["directory_scope_id"] = directory_scope_id
    current_row["retention_class"] = RETENTION_CLASS

    snapshot_row: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "source_object_id": source_object_id,
        "collection_run_id": collection_run_id,
        "endpoint_run_id": endpoint_run_id,
        "snapshot_at": observed_at,
        "role_definition_id": role_definition_id,
        "principal_id": principal_id,
        "directory_scope_id": directory_scope_id,
        "retention_class": RETENTION_CLASS,
    }
    return current_row, snapshot_row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__