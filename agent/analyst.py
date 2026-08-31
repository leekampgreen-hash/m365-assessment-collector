"""Security Analyst Agent."""
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime

if not logging.root.handlers:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )

from agent import config
from agent.anonymizer import Anonymizer

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


def _build_data_message(data: dict) -> str:
    """Build a message containing the compact security data."""
    return json.dumps(_summarize_data(data), separators=(",", ":"), default=str)


def _plain_text_report(report: str) -> str:
    lines = []
    for line in report.replace("```", "").splitlines():
        line = line.replace("**", "").replace("__", "").replace("`", "")
        line = line.lstrip("# ")
        if line.strip() and set(line.strip()) <= {"-", "_", "="}:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def generate_security_report(system_prompt: str = None, choice: str = "", history: list = None) -> dict:
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
        anon = Anonymizer()
        summarized = _summarize_data(data)
        anonymized = dict(summarized)
        risk_score = dict(anonymized.get("risk_score", {}))
        if "top_risks" in risk_score:
            risk_score["top_risks"] = anon.anonymize_data(risk_score["top_risks"])
        anonymized["risk_score"] = risk_score
        for section in ("mfa_registration", "signin_summary"):
            if section in anonymized:
                anonymized[section] = anon.anonymize_data(anonymized[section])
        logger.info("ANON_MAPPING: %s", anon.mapping_summary())

        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                *[{"role": item["role"], "content": item["content"]} for item in (history or [])],
                {
                    "role": "user",
                    "content": f"Security data:\n{json.dumps(anonymized, separators=(',', ':'), default=str)}\n\nUser selection: {choice or 'Start analysis'}",
                },
            ]
        else:
            user_content = json.dumps(anonymized, separators=(",", ":"), default=str)
            if choice:
                user_content = f"{choice}\n\n{user_content}"
            messages = [{"role": "user", "content": user_content}]

        logger.info("LLM_PAYLOAD_KEYS: %s", [message["role"] for message in messages])
        logger.info("LLM_PAYLOAD_DATA: %s", json.dumps(anonymized, separators=(",", ":"), default=str))
        response = client.chat.completions.create(
            model=config.ANALYST_MODEL,
            messages=messages,
            max_tokens=1200,
        )
        raw_report = _plain_text_report(response.choices[0].message.content or "")
        report = anon.deanonymize(raw_report)
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
