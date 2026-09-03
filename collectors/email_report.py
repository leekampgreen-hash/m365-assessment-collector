from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)
_last_sent: str | None = None


def _enabled() -> bool:
    return os.getenv("REPORT_ENABLED", "false").lower() == "true"


def _fetch(path: str) -> dict:
    base = os.getenv("REPORT_API_URL", "http://operations-api:8080")
    headers = {"Accept": "application/json"}
    if os.getenv("API_KEY"):
        headers["X-API-Key"] = os.environ["API_KEY"]
    with urlopen(Request(base.rstrip("/") + path, headers=headers), timeout=30) as response:
        return json.load(response)


def collect_report_data() -> dict:
    summary = _fetch("/api/security/summary").get("data", {})
    findings = _fetch("/api/security/findings?status=open&severity=HIGH").get("data", {}).get("findings", [])
    mfa = _fetch("/api/security/mfa-coverage").get("data", {})
    inactivity = _fetch("/api/operations/inactivity?days=30").get("data", {})
    licenses = _fetch("/api/operations/license-utilization").get("data", {})
    safe_findings = [{"title": item.get("title") or item.get("name") or "Security finding", "severity": item.get("severity", "HIGH")} for item in findings[:5]]
    severity = summary.get("by_severity", summary.get("severity", {}))
    return {"severity": severity, "findings": safe_findings, "mfa_pct": mfa.get("mfa_coverage_pct", mfa.get("coverage_pct", mfa.get("mfa_registration_rate_pct", 0))), "inactive_users": inactivity.get("inactive_users", inactivity.get("total", 0)), "license_util_pct": licenses.get("utilization_pct", licenses.get("license_utilization_pct", licenses.get("utilization", 0)))}


def build_html(data: dict) -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_dir = Path(__file__).parent / "templates"
    environment = Environment(loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html", "xml"]))
    return environment.get_template("email_report.html").render(**data, dashboard_url=os.getenv("REPORT_DASHBOARD_URL", "http://localhost:18080"), unsubscribe_url=os.getenv("REPORT_UNSUBSCRIBE_URL", "#"), generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))


def send_report() -> bool:
    global _last_sent
    if not _enabled():
        logger.info("Email report disabled")
        return False
    recipients = [item.strip() for item in os.getenv("REPORT_EMAIL_TO", "").split(",") if item.strip()]
    if not recipients:
        logger.warning("Email report has no recipients")
        return False
    message = EmailMessage()
    message["Subject"] = "Microsoft 365 Operations Intelligence Report"
    message["From"] = os.getenv("SMTP_USER", "")
    message["To"] = ", ".join(recipients)
    message.set_content("Your Microsoft 365 Operations Intelligence report is available in HTML format.")
    message.add_alternative(build_html(collect_report_data()), subtype="html")
    host, port = os.getenv("SMTP_HOST", ""), int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        if os.getenv("SMTP_USER"):
            smtp.starttls()
            smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message)
    _last_sent = datetime.now(timezone.utc).isoformat()
    return True


def report_status(next_scheduled: str | None = None) -> dict:
    return {"last_sent": _last_sent, "next_scheduled": next_scheduled, "enabled": _enabled(), "schedule_type": os.getenv("REPORT_SCHEDULE", "daily")}
