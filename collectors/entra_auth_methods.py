"""Collect Entra authentication method registration details."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from collectors.core.transport import GraphHttpError, GraphTransport

REQUIRED_PERMISSION = "UserAuthenticationMethod.Read.All"
PATH = "/v1.0/reports/authenticationMethods/userRegistrationDetails?$select=id,userDisplayName,isMfaRegistered,isMfaCapable,isPasswordlessCapable,methodsRegistered&$top=100"
BETA_PATH = "https://graph.microsoft.com/beta/reports/authenticationMethods/userRegistrationDetails?$select=id,userDisplayName,isMfaRegistered,isMfaCapable,isPasswordlessCapable,methodsRegistered&$top=100"
LOGGER = logging.getLogger(__name__)


def collect_and_persist_entra_auth_methods(*, tenant_id: int, transport: GraphTransport, connection: Any) -> dict:
    observed_at = datetime.now(timezone.utc)
    rows = []
    url = PATH
    try:
        payload = transport.get_json(url)
    except GraphHttpError as exc:
        LOGGER.error(
            "Entra auth methods Graph request failed: status=%s code=%s message=%s path=%s",
            exc.status, exc.code, exc.message, PATH.split("?")[0],
        )
        LOGGER.info("Retrying Entra auth methods report using beta endpoint")
        try:
            payload = transport.get_json(BETA_PATH)
            url = BETA_PATH
        except GraphHttpError as beta_exc:
            LOGGER.error(
                "Entra auth methods beta Graph request failed: status=%s code=%s message=%s path=%s",
                beta_exc.status, beta_exc.code, beta_exc.message, BETA_PATH.split("?")[0],
            )
            raise
    except Exception:
        LOGGER.exception("Unexpected Entra auth methods Graph request failure")
        raise

    while url:
        for user in payload.get("value", []):
            methods = user.get("methodsRegistered") or []
            rows.append((
                user.get("id"), tenant_id, user.get("userDisplayName"),
                bool(user.get("isMfaRegistered")), bool(user.get("isMfaCapable")),
                bool(user.get("isPasswordlessCapable")), ",".join(str(method) for method in methods),
                user.get("defaultMfaMethod"), observed_at,
            ))
        url = payload.get("@odata.nextLink")
        if url:
            try:
                payload = transport.get_json(url)
            except GraphHttpError as exc:
                LOGGER.error(
                    "Entra auth methods pagination failed: status=%s code=%s message=%s",
                    exc.status, exc.code, exc.message,
                )
                raise
            except Exception:
                LOGGER.exception("Unexpected Entra auth methods pagination failure")
                raise
    with connection.cursor() as cur:
        for row in rows:
            cur.execute("""
                INSERT INTO core.entra_auth_method
                (user_id, tenant_id, display_name, is_mfa_registered, is_mfa_capable,
                 is_passwordless_capable, methods_registered, default_mfa_method, observed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                  display_name=EXCLUDED.display_name, is_mfa_registered=EXCLUDED.is_mfa_registered,
                  is_mfa_capable=EXCLUDED.is_mfa_capable, is_passwordless_capable=EXCLUDED.is_passwordless_capable,
                  methods_registered=EXCLUDED.methods_registered, default_mfa_method=EXCLUDED.default_mfa_method,
                  observed_at=EXCLUDED.observed_at
            """, row)
    connection.commit()
    return {"users_fetched": len(rows), "observed_at": observed_at.isoformat()}
