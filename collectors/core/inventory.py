"""Inventory loader adapter.

The Discovery Agent's inventory lives at
``config/api_inventory.json`` as a JSON array of objects with the
following shape:

    {
      "id": "G01-001",
      "key": "users",
      "name": "Users",
      "workload": "Entra ID",
      "method": "GET",
      "path": "/v1.0/users",
      "auth": "application",
      "documented_permissions": ["User.Read.All"],
      "permission": "User.Read.All",
      "select": ["id", "..."],
      "top": 10,
      "pagination": true,
      "enabled": true
    }

This module is a thin adapter that converts each entry into an
``EndpointSpec`` and validates it defensively. It does NOT modify the
JSON file -- callers that want a different schema for G07 can supply
their own loader or extend this one.

Defensive validation:
- Required fields are present.
- ``select`` is a list of strings (or absent).
- ``top`` is an int or None.
- ``pagination`` is a bool.
- Unknown fields are tolerated but ignored.

Validation errors are collected and a single ``InventoryValidationError``
is raised describing every problem so callers can fix the config file
in one pass.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import (
    COLLECTION_PATTERN_PAGED,
    COLLECTION_PATTERN_SINGLE,
    COLLECTION_PATTERN_UNKNOWN,
    EndpointSpec,
    ENDPOINT_TYPES,
    ENDPOINT_TYPE_WORKLOAD,
)


REQUIRED_FIELDS = ("id", "name", "path")


class InventoryValidationError(ValueError):
    """Raised when one or more endpoint entries fail validation."""


def _string_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if not isinstance(value, list):
        raise InventoryValidationError("select must be a list")
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise InventoryValidationError("select entries must be strings")
        out.append(item)
    return out


def _as_int(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise InventoryValidationError("{} must be int or null".format(field_name))
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise InventoryValidationError("{} must be int or null".format(field_name)) from exc
    raise InventoryValidationError("{} must be int or null".format(field_name))


def _as_bool(value: Any, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise InventoryValidationError("{} must be a bool".format(field_name))


def _documented_permissions(entry: Dict[str, Any]) -> List[str]:
    perms = entry.get("documented_permissions")
    if isinstance(perms, list) and perms:
        cleaned = [p for p in perms if isinstance(p, str) and p]
        if cleaned:
            return sorted(set(cleaned))
    single = entry.get("permission")
    if isinstance(single, str) and single:
        return [single]
    return []


def _collection_pattern(entry: Dict[str, Any]) -> str:
    pagination = entry.get("pagination")
    if isinstance(pagination, bool):
        return COLLECTION_PATTERN_PAGED if pagination else COLLECTION_PATTERN_SINGLE
    return COLLECTION_PATTERN_UNKNOWN


def entry_to_spec(entry: Dict[str, Any]) -> EndpointSpec:
    """Convert one raw JSON entry into an ``EndpointSpec``.

    Raises ``InventoryValidationError`` on invalid data.
    """
    if not isinstance(entry, dict):
        raise InventoryValidationError("entry is not an object")

    missing = [field for field in REQUIRED_FIELDS if not entry.get(field)]
    if missing:
        raise InventoryValidationError("entry missing required field(s): {}".format(", ".join(missing)))

    select = _string_list(entry.get("select"))
    top = _as_int(entry.get("top"), "top")
    pagination = _as_bool(entry.get("pagination"), "pagination", default=True)
    enabled = _as_bool(entry.get("enabled"), "enabled", default=True)

    method = entry.get("method") or "GET"
    if not isinstance(method, str):
        raise InventoryValidationError("method must be a string")

    auth = entry.get("auth") or "application"
    if not isinstance(auth, str):
        raise InventoryValidationError("auth must be a string")

    api_version = entry.get("api_version") or "v1.0"
    if not isinstance(api_version, str):
        raise InventoryValidationError("api_version must be a string")

    workload = entry.get("workload") or ""
    if not isinstance(workload, str):
        raise InventoryValidationError("workload must be a string")

    data_domain = entry.get("data_domain") or workload
    if not isinstance(data_domain, str):
        raise InventoryValidationError("data_domain must be a string")

    transport_type = entry.get("transport_type") or "NORMAL_GRAPH_JSON"
    if transport_type not in ("NORMAL_GRAPH_JSON", "USAGE_REPORT_CSV"):
        raise InventoryValidationError("transport_type must be NORMAL_GRAPH_JSON or USAGE_REPORT_CSV")
    report_key = entry.get("report_key")
    period = entry.get("period")
    required_capabilities = entry.get("required_capabilities", [])
    if not isinstance(required_capabilities, list) or not all(isinstance(value, str) and value for value in required_capabilities):
        raise InventoryValidationError("required_capabilities must be a list of non-empty strings")
    endpoint_type = entry.get("endpoint_type") or ENDPOINT_TYPE_WORKLOAD
    if endpoint_type not in ENDPOINT_TYPES:
        raise InventoryValidationError("endpoint_type must be WORKLOAD or SECURITY_ONLY")
    if transport_type == "USAGE_REPORT_CSV":
        if not isinstance(report_key, str) or not report_key:
            raise InventoryValidationError("usage report entry requires report_key")
        if period is not None and not isinstance(period, str):
            raise InventoryValidationError("period must be a string or null")

    spec = EndpointSpec(
        endpoint_id=entry["id"],
        name=entry["name"],
        path=entry["path"],
        api_version=api_version,
        workload=workload,
        method=method,
        collection_pattern=COLLECTION_PATTERN_PAGED if pagination else COLLECTION_PATTERN_SINGLE,
        pagination=pagination,
        select=select,
        top=top,
        permission=entry.get("permission") or "",
        documented_permissions=_documented_permissions(entry),
        data_domain=data_domain,
        enabled=enabled,
        auth_type=auth,
        transport_type=transport_type,
        report_key=report_key,
        period=period,
        required_capabilities=required_capabilities,
        endpoint_type=endpoint_type,
    )
    return spec


def load_inventory(path: Path) -> List[EndpointSpec]:
    """Load and validate an inventory file. All entries are returned,
    including those with ``enabled=False`` -- callers filter."""
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise InventoryValidationError("inventory root must be a JSON array")
    specs: List[EndpointSpec] = []
    for index, entry in enumerate(raw):
        try:
            specs.append(entry_to_spec(entry))
        except InventoryValidationError as exc:
            raise InventoryValidationError("entry #{}: {}".format(index, exc)) from exc
    return specs


def enabled_specs(specs: Iterable[EndpointSpec]) -> List[EndpointSpec]:
    return [spec for spec in specs if spec.enabled]
