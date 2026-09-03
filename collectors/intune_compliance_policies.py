from datetime import datetime, timezone

from collectors.core.transport import GraphHttpError, GraphTransport

REQUIRED_PERMISSION = "DeviceManagementConfiguration.Read.All"
PATH = "/v1.0/deviceManagement/deviceCompliancePolicies?$top=100"


def collect_and_persist_intune_compliance_policies(*, tenant_id: int, transport: GraphTransport, connection):
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
            return {"policies_fetched": 0, "observed_at": observed_at.isoformat(), "skipped": True, "skip_reason": "compliance policies unavailable: HTTP {}".format(exc.status)}
        raise
    with connection.cursor() as cur:
        for item in items:
            cur.execute("""INSERT INTO core.intune_compliance_policy (policy_id,tenant_id,display_name,description,platforms,created_datetime,last_modified_datetime,scheduled_actions,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,policy_id) DO UPDATE SET display_name=EXCLUDED.display_name,description=EXCLUDED.description,platforms=EXCLUDED.platforms,created_datetime=EXCLUDED.created_datetime,last_modified_datetime=EXCLUDED.last_modified_datetime,scheduled_actions=EXCLUDED.scheduled_actions,observed_at=EXCLUDED.observed_at""", (item.get("id"), tenant_id, item.get("displayName"), item.get("description"), item.get("platforms"), item.get("createdDateTime"), item.get("lastModifiedDateTime"), item.get("scheduledActionsForRule"), observed_at))
    connection.commit()
    return {"policies_fetched": len(items), "observed_at": observed_at.isoformat()}
