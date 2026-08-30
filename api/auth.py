"""API key authentication for the Operations API."""
from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler


API_KEY_HEADER = "X-API-Key"
_API_KEY = os.getenv("API_KEY", "")


def verify_api_key(handler: BaseHTTPRequestHandler) -> bool:
    if not _API_KEY:
        return True
    return handler.headers.get(API_KEY_HEADER) == _API_KEY
