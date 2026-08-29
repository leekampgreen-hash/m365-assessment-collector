"""Closed HTTP opener for the collector's app-only read surface.

The opener is deliberately shared by token acquisition and Graph reads, but
validates each request before it reaches urllib.  It does not retain request
objects, headers, or tokens.
"""
from __future__ import annotations

from typing import Callable, Iterable, Set
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from .models import EndpointSpec


GRAPH_HOST = "graph.microsoft.com"
LOGIN_HOST = "login.microsoftonline.com"


class CollectorHttpOpenError(OSError):
    """A request outside the collector's allowlist was rejected locally."""


class _RejectRedirects(HTTPRedirectHandler):
    """Redirects could move an authenticated request to an untrusted host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _production_open(request, *, timeout=None):
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


class CollectorHttpOpener:
    """Validate collector HTTP requests before forwarding them to urllib."""

    def __init__(
        self,
        specs: Iterable[EndpointSpec],
        tenant_id: str,
        *,
        upstream_open: Callable[..., object] = _production_open,
    ) -> None:
        self._graph_paths = self._allowed_graph_paths(specs)
        self._token_path = "/{}/oauth2/v2.0/token".format(tenant_id)
        self._upstream_open = upstream_open

    @staticmethod
    def _allowed_graph_paths(specs: Iterable[EndpointSpec]) -> Set[str]:
        paths: Set[str] = set()
        for spec in specs:
            if spec.method != "GET" or spec.auth_type != "application":
                raise ValueError("collector inventory must contain app-only GET endpoints")
            parsed = urlsplit(spec.path)
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                raise ValueError("collector endpoint paths must be relative paths")
            if not parsed.path.startswith("/v1.0/"):
                raise ValueError("collector endpoint paths must target /v1.0")
            paths.add(parsed.path)
        return paths

    def __call__(self, request, timeout=None):
        parsed = urlsplit(request.full_url)
        if self._is_token_request(request, parsed) or self._is_graph_request(request, parsed):
            return self._upstream_open(request, timeout=timeout)
        raise CollectorHttpOpenError("collector request rejected by allowlist")

    def _is_token_request(self, request, parsed) -> bool:
        return (
            request.get_method() == "POST"
            and parsed.scheme == "https"
            and parsed.hostname == LOGIN_HOST
            and parsed.port is None
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path == self._token_path
        )

    def _is_graph_request(self, request, parsed) -> bool:
        return (
            request.get_method() == "GET"
            and parsed.scheme == "https"
            and parsed.hostname == GRAPH_HOST
            and parsed.port is None
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and parsed.path in self._graph_paths
            and request.data is None
        )


def build_collector_http_open(
    specs: Iterable[EndpointSpec],
    tenant_id: str,
    *,
    upstream_open: Callable[..., object] = _production_open,
) -> CollectorHttpOpener:
    """Build the read-only, no-redirect HTTP opener for a collector runtime."""
    return CollectorHttpOpener(specs, tenant_id, upstream_open=upstream_open)


__all__ = [
    "CollectorHttpOpenError",
    "CollectorHttpOpener",
    "GRAPH_HOST",
    "LOGIN_HOST",
    "build_collector_http_open",
]
