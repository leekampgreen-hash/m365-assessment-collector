"""HTTP boundary for the agent chat endpoint."""
from __future__ import annotations

from typing import Any

from agent.orchestrator import chat


def handle_chat(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("message"), str) or not payload["message"].strip():
        raise ValueError("message must be a non-empty string")
    history = payload.get("history", [])
    if not isinstance(history, list):
        raise ValueError("history must be a list")
    return chat(payload["message"], history)
