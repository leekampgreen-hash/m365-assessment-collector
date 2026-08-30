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


def _build_analysis_prompt(data: dict) -> str:
    """Build analysis prompt from collected security data."""
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""You are a Microsoft 365 Security Analyst.
Analyze the following security data and generate a professional
security analysis report in plain text format.

The report must follow this exact structure:

SECURITY ANALYSIS REPORT
Generated: {generated}

EXECUTIVE SUMMARY
[2-3 sentences summarizing overall security posture]

CRITICAL FINDINGS ([count] items)
[List each critical finding with:]
- Finding: [what the issue is in plain language]
- Risk: [why this is dangerous, business impact]
- Action: [specific steps to fix, numbered]

HIGH FINDINGS ([count] items)
[Same format]

MEDIUM FINDINGS ([count] items)
[Same format]

RECOMMENDED PRIORITY ORDER
[Numbered list of what to fix first, with brief reason]

OVERALL SECURITY SCORE: [X]/100
[One sentence justification]

RULES:
- Plain text only — no markdown, no asterisks, no hashtags
- No technical jargon — write for IT support staff
- No rule IDs, UUIDs, UPNs, or email addresses
- Be specific and actionable
- If data is unavailable for a section, say "No data available"

SECURITY DATA:
{json.dumps(data, indent=2, default=str)}
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
        )
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=[{"role": "user", "content": _build_analysis_prompt(data)}],
            max_tokens=2000,
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
