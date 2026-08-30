"""Bounded sign-in log collection for the dedicated analytics projection."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

ENDPOINT_ID = "G01-006"
PATH = "/v1.0/auditLogs/signIns"
MAX_RECORDS = 1000


def _value(record: dict[str, Any], *keys: str) -> Any:
    value: Any = record
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def normalize(record: dict[str, Any], tenant_id: int, collected_at: Any = None) -> dict[str, Any]:
    location = record.get("location") or {}
    status = record.get("status") or {}
    conditional = record.get("conditionalAccessStatus")
    risk = record.get("riskLevelDuringSignIn")
    return {
        "tenant_id": tenant_id, "source_signin_id": record.get("id"),
        "user_principal_name": record.get("userPrincipalName"), "user_display_name": record.get("userDisplayName"),
        "app_display_name": record.get("appDisplayName"), "ip_address": record.get("ipAddress"),
        "location_city": location.get("city"), "location_country": location.get("countryOrRegion"),
        "signin_datetime": record.get("createdDateTime"), "status_error_code": status.get("errorCode"),
        "status_failure_reason": status.get("failureReason"), "is_interactive": record.get("isInteractive"),
        "client_app_used": record.get("clientAppUsed"), "conditional_access_status": conditional,
        "risk_level_during_signin": risk, "risk_state": record.get("riskState"),
        "collected_at": collected_at or datetime.now(timezone.utc), "retention_class": "SHORT",
    }


def collect(transport: Any, *, tenant_id: int, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    url = PATH + "?" + urlencode({"$filter": f"createdDateTime ge {cutoff}", "$top": 100})
    rows: list[dict[str, Any]] = []
    while url and len(rows) < MAX_RECORDS:
        payload = transport.get_json(url)
        page = payload.get("value", [])
        if not isinstance(page, list):
            raise ValueError("Graph sign-in response value must be a list")
        rows.extend(normalize(item, tenant_id, now) for item in page if isinstance(item, dict) and item.get("id"))
        url = payload.get("@odata.nextLink")
    return rows[:MAX_RECORDS]
