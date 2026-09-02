"""Feature flag checker."""
from __future__ import annotations

from collectors.persistence import open_database_connection


def is_feature_enabled(flag_name: str, tenant_id: int | None = None) -> bool:
    """Return whether a feature is enabled, failing open on lookup errors."""
    conn = None
    try:
        conn = open_database_connection()
        with conn.cursor() as cur:
            if tenant_id:
                cur.execute(
                    """
                    SELECT is_enabled FROM core.tenant_feature
                    WHERE tenant_id = %s AND flag_name = %s
                    """,
                    (tenant_id, flag_name),
                )
                row = cur.fetchone()
                if row is not None:
                    return bool(row[0])
            cur.execute(
                """
                SELECT is_enabled FROM core.feature_flag
                WHERE flag_name = %s
                """,
                (flag_name,),
            )
            row = cur.fetchone()
            return bool(row[0]) if row else True
    except Exception:
        return True
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
