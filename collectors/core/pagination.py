"""Reusable pagination driver.

A paginator takes a transport and an initial URL. It iterates:

    request -> parse value[] -> inspect @odata.nextLink -> next URL ...

Until either:
- the response has no ``@odata.nextLink`` (success / end),
- the transport raises ``GraphHttpError`` or ``GraphNetworkError``.

The paginator does NOT classify HTTP errors itself; it relies on
``collectors.core.errors`` for that. It does however populate
``PaginationResult.http_status`` and ``error_classification`` so the
orchestrator can drive the retry policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import errors
from .transport import GraphHttpError, GraphNetworkError


FetchFn = Callable[[str], Dict[str, Any]]


@dataclass
class Page:
    index: int
    items: List[Any]
    next_link: Optional[str] = None


@dataclass
class PaginationResult:
    pages: int = 0
    rows: int = 0
    items: List[Any] = field(default_factory=list)
    next_link: Optional[str] = None
    http_status: Optional[int] = None
    error_classification: Optional[str] = None
    error_message: Optional[str] = None
    retry_after: Optional[str] = None
    graph_error_code: Optional[str] = None
    pages_detail: List[Page] = field(default_factory=list)


PaginationHandler = Callable[[Page], None]


class Paginator:
    """Iterate a Graph collection endpoint using ``@odata.nextLink``.

    ``fetch`` is a callable ``(url: str) -> dict`` that performs a
    single HTTP request and returns the parsed JSON body. The paginator
    follows ``@odata.nextLink`` until exhausted.
    """

    def __init__(self, fetch: FetchFn):
        self._fetch = fetch

    def run(self, initial_url: str, *, on_page: Optional[PaginationHandler] = None) -> PaginationResult:
        result = PaginationResult()
        url: Optional[str] = initial_url
        while url is not None:
            try:
                payload = self._fetch(url)
                status: Optional[int] = 200
            except GraphHttpError as error:
                result.http_status = error.status
                result.error_classification = errors.classify_http_status(error.status)
                result.error_message = error.message
                result.retry_after = error.retry_after()
                result.graph_error_code = error.code
                return result
            except GraphNetworkError as error:
                result.http_status = None
                result.error_classification = errors.NETWORK_ERROR
                result.error_message = str(error)
                return result

            result.http_status = status
            if not isinstance(payload, dict):
                result.error_classification = errors.API_ERROR
                result.error_message = "Graph response was not a JSON object"
                return result

            if "value" not in payload or not isinstance(payload["value"], list):
                result.error_classification = errors.API_ERROR
                result.error_message = "Graph response field 'value' must be a list"
                return result
            items = list(payload["value"])
            result.pages += 1
            result.rows += len(items)
            result.items.extend(items)
            next_link = payload.get("@odata.nextLink")
            if next_link is not None and not isinstance(next_link, str):
                result.error_classification = errors.API_ERROR
                result.error_message = "Graph response field '@odata.nextLink' must be a string"
                return result
            page = Page(
                index=result.pages,
                items=items,
                next_link=next_link,
            )
            result.pages_detail.append(page)
            if on_page is not None:
                on_page(page)

            url = page.next_link

        result.error_classification = errors.PASS if result.http_status and 200 <= result.http_status < 300 else errors.API_ERROR
        return result


def make_fetch_from_transport(transport) -> FetchFn:
    """Build a ``(url) -> dict`` callable from a ``GraphTransport``.

    Kept separate from ``Paginator`` so the paginator can be unit-tested
    with plain dicts instead of a full transport.
    """

    def _fetch(url: str) -> Dict[str, Any]:
        return transport.get_json(url)

    return _fetch
