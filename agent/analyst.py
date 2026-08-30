"""Security Analyst Agent."""
import json
import logging
import os
import urllib.request
from datetime import datetime

from agent import config

logger = logging.getLogger(__name__)

INTERNAL_BASE = f"http://localhost:{config.INTERNAL_API_PORT}"
INTERNAL_KEY = os.getenv("API_KEY", "")

SECURITY_ENDPOINTS = [
    "/api/security/risk-score",
    "/api/security/admin-roles",
    "/api/security/mfa-coverage",
    "/api/security/mfa-registration",
    "/api/security/signin-summary",
    "/api/security/ca-policies",
    "/api/security/findings?status=open",
]


def _fetch(path: str) -> dict:
    try:
        request_path = path.replace("status=open", "status=OPEN")
        request = urllib.request.Request(
            f"{INTERNAL_BASE}{request_path}",
            headers={"X-API-Key": INTERNAL_KEY},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", path, exc)
        return {}


def _collect_security_data() -> dict:
    """Fetch all security endpoints and return combined data."""
    return {
        "risk_score": _fetch("/api/security/risk-score"),
        "admin_roles": _fetch("/api/security/admin-roles"),
        "mfa_coverage": _fetch("/api/security/mfa-coverage"),
        "mfa_registration": _fetch("/api/security/mfa-registration"),
        "signin_summary": _fetch("/api/security/signin-summary"),
        "ca_policies": _fetch("/api/security/ca-policies"),
        "findings": _fetch("/api/security/findings?status=open"),
    }


def _summarize_data(data: dict) -> dict:
    """Keep only compact, report-relevant security metrics."""
    data = {key: value.get("data", value) if isinstance(value, dict) else value for key, value in data.items()}
    risk = data.get("risk_score", {})
    admin = data.get("admin_roles", {})
    coverage = data.get("mfa_coverage", {})
    registration = data.get("mfa_registration", {})
    signin = data.get("signin_summary", {})
    policies = data.get("ca_policies", {})
    findings = data.get("findings", {}).get("findings", []) if isinstance(data.get("findings", {}), dict) else []
    if isinstance(findings, dict):
        findings = findings.get("items", [])
    translations = {}
    try:
        from agent.knowledge.loader import KnowledgeBase
        knowledge = KnowledgeBase()
        translations = {
            item.get("rule_id"): knowledge.get_rule_info(item.get("rule_id", ""))
            for item in findings if item.get("rule_id")
        }
    except Exception:
        pass

    def finding(item: dict) -> dict:
        info = translations.get(item.get("rule_id")) or {}
        return {
            "finding": info.get("title") or item.get("title") or item.get("finding") or item.get("category") or "Security finding",
            "severity": item.get("severity") or item.get("risk"),
            "status": item.get("status"),
        }

    return {
        "risk_score": {
            "distribution": risk.get("risk_distribution", {}),
            "top_risks": [
                {key: item.get(key) for key in ("display_name", "risk_level", "score")}
                for item in risk.get("top_risks", [])[:3]
            ],
        },
        "admin_roles": {key: admin.get(key) for key in ("total_roles_assigned", "high_privilege_roles", "findings")},
        "mfa_coverage": {key: coverage.get(key) for key in ("mfa_pass_rate", "findings")},
        "mfa_registration": {key: registration.get(key) for key in ("total_users", "mfa_registered", "mfa_not_registered", "registration_rate_pct")},
        "signin_summary": {key: signin.get(key) for key in ("total_signins", "failed_signins", "failure_rate_pct", "legacy_auth_signins", "findings")},
        "ca_policies": {
            key: policies.get(key) for key in ("total", "enabled", "disabled")
        } | {"policies": [{key: policy.get(key) for key in ("display_name", "state")} for policy in policies.get("policies", [])[:3]]},
        "findings": [finding(item) for item in findings[:5]],
    }


def _build_analysis_prompt(data: dict) -> str:
    """Build analysis prompt from compact security data."""
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""You are a Microsoft 365 Security Analyst. Write a concise plain-text report for IT support staff using only this data.

SECURITY ANALYSIS REPORT
Generated: {generated}

EXECUTIVE SUMMARY
2-3 sentences on overall posture.

CRITICAL FINDINGS ([count] items)
HIGH FINDINGS ([count] items)
MEDIUM FINDINGS ([count] items)
For each: Finding, Risk/business impact, and numbered Action steps.

RECOMMENDED PRIORITY ORDER
Numbered fixes with brief reasons.

OVERALL SECURITY SCORE: [X]/100
One-sentence justification.

Use no markdown, jargon, rule IDs, UUIDs, UPNs, or email addresses. Cover every security area. Say "No data available" when needed.

SECURITY DATA:
{json.dumps(_summarize_data(data), separators=(",", ":"), default=str)}
"""


def _plain_text_report(report: str) -> str:
    lines = []
    for line in report.replace("```", "").splitlines():
        line = line.replace("**", "").replace("__", "").replace("`", "")
        line = line.lstrip("# ")
        if line.strip() and set(line.strip()) <= {"-", "_", "="}:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def generate_security_report() -> dict:
    """Collect security data and generate an analysis report."""
    from openai import OpenAI

    logger.info("Security Analyst: collecting data")
    data = _collect_security_data()
    try:
        client = OpenAI(
            api_key=config.KRYPTONLAB_API_KEY or config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            timeout=45.0,
        )
        response = client.chat.completions.create(
            model=config.ANALYST_MODEL,
            messages=[{"role": "user", "content": _build_analysis_prompt(data)}],
            max_tokens=1200,
        )
        report = _plain_text_report(response.choices[0].message.content or "")
        tokens_used = getattr(response.usage, "total_tokens", None)
        if tokens_used:
            logger.info("Security Analyst: %s tokens used", tokens_used)
        return {
            "status": "READY",
            "generated_at": datetime.utcnow().isoformat(),
            "report": report,
            "data_sources": list(SECURITY_ENDPOINTS),
        }
    except Exception as exc:
        logger.error("Security Analyst failed: %s", exc)
        return {
            "status": "ERROR",
            "generated_at": datetime.utcnow().isoformat(),
            "error": "Security analysis could not be completed. Please try again.",
        }
