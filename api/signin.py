from __future__ import annotations
from datetime import date
from typing import Any

class SigninSummaryService:
    def __init__(self, connection: Any, tenant_id: int):
        self.connection, self.tenant_id = connection, tenant_id

    def summary(self) -> dict[str, Any]:
        c = self.connection.cursor()
        c.execute("""SELECT count(*)::int, count(*) FILTER (WHERE COALESCE(status_error_code,0) <> 0)::int,
            count(*) FILTER (WHERE client_app_used ILIKE '%%legacy%%' OR client_app_used IN ('IMAP','POP','SMTP','Other'))::int
            FROM core.signin_log WHERE tenant_id=%s AND signin_datetime >= CURRENT_TIMESTAMP - INTERVAL '30 days'""", (self.tenant_id,))
        total, failed, legacy = c.fetchone()
        c.execute("SELECT status_failure_reason, count(*)::int FROM core.signin_log WHERE tenant_id=%s AND signin_datetime >= CURRENT_TIMESTAMP - INTERVAL '30 days' AND status_failure_reason IS NOT NULL GROUP BY status_failure_reason ORDER BY count(*) DESC LIMIT 10", (self.tenant_id,))
        reasons = [{"reason": r, "count": n} for r, n in c.fetchall()]
        c.execute("SELECT COALESCE(location_country,'Unknown'), count(*)::int FROM core.signin_log WHERE tenant_id=%s AND signin_datetime >= CURRENT_TIMESTAMP - INTERVAL '30 days' GROUP BY 1 ORDER BY 2 DESC", (self.tenant_id,))
        countries = [{"country": r, "count": n} for r, n in c.fetchall()]
        rate = round(failed * 100.0 / total, 2) if total else 0.0
        findings = []
        if rate > 20: findings.append({"finding": f"High sign-in failure rate ({rate}%) — possible attack", "risk": "HIGH"})
        if legacy: findings.append({"finding": f"Legacy authentication detected ({legacy} sign-ins)", "risk": "HIGH"})
        if len(countries) > 5: findings.append({"finding": f"Sign-ins from {len(countries)} countries — review for anomalies", "risk": "MEDIUM"})
        return {"period_days": 30, "total_signins": total, "failed_signins": failed, "failure_rate_pct": rate, "legacy_auth_signins": legacy, "top_failure_reasons": reasons, "signin_by_country": countries, "findings": findings}
