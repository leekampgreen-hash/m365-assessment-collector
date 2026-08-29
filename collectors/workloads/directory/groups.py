"""G01-002 -- Groups -- CURRENT_ONLY upsert into ``core."group"``.

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-002 SNAPSHOT CURRENT_ONLY)
- ``docs/database-schema-design.md`` Section 7.1
- ``database/migrations/003_core_directory_and_licensing.sql``

Schema column set:
    tenant_id, source_object_id, display_name, mail, mail_enabled,
    security_enabled, group_types, last_observed_at, retention_class
"""
from __future__ import annotations

from typing import Any, Dict, List

from .common import (
    AdapterSpec,
    HISTORY_MODE_CURRENT_ONLY,
    _ensure_lineage,
    _get_bool,
    _get_text,
    _require_mapping,
    _wrap_current,
)


ENDPOINT_ID = "G01-002"
TARGET_TABLE = 'core."group"'
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_CURRENT_ONLY


def _get_group_types(record: Any) -> List[str]:
    """Return ``groupTypes`` as a list of strings, or an empty list.

    The schema column is ``TEXT[]``. Graph returns either an array of
    strings or an empty array; the adapter preserves the array as-is
    when every element is a string, otherwise returns ``[]`` so the
    persisted column never contains non-string values.
    """
    if not isinstance(record, dict):
        return []
    raw = record.get("groupTypes")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
    return out


@_wrap_current(ENDPOINT_ID, TARGET_TABLE, RETENTION_CLASS,
               description="Groups -- CURRENT_ONLY upsert")
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/groups`` record into a
    ``core."group"`` row-shaped dict.

    Membership payloads (``members``) are explicitly excluded per the
    G03 catalog note; only the curated top-level fields are retained.
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
    row["mail"] = _get_text(record, "mail")
    row["mail_enabled"] = _get_bool(record, "mailEnabled")
    row["security_enabled"] = _get_bool(record, "securityEnabled")
    row["group_types"] = _get_group_types(record)
    row["retention_class"] = RETENTION_CLASS
    return row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__