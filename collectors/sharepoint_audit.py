from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

from collectors.core.auth import CollectorAuthConfig, CollectorTokenProvider
from collectors.core.retry import RetryPolicy
from collectors.persistence import (
    advance_onedrive_audit_checkpoint,
    get_onedrive_audit_checkpoint,
    persist_sharepoint_high_value_audit_batch,
)
from collectors.workloads.security_service.adapters import adapt_sharepoint_audit_logs

MANAGEMENT_RESOURCE = "https://manage.office.com"
CONTENT_TYPE = "Audit.SharePoint"
PERMISSION = "ActivityFeed.Read"
DEFAULT_OVERLAP = timedelta(hours=2)
DEFAULT_INITIAL_LOOKBACK = timedelta(hours=4)
DEFAULT_MAX_WINDOW = timedelta(hours=24)
DEFAULT_MAX_PAGES = 1000
DEFAULT_MAX_ATTEMPTS = 4

class AuditTransportError(Exception):
    def __init__(self, classification: str, message: str, *, retry_after: str | None = None):
        self.classification = classification
        self.retry_after = retry_after
        super().__init__(message)

@dataclass(frozen=True)
class AuditContent:
    content_id: str
    content_created: str | None
    content_expiration: str | None
    records: tuple[Mapping[str, Any], ...]

@dataclass
class AuditMetrics:
    windows_attempted: int = 0
    pages_processed: int = 0
    content_entries: int = 0
    blobs_attempted: int = 0
    blobs_succeeded: int = 0
    blobs_failed: int = 0
    records_parsed: int = 0
    sharepoint_records: int = 0
    high_value_candidates: int = 0
    normalized_events: int = 0
    inserted: int = 0
    duplicate_skips: int = 0
    records_dropped_out_of_scope: int = 0
    malformed_records: int = 0
    retries: int = 0
    checkpoint_before: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    overlap_seconds: int = 0
    checkpoint_proposed: str | None = None
    checkpoint_after: str | None = None
    checkpoint_advanced: str = "NO"
    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d.update(content_entries_discovered=d["content_entries"], pages_processed=d["pages_processed"], blobs_retrieved=d["blobs_succeeded"], normalized=d["normalized_events"], persisted=d["inserted"], duplicates=d["duplicate_skips"])
        return d

def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "window must use UTC")
    result = value.astimezone(timezone.utc)
    if result.tzinfo != timezone.utc:
        raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "window must use UTC")
    return result

def bounded_windows(start: datetime, end: datetime, maximum: timedelta = DEFAULT_MAX_WINDOW) -> tuple[tuple[datetime, datetime], ...]:
    start, end = _utc(start), _utc(end)
    if end <= start or maximum <= timedelta(0):
        raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "bounded UTC window is invalid")
    windows = []
    cursor = start
    while cursor < end:
        finish = min(cursor + maximum, end)
        windows.append((cursor, finish))
        cursor = finish
    return tuple(windows)

class ManagementActivityTransport:
    def __init__(self, tenant_id: str, token_provider: Callable[[], str], *, url_open: Callable[..., Any], timeout: float = 60.0, retry_policy: RetryPolicy | None = None, max_pages: int = DEFAULT_MAX_PAGES, sleep: Callable[[float], None] = time.sleep):
        self.tenant_id, self.token_provider, self.url_open, self.timeout = tenant_id, token_provider, url_open, timeout
        self.base = f"{MANAGEMENT_RESOURCE}/api/v1.0/{tenant_id}/activity/feed"
        self.retry_policy, self.max_pages, self.sleep = retry_policy or RetryPolicy(max_retries=DEFAULT_MAX_ATTEMPTS - 1), max_pages, sleep
        self.retries = 0

    def _get(self, url: str) -> Any:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "manage.office.com" or parsed.username or parsed.password:
            raise AuditTransportError("SOURCE_FAILURE", "Management Activity URL rejected")
        attempts = 0
        while True:
            attempts += 1
            try:
                request = Request(url, headers={"Authorization": "Bearer " + self.token_provider(), "Accept": "application/json"}, method="GET")
                response = self.url_open(request, timeout=self.timeout)
                status = int(getattr(response, "status", 200))
                if status == 401: raise AuditTransportError("PERMISSION_REQUIRED", "Management Activity authentication failed")
                if status == 403: raise AuditTransportError("PERMISSION_REQUIRED", "ActivityFeed.Read permission required")
                if status == 429: raise AuditTransportError("THROTTLED", "Management Activity throttled", retry_after=getattr(response, "headers", {}).get("Retry-After"))
                if 500 <= status < 600: raise AuditTransportError("SOURCE_FAILURE", "Management Activity transient source failure")
                if status != 200: raise AuditTransportError("SOURCE_FAILURE", "Management Activity API returned HTTP {}".format(status))
                return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                classification = "PERMISSION_REQUIRED" if exc.code in (401, 403) else "THROTTLED" if exc.code == 429 else "SOURCE_FAILURE" if exc.code >= 500 else "SOURCE_FAILURE"
                error = AuditTransportError(classification, "Management Activity HTTP failure", retry_after=exc.headers.get("Retry-After") if exc.headers else None)
            except AuditTransportError as exc:
                error = exc
            except (TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                error = AuditTransportError("SCHEMA_CONTRACT_FAILURE" if isinstance(exc, (ValueError, json.JSONDecodeError)) else "SOURCE_FAILURE", "Management Activity response failure")
            decision = self.retry_policy.should_retry(error.classification, retry_after=error.retry_after, attempts_so_far=attempts)
            if not decision.retry:
                if error.classification in ("THROTTLED", "SOURCE_FAILURE") and attempts > 1:
                    error = AuditTransportError("RETRY_EXHAUSTED", "Management Activity retry budget exhausted")
                raise error
            self.retries += 1
            self.retry_policy.wait(decision)

    def subscription(self) -> Mapping[str, Any]:
        data = self._get(self.base + "/subscriptions/list")
        matches = [x for x in data if isinstance(x, Mapping) and x.get("contentType") == CONTENT_TYPE] if isinstance(data, list) else []
        if not matches or str(matches[0].get("status", "")).lower() != "enabled":
            raise AuditTransportError("SUBSCRIPTION_UNAVAILABLE", "Audit.SharePoint subscription is unavailable")
        return matches[0]

    def collect(self, start: datetime, end: datetime, metrics: AuditMetrics | None = None) -> tuple[AuditContent, ...]:
        start, end = _utc(start), _utc(end)
        if end <= start: raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "bounded UTC window is invalid")
        url = self.base + "/subscriptions/content?" + urlencode({"contentType": CONTENT_TYPE, "startTime": start.isoformat(), "endTime": end.isoformat()})
        out, seen_pages, seen_blobs = [], set(), set()
        while url:
            if url in seen_pages: raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "cyclic NextPageUri")
            if len(seen_pages) >= self.max_pages: raise AuditTransportError("SOURCE_FAILURE", "pagination page bound exceeded")
            seen_pages.add(url)
            data = self._get(url)
            if not isinstance(data, list): raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "content listing is not an array")
            if metrics: metrics.pages_processed += 1
            for item in data:
                if not isinstance(item, Mapping) or not item.get("contentUri"): raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "malformed content entry")
                content_id = str(item.get("contentId") or "")
                uri = str(item["contentUri"])
                if content_id and content_id in seen_blobs: continue
                if content_id: seen_blobs.add(content_id)
                if metrics: metrics.content_entries += 1; metrics.blobs_attempted += 1
                try: blob = self._get(uri)
                except AuditTransportError:
                    if metrics: metrics.blobs_failed += 1
                    raise
                if not isinstance(blob, list): raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "content blob is not an array")
                if metrics: metrics.blobs_succeeded += 1; metrics.records_parsed += len(blob)
                out.append(AuditContent(content_id, item.get("contentCreated"), item.get("contentExpiration"), tuple(x for x in blob if isinstance(x, Mapping))))
            next_uri = data[0].get("nextPageUri") if data else None
            if next_uri is not None and (not isinstance(next_uri, str) or not next_uri.startswith("https://manage.office.com/")):
                raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "malformed NextPageUri")
            url = next_uri
        return tuple(out)

