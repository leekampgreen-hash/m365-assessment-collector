"""Dedicated, non-JSON transport for Microsoft 365 usage reports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.parse import urlsplit

GRAPH_REPORTS_BASE = "https://graph.microsoft.com/v1.0/reports/"
REPORT_HOST_SUFFIX = ".office.com"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_BYTES = 25 * 1024 * 1024


def build_usage_report_http_open():
    """Return the canonical opener for Graph's explicit report redirect."""
    from urllib.request import BaseHandler, build_opener

    class RejectRedirects(BaseHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return build_opener(RejectRedirects()).open


class UsageReportError(Exception):
    pass


class UsageReportHttpError(UsageReportError):
    def __init__(self, status: int, *, location: Optional[str] = None, retry_after: Optional[str] = None):
        self.status = status
        self.location = location
        self.retry_after = retry_after
        super().__init__("Usage report HTTP {}".format(status))


class UsageReportRetryExhausted(UsageReportError):
    pass


class UsageReportNetworkError(UsageReportError):
    def __init__(self, exc: BaseException):
        super().__init__("Usage report network error: {}".format(type(exc).__name__))


@dataclass(frozen=True)
class UsageReportResponse:
    content: bytes
    status: int
    content_type: Optional[str]
    report_host: Optional[str]


def _safe_report_path(path: str) -> str:
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("report path must be relative and contain no query or fragment")
    if not parsed.path.startswith("/v1.0/reports/"):
        raise ValueError("report path must target /v1.0/reports/")
    return "https://graph.microsoft.com" + parsed.path


def _is_allowed_download(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https" and parsed.port is None and
        not parsed.username and not parsed.password and not parsed.fragment and
        host.startswith("reports") and host.endswith(REPORT_HOST_SUFFIX)
    )


class UsageReportTransport:
    """Fetch one report, explicitly handling Graph's single 302 response."""

    def __init__(self, token_provider: Callable[[], str], *, url_open: Optional[Callable[..., Any]] = None,
                 timeout: float = DEFAULT_TIMEOUT, max_bytes: int = DEFAULT_MAX_BYTES):
        if token_provider is None:
            raise ValueError("token_provider is required")
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("timeout and max_bytes must be positive")
        self._token_provider = token_provider
        self._url_open = url_open or build_usage_report_http_open()
        self._timeout = float(timeout)
        self._max_bytes = int(max_bytes)

    def get(self, path: str, *, params: Optional[Mapping[str, Any]] = None) -> UsageReportResponse:
        url = _safe_report_path(path)
        if params:
            if "period" in params:
                raise ValueError("usage report period must be part of the canonical function path")
            from urllib.parse import urlencode
            url += "?" + urlencode({k: str(v) for k, v in params.items() if v is not None})
        # Keep urllib's request implementation out of module import paths so
        # dry-run Scenario Agent tests do not observe a Graph HTTP import.
        from urllib.request import Request
        token = self._token_provider()
        request = Request(url, headers={"Authorization": "Bearer " + token, "Accept": "text/csv, application/octet-stream"}, method="GET")
        try:
            with self._url_open(request, timeout=self._timeout) as response:
                status = int(getattr(response, "status", 200))
                headers = dict(getattr(response, "headers", {}))
                if status not in (200, 302):
                    raise UsageReportHttpError(status, retry_after=headers.get("Retry-After") or headers.get("retry-after"))
                if status == 302:
                    location = headers.get("Location") or headers.get("location")
                    if not location or not _is_allowed_download(location):
                        raise UsageReportHttpError(status)
                    download_request = Request(location, headers={"Accept": "text/csv, application/octet-stream"}, method="GET")
                    with self._url_open(download_request, timeout=self._timeout) as download:
                        return self._read(download, urlsplit(location).hostname)
                return self._read(response, "graph.microsoft.com")
        except UsageReportError:
            raise
        except (TimeoutError, OSError) as error:
            if type(error).__name__ == "HTTPError":
                raise UsageReportHttpError(getattr(error, "code", 0)) from None
            raise UsageReportNetworkError(error) from None

    def _read(self, response: Any, host: str) -> UsageReportResponse:
        content_length = getattr(response, "headers", {}).get("Content-Length")
        if content_length and int(content_length) > self._max_bytes:
            raise UsageReportHttpError(413)
        content = response.read(self._max_bytes + 1)
        if len(content) > self._max_bytes:
            raise UsageReportHttpError(413)
        headers = dict(getattr(response, "headers", {}))
        return UsageReportResponse(content=content, status=200,
                                   content_type=headers.get("Content-Type"), report_host=host)
