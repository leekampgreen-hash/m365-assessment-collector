"""G01-009 -- Devices -- CURRENT_ONLY upsert into ``core.device``.

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-009 SNAPSHOT CURRENT_ONLY, SENSITIVE)
- ``docs/database-schema-design.md`` Section 7.1
- ``database/migrations/003_core_directory_and_licensing.sql``

Schema column set:
    tenant_id, source_object_id, device_graph_id, account_enabled,
    operating_system, operating_system_version, trust_type,
    approximate_last_sign_in_date_time, last_observed_at,
    retention_class

Notes:
- ``approximateLastSignInDateTime`` is operational only; it is NOT a
  watermark and is NOT used for incremental filtering.
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


ENDPOINT_ID = "G01-009"
TARGET_TABLE = "core.device"
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_CURRENT_ONLY


@_wrap_current(ENDPOINT_ID, TARGET_TABLE, RETENTION_CLASS,
               description="Devices -- CURRENT_ONLY upsert")
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/devices`` record into a
    ``core.device`` row-shaped dict."""
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
    row["device_graph_id"] = _get_text(record, "deviceId")
    row["account_enabled"] = _get_bool(record, "accountEnabled")
    row["operating_system"] = _get_text(record, "operatingSystem")
    row["operating_system_version"] = _get_text(record, "operatingSystemVersion")
    row["trust_type"] = _get_text(record, "trustType")
    row["approximate_last_sign_in_date_time"] = _get_timestamp(
        record, "approximateLastSignInDateTime"
    )
    row["retention_class"] = RETENTION_CLASS
    return row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__