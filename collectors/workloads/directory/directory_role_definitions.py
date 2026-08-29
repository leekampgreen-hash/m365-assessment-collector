"""G01-018 -- Directory Role Definitions -- REFERENCE.

Emits a single reference row per Graph record into
``core.directory_role_definition``.

Authoritative sources:
- ``config/api_inventory.json`` (no ``$select`` exposed -- curated
  field set comes from the data catalog).
- ``docs/data-catalog.md`` (G01-018 REFERENCE CURRENT_ONLY, INTERNAL)
- ``docs/database-schema-design.md`` Section 7.6
- ``database/migrations/004_core_security_governance_rbac.sql``

Schema column set:
    tenant_id, source_object_id, display_name, description, is_built_in,
    last_observed_at, retention_class

Security note:
- Per the catalog, ``rolePermissions`` payloads are NEVER retained; only
  the curated reference fields are stored.
"""
from __future__ import annotations

from typing import Any, Dict

from .common import (
    AdapterSpec,
    HISTORY_MODE_REFERENCE,
    _ensure_lineage,
    _get_bool,
    _get_text,
    _require_mapping,
    _wrap_reference,
)


ENDPOINT_ID = "G01-018"
TARGET_TABLE = "core.directory_role_definition"
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_REFERENCE


@_wrap_reference(
    ENDPOINT_ID,
    TARGET_TABLE,
    RETENTION_CLASS,
    description="Directory Role Definitions -- REFERENCE upsert",
)
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/roleManagement/directory/roleDefinitions``
    record into a ``core.directory_role_definition`` row-shaped dict.

    The reference semantics are preserved: the row is stable, the
    retention class is ``REFERENCE``, and ``rolePermissions`` payloads
    are never copied in.
    """
    _require_mapping(record, ENDPOINT_ID)
    lineage, _ = _ensure_lineage(
        ENDPOINT_ID,
        record,
        tenant_id=tenant_id,
        collection_run_id=collection_run_id,
        endpoint_run_id=endpoint_run_id,
        observed_at=observed_at,
    )
    row: Dict[str, Any] = dict(lineage)
    row["display_name"] = _get_text(record, "displayName")
    row["description"] = _get_text(record, "description")
    row["is_built_in"] = _get_bool(record, "isBuiltIn")
    row["retention_class"] = RETENTION_CLASS
    return row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__