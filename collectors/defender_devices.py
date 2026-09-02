"""Collect Defender device threat state from Intune managed devices."""
from datetime import datetime, timezone
from collectors.core.transport import GraphTransport

REQUIRED_PERMISSION = "DeviceManagementManagedDevices.Read.All"
PATH = "/v1.0/deviceManagement/managedDevices?$select=id,deviceName&$top=100"

def collect_and_persist_defender_devices(*, tenant_id, transport: GraphTransport, connection):
    rows, url = [], PATH
    observed_at = datetime.now(timezone.utc)
    while url:
        payload = transport.get_json(url)
        rows.extend((d.get("id"), tenant_id, d.get("deviceName"), d.get("threatState"), None, observed_at) for d in payload.get("value", []))
        url = payload.get("@odata.nextLink")
    with connection.cursor() as cur:
        for row in rows:
            cur.execute("""INSERT INTO core.defender_threat (device_id,tenant_id,device_name,threat_state,threat_category,observed_at) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,device_id) DO UPDATE SET device_name=EXCLUDED.device_name,threat_state=EXCLUDED.threat_state,threat_category=EXCLUDED.threat_category,observed_at=EXCLUDED.observed_at""", row)
    connection.commit()
    return {"devices_fetched": len(rows), "observed_at": observed_at.isoformat()}
