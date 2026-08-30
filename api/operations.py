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
from collectors.persistence import open_database_connection
from capabilities.persistence import CapabilityQueryService


BASE_PATH = "/api/operations"
VALID_INACTIVITY_WINDOWS = (30, 60, 90)


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
                self._write(200, generate_security_report())
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
        if (path.startswith(BASE_PATH) or path.startswith("/api/security") or path == "/api/capabilities") and not verify_api_key(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "X-API-Key")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not path.startswith(BASE_PATH) and not path.startswith("/api/security") and path != "/api/capabilities":
            self._write(404, _response("NOT_FOUND"))
            return
        try:
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
