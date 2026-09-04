"""Safe serialization of execution results and auth-failure result shape.

This module exists to keep a single audit-friendly view of what can be
serialized for evidence / dry-run / test output. The serializations
here MUST NOT contain:

- the access token,
- the ``Authorization`` header value,
- the client secret,
- the password of any kind,
- the raw environment contents.

Errors that come from authentication failures are mapped to the
framework's existing ``error_classification`` taxonomy so downstream
tools don't have to special-case auth problems.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .auth import (
    AUTH_ERROR_CLASSIFICATIONS,
    AUTH_ERROR_HTTP,
    AUTH_ERROR_INVALID_CLIENT,
    AUTH_ERROR_MALFORMED,
    AUTH_ERROR_MISSING_CONFIG,
    AUTH_ERROR_NETWORK,
    AuthError,
)
from .errors import API_ERROR, AUTH_FAILURE, NETWORK_ERROR, PASS, UNKNOWN
from .models import CollectionResult


# Map auth-error classifications to the framework's CollectionResult
# ``error_classification`` vocabulary. Auth problems are NOT 401/403 from
# Graph; they are token-acquisition problems that prevent the Graph call
# from happening at all. We surface them as ``AUTH_FAILURE`` so callers
# can act on them uniformly.
_AUTH_TO_COLLECTION_CLASSIFICATION = {
    AUTH_ERROR_MISSING_CONFIG: AUTH_FAILURE,
    AUTH_ERROR_INVALID_CLIENT: AUTH_FAILURE,
    AUTH_ERROR_NETWORK: NETWORK_ERROR,
    AUTH_ERROR_MALFORMED: API_ERROR,
    AUTH_ERROR_HTTP: API_ERROR,
}


# Disallowed substrings that MUST NOT appear in any serialized evidence.
# These are checked at the unit-test level and at runtime in
# ``safe_dumps``. They are intentionally narrow so that legitimate
# metadata such as missing-env-variable names in error messages can
# still be serialized.
#
# The auth configuration NAMES (``GRAPH_TENANT_ID``, etc.) are NOT
# secrets; they appear in operator-facing error messages when env vars
# are missing, and that is desirable.
_FORBIDDEN_SUBSTRINGS = (
    "Bearer ",
    "Authorization:",
    "client_secret=",
    "password=",
    "access_token=",
    "refresh_token=",
)


def auth_error_to_classification(auth_error: AuthError) -> str:
    """Map an ``AuthError`` to a framework ``error_classification`` value."""
    if not isinstance(auth_error, AuthError):
        raise TypeError("auth_error must be an AuthError")
    if auth_error.classification not in AUTH_ERROR_CLASSIFICATIONS:
        return UNKNOWN
    return _AUTH_TO_COLLECTION_CLASSIFICATION.get(auth_error.classification, UNKNOWN)


def auth_error_to_result(auth_error: AuthError, *, endpoint_id: str = "") -> CollectionResult:
    """Build a ``CollectionResult`` that represents an auth-side failure.

    The returned result:
    - carries the framework's standard ``error_classification`` value,
    - carries the auth classification in ``error_message`` as a SAFE label
      (never the exception message verbatim),
    - sets ``status = "ERROR"``,
    - has no pages / rows,
    - has no ``http_status`` (no Graph call was attempted),
    - serializes to a JSON dict that never contains a token, secret, or
      Authorization header.
    """
    if not isinstance(auth_error, AuthError):
        raise TypeError("auth_error must be an AuthError")
    classification = auth_error_to_classification(auth_error)
    return CollectionResult(
        endpoint_id=endpoint_id,
        status="ERROR",
        pages=0,
        rows=0,
        started_at=None,
        completed_at=None,
        duration=None,
        http_status=None,
        error_classification=classification,
        # Only carry the auth classification label (e.g.
        # ``MISSING_CONFIG``). Never include the original exception
        # message verbatim -- Microsoft identity platform can echo
        # request fields in error descriptions.
        error_message=auth_error.classification,
        retry_count=0,
        retry_after=None,
        graph_error_code=auth_error.classification,
        pagination_detected=False,
        recovery_evidence={
            "endpoint": endpoint_id,
            "failure_category": classification,
            "retry_attempts": 0,
            "final_status": "FAILED_PERMANENT",
            "recommended_action": "CHECK_GRAPH_PERMISSION" if classification in (AUTH_FAILURE, "PERMISSION_REQUIRED") else "RETRY_RUN",
        },
    )


def _scrub(value: Any) -> Any:
    """Defensive scrub: remove any key that could carry credentials."""
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, inner in value.items():
            if not isinstance(key, str):
                continue
            lowered = key.lower()
            # Common credential field names -- none of these should ever
            # reach evidence.
            if lowered in (
                "authorization", "bearer", "access_token", "access token",
                "client_secret", "client secret", "password", "secret",
                "refresh_token", "refresh token",
            ):
                continue
            cleaned[key] = _scrub(inner)
        return cleaned
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def safe_dumps(payload: Any) -> str:
    """Serialize ``payload`` as JSON, scrubbing credential-shaped fields
    and verifying the output does not contain disallowed substrings.
    """
    cleaned = _scrub(payload)
    serialized = json.dumps(cleaned, default=str, sort_keys=False)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        if forbidden in serialized:
            # Defensive: scrub failed -- raise to make the leak visible
            # to tests / dry-run output. The runtime never reaches this
            # because the framework does not put credentials in payload.
            raise ValueError("safe_dumps detected forbidden substring in output")
    return serialized


def result_to_dict(result) -> Dict[str, Any]:
    """Serialize a ``CollectionResult`` (or any dataclass-like) safely.

    Returns the dataclass's own ``to_dict()`` if present, then scrubs.
    """
    if hasattr(result, "to_dict") and callable(result.to_dict):
        as_dict = result.to_dict()
    elif hasattr(result, "__dict__"):
        as_dict = dict(result.__dict__)
    else:
        raise TypeError("result must be a dataclass-like object")
    return _scrub(as_dict)


__all__ = [
    "AUTH_ERROR_CLASSIFICATIONS",
    "auth_error_to_classification",
    "auth_error_to_result",
    "result_to_dict",
    "safe_dumps",
]