def collect_and_persist_sharepoint_audit(*, tenant_id: int, auth_config: CollectorAuthConfig, connection: Any, url_open: Callable[..., Any], start: datetime, end: datetime, collected_at: str, collection_run_id: int | None = None, endpoint_run_id: int | None = None, overlap: timedelta = DEFAULT_OVERLAP, max_window: timedelta = DEFAULT_MAX_WINDOW, dry_run: bool = False, initial_lookback: timedelta = DEFAULT_INITIAL_LOOKBACK) -> Mapping[str, Any]:
    metrics = AuditMetrics()
    if overlap < timedelta(0) or overlap > max_window or initial_lookback <= timedelta(0) or initial_lookback > max_window:
        raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "checkpoint bounds are invalid")
    checkpoint = get_onedrive_audit_checkpoint(
        connection, tenant_id=tenant_id, collector_id="sharepoint_audit"
    )
    target_end = _utc(end)
    requested_start = _utc(start)
    effective_start = _utc(checkpoint - overlap) if checkpoint else requested_start
    if checkpoint is None and target_end - effective_start > initial_lookback:
        effective_start = target_end - initial_lookback
    metrics.checkpoint_before = checkpoint.isoformat() if checkpoint else None
    metrics.effective_start = effective_start.isoformat()
    metrics.effective_end = target_end.isoformat()
    metrics.overlap_seconds = int(overlap.total_seconds())
    provider = CollectorTokenProvider(auth_config, http_open=url_open, resource=MANAGEMENT_RESOURCE)
    transport = ManagementActivityTransport(auth_config.tenant_id, provider.get_token, url_open=url_open)
    transport.subscription()
    all_contents = []
    for window_start, window_end in bounded_windows(effective_start, target_end, max_window):
        metrics.windows_attempted += 1
        all_contents.extend(transport.collect(window_start, window_end, metrics))
    records = [record for content in all_contents for record in content.records]
    metrics.sharepoint_records = sum(record.get("Workload") == "SharePoint" for record in records)
    normalized = adapt_sharepoint_audit_logs(
        records,
        {
            "tenant_id": tenant_id,
            "collection_run_id": collection_run_id,
            "endpoint_run_id": endpoint_run_id,
            "collected_at": collected_at,
            "retention_class": "LONG",
        },
    )
    metrics.high_value_candidates = len(normalized)
    metrics.normalized_events = len(normalized)
    metrics.records_dropped_out_of_scope = len(records) - len(normalized)
    metrics.checkpoint_proposed = target_end.isoformat()
    if not dry_run:
        result = persist_sharepoint_high_value_audit_batch(
            connection, normalized, trusted_tenant_id=tenant_id
        )
        metrics.inserted, metrics.duplicate_skips = result.inserted, result.duplicate_skips
        advance_onedrive_audit_checkpoint(
            connection,
            tenant_id=tenant_id,
            checkpoint_at=target_end,
            collector_id="sharepoint_audit",
        )
        metrics.checkpoint_advanced = "YES"
        metrics.checkpoint_after = target_end.isoformat()
    else:
        metrics.checkpoint_after = metrics.checkpoint_before
    metrics.retries = transport.retries
    return metrics.as_dict()