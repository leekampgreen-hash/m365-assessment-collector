"""Microsoft Graph HTTP transport abstraction.

Responsibilities:
- Issue GET requests against Microsoft Graph.
- Attach the ``Authorization`` header via a caller-supplied token
  callback (``token_provider``). The framework never stores or logs
  tokens; the callback is invoked at request time.
- Apply a timeout.
- Parse JSON responses and raise ``GraphHttpError`` on non-success
  responses so the orchestrator can classify them deterministically.

Security:
- No token or secret value is stored on this object.
- No ``Authorization`` header value is ever logged.
- Error messages from Graph are propagated but never include secrets.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

# ``urlopen`` is injected for tests; in production it's stdlib ``urlopen``.
UrlOpen = Callable[..., Any]
TokenProvider = Callable[[], str]


GRAPH_BASE_V1 = "https://graph.microsoft.com/v1.0"
DEFAULT_TIMEOUT = 30


class GraphTransportError(Exception):
    """Base class for transport-level errors."""


class GraphHttpError(GraphTransportError):
    """A non-success HTTP response from Microsoft Graph."""

    def __init__(self, status: int, code: Optional[str], message: Optional[str], headers: Mapping[str, str]):
        self.status = status
        self.code = code
        self.message = message
        self.headers = dict(headers) if headers else {}
        # Never include any header value that could be a token.
        safe_headers = {k: v for k, v in self.headers.items() if k.lower() == "retry-after"}
        super().__init__(
            "Graph HTTP {}{}".format(
                status,
                " " + str(code) if code else "",
            )
        )
        self._safe_headers = safe_headers

    def retry_after(self) -> Optional[str]:
        return self._safe_headers.get("Retry-After")


class GraphNetworkError(GraphTransportError):
    """A transport-level (DNS, socket, timeout) failure."""

    def __init__(self, exc: BaseException):
        self.original_exc_type = type(exc).__name__
        # str(exc) is safe; Graph/urllib network messages never carry secrets.
        super().__init__("Graph network error: {}: {}".format(type(exc).__name__, str(exc)))


@dataclass
class Response:
    status: int
    payload: Optional[Dict[str, Any]]
    headers: Dict[str, str]


def _normalize_path(path: str) -> str:
    """Allow callers to pass either ``/v1.0/users`` or ``users``."""
    if path.startswith("https://") or path.startswith("http://"):
        return path
    normalized = "/" + path.lstrip("/")
    if normalized.startswith("/v1.0/"):
        normalized = normalized[len("/v1.0"):]
    return GRAPH_BASE_V1.rstrip("/") + normalized


def _build_query(params: Optional[Mapping[str, Any]]) -> str:
    if not params:
        return ""
    flat: Dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, list):
            # Join list values with comma (matches Graph $select syntax and
            # the prior Discovery Agent behavior).
            flat[key] = ",".join(str(v) for v in value)
        elif isinstance(value, bool):
            flat[key] = "true" if value else "false"
        else:
            flat[key] = str(value)
    return urlencode(flat, doseq=False)


class GraphTransport:
    """Reusable Microsoft Graph HTTP transport.

    Use ``get(url, params=...)`` to issue a single request. The transport
    owns the request lifecycle and returns a ``Response`` object on
    success or raises a structured exception on failure.
    """

    def __init__(
        self,
        token_provider: TokenProvider,
        *,
        url_open: UrlOpen,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        if token_provider is None:
            raise ValueError("token_provider is required")
        self._token_provider = token_provider
        self._url_open = url_open
        self._timeout = timeout

    @property
    def timeout(self) -> float:
        return self._timeout

    def get(self, url: str, *, params: Optional[Mapping[str, Any]] = None) -> Response:
        """Issue a GET request.

        ``url`` may be either a full https:// URL (e.g. an
        ``@odata.nextLink``) or a relative path like ``/v1.0/users``.
        """
        url = _normalize_path(url)
        query = _build_query(params)
        if query:
            url = url + ("&" if "?" in url else "?") + query

        token = self._token_provider()
        request = Request(
            url,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with self._url_open(request, timeout=self._timeout) as response:
                raw = response.read()
                headers = dict(response.headers)
        except HTTPError as error:
            raw = error.read()
            headers = dict(error.headers)
            code, message = _parse_error_payload(raw)
            raise GraphHttpError(error.code, code, message, headers) from None
        except (URLError, TimeoutError, OSError) as error:
            raise GraphNetworkError(error) from None

        payload: Optional[Dict[str, Any]]
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError:
            decoded = ""
        if not decoded:
            payload = {}
        else:
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError:
                payload = None
            else:
                payload = parsed if isinstance(parsed, dict) else {"value": parsed}
        # Caller asked for ``status`` from the transport; success branch.
        status = 200
        return Response(status=status, payload=payload, headers=headers)

    def get_json(self, url: str, *, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Convenience wrapper that returns just the parsed JSON payload."""
        response = self.get(url, params=params)
        return response.payload or {}


def _parse_error_payload(raw: bytes) -> tuple[Optional[str], Optional[str]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    error = payload.get("error")
    if isinstance(error, dict):
        return error.get("code"), error.get("message")
    return None, None


def build_endpoint_url(path: str, *, select: Optional[list] = None, top: Optional[int] = None) -> str:
    """Build a Graph URL from a path and optional query parameters."""
    url = _normalize_path(path)
    query: Dict[str, Any] = {}
    if select:
        # Comma-separated, exactly as Graph expects for $select.
        query["$select"] = ",".join(str(v) for v in select)
    if top is not None:
        query["$top"] = str(top)
    if query:
        url = url + ("&" if "?" in url else "?") + urlencode(query, doseq=False)
    return url