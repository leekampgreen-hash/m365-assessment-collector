"""G01-010 -- Administrative Units -- CURRENT_ONLY upsert into
``core.administrative_unit``.

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-010 SNAPSHOT CURRENT_ONLY, INTERNAL)
- ``docs/database-schema-design.md`` Section 7.1
- ``database/migrations/003_core_directory_and_licensing.sql``

Schema column set:
    tenant_id, source_object_id, display_name, description, visibility,
    last_observed_at, retention_class

Notes:
- The catalog notes that ``0`` rows at discovery is expected; the
  collector framework must handle empty results, and the adapter does
  not change that contract.
"""
from __future__ import annotations

from typing import Any, Dict

from .common import (
    AdapterSpec,
    HISTORY_MODE_CURRENT_ONLY,
    _ensure_lineage,
    _get_text,
    _require_mapping,
    _wrap_current,
)


ENDPOINT_ID = "G01-010"
TARGET_TABLE = "core.administrative_unit"
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_CURRENT_ONLY


@_wrap_current(ENDPOINT_ID, TARGET_TABLE, RETENTION_CLASS,
               description="Administrative Units -- CURRENT_ONLY upsert")
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/directory/administrativeUnits``
    record into a ``core.administrative_unit`` row-shaped dict."""
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
    row["visibility"] = _get_text(record, "visibility")
    row["retention_class"] = RETENTION_CLASS
    return row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__