"""Trusted tenant resolution shared by Collector and persistence boundaries."""
from __future__ import annotations

from typing import Any


class TrustedTenantResolutionError(RuntimeError):
    """Raised when the authenticated Entra tenant is not uniquely mapped."""


def resolve_trusted_tenant(config: Any, connection: Any) -> int:
    """Resolve the internal tenant only from the authenticated Entra tenant.

    A missing connection, missing mapping, disabled mapping, or ambiguous
    mapping fails closed. No tenant row is created or selected by position.
    """
    if connection is None:
        raise TrustedTenantResolutionError("trusted tenant database mapping is unavailable")
    cursor = connection.cursor()
    cursor.execute(
        "SELECT tenant_id FROM core.tenant "
        "WHERE entra_tenant_id = %s AND enabled = TRUE",
        (config.tenant_id,),
    )
    rows = cursor.fetchall()
    if len(rows) != 1 or not rows[0][0]:
        raise TrustedTenantResolutionError("trusted tenant mapping is missing or ambiguous")
    return rows[0][0]


__all__ = ["TrustedTenantResolutionError", "resolve_trusted_tenant"]
