from datetime import datetime, timedelta, timezone
from typing import Any

from collectors.core.transport import GraphTransport

SOURCES = {
    "DEF-P02": {"key": "defender_o365", "permission": "SecurityEvents.Read.All", "path": "/v1.0/security/alerts_v2?$filter=serviceSource%20eq%20%20%27microsoftDefenderForOffice365%27", "table": "core.defender_o365_alert"},
    "DEF-P03": {"key": "defender_cloud_app", "permission": "SecurityEvents.Read.All", "path": "/v1.0/security/alerts_v2?$filter=serviceSource%20eq%20%20%27microsoftCloudAppSecurity%27", "table": "core.defender_cloud_app_alert"},
    "DLP-P01": {"key": "dlp_alerts", "permission": "SecurityEvents.Read.All", "path": "/v1.0/security/alerts_v2?$filter=category%20eq%20%27DataLossPrevention%27", "table": "core.dlp_alert"},
    "DLP-P02": {"key": "dlp_labels", "permission": "InformationProtectionPolicy.Read", "path": "/v1.0/informationProtection/policy/labels", "table": "core.dlp_label"},
}


def normalize_record(source_id: str, item: dict[str, Any], tenant_id: int, observed_at: datetime) -> dict[str, Any]:
    name = item.get("title") or item.get("displayName") or item.get("name")
    category = item.get("category") or item.get("threatType") or item.get("sensitivityType") or item.get("serviceSource")
    if source_id == "DEF-P02":
        category = item.get("threatType") or category
    if source_id == "DEF-P03":
        name = item.get("appDisplayName") or item.get("application") or item.get("appName") or name
    if source_id == "DLP-P01":
        name = item.get("policyName") or item.get("policy") or name
    return {"source_id": str(item.get("id") or item.get("name") or ""), "tenant_id": tenant_id, "name": name, "status": item.get("status") or item.get("state"), "severity": item.get("severity"), "category": category, "observed_at": observed_at, "created_at": item.get("createdDateTime"), "updated_at": item.get("lastUpdateDateTime") or item.get("lastModifiedDateTime")}




def aggregate_records(source_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    severities = {key: 0 for key in ("Low", "Medium", "High", "Informational")}
    if source_id == "DLP-P01":
        severities = {key: 0 for key in ("Low", "Medium", "High")}
    for item in records:
        value = str(item.get("severity") or "")
        if value in severities:
            severities[value] += 1
    result = {"total": len(records), "severity": severities}
    if source_id == "DEF-P02":
        result["threat_types"] = {key: sum(1 for item in records if str(item.get("category") or "") == key) for key in ("Malware", "Phishing", "Spam")}
    if source_id == "DEF-P03":
        result["top_apps_flagged"] = _top_values(records, ("appDisplayName", "application", "appName"))
    if source_id == "DLP-P01":
        result["top_policies"] = _top_values(records, ("policyName", "policy", "name"))
    return result


def _top_values(records: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in records:
        value = next((item.get(key) for key in keys if item.get(key)), None)
        if value:
            counts[str(value)] = counts.get(str(value), 0) + 1
    return [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:10]]


def collect_and_persist(source_id: str, *, tenant_id: int, transport: GraphTransport, connection: Any) -> dict[str, Any]:
    source = SOURCES[source_id]
    observed_at = datetime.now(timezone.utc)
    raw: list[dict[str, Any]] = []
    url = source["path"]
    try:
        while url:
            payload = transport.get_json(url)
            raw.extend(item for item in payload.get("value", []) if isinstance(item, dict))
            url = payload.get("@odata.nextLink")
    except Exception:
        raw = []
    records = [normalize_record(source_id, item, tenant_id, observed_at) for item in raw]
    with connection.cursor() as cursor:
        for record in records:
            cursor.execute("INSERT INTO {} (source_id,tenant_id,name,status,severity,category,observed_at,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,source_id) DO UPDATE SET name=EXCLUDED.name,status=EXCLUDED.status,severity=EXCLUDED.severity,category=EXCLUDED.category,observed_at=EXCLUDED.observed_at,created_at=EXCLUDED.created_at,updated_at=EXCLUDED.updated_at".format(source["table"]), tuple(record.values()))
    connection.commit()
    return {"source": source["key"], "records": len(records), "observed_at": observed_at.isoformat()}


def collect_and_persist_batch2(source: str, **kwargs: Any) -> dict[str, Any]:
    source_id = source if source in SOURCES else next(key for key, value in SOURCES.items() if value["key"] == source)
    return collect_and_persist(source_id, **kwargs)


def collect_and_persist_defender_alerts(**kwargs: Any) -> dict[str, Any]:
    return collect_and_persist("DEF-P02", **kwargs)


def collect_and_persist_defender_incidents(**kwargs: Any) -> dict[str, Any]:
    return collect_and_persist("DEF-P03", **kwargs)


def collect_and_persist_dlp_policies(**kwargs: Any) -> dict[str, Any]:
    return collect_and_persist("DLP-P01", **kwargs)


def collect_and_persist_dlp_incidents(**kwargs: Any) -> dict[str, Any]:
    return collect_and_persist("DLP-P02", **kwargs)
