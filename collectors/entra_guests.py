"""Collect Entra guest user inventory."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from collectors.core.transport import GraphTransport

REQUIRED_PERMISSION = "User.Read.All"
PATH = "/v1.0/users?$filter=userType%20eq%20%27Guest%27&$select=id,displayName,userPrincipalName,createdDateTime,signInActivity,assignedLicenses,accountEnabled&$top=100"


def collect_and_persist_entra_guests(*, tenant_id: int, transport: GraphTransport, connection: Any) -> dict:
    guests = []
    url = PATH
    observed_at = datetime.now(timezone.utc)
    while url:
        payload = transport.get_json(url)
        for user in payload.get("value", []):
            last_signin = (user.get("signInActivity") or {}).get("lastSignInDateTime")
            parsed = datetime.fromisoformat(last_signin.replace("Z", "+00:00")) if last_signin else None
            days = (observed_at - parsed).days if parsed else None
            guests.append((user.get("id"), tenant_id, user.get("displayName"), user.get("createdDateTime"), last_signin, user.get("accountEnabled"), bool(user.get("assignedLicenses")), observed_at))
        url = payload.get("@odata.nextLink")
    with connection.cursor() as cur:
        for row in guests:
            cur.execute("""
                INSERT INTO core.entra_guest
                (user_id, tenant_id, display_name, created_datetime, last_signin_datetime, account_enabled, has_license, observed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                  display_name=EXCLUDED.display_name, created_datetime=EXCLUDED.created_datetime,
                  last_signin_datetime=EXCLUDED.last_signin_datetime, account_enabled=EXCLUDED.account_enabled,
                  has_license=EXCLUDED.has_license, observed_at=EXCLUDED.observed_at
            """, row)
    connection.commit()
    return {"guests_fetched": len(guests), "observed_at": observed_at.isoformat()}
