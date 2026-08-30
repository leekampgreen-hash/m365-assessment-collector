"""G01-004 -- Subscribed SKUs -- HISTORICAL_WITH_SNAPSHOT.

Emits TWO row-shaped dicts per Graph record:
  1. ``core.subscribed_sku``          -- current-state row
  2. ``core.subscribed_sku_snapshot`` -- per-run snapshot row

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-004 SNAPSHOT HISTORICAL_WITH_SNAPSHOT)
- ``docs/database-schema-design.md`` Section 7.2
- ``database/migrations/003_core_directory_and_licensing.sql``
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from .common import (
    AdapterSpec,
    HISTORY_MODE_HISTORICAL_WITH_SNAPSHOT,
    _ensure_lineage,
    _get_int,
    _get_json_value,
    _get_text,
    _get_timestamp,
    _require_mapping,
    _wrap_snapshot,
)


ENDPOINT_ID = "G01-004"
TARGET_TABLE = "core.subscribed_sku"
SNAPSHOT_TABLE = "core.subscribed_sku_snapshot"
RETENTION_CLASS = "STANDARD"
HISTORY_MODE = HISTORY_MODE_HISTORICAL_WITH_SNAPSHOT


@_wrap_snapshot(
    ENDPOINT_ID,
    TARGET_TABLE,
    SNAPSHOT_TABLE,
    RETENTION_CLASS,
    description="Subscribed SKUs -- current + per-run snapshot rows",
)
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Normalise one Graph ``/v1.0/subscribedSkus`` record into a
    ``(current_row, snapshot_row)`` pair.

    Current-state row carries the full curated column set plus
    ``last_observed_at``. The snapshot row carries the versioned
    fields and the lineage ids required by
    ``core.subscribed_sku_snapshot`` (per-run, dedup by
    ``(tenant_id, source_object_id, collection_run_id)``).

    The ``prepaid_units`` Graph field is an object
    (``{enabled: int, suspended: int, warning: int}``). The accepted
    schema column is a single ``INTEGER`` so the adapter sums the
    three sub-fields into a single total. When Graph omits the
    object the column stays ``NULL``.
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

    consumed_units = _get_int(record, "consumedUnits")
    prepaid_total = _prepaid_units_total(record.get("prepaidUnits"))
    capability_status = _get_text(record, "capabilityStatus")
    service_plans = _get_json_value(record, "servicePlans")
    sku_id = _get_text(record, "skuId")
    sku_part_number = _get_text(record, "skuPartNumber")
    next_lifecycle_datetime = _get_timestamp(record, "nextLifecycleDateTime")

    current_row: Dict[str, Any] = dict(lineage)
    current_row["sku_id"] = sku_id
    current_row["sku_part_number"] = sku_part_number
    current_row["capability_status"] = capability_status
    current_row["consumed_units"] = consumed_units
    current_row["prepaid_units"] = prepaid_total
    current_row["service_plans"] = service_plans
    current_row["next_lifecycle_datetime"] = next_lifecycle_datetime
    current_row["retention_class"] = RETENTION_CLASS

    snapshot_row: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "source_object_id": source_object_id,
        "collection_run_id": collection_run_id,
        "endpoint_run_id": endpoint_run_id,
        "snapshot_at": observed_at,
        "consumed_units": consumed_units,
        "prepaid_units": prepaid_total,
        "capability_status": capability_status,
        "service_plans": service_plans,
        "retention_class": RETENTION_CLASS,
    }
    return current_row, snapshot_row


def _prepaid_units_total(value: Any) -> int:
    """Sum Graph's ``prepaidUnits`` sub-fields into a single integer.

    Graph returns ``prepaidUnits`` as an object with
    ``enabled``, ``suspended``, ``warning`` integer fields. The schema
    column is a single ``INTEGER`` (total prepaid seat count), so the
    adapter sums the sub-fields. Non-dict input returns 0.
    """
    if not isinstance(value, dict):
        return 0
    total = 0
    seen = False
    for key in ("enabled", "suspended", "warning"):
        sub = value.get(key)
        if isinstance(sub, bool):
            continue
        if isinstance(sub, int):
            total += sub
            seen = True
    return total if seen else 0


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__