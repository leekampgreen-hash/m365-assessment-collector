"""Collector authentication: app-only OAuth 2.0 client credentials.

This module is intentionally small and stdlib-only. It owns:

- ``CollectorAuthConfig`` - a typed view of the three required environment
  variables (``GRAPH_TENANT_ID``, ``GRAPH_CLIENT_ID``, ``GRAPH_CLIENT_SECRET``).
  The config object is the ONLY place secret material is held while the
  process is alive; once ``CollectorTokenProvider`` has obtained a token
  the config can be discarded by the caller.
- ``CollectorTokenProvider`` - a thread-unsafe (collector runs are
  sequential) token cache that acquires a fresh token lazily, reuses a
  still-valid token, and refreshes it before expiry. Tokens are never
  persisted to disk.
- ``AuthError`` / structured error classification for token acquisition
  failures. Errors are deterministic and carry NO credential values.

Security guarantees:

- ``client_secret``, ``access_token``, and the ``Authorization`` header
  are NEVER included in any exception message, repr, or log line.
- ``repr()`` of the config and the provider is redacted.
- ``__str__`` and exception messages only carry safe metadata
  (``token_endpoint`` host, ``classification`` label, ``tenant_id``).
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request


# --- Error classification ----------------------------------------------

AUTH_ERROR_MISSING_CONFIG = "MISSING_CONFIG"
AUTH_ERROR_INVALID_CLIENT = "INVALID_CLIENT"
AUTH_ERROR_NETWORK = "TOKEN_NETWORK_ERROR"
AUTH_ERROR_MALFORMED = "MALFORMED_TOKEN_RESPONSE"
AUTH_ERROR_HTTP = "TOKEN_HTTP_ERROR"

AUTH_ERROR_CLASSIFICATIONS = (
    AUTH_ERROR_MISSING_CONFIG,
    AUTH_ERROR_INVALID_CLIENT,
    AUTH_ERROR_NETWORK,
    AUTH_ERROR_MALFORMED,
    AUTH_ERROR_HTTP,
)


# Mapping from OAuth2 token-endpoint error codes to our internal classification.
# Per Microsoft identity platform docs:
#   invalid_client -> wrong / rotated client_id or client_secret
#   invalid_grant -> usually wrong credential or scope
#   invalid_scope -> usually misconfigured scope for app-only
#   invalid_request -> malformed request
_OAUTH_ERROR_TO_CLASSIFICATION = {
    "invalid_client": AUTH_ERROR_INVALID_CLIENT,
    "invalid_grant": AUTH_ERROR_INVALID_CLIENT,
    "invalid_scope": AUTH_ERROR_INVALID_CLIENT,
    "invalid_request": AUTH_ERROR_MALFORMED,
}


class AuthError(Exception):
    """Structured authentication error.

    Carries a deterministic ``classification`` and a SAFE ``message``
    that never contains a token, secret, or ``Authorization`` header.
    """

    def __init__(self, classification: str, message: str):
        if classification not in AUTH_ERROR_CLASSIFICATIONS:
            raise ValueError("unknown auth classification: " + str(classification))
        self.classification = classification
        self.message = message
        super().__init__(message)

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return "AuthError(classification={!r})".format(self.classification)


# --- Config -------------------------------------------------------------


REDACTED = "<redacted>"


@dataclass
class CollectorAuthConfig:
    """Typed auth configuration.

    The three required fields are non-empty strings; ``repr`` is redacted.
    """

    tenant_id: str
    client_id: str
    client_secret: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "client_id", "client_secret"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError("CollectorAuthConfig.{} must be a non-empty string".format(name))

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return "CollectorAuthConfig(tenant_id={!r}, client_id={!r}, client_secret={!r})".format(
            REDACTED, REDACTED, REDACTED,
        )

    def to_dict(self) -> dict:
        # For structured logging / serialization. Secret is redacted.
        return {
            "tenant_id": self.tenant_id,
            "client_id": self.client_id,
            "client_secret": REDACTED,
        }


# --- Token cache --------------------------------------------------------


@dataclass
class _CachedToken:
    access_token: str
    expires_at: float  # monotonic seconds


class CollectorTokenProvider:
    """Lazy, in-memory app-only token provider with reuse-while-valid.

    Constructor arguments:

    - ``config``: a ``CollectorAuthConfig`` with the three required env values.
    - ``http_open``: a ``urlopen``-compatible callable. Tests inject a fake.
    - ``clock``: monotonic clock (seconds). Tests inject a fake.
    - ``expires_in``: ``expires_in`` from the token response (seconds).
    - ``refresh_skew_seconds``: how early to refresh before the nominal
      expiry. Microsoft identity platform recommends treating the token
      as expired slightly before ``exp``. We default to 60s, which is
      conservative for app-only workloads.
    - ``timeout``: HTTP timeout for the token request.
    """

    def __init__(
        self,
        config: CollectorAuthConfig,
        *,
        http_open: Callable[..., object],
        clock: Callable[[], float] = time.monotonic,
        refresh_skew_seconds: float = 60.0,
        timeout: float = 30.0,
        resource: str = "https://graph.microsoft.com",
    ) -> None:
        if not isinstance(config, CollectorAuthConfig):
            raise TypeError("config must be a CollectorAuthConfig")
        if http_open is None:
            raise ValueError("http_open is required")
        self._config = config
        self._http_open = http_open
        self._clock = clock
        self._refresh_skew = float(refresh_skew_seconds)
        self._timeout = float(timeout)
        self._resource = resource.rstrip("/")
        if not self._resource.startswith("https://"):
            raise ValueError("resource must be an HTTPS URL")
        if self._resource not in ("https://graph.microsoft.com", "https://manage.office.com"):
            raise ValueError("unsupported token resource")
        self._cached: Optional[_CachedToken] = None
        self._lock = threading.Lock()

    # ---- Public properties --------------------------------------------

    @property
    def token_endpoint(self) -> str:
        return "https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(
            self._config.tenant_id,
        )

    @property
    def resource(self) -> str:
        return self._resource

    @property
    def timeout(self) -> float:
        return self._timeout

    # ---- Public API ---------------------------------------------------

    def get_token(self) -> str:
        """Return a valid access token, acquiring one if necessary.

        Returns a cached token that is still valid. If the cache is empty
        or the cached token is within the refresh skew window, a fresh
        token is acquired. A failed acquisition clears any partial state
        so the next call is a fresh attempt.
        """
        with self._lock:
            cached = self._cached
            if cached is not None:
                # Treat as expired if we are inside the refresh-skew window.
                if cached.expires_at - self._clock() > self._refresh_skew:
                    return cached.access_token
            try:
                token, expires_at = self._acquire()
            except Exception:
                # A failed acquisition MUST NOT cache anything bad.
                self._cached = None
                raise
            self._cached = _CachedToken(access_token=token, expires_at=expires_at)
            return token

    def invalidate(self) -> None:
        """Drop any cached token. The next ``get_token`` will acquire fresh."""
        with self._lock:
            self._cached = None

    # ---- Internals ----------------------------------------------------

    def _acquire(self) -> tuple:
        """Perform the OAuth 2.0 client credentials grant and return
        ``(access_token, expires_at_monotonic)``.

        All exceptions are normalized into ``AuthError``.
        """
        body = urlencode({
            "grant_type": "client_credentials",
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
            "scope": self._resource + "/.default",
        }).encode("ascii")
        request = Request(
            self.token_endpoint,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with self._http_open(request, timeout=self._timeout) as response:
                status = getattr(response, "status", 200)
                raw = response.read()
        except HTTPError as error:
            raw = error.read()
            return self._classify_http_error(error.code, raw)
        except (URLError, TimeoutError, OSError) as error:
            # Transport-level failure: do NOT include any error message
            # that could carry a secret (URLError messages from
            # urlopen are safe but we keep them generic).
            raise AuthError(
                AUTH_ERROR_NETWORK,
                "Token endpoint transport error ({}); tenant id present".format(
                    type(error).__name__,
                ),
            ) from None
        except Exception as error:  # pragma: no cover - defensive
            raise AuthError(
                AUTH_ERROR_NETWORK,
                "Token endpoint unexpected error ({}); tenant id present".format(
                    type(error).__name__,
                ),
            ) from None

        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise AuthError(AUTH_ERROR_MALFORMED, "Token response was not valid UTF-8") from None
        try:
            payload = json.loads(decoded)
        except json.JSONDecodeError:
            raise AuthError(AUTH_ERROR_MALFORMED, "Token response was not valid JSON") from None
        if not isinstance(payload, dict):
            raise AuthError(AUTH_ERROR_MALFORMED, "Token response was not a JSON object")

        # If the token endpoint replied with a non-2xx status but a JSON body.
        if not (200 <= status < 300):
            return self._classify_oauth_error(payload, status)

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise AuthError(AUTH_ERROR_MALFORMED, "Token response missing access_token")

        # Microsoft identity platform returns ``expires_in`` in seconds.
        # We treat 0 / negative / missing values as "expire immediately".
        try:
            expires_in = int(payload.get("expires_in", 0))
        except (TypeError, ValueError):
            raise AuthError(AUTH_ERROR_MALFORMED, "Token response missing valid expires_in") from None
        if expires_in <= 0:
            raise AuthError(AUTH_ERROR_MALFORMED, "Token response missing valid expires_in")

        expires_at = self._clock() + float(expires_in)
        return access_token, expires_at

    def _classify_http_error(self, status: int, raw: bytes) -> None:
        # ``raw`` is the response body bytes; never include them in the message.
        try:
            decoded = raw.decode("utf-8")
            payload = json.loads(decoded) if decoded else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            self._classify_oauth_error(payload, status)
        # Fallback: treat as a generic HTTP error without leaking the body.
        raise AuthError(
            AUTH_ERROR_HTTP,
            "Token endpoint returned HTTP {} (body omitted)".format(status),
        ) from None

    def _classify_oauth_error(self, payload: Mapping, status: int) -> None:
        # Only carry the ``error`` field label (e.g. ``invalid_client``) into
        # the message. NEVER include ``error_description`` verbatim --
        # Microsoft identity platform occasionally echoes request fields in
        # descriptions, which could leak credential material indirectly.
        oauth_error = None
        if isinstance(payload, dict):
            inner = payload.get("error")
            if isinstance(inner, str):
                oauth_error = inner
        classification = _OAUTH_ERROR_TO_CLASSIFICATION.get(
            oauth_error or "", AUTH_ERROR_HTTP,
        )
        safe_label = oauth_error if isinstance(oauth_error, str) and oauth_error else "<unknown>"
        raise AuthError(
            classification,
            "Token endpoint rejected request (HTTP {}; oauth_error={})".format(
                status, safe_label,
            ),
        ) from None


__all__ = [
    "AuthError",
    "AUTH_ERROR_CLASSIFICATIONS",
    "AUTH_ERROR_HTTP",
    "AUTH_ERROR_INVALID_CLIENT",
    "AUTH_ERROR_MALFORMED",
    "AUTH_ERROR_MISSING_CONFIG",
    "AUTH_ERROR_NETWORK",
    "CollectorAuthConfig",
    "CollectorTokenProvider",
]