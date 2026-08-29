"""G07-A -- Directory / Licensing / RBAC workload adapters.

Ten Graph endpoint adapters that produce normalised, schema-aligned
row-shaped dicts for the G06 database:

    G01-001  Users                              CURRENT_ONLY
    G01-002  Groups                             CURRENT_ONLY
    G01-003  Organization                       CURRENT_ONLY
    G01-004  Subscribed SKUs                    HISTORICAL_WITH_SNAPSHOT
    G01-007  Applications                       CURRENT_ONLY
    G01-008  Service Principals                 CURRENT_ONLY
    G01-009  Devices                            CURRENT_ONLY
    G01-010  Administrative Units               CURRENT_ONLY
    G01-018  Directory Role Definitions         REFERENCE
    G01-019  Directory Role Assignments         HISTORICAL_WITH_SNAPSHOT

Contract:
- The adapter layer does NOT call live Microsoft Graph.
- The adapter layer does NOT perform database writes.
- The adapter layer does NOT touch tokens, secrets, or Authorization
  headers.
- Each adapter module exposes:
    - ``ENDPOINT_ID``           (str)
    - ``TARGET_TABLE``          (str)
    - ``SNAPSHOT_TABLE``        (str or None)
    - ``HISTORY_MODE``          (str)
    - ``RETENTION_CLASS``       (str)
    - ``normalize(record, **lineage)`` (returns dict or tuple of dicts)
    - ``ADAPTER_SPEC``          (AdapterSpec -- frozen contract object)

Use ``get_adapter(endpoint_id)`` to look up the adapter module by
inventory id. ``iter_adapters()`` walks every adapter owned by G07-A in
deterministic order; the order matches the task scope ordering.
"""
from __future__ import annotations

from typing import Dict, Iterator, List

from .common import AdapterSpec  # noqa: F401  -- re-exported for downstream
from . import (
    administrative_units,
    applications,
    devices,
    directory_role_assignments,
    directory_role_definitions,
    groups,
    organization,
    service_principals,
    subscribed_skus,
    users,
)

__all__ = [
    "administrative_units",
    "applications",
    "devices",
    "directory_role_assignments",
    "directory_role_definitions",
    "groups",
    "organization",
    "service_principals",
    "subscribed_skus",
    "users",
    "ENDPOINT_IDS",
    "get_adapter",
    "iter_adapters",
    "AdapterSpec",
]


# The deterministic ordering matches the task scope; tests rely on it.
ADAPTER_MODULES = (
    users,
    groups,
    organization,
    subscribed_skus,
    applications,
    service_principals,
    devices,
    administrative_units,
    directory_role_definitions,
    directory_role_assignments,
)

ENDPOINT_IDS: List[str] = [m.ENDPOINT_ID for m in ADAPTER_MODULES]


def get_adapter(endpoint_id: str):
    """Return the adapter module for ``endpoint_id`` or ``None``."""
    for module in ADAPTER_MODULES:
        if module.ENDPOINT_ID == endpoint_id:
            return module
    return None


def iter_adapters() -> Iterator:
    """Yield adapter modules in deterministic order."""
    for module in ADAPTER_MODULES:
        yield module