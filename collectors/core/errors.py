"""Deterministic error classification for the collector framework.

The classification rules below preserve the behavior of the existing
Discovery Agent:

    2xx                 -> "PASS"
    401                 -> AUTH_FAILURE
    403                 -> PERMISSION_REQUIRED
    429                 -> THROTTLED
    other non-2xx       -> API_ERROR
    transport / network -> NETWORK_ERROR

AUTH_FAILURE and PERMISSION_REQUIRED are NOT retryable (they will not
resolve by themselves). THROTTLED, API_ERROR (5xx subset), and
NETWORK_ERROR are retryable -- see ``retry.py``.
"""
from __future__ import annotations

from typing import Optional, Tuple

AUTH_FAILURE = "AUTH_FAILURE"
PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
THROTTLED = "THROTTLED"
API_ERROR = "API_ERROR"
NETWORK_ERROR = "NETWORK_ERROR"
PASS = "PASS"
UNKNOWN = "UNKNOWN"
ENTITY_IDENTITY_UNAVAILABLE = "ENTITY_IDENTITY_UNAVAILABLE"
PERSISTENCE_ERROR = "PERSISTENCE_ERROR"


CLASSIFICATIONS = (
    PASS,
    AUTH_FAILURE,
    PERMISSION_REQUIRED,
    THROTTLED,
    API_ERROR,
    NETWORK_ERROR,
    UNKNOWN,
    ENTITY_IDENTITY_UNAVAILABLE,
    PERSISTENCE_ERROR,
)


def classify_http_status(status: Optional[int]) -> str:
    """Classify an HTTP status code into a framework classification string."""
    if status is None:
        return NETWORK_ERROR
    if 200 <= status < 300:
        return PASS
    if status == 401:
        return AUTH_FAILURE
    if status == 403:
        return PERMISSION_REQUIRED
    if status == 429:
        return THROTTLED
    return API_ERROR


def classify_transport_failure(exc: BaseException) -> str:
    """A network/transport failure (no HTTP response received) is always
    classified as NETWORK_ERROR. The exception itself is not serialized."""
    return NETWORK_ERROR


def is_retryable(classification: str) -> bool:
    """Auth/permission failures must never be retried in a loop."""
    if classification in (AUTH_FAILURE, PERMISSION_REQUIRED, PASS):
        return False
    return classification in (THROTTLED, API_ERROR, NETWORK_ERROR)


def classify_response(status: Optional[int], exc: Optional[BaseException] = None) -> Tuple[str, bool]:
    """Return (classification, retryable)."""
    if exc is not None:
        return classify_transport_failure(exc), True
    cls = classify_http_status(status)
    return cls, is_retryable(cls)
