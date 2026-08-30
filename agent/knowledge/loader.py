"""Load and search the M365 operations knowledge base."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Read-only, file-backed knowledge lookup for agent responses."""

    _TOPIC_KEYWORDS = {
        "exchange": ("exchange", "email", "mailbox", "outlook"),
        "sharepoint": ("sharepoint", "site", "sites"),
        "onedrive": ("onedrive", "one drive", "cloud storage"),
        "teams": ("teams", "meeting", "channel"),
        "entra": ("entra", "mfa", "conditional access", "identity", "sign-in", "risky", "password", "admin", "role"),
        "license": ("license", "sku", "subscription", "assigned"),
    }

    def __init__(self) -> None:
        directory = Path(__file__).resolve().parent
        self._directory = directory
        self._data: dict[str, dict[str, Any]] = {
            "rules": self._load(directory / "core" / "rule_translations.json"),
            "ca_states": self._load(directory / "core" / "ca_policy_states.json"),
            "terms": self._load(directory / "core" / "m365_terminology.json"),
            "recommendations": self._load(directory / "core" / "recommendations.json"),
        }
        self._products: dict[str, dict[str, Any]] = {}
        self._validate_schema()
        available = sum(1 for topic in self._TOPIC_KEYWORDS if (directory / "products" / f"{topic}.json").is_file())
        logger.info("knowledge base loaded: core files ready, %d product files available", available)

    def _validate_schema(self) -> None:
        schemas = {
            "rules": {"title", "risk_level", "plain_language", "recommended_action"},
            "ca_states": {"label", "risk", "plain_language", "action_needed"},
            "terms": {"full_name", "plain_language", "why_it_matters"},
            "recommendations": {"priority", "title", "plain_language", "immediate_action", "long_term_action"},
        }
        for group, required in schemas.items():
            if not self._data[group]:
                raise ValueError(f"Invalid knowledge schema for {group}; file must contain entries")
            for key, value in self._data[group].items():
                if not isinstance(value, dict) or not required.issubset(value):
                    missing = sorted(required - set(value) if isinstance(value, dict) else required)
                    raise ValueError(f"Invalid knowledge schema for {group}.{key}; missing keys: {', '.join(missing)}")

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as file:
            value = json.load(file)
        if not isinstance(value, dict):
            raise ValueError(f"Knowledge file must contain an object: {path}")
        return value

    def detect_topics(self, message: str) -> list[str]:
        text = message.casefold()
        return [topic for topic, keywords in self._TOPIC_KEYWORDS.items() if any(keyword in text for keyword in keywords)]

    def load_product(self, topic: str) -> dict[str, Any]:
        if topic in self._products:
            return self._products[topic]
        path = self._directory / "products" / f"{topic}.json"
        if not path.is_file():
            return {}
        self._products[topic] = self._load(path)
        return self._products[topic]

    def get_rule_info(self, rule_id: str) -> dict[str, Any] | None:
        return self._data["rules"].get(rule_id)

    def get_ca_state_info(self, state: str) -> dict[str, Any] | None:
        return self._data["ca_states"].get(state)

    def get_term_info(self, term: str) -> dict[str, Any] | None:
        if term in self._data["terms"]:
            return self._data["terms"][term]
        lowered = term.casefold()
        return next((info for name, info in self._data["terms"].items() if name.casefold() == lowered), None)

    def get_recommendation(self, category: str) -> dict[str, Any] | None:
        return self._data["recommendations"].get(category)

    def get_context_for_prompt(self, keywords: list[str]) -> str:
        query = {word.casefold() for word in keywords if len(word) > 2}
        topics = self.detect_topics(" ".join(keywords))
        entries = dict(self._data)
        for topic in topics:
            product = self.load_product(topic)
            if product:
                entries[f"{topic} product"] = product.get("topics", {})
        matches: list[tuple[int, str]] = []
        for group, group_entries in entries.items():
            for key, value in group_entries.items():
                searchable = f"{key} {json.dumps(value, ensure_ascii=False)}".casefold()
                score = sum(1 for word in query if re.search(rf"\b{re.escape(word)}\b", searchable))
                if score:
                    selected = {field: value[field] for field in ("title", "plain_language", "recommended_action", "recommended_actions", "label", "risk", "action_needed", "full_name", "why_it_matters", "immediate_action", "long_term_action", "common_issues", "learn_more") if field in value}
                    matches.append((score, f"{group}: {key} — {json.dumps(selected, ensure_ascii=False)}"))
        matches.sort(key=lambda item: item[0], reverse=True)
        result = ""
        for _, text in matches:
            candidate = f"{result}\n{text}" if result else text
            if len(candidate) > 600:
                continue
            result = candidate
            if len(result) >= 600:
                break
        return result


knowledge_base = KnowledgeBase()
