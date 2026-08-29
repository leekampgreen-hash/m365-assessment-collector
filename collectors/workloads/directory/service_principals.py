"""G01-008 -- Service Principals -- CURRENT_ONLY upsert into
``core.service_principal``.

Authoritative sources:
- ``config/api_inventory.json``
- ``docs/data-catalog.md`` (G01-008 SNAPSHOT CURRENT_ONLY, SENSITIVE)
- ``docs/database-schema-design.md`` Section 7.1
- ``database/migrations/003_core_directory_and_licensing.sql``

Schema column set:
    tenant_id, source_object_id, app_id, display_name, account_enabled,
    service_principal_type, last_observed_at, retention_class

Security note:
- ``appId`` is the public app identifier (NOT a credential).
- ``appRoleAssignments``, ``oauth2PermissionGrants``, ``keyCredentials``,
  ``passwordCredentials`` and similar payloads are NEVER retained.
"""
from __future__ import annotations

from typing import Any, Dict

from .common import (
    AdapterSpec,
    HISTORY_MODE_CURRENT_ONLY,
    _ensure_lineage,
    _get_bool,
    _get_text,
    _require_mapping,
    _wrap_current,
)


ENDPOINT_ID = "G01-008"
TARGET_TABLE = "core.service_principal"
SNAPSHOT_TABLE = None
RETENTION_CLASS = "REFERENCE"
HISTORY_MODE = HISTORY_MODE_CURRENT_ONLY


@_wrap_current(ENDPOINT_ID, TARGET_TABLE, RETENTION_CLASS,
               description="Service Principals -- CURRENT_ONLY upsert")
def normalize(
    record: Any,
    *,
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Dict[str, Any]:
    """Normalise one Graph ``/v1.0/servicePrincipals`` record into a
    ``core.service_principal`` row-shaped dict.

    Permission / role-assignment payloads are explicitly excluded per
    the G03 catalog note.
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
    row["account_enabled"] = _get_bool(record, "accountEnabled")
    row["service_principal_type"] = _get_text(record, "servicePrincipalType")
    row["retention_class"] = RETENTION_CLASS
    return row


ADAPTER_SPEC: AdapterSpec = normalize.__adapter_spec__