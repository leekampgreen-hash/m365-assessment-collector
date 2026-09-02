"""Collect Entra PIM role assignment schedule instances."""
from datetime import datetime, timezone
from collectors.core.transport import GraphTransport

REQUIRED_PERMISSION = "RoleManagement.Read.Directory"
PATH = "/v1.0/roleManagement/directory/roleAssignmentScheduleInstances?$select=id,principalId,roleDefinitionId,assignmentType,startDateTime,endDateTime&$expand=principal($select=displayName),roleDefinition($select=displayName)&$top=100"

def collect_and_persist_entra_pim(*, tenant_id, transport: GraphTransport, connection):
    rows, url = [], PATH
    observed_at = datetime.now(timezone.utc)
    while url:
        payload = transport.get_json(url)
        for item in payload.get("value", []):
            rows.append((item.get("id"), tenant_id, (item.get("principal") or {}).get("displayName"), (item.get("roleDefinition") or {}).get("displayName"), item.get("assignmentType"), item.get("startDateTime"), item.get("endDateTime"), observed_at))
        url = payload.get("@odata.nextLink")
    with connection.cursor() as cur:
        for row in rows:
            cur.execute("""INSERT INTO core.entra_pim_assignment (assignment_id,tenant_id,principal_display_name,role_display_name,assignment_type,start_datetime,end_datetime,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,assignment_id) DO UPDATE SET principal_display_name=EXCLUDED.principal_display_name,role_display_name=EXCLUDED.role_display_name,assignment_type=EXCLUDED.assignment_type,start_datetime=EXCLUDED.start_datetime,end_datetime=EXCLUDED.end_datetime,observed_at=EXCLUDED.observed_at""", row)
    connection.commit()
    return {"assignments_fetched": len(rows), "observed_at": observed_at.isoformat()}
