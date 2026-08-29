"""G01-007 -- Applications -- CURRENT_ONLY upsert into ``core.application``.

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-007 SNAPSHOT CURRENT_ONLY, SENSITIVE)
- ``docs/database-schema-design.md`` Section 7.1
- ``database/migrations/003_core_directory_and_licensing.sql``

Schema column set:
    tenant_id, source_object_id, app_id, display_name, sign_in_audience,
    created_date_time, last_observed_at, retention_class

Security note:
- ``appId`` is a public-ish identifier (NOT a credential).
- Keys / credentials / password fields are NEVER retained.
"""
from __future__ import annotations

from typing import Any, Dict

from .common import (
    AdapterSpec,
    HISTORY_MODE_CURRENT_ONLY,
    _ensure_lineage,
    _get_text,
    _get_timestamp,
    _require_mapping,
    _wrap_current,
)


ENDPOINT_ID = "G01-007"
TARGET_TABLE = "core.application"
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_CURRENT_ONLY


@_wrap_current(ENDPOINT_ID, TARGET_TABLE, RETENTION_CLASS,
               description="Applications -- CURRENT_ONLY upsert")
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/applications`` record into a
    ``core.application`` row-shaped dict.

    The catalog explicitly excludes credential / key material:
    ``passwordCredentials``, ``keyCredentials``, ``publicClient``,
    ``web`` / ``spa`` redirect URI bodies, and ``requiredResourceAccess``
    payloads are NEVER copied into the row.
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
    row["app_id"] = _get_text(record, "appId")
    row["display_name"] = _get_text(record, "displayName")
    row["sign_in_audience"] = _get_text(record, "signInAudience")
    row["created_date_time"] = _get_timestamp(record, "createdDateTime")
    row["retention_class"] = RETENTION_CLASS
    return row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__