"""Small standard-library HTTP boundary for Operations Analytics.

The handler is intentionally an adapter only: analytics calculations remain in
``OperationsAnalyticsQueryService`` and database access remains in the
Collector persistence runtime.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from analytics import OperationsAnalyticsQueryService
from api.security import SecurityFindingQueryService, validate_filters
from api.signin import SigninSummaryService
from api.auth import verify_api_key
from api.agent import handle_chat
from agent.orchestrator import RejectedInputError
from agent import config
from collectors.persistence import open_database_connection
from capabilities.persistence import CapabilityQueryService


BASE_PATH = "/api/operations"
VALID_INACTIVITY_WINDOWS = (30, 60, 90)
LICENSE_PRICES = {
    "SPB": 22.00,
    "AAD_PREMIUM_P2": 9.00,
    "POWER_BI_STANDARD": 10.00,
    "O365_BUSINESS_PREMIUM": 22.00,
    "ENTERPRISEPACK": 36.00,
    "ENTERPRISEPREMIUM": 57.00,
    "DESKLESSPACK": 4.00,
}


def _contains_status(value: Any, status: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_status(item, status) for item in value.values())
    if isinstance(value, list):
        return any(_contains_status(item, status) for item in value)
    return value == status


def _response(status: str, data: Any = None, *, quality: Any = None, limitations: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status, "as_of": date.today().isoformat()}
    if data is not None:
        payload["data"] = data
    if quality is not None:
        payload["data_quality"] = quality
    if limitations is not None:
        payload["limitations"] = limitations
    return payload


def _service_status(value: Any) -> str:
    return "DATA_DEPENDENCY_UNAVAILABLE" if _contains_status(value, "DATA_DEPENDENCY_UNAVAILABLE") else "READY"


def _aggregate_inactivity(candidates: list[dict[str, Any]], days: int) -> dict[str, int]:
    key = str(days)
    counts = {"inactive_users": 0, "active_users": 0, "unknown_users": 0, "multi_workload_inactive_users": 0}
    for candidate in candidates:
        state = candidate.get("inactivity_30_60_90", {}).get(key, "unknown")
        counts[state + "_users"] += 1
        if candidate.get("multi_workload_inactive"):
            counts["multi_workload_inactive_users"] += 1
    return counts


def _quality(service: OperationsAnalyticsQueryService) -> dict[str, Any]:
    built = service.build()
    return {
        "source_freshness_exposed": built["data_quality"]["source_freshness_exposed"],
        "missing_workload_data": built["data_quality"]["missing_workload_data"],
        "missing_entitlement_data": built["data_quality"]["missing_entitlement_data"],
        "partial_tenant_coverage": built["data_quality"]["partial_tenant_coverage"],
        "identity_joins": built["data_quality"]["identity_joins"],
    }


def _license_optimizer_report(connection: Any, tenant_id: int) -> dict[str, Any]:
    cursor = connection.cursor()
    cursor.execute("""
        SELECT u.user_id, u.display_name, u.user_principal_name, u.user_type,
               u.account_enabled, s.sku_part_number, oa.last_activity_date
        FROM core.user u
        JOIN core.user_license_assignment ula ON ula.tenant_id = u.tenant_id AND ula.user_id = u.user_id
        JOIN core.subscribed_sku s ON s.tenant_id = ula.tenant_id AND s.sku_id = ula.sku_id
        LEFT JOIN LATERAL (
            SELECT MAX(last_activity_date) AS last_activity_date
            FROM core.usage_office365_active_user
            WHERE tenant_id = u.tenant_id AND LOWER(entity_key) = LOWER(u.user_principal_name)
        ) oa ON TRUE
        WHERE u.tenant_id = %s
        ORDER BY u.user_id, s.sku_part_number
    """, (tenant_id,))
    users: dict[Any, dict[str, Any]] = {}
    for user_id, display_name, upn, user_type, enabled, sku, last_activity in cursor.fetchall():
        user = users.setdefault(user_id, {"user_id": user_id, "display_name": display_name,
            "user_principal_name": upn, "user_type": user_type, "account_enabled": enabled,
            "last_activity_date": last_activity, "licenses": []})
        user["licenses"].append(sku)
        if last_activity is not None:
            current = user.get("last_activity_date")
            if current is None or last_activity > current:
                user["last_activity_date"] = last_activity
    now = datetime.now(timezone.utc).date()
    categories = {key: 0 for key in ("inactive_licensed_user", "zero_usage_licensed_user", "over_licensed_user", "duplicate_license_user", "guest_with_license", "blocked_with_license")}
    recommendations = []
    for user in users.values():
        flags = []
        last = user["last_activity_date"]
        age = (now - last).days if last else None
        counts = {sku: user["licenses"].count(sku) for sku in set(user["licenses"])}
        def add(flag: str, confidence: str, detail: str) -> None:
            categories[flag] += 1
            flags.append({"flag": flag, "confidence": confidence, "detail": detail})
        if age is not None and age > 15:
            add("inactive_licensed_user", "medium", f"No sign-in activity in {age} days")
        if last is None:
            add("zero_usage_licensed_user", "medium", "No usage activity recorded")
        if len(user["licenses"]) > 1:
            add("over_licensed_user", "low", f"Assigned {len(user['licenses'])} licenses")
        if any(count > 1 for count in counts.values()):
            add("duplicate_license_user", "high", "The same license is assigned more than once")
        if str(user.get("user_type") or "").lower() == "guest":
            add("guest_with_license", "high", "Guest account has an assigned license")
        if user.get("account_enabled") is False:
            add("blocked_with_license", "high", "Blocked account has an assigned license")
        if flags:
            recommendations.append({"user_id": user["user_id"], "display_name": user["display_name"],
                "user_principal_name": user["user_principal_name"], "licenses": user["licenses"],
                "flags": flags, "recommended_action": "Review and consider license reclaim"})
    summary = {"total_users_with_license": len(users), "flagged_users": len(recommendations), "by_category": categories}
    try:
        recommendation_summary = _generate_license_recommendation(summary)
    except Exception:
        recommendation_summary = "A license optimization recommendation could not be generated at this time. Review the flagged users and category counts to identify reclaim and assignment cleanup opportunities."
    return {"summary": summary, "recommendation_summary": recommendation_summary, "recommendations": recommendations}


def _generate_license_recommendation(summary: dict[str, Any]) -> str:
    from openai import OpenAI

    prompt = f"""You are a Microsoft 365 licensing analyst. Write a general recommendation for this tenant in English using only the supplied aggregate data. Return exactly 2-3 concise sentences in plain text. Explain the most important license optimization priorities and practical next steps. Do not mention individual users, identifiers, or invent facts.

