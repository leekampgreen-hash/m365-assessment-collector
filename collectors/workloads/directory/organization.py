"""G01-003 -- Organization -- CURRENT_ONLY upsert into
``core.organization``.

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-003 SNAPSHOT CURRENT_ONLY, single row)
- ``docs/database-schema-design.md`` Section 7.1
- ``database/migrations/003_core_directory_and_licensing.sql``

Schema column set:
    tenant_id, source_object_id, display_name, country_letter_code,
    tenant_type, verified_domains, last_observed_at, retention_class
"""
from __future__ import annotations

from typing import Any, Dict

from .common import (
    AdapterSpec,
    HISTORY_MODE_CURRENT_ONLY,
    _ensure_lineage,
    _get_json_value,
    _get_text,
    _require_mapping,
    _wrap_current,
)


ENDPOINT_ID = "G01-003"
TARGET_TABLE = "core.organization"
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_CURRENT_ONLY


@_wrap_current(ENDPOINT_ID, TARGET_TABLE, RETENTION_CLASS,
               description="Organization -- CURRENT_ONLY upsert")
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/organization`` record into a
    ``core.organization`` row-shaped dict.

    The Graph endpoint returns a single object; the adapter is robust
    to receiving either a single object (the typical case) or a
    mapping whose ``verifiedDomains`` is a list of mappings.
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
    row["country_letter_code"] = _get_text(record, "countryLetterCode")
    row["tenant_type"] = _get_text(record, "tenantType")
    row["verified_domains"] = _get_json_value(record, "verifiedDomains")
    row["retention_class"] = RETENTION_CLASS
    return row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__