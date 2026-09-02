"""Collect Intune device enrollment inventory."""
from datetime import datetime, timezone
from collectors.core.transport import GraphTransport

REQUIRED_PERMISSION = "DeviceManagementManagedDevices.Read.All"
PATH = "/v1.0/deviceManagement/managedDevices?$select=id,deviceName,operatingSystem,osVersion,enrolledDateTime,managedDeviceOwnerType,deviceEnrollmentType,userDisplayName&$top=100"

def collect_and_persist_intune_enrollment(*, tenant_id, transport: GraphTransport, connection):
    rows, url = [], PATH
    observed_at = datetime.now(timezone.utc)
    while url:
        payload = transport.get_json(url)
        rows.extend((d.get("id"), tenant_id, d.get("deviceName"), d.get("operatingSystem"), d.get("osVersion"), d.get("enrolledDateTime"), d.get("managedDeviceOwnerType"), d.get("deviceEnrollmentType"), d.get("userDisplayName"), observed_at) for d in payload.get("value", []))
        url = payload.get("@odata.nextLink")
    with connection.cursor() as cur:
        for row in rows:
            cur.execute("""INSERT INTO core.intune_stale_device (device_id,tenant_id,device_name,operating_system,os_version,enrolled_datetime,owner_type,enrollment_type,user_display_name,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,device_id) DO UPDATE SET device_name=EXCLUDED.device_name,operating_system=EXCLUDED.operating_system,os_version=EXCLUDED.os_version,enrolled_datetime=EXCLUDED.enrolled_datetime,owner_type=EXCLUDED.owner_type,enrollment_type=EXCLUDED.enrollment_type,user_display_name=EXCLUDED.user_display_name,observed_at=EXCLUDED.observed_at""", row)
    connection.commit()
    return {"devices_fetched": len(rows), "observed_at": observed_at.isoformat()}
