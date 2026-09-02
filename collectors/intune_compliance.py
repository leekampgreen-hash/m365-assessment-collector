"""Collect Intune managed-device compliance snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from collectors.core.transport import GraphTransport

REQUIRED_PERMISSION = "DeviceManagementManagedDevices.Read.All"
PATH = "/v1.0/deviceManagement/managedDevices?$select=id,deviceName,complianceState,operatingSystem,osVersion,userDisplayName,lastSyncDateTime,managedDeviceOwnerType&$top=100"


def collect_and_persist_intune_compliance(*, tenant_id: int, transport: GraphTransport, connection: Any) -> dict:
    devices = []
    url = PATH
    while url:
        payload = transport.get_json(url)
        devices.extend(payload.get("value", []))
        url = payload.get("@odata.nextLink")
    observed_at = datetime.now(timezone.utc)
    with connection.cursor() as cur:
        for device in devices:
            cur.execute("""
                INSERT INTO core.intune_device
                (device_id, tenant_id, device_name, compliance_state, operating_system, os_version,
                 user_display_name, last_sync_datetime, owner_type, observed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id, device_id) DO UPDATE SET
                  device_name=EXCLUDED.device_name, compliance_state=EXCLUDED.compliance_state,
                  operating_system=EXCLUDED.operating_system, os_version=EXCLUDED.os_version,
                  user_display_name=EXCLUDED.user_display_name, last_sync_datetime=EXCLUDED.last_sync_datetime,
                  owner_type=EXCLUDED.owner_type, observed_at=EXCLUDED.observed_at
            """, (device.get("id"), tenant_id, device.get("deviceName"), device.get("complianceState"),
                  device.get("operatingSystem"), device.get("osVersion"), device.get("userDisplayName"),
                  device.get("lastSyncDateTime"), device.get("managedDeviceOwnerType"), observed_at))
    connection.commit()
    return {"devices_fetched": len(devices), "observed_at": observed_at.isoformat()}
