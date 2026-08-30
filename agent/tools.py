"""HTTP tools for the internal Operations API."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

from .config import INTERNAL_API_KEY, INTERNAL_API_PORT


class ToolError(RuntimeError):
    """Raised when an internal Operations API tool cannot retrieve data."""


def _get(path: str) -> dict[str, Any]:
    request = Request(f"http://localhost:{INTERNAL_API_PORT}{path}", method="GET", headers={"Accept": "application/json", "X-API-Key": INTERNAL_API_KEY})
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ToolError(f"Operations API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise ToolError("Service temporarily unavailable. Please try again.") from exc
    except (TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolError(f"Operations API request failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ToolError("Operations API returned an invalid JSON object")
    return payload


def get_kpi() -> dict[str, Any]:
    return _get("/api/operations/kpi")


def get_summary() -> dict[str, Any]:
    return _get("/api/operations/summary")


def get_data_quality() -> dict[str, Any]:
    return _get("/api/operations/data-quality")


def get_capabilities() -> dict[str, Any]:
    return _get("/api/capabilities")


def get_adoption_exchange() -> dict[str, Any]:
    return _get("/api/operations/adoption/exchange")


def get_adoption_onedrive() -> dict[str, Any]:
    return _get("/api/operations/adoption/onedrive")


def get_adoption_sharepoint() -> dict[str, Any]:
    return _get("/api/operations/adoption/sharepoint")


def get_inactivity(days: int) -> dict[str, Any]:
    if days not in (30, 60, 90):
        raise ToolError("days must be one of 30, 60, or 90")
    return _get(f"/api/operations/inactivity?days={days}")


def get_license_utilization() -> dict[str, Any]:
    return _get("/api/operations/license-utilization")


def get_correlation_users() -> dict[str, Any]:
    return _get("/api/operations/correlation/users")


def get_signin_summary() -> dict[str, Any]:
    return _get("/api/security/signin-summary")


def get_signin_risk() -> dict[str, Any]:
    return _get("/api/security/signin-risk")


def get_signin_detail() -> dict[str, Any]:
    return _get("/api/security/signin-detail")


def get_risk_score() -> dict[str, Any]:
    return _get("/api/security/risk-score")


def get_mfa_coverage() -> dict[str, Any]:
    return _get("/api/security/mfa-coverage")


def get_mfa_registration() -> dict[str, Any]:
    return _get("/api/security/mfa-registration")


def get_ca_policies() -> dict[str, Any]:
    return _get("/api/security/ca-policies")


def get_admin_roles() -> dict[str, Any]:
    return _get("/api/security/admin-roles")


def run_security_analysis() -> dict[str, Any]:
    request = Request(
        f"http://localhost:{INTERNAL_API_PORT}/api/agent/analyze/security",
        data=b"{}",
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json", "X-API-Key": INTERNAL_API_KEY},
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ToolError(f"Operations API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise ToolError("Service temporarily unavailable. Please try again.") from exc
    except (TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolError(f"Operations API request failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ToolError("Operations API returned an invalid JSON object")
    return payload
