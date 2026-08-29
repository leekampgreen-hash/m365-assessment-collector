"""Collector orchestration: glue between endpoint spec, transport, paginator, retry.

A ``BaseCollector`` collects one ``EndpointSpec`` end-to-end:

    build initial URL -> request -> (classify -> retry -> request) -> paginate -> CollectionResult

It owns no secrets. The token is supplied through a callable that the
transport invokes at request time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import errors
from .models import CollectionResult, EndpointSpec, utcnow_iso
from .pagination import PaginationResult, Paginator, make_fetch_from_transport
from .retry import RetryDecision, RetryPolicy
from .transport import GraphTransport


TokenProvider = Callable[[], str]


@dataclass
class CollectorRun:
    spec: EndpointSpec
    result: CollectionResult = field(default_factory=CollectionResult)
    records: List[Any] = field(default_factory=list)

    def __post_init__(self):
        if not self.result.endpoint_id:
            self.result.endpoint_id = self.spec.endpoint_id


class BaseCollector:
    """Orchestrate one endpoint collection run with bounded retries."""

    def __init__(
        self,
        spec: EndpointSpec,
        transport: GraphTransport,
        *,
        retry_policy: Optional[RetryPolicy] = None,
        clock: Callable[[], float] = __import__("time").monotonic,
    ):
        if not isinstance(spec, EndpointSpec):
            raise TypeError("spec must be an EndpointSpec")
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.spec = spec
        self.transport = transport
        self.retry_policy = retry_policy or RetryPolicy()
        self._clock = clock

    def collect(self) -> CollectorRun:
        run = CollectorRun(spec=self.spec)
        run.result.started_at = utcnow_iso()
        started = self._clock()

        url = self._initial_url()
        attempts = 0
        last_retry_after: Optional[str] = None
        last_classification: Optional[str] = None
        last_message: Optional[str] = None
        last_http_status: Optional[int] = None
        last_code: Optional[str] = None

        while True:
            fetch = self._make_fetch()
            paginator = Paginator(fetch)
            page_result = paginator.run(url)
            attempts += 1
            last_classification = page_result.error_classification or errors.PASS
            last_message = page_result.error_message
            last_http_status = page_result.http_status
            last_code = page_result.graph_error_code
            last_retry_after = page_result.retry_after

            decision = self.retry_policy.should_retry(
                last_classification or errors.UNKNOWN,
                retry_after=last_retry_after,
                attempts_so_far=attempts,
            )

            if not decision.retry:
                break

            self.retry_policy.wait(decision)
            # Reset URL to the initial URL on retry; the next attempt is a
            # fresh page-1 request (no state carried from the failed run).
            url = self._initial_url()

        # If we retried, the FINAL attempt's pagination result is what we
        # keep. The retry loop above always re-runs from the start, so the
        # last computed ``page_result`` is the authoritative one.
        run.result.pages = page_result.pages
        run.result.rows = page_result.rows
        # Keep the final attempt's complete, source-ordered payload for the
        # runtime handoff. Retrying restarts pagination, so this never
        # combines records from failed attempts.
        run.records = list(page_result.items)
        run.result.pagination_detected = any(bool(p.next_link) for p in page_result.pages_detail)
        run.result.http_status = last_http_status
        run.result.retry_after = last_retry_after
        run.result.graph_error_code = last_code
        run.result.error_classification = last_classification or errors.UNKNOWN
        run.result.status = (
            "PASS"
            if run.result.error_classification == errors.PASS
            else "ERROR"
        )
        run.result.error_message = last_message if run.result.error_classification and run.result.error_classification != errors.PASS else None
        run.result.retry_count = max(0, attempts - 1)
        run.result.completed_at = utcnow_iso()
        run.result.duration = round(self._clock() - started, 3)
        return run

    def _initial_url(self) -> str:
        from .transport import build_endpoint_url
        return build_endpoint_url(
            self.spec.path,
            select=self.spec.select,
            top=self.spec.top,
        )

    def _make_fetch(self):
        return make_fetch_from_transport(self.transport)
