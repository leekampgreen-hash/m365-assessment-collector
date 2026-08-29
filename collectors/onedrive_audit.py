from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

from collectors.core.auth import CollectorAuthConfig, CollectorTokenProvider
from collectors.persistence import persist_onedrive_high_value_audit_batch

MANAGEMENT_RESOURCE = "https://manage.office.com"
CONTENT_TYPE = "Audit.SharePoint"
PERMISSION = "ActivityFeed.Read"

class AuditTransportError(Exception):
    def __init__(self, classification: str, message: str):
        self.classification = classification
        super().__init__(message)

@dataclass(frozen=True)
class AuditContent:
    content_id: str
    content_created: str | None
    content_expiration: str | None
    records: tuple[Mapping[str, Any], ...]

class ManagementActivityTransport:
    def __init__(self, tenant_id: str, token_provider: Callable[[], str], *, url_open: Callable[..., Any], timeout: float = 60.0):
        self.tenant_id, self.token_provider, self.url_open, self.timeout = tenant_id, token_provider, url_open, timeout
        self.base = f"{MANAGEMENT_RESOURCE}/api/v1.0/{tenant_id}/activity/feed"

    def _get(self, url: str) -> Any:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "manage.office.com" or parsed.username or parsed.password:
            raise AuditTransportError("SOURCE_FAILURE", "Management Activity URL rejected")
        request = Request(url, headers={"Authorization": "Bearer " + self.token_provider(), "Accept": "application/json"}, method="GET")
        try:
            response = self.url_open(request, timeout=self.timeout)
            status = int(getattr(response, "status", 200))
            if status != 200:
                raise AuditTransportError("SOURCE_FAILURE", "Management Activity API returned HTTP {}".format(status))
            return json.loads(response.read().decode("utf-8"))
        except AuditTransportError:
            raise
        except Exception as exc:
            raise AuditTransportError("SOURCE_FAILURE", "Management Activity transport failed: {}".format(type(exc).__name__)) from None

    def subscription(self) -> Mapping[str, Any]:
        data = self._get(self.base + "/subscriptions/list")
        matches = [x for x in data if x.get("contentType") == CONTENT_TYPE] if isinstance(data, list) else []
        if not matches or str(matches[0].get("status", "")).lower() != "enabled":
            raise AuditTransportError("SUBSCRIPTION_UNAVAILABLE", "Audit.SharePoint subscription is unavailable")
        return matches[0]

    def collect(self, start: datetime, end: datetime) -> tuple[AuditContent, ...]:
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            raise AuditTransportError("SCHEMA_CONTRACT_FAILURE", "bounded UTC window is invalid")
        url = self.base + "/subscriptions/content?" + urlencode({"contentType": CONTENT_TYPE, "startTime": start.astimezone(timezone.utc).isoformat(), "endTime": end.astimezone(timezone.utc).isoformat()})
        out = []
        while url:
            data = self._get(url)
            for item in data if isinstance(data, list) else []:
                blob = self._get(item["contentUri"])
                records = tuple(blob if isinstance(blob, list) else ())
                out.append(AuditContent(item.get("contentId", ""), item.get("contentCreated"), item.get("contentExpiration"), records))
            url = data[0].get("nextPageUri") if isinstance(data, list) and data and data[0].get("nextPageUri") else None
        return tuple(out)


def collect_and_persist_onedrive_audit(
    *,
    tenant_id: int,
    auth_config: CollectorAuthConfig,
    connection: Any,
    url_open: Callable[..., Any],
    start: datetime,
    end: datetime,
    collected_at: str,
) -> Mapping[str, int]:
    provider = CollectorTokenProvider(
        auth_config,
        http_open=url_open,
        resource=MANAGEMENT_RESOURCE,
    )
    transport = ManagementActivityTransport(
        auth_config.tenant_id,
        provider.get_token,
        url_open=url_open,
    )
    transport.subscription()
    contents = transport.collect(start, end)
    records = [record for content in contents for record in content.records]
    normalized = [
        row for record in records
        if (row := normalize_onedrive_audit_record(record, tenant_id, collected_at)) is not None
    ]
    result = persist_onedrive_high_value_audit_batch(
        connection, normalized, trusted_tenant_id=tenant_id,
    )
    return {
        "content_entries": len(contents),
        "blobs_retrieved": len(contents),
        "records_parsed": len(records),
        "normalized": len(normalized),
        "persisted": result.inserted,
        "duplicates": result.duplicate_skips,
    }


def normalize_onedrive_audit_record(record: Mapping[str, Any], tenant_id: int, collected_at: str) -> Mapping[str, Any] | None:
    if record.get("Workload") != "OneDrive" or not record.get("Id") or not isinstance(record.get("CreationTime"), str):
        return None
    operation = record.get("Operation")
    if operation == "AnonymousLinkCreated": category, external, anonymous = "EXTERNAL_SHARING", True, True
    elif operation in ("SharingInvitationCreated", "SharingSet") and record.get("TargetUserOrGroupType") == "Guest": category, external, anonymous = "EXTERNAL_SHARING", True, False
    elif operation == "FileMalwareDetected": category, external, anonymous = "MALWARE_DETECTED", None, False
    else: return None
    try: datetime.fromisoformat(record["CreationTime"].replace("Z", "+00:00"))
    except ValueError: return None
    return {"tenant_id": tenant_id, "audit_record_id": record["Id"], "event_time": record["CreationTime"], "operation": operation, "workload": "OneDrive", "record_type": record.get("RecordType"), "actor_upn": record.get("UserId"), "event_category": category, "external_flag": external, "anonymous_flag": anonymous, "collected_at": collected_at, "retention_class": "LONG", **{k: record.get(src) for k, src in {"client_ip":"ClientIP","object_id":"ObjectId","site_url":"SiteUrl","source_relative_url":"SourceRelativeUrl","source_file_name":"SourceFileName","unique_sharing_id":"UniqueSharingId","target_user_or_group_name":"TargetUserOrGroupName","target_user_or_group_type":"TargetUserOrGroupType"}.items()}}
