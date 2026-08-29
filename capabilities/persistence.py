"""Read-only capability query service backed by subscribed SKU persistence."""
from __future__ import annotations

import json
from typing import Any

from .resolver import CapabilityResolver


class CapabilityQueryService:
    def __init__(self, subscribed_skus: list[dict[str, Any]]):
        self._resolver = CapabilityResolver(subscribed_skus)

    @classmethod
    def from_connection(cls, connection: Any, tenant_id: int) -> "CapabilityQueryService":
        cursor = connection.cursor()
        cursor.execute(
            "SELECT service_plans FROM core.subscribed_sku WHERE tenant_id = %s",
            (tenant_id,),
        )
        rows = cursor.fetchall()
        return cls([{"service_plans": _json_value(row[0])} for row in rows])

    def capabilities(self) -> list[dict[str, str]]:
        return [capability.to_dict() for capability in self._resolver.all()]


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value