SUMMARY DATA:
{json.dumps(summary, separators=(",", ":"))}
"""
    client = OpenAI(
        api_key=config.KRYPTONLAB_API_KEY or config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
        timeout=45.0,
    )
    response = client.chat.completions.create(
        model=config.ANALYST_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
    )
    return (response.choices[0].message.content or "").strip()


def _license_parking(connection: Any, tenant_id: int) -> dict[str, Any]:
    cursor = connection.cursor()
    cursor.execute("""
        SELECT u.user_id, u.display_name, u.account_enabled, oa.last_activity_date,
               s.sku_part_number
        FROM core.user u
        JOIN core.user_license_assignment ula ON ula.tenant_id = u.tenant_id AND ula.user_id = u.user_id
        JOIN core.subscribed_sku s ON s.tenant_id = ula.tenant_id AND s.sku_id = ula.sku_id
        LEFT JOIN LATERAL (SELECT MAX(last_activity_date) AS last_activity_date FROM core.usage_office365_active_user WHERE tenant_id = u.tenant_id AND LOWER(entity_key) = LOWER(u.user_principal_name)) oa ON TRUE
        WHERE u.tenant_id = %s
        ORDER BY u.user_id
    """, (tenant_id,))
    users: dict[int, dict[str, Any]] = {}
    for user_id, display_name, enabled, last_activity, sku in cursor.fetchall():
        user = users.setdefault(user_id, {"display_name": display_name, "account_enabled": enabled, "last_activity_date": last_activity, "licenses": []})
        if sku not in user["licenses"]:
            user["licenses"].append(sku)
    def shaped(user: dict[str, Any]) -> dict[str, Any]:
        cost = round(sum(LICENSE_PRICES.get(sku, 0.0) for sku in user["licenses"]), 2)
        return {"display_name": user["display_name"], "licenses": user["licenses"], "monthly_cost_usd": cost}
    now = datetime.now(timezone.utc).date()
    categories = {}
    for days, key in ((90, "inactive_90d"), (60, "inactive_60d"), (30, "inactive_30d")):
        categories[key] = [shaped(user) for user in users.values() if user["account_enabled"] and (user["last_activity_date"] is None or user["last_activity_date"] < now - timedelta(days=days))]
        categories[key].sort(key=lambda item: item["monthly_cost_usd"], reverse=True)
    disabled = [shaped(user) for user in users.values() if not user["account_enabled"]]
    disabled.sort(key=lambda item: item["monthly_cost_usd"], reverse=True)
    cursor.execute("SELECT sku_part_number, prepaid_units, consumed_units FROM core.subscribed_sku WHERE tenant_id = %s AND prepaid_units > consumed_units", (tenant_id,))
    unassigned = []
    for sku, purchased, assigned in cursor.fetchall():
        count = purchased - assigned
        unassigned.append({"sku_part_number": sku, "purchased": purchased, "assigned": assigned, "unassigned_count": count, "monthly_waste_usd": round(count * LICENSE_PRICES.get(sku, 0.0), 2)})
    unassigned.sort(key=lambda item: item["monthly_waste_usd"], reverse=True)
    total_users = len(users)
    waste = disabled + categories["inactive_90d"] + unassigned
    total_monthly = round(sum(item["monthly_cost_usd"] for item in disabled + categories["inactive_90d"]) + sum(item["monthly_waste_usd"] for item in unassigned), 2)
    recommendations = []
    for label, items, action in (("disabled", disabled, "Reclaim licenses from disabled accounts."), ("inactive 90d", categories["inactive_90d"], "Review and reclaim licenses from users inactive 90+ days."), ("unassigned", unassigned, "Review and remove unassigned license capacity.")):
        saving = round(sum(item.get("monthly_cost_usd", item.get("monthly_waste_usd", 0.0)) for item in items), 2)
        if saving:
            recommendations.append({"priority": 1 if label == "disabled" else 2, "action": action, "potential_saving_monthly_usd": saving})
    recommendations.sort(key=lambda item: item["potential_saving_monthly_usd"], reverse=True)
    return {"summary": {"total_licensed_users": total_users, "total_waste_monthly_usd": total_monthly, "total_waste_annual_usd": round(total_monthly * 12, 2), "waste_categories": {"disabled_with_license": len(disabled), "inactive_90d_with_license": len(categories["inactive_90d"]), "inactive_60d_with_license": len(categories["inactive_60d"]), "inactive_30d_with_license": len(categories["inactive_30d"]), "unassigned_licenses": sum(item["unassigned_count"] for item in unassigned)}}, "disabled_accounts": disabled, "inactive_90d": categories["inactive_90d"], "inactive_60d": categories["inactive_60d"], "inactive_30d": categories["inactive_30d"], "unassigned_licenses": unassigned, "recommendations": recommendations}


class OperationsApiHandler(BaseHTTPRequestHandler):
    """Read-only Operations Analytics request handler."""

    service_factory: Callable[[], OperationsAnalyticsQueryService] | None = None
    security_service_factory: Callable[[], SecurityFindingQueryService] | None = None
    capability_service_factory: Callable[[], CapabilityQueryService] | None = None
    connection_factory: Callable[[], Any] = staticmethod(open_database_connection)
    tenant_id: int | None = None

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _write(self, http_status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(http_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _load_service(self) -> OperationsAnalyticsQueryService:
        if self.service_factory is not None:
            return self.service_factory()
        if self.tenant_id is None:
            raise RuntimeError("analytics tenant configuration is unavailable")
        connection = self.connection_factory()
        try:
            return OperationsAnalyticsQueryService.from_connection(connection, self.tenant_id)
        finally:
            close = getattr(connection, "close", None)
            if close is not None:
                close()

    def _load_security_service(self) -> SecurityFindingQueryService:
        if self.security_service_factory is not None:
            return self.security_service_factory()
        if self.tenant_id is None:
            raise RuntimeError("security tenant configuration is unavailable")
        connection = self.connection_factory()
        self._security_connection = connection
        return SecurityFindingQueryService.from_connection(connection, self.tenant_id)

    def _load_capability_service(self) -> CapabilityQueryService:
        if self.capability_service_factory is not None:
            return self.capability_service_factory()
        if self.tenant_id is None:
            raise RuntimeError("capability tenant configuration is unavailable")
        connection = self.connection_factory()
        self._capability_connection = connection
        return CapabilityQueryService.from_connection(connection, self.tenant_id)

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path.rstrip("/") == "/api/agent/analyze/security":
            if not verify_api_key(self):
                self.send_response(401)
                self.send_header("WWW-Authenticate", "X-API-Key")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            try:
                from agent.analyst import generate_security_report
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                self._write(
                    200,
                    generate_security_report(
                        system_prompt=payload.get("system_prompt"),
                        choice=payload.get("choice", ""),
                        history=payload.get("history"),
                    ),
                )
            except Exception as exc:
                self._write(503, {"status": "ERROR", "error": str(exc)})
            return
        if parsed.path.rstrip("/") == "/api/agent/chat" and not verify_api_key(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "X-API-Key")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path.rstrip("/") != "/api/agent/chat":
            self._write(404, _response("NOT_FOUND"))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self._write(200, handle_chat(payload))
        except RejectedInputError:
            self._write(400, {"error": "Request not permitted.", "code": "REJECTED"})
        except ValueError as exc:
            self._write(400, {"error": str(exc)})
        except Exception as exc:
            self._write(503, {"error": str(exc)})

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path.rstrip("/")
        if path == "/api/scheduler/status":
            try:
                config_path = Path("config/scheduler.json")
                config = json.loads(config_path.read_text())
                now = datetime.now(timezone.utc)
                schedules = []
                for schedule in config.get("schedules", []):
                    interval = schedule.get("interval_hours", 24)
                    schedules.append({**schedule, "next_run": (now + timedelta(hours=interval)).isoformat()})
                self._write(200, {"status": "RUNNING", "schedules": schedules})
            except Exception:
                self._write(503, {"status": "UNAVAILABLE", "schedules": []})
            return
        if path == "/health":
            connection = None
            try:
                connection = self.connection_factory()
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                self._write(200, {"status": "READY", "database": "READY"})
            except Exception:
                self._write(503, {"status": "DATA_DEPENDENCY_UNAVAILABLE", "database": "UNAVAILABLE"})
            finally:
                close = getattr(connection, "close", None)
                if close is not None:
                    close()
            return
        if (path.startswith(BASE_PATH) or path.startswith("/api/security") or path.startswith("/api/license") or path == "/api/capabilities") and not verify_api_key(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "X-API-Key")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not path.startswith(BASE_PATH) and not path.startswith("/api/security") and not path.startswith("/api/license") and path != "/api/capabilities":
            self._write(404, _response("NOT_FOUND"))
            return
        try:
            if path == "/api/license/optimizer-report":
                connection = self.connection_factory()
                try:
                    self._write(200, _license_optimizer_report(connection, self.tenant_id))
                finally:
                    connection.close()
                return
            if path == "/api/license/parking-report":
                connection = self.connection_factory()
                try:
                    self._write(200, _response("READY", _license_parking(connection, self.tenant_id)))
                finally:
                    connection.close()
                return
            if path.startswith("/api/security"):
                try:
                    if path == "/api/security/summary":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.summary()))
                        return
                    if path == "/api/security/findings":
                        values = parse_qs(parsed.query, keep_blank_values=True)
                        status = values.get("status", [None])
                        severity = values.get("severity", [None])
                        if len(status) != 1 or len(severity) != 1:
                            self._write(400, _response("INVALID_FILTER"))
                            return
                        error = validate_filters(status[0], severity[0])
                        if error:
                            self._write(400, _response(error))
                            return
                        service = self._load_security_service()
                        self._write(200, _response("READY", {"findings": service.findings(status=status[0], severity=severity[0])}))
                        return
                    if path == "/api/security/data-quality":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.data_quality()))
                        return
                    if path == "/api/security/signin-detail":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.signin_detail()))
                        return
                    if path == "/api/security/risk-score":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.risk_score()))
                        return
                    if path == "/api/security/signin-summary":
                        service = SigninSummaryService(self._load_security_service().connection, 2)
                        self._write(200, _response("READY", service.summary()))
                        return
                    if path == "/api/security/signin-risk":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.signin_risk()))
                        return
                    if path == "/api/security/mfa-registration":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.mfa_registration()))
                        return
                    if path == "/api/security/mfa-coverage":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.mfa_coverage()))
                        return
                    if path == "/api/security/ca-policies":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.ca_policies()))
                        return
                    if path == "/api/security/admin-roles":
                        service = self._load_security_service()
                        self._write(200, _response("READY", service.admin_roles()))
                        return
                    detail_prefix = "/api/security/findings/"
                    if path.startswith(detail_prefix) and path[len(detail_prefix):]:
                        service = self._load_security_service()
                        finding = service.detail(path[len(detail_prefix):])
                        if finding is None:
                            self._write(404, _response("NOT_FOUND"))
                        else:
                            self._write(200, _response("READY", finding))
                        return
                    self._write(404, _response("NOT_FOUND"))
                    return
                finally:
                    connection = getattr(self, "_security_connection", None)
                    close = getattr(connection, "close", None)
                    if close is not None:
                        close()
            if path == "/api/capabilities":
                try:
                    service = self._load_capability_service()
                    self._write(200, _response("READY", {"capabilities": service.capabilities()}))
                    return
                finally:
                    connection = getattr(self, "_capability_connection", None)
                    close = getattr(connection, "close", None)
                    if close is not None:
                        close()
            if path == BASE_PATH + "/correlation/users":
                service = self._load_service()
                self._write(200, _response("READY", {"users": service.cross_workload_user_status()}))
                return
            if path == BASE_PATH + "/kpi":
                service = self._load_service()
                data = service.standard_kpi_summary()
                self._write(200, _response(_service_status(data), data, quality=_quality(service)))
                return
            if path == BASE_PATH + "/summary":
                service = self._load_service()
                tenant = service.tenant_summary()
                data = {"tenant_summary": tenant, "adoption_summary": {"exchange": service.exchange_adoption(), "onedrive": service.onedrive_adoption(), "sharepoint_user": service.sharepoint_user_adoption()}, "license_utilization": service.license_utilization()}
                self._write(200, _response(_service_status(data), data, quality=_quality(service), limitations={"sharepoint_site_analytics_status": "IDENTITY_UNAVAILABLE"}))
                return
            if path == BASE_PATH + "/onedrive/high-value-audit":
                values = parse_qs(parsed.query).get("limit", ["50"])
                if len(values) != 1 or not values[0].isdigit() or int(values[0]) < 1:
                    self._write(400, _response("INVALID_LIMIT"))
                    return
                service = self._load_service()
                data = service.onedrive_high_value_audit(int(values[0]))
                self._write(200, _response(data.pop("status", _service_status(data)), data))
                return
            if path == BASE_PATH + "/sharepoint/audit-summary":
                values = parse_qs(parsed.query).get("limit", ["50"])
                if len(values) != 1 or not values[0].isdigit() or int(values[0]) < 1:
                    self._write(400, _response("INVALID_LIMIT"))
                    return
                service = self._load_service()
                data = service.sharepoint_audit_summary(int(values[0]))
                self._write(200, _response(data.pop("status", _service_status(data)), data))
                return
            if path == BASE_PATH + "/sharepoint/orphaned-sites":
                service = self._load_service()
                data = {"sites": service.orphaned_sites()}
                self._write(200, _response("READY", data, quality=_quality(service)))
                return
            if path == BASE_PATH + "/sharepoint/external-sharing":
                service = self._load_service()
                data = {"tenants": service.external_sharing_summary()}
                self._write(200, _response("READY", data, quality=_quality(service)))
                return
            if path == BASE_PATH + "/sharepoint/tenant-settings":
                service = self._load_service()
                data = service.sharepoint_tenant_settings()
                self._write(200, _response(data.pop("status", _service_status(data)), data))
                return
            if path == BASE_PATH + "/license/expiry":
                service = self._load_service()
                data = service.license_expiry()
                self._write(200, _response(data.pop("status", _service_status(data)), data))
                return
            if path == BASE_PATH + "/teams/activity-summary":
                service = self._load_service()
                data = {"tenants": service.teams_activity_summary()}
                self._write(200, _response(_service_status(data), data, quality=_quality(service)))
                return
            if path == BASE_PATH + "/inactivity":
                values = parse_qs(parsed.query).get("days", ["30"])
                if len(values) != 1 or not values[0].isdigit() or int(values[0]) not in VALID_INACTIVITY_WINDOWS:
                    self._write(400, _response("INVALID_INACTIVITY_WINDOW", {"allowed_days": list(VALID_INACTIVITY_WINDOWS)}))
                    return
                days = int(values[0])
                service = self._load_service()
                candidates = service.inactivity_candidates()
                quality = _quality(service)
                self._write(200, _response("READY" if not quality["partial_tenant_coverage"] else "DATA_DEPENDENCY_UNAVAILABLE", {"window_days": days, **_aggregate_inactivity(candidates, days)}, quality=quality))
                return
            routes = {
                BASE_PATH + "/adoption/exchange": "exchange_adoption",
                BASE_PATH + "/adoption/onedrive": "onedrive_adoption",
                BASE_PATH + "/adoption/sharepoint": "sharepoint_user_adoption",
                BASE_PATH + "/adoption/sharepoint/sites": "sharepoint_site_adoption",
                BASE_PATH + "/license-utilization": "license_utilization",
            }
            if path in routes:
                service = self._load_service()
                data = getattr(service, routes[path])()
                self._write(200, _response(_service_status(data), data, quality=_quality(service)))
                return
            if path == BASE_PATH + "/data-quality":
                service = self._load_service()
                built = service.build()
                quality = _quality(service)
                quality["sharepoint_site_analytics_status"] = "IDENTITY_UNAVAILABLE"
                self._write(200, _response("READY", quality, limitations=built["limitations"]))
                return
            self._write(404, _response("NOT_FOUND"))
        except Exception:
            self._write(503, _response("DATA_DEPENDENCY_UNAVAILABLE"))


def create_server(host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    OperationsApiHandler.tenant_id = int(os.environ["GRAPH_TENANT_DB_ID"])
    return ThreadingHTTPServer((host or os.environ.get("API_HOST", "0.0.0.0"), port or int(os.environ.get("API_PORT", "8080"))), OperationsApiHandler)
