from datetime import datetime, timezone

from collectors.core.transport import GraphHttpError, GraphTransport

REQUIRED_PERMISSION = "DeviceManagementApps.Read.All"
PATH = "/v1.0/deviceAppManagement/mobileApps?$top=100"


def collect_and_persist_intune_mobile_apps(*, tenant_id: int, transport: GraphTransport, connection):
    observed_at = datetime.now(timezone.utc)
    items = []
    url = PATH
    try:
        while url:
            payload = transport.get_json(url)
            items.extend(payload.get("value", []))
            url = payload.get("@odata.nextLink")
    except GraphHttpError as exc:
        if exc.status in (403, 404):
            return {"apps_fetched": 0, "observed_at": observed_at.isoformat(), "skipped": True, "skip_reason": "mobile apps unavailable: HTTP {}".format(exc.status)}
        raise
    with connection.cursor() as cur:
        for item in items:
            cur.execute("""INSERT INTO core.intune_mobile_app (app_id,tenant_id,display_name,publisher,app_type,platform,description,is_featured,publishing_state,created_datetime,last_modified_datetime,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,app_id) DO UPDATE SET display_name=EXCLUDED.display_name,publisher=EXCLUDED.publisher,app_type=EXCLUDED.app_type,platform=EXCLUDED.platform,description=EXCLUDED.description,is_featured=EXCLUDED.is_featured,publishing_state=EXCLUDED.publishing_state,created_datetime=EXCLUDED.created_datetime,last_modified_datetime=EXCLUDED.last_modified_datetime,observed_at=EXCLUDED.observed_at""", (item.get("id"), tenant_id, item.get("displayName"), item.get("publisher"), item.get("@odata.type", "").split(".")[-1], item.get("applicableArchitectures"), item.get("description"), item.get("isFeatured"), item.get("publishingState"), item.get("createdDateTime"), item.get("lastModifiedDateTime"), observed_at))
    connection.commit()
    return {"apps_fetched": len(items), "observed_at": observed_at.isoformat()}
