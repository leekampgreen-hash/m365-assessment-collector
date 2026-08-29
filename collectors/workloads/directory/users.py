"""G01-001 -- Users -- CURRENT_ONLY upsert into ``core."user"``.

Authoritative sources:
- ``config/api_inventory.json`` -- Graph ``$select`` and endpoint path.
- ``docs/data-catalog.md`` -- G01-001 SNAPSHOT CURRENT_ONLY.
- ``docs/database-schema-design.md`` -- ``core."user"`` (Section 7.1).
- ``database/migrations/003_core_directory_and_licensing.sql`` -- DDL.

Schema column set (current-state row):
    tenant_id, source_object_id, user_principal_name, display_name,
    user_type, account_enabled, created_date_time, last_observed_at,
    retention_class, extension. ``assignedLicenses`` is retained only as
    an internal handoff to the canonical persistence writer.
"""
from __future__ import annotations

from typing import Any, Dict

from .common import (
    AdapterSpec,
    HISTORY_MODE_CURRENT_ONLY,
    _ensure_lineage,
    _get_bool,
    _get_text,
    _get_timestamp,
    _require_mapping,
    _wrap_current,
)


ENDPOINT_ID = "G01-001"
TARGET_TABLE = 'core."user"'
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_CURRENT_ONLY


@_wrap_current(ENDPOINT_ID, TARGET_TABLE, RETENTION_CLASS,
               description="Users -- CURRENT_ONLY upsert")
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/users`` record into a ``core."user"``
    row-shaped dict.

    Fields retained (per the accepted schema):
        source_object_id (Graph ``id``)
        user_principal_name (``userPrincipalName``)
        display_name (``displayName``)
        user_type (``userType``)
        account_enabled (``accountEnabled``)
        created_date_time (``createdDateTime``)
        last_observed_at (runtime-supplied observation timestamp)
        retention_class (``REFERENCE`` per G03)
    Fields the catalog explicitly excludes (e.g. ``mail``,
    ``businessPhones``, ``mobilePhone``, ``otherMails``, ``aboutMe``,
    free-text profile enrichment) are NOT retained; the adapter never
    copies unknown Graph fields into the row.
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
    row["user_principal_name"] = _get_text(record, "userPrincipalName")
    row["display_name"] = _get_text(record, "displayName")
    row["user_type"] = _get_text(record, "userType")
    row["account_enabled"] = _get_bool(record, "accountEnabled")
    row["created_date_time"] = _get_timestamp(record, "createdDateTime")
    assigned = record.get("assignedLicenses")
    row["_assigned_licenses_available"] = isinstance(assigned, list)
    row["_assigned_licenses"] = _license_ids(assigned) if isinstance(assigned, list) else None
    row["retention_class"] = RETENTION_CLASS
    return row


def _license_ids(value: list[Any]) -> list[str]:
    """Keep only immutable SKU ids from Graph assigned-license objects."""
    return sorted({item["skuId"] for item in value
                   if isinstance(item, dict) and isinstance(item.get("skuId"), str)})


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__
