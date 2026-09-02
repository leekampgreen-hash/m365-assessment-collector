"""Collect Entra device inventory for stale-device analysis."""
from datetime import datetime, timezone
from collectors.core.transport import GraphTransport

REQUIRED_PERMISSION = "Device.Read.All"
PATH = "/v1.0/devices?$select=id,displayName,operatingSystem,operatingSystemVersion,approximateLastSignInDateTime,isManaged,isCompliant,trustType&$top=100"

def collect_and_persist_entra_stale_devices(*, tenant_id, transport: GraphTransport, connection):
    rows, url = [], PATH
    observed_at = datetime.now(timezone.utc)
    while url:
        payload = transport.get_json(url)
        rows.extend((d.get("id"), tenant_id, d.get("displayName"), d.get("operatingSystem"), d.get("operatingSystemVersion"), d.get("approximateLastSignInDateTime"), d.get("isManaged"), d.get("isCompliant"), d.get("trustType"), observed_at) for d in payload.get("value", []))
        url = payload.get("@odata.nextLink")
    with connection.cursor() as cur:
        for row in rows:
            cur.execute("""INSERT INTO core.entra_device (device_id,tenant_id,display_name,operating_system,os_version,last_signin_datetime,is_managed,is_compliant,trust_type,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,device_id) DO UPDATE SET display_name=EXCLUDED.display_name,operating_system=EXCLUDED.operating_system,os_version=EXCLUDED.os_version,last_signin_datetime=EXCLUDED.last_signin_datetime,is_managed=EXCLUDED.is_managed,is_compliant=EXCLUDED.is_compliant,trust_type=EXCLUDED.trust_type,observed_at=EXCLUDED.observed_at""", row)
    connection.commit()
    return {"devices_fetched": len(rows), "observed_at": observed_at.isoformat()}
