"""Collect Entra role assignments (P1-compatible) from roleAssignments endpoint.

PIM-specific endpoints (roleAssignmentScheduleInstances) require Entra ID P2.
This collector uses /v1.0/roleManagement/directory/roleAssignments which works
with Entra ID P1 and RoleManagement.Read.Directory permission.

Principal display names are resolved via /v1.0/directoryObjects/{id} using the
principalId on each assignment. Unknown principals are stored as None.

If the tenant does not have the required license or permission, the collector
exits gracefully with a skip result rather than raising an unhandled error.
"""
from datetime import datetime, timezone
from collectors.core.transport import GraphHttpError, GraphTransport

REQUIRED_PERMISSION = "RoleManagement.Read.Directory"

_ASSIGNMENTS_PATH = (
    "/v1.0/roleManagement/directory/roleAssignments"
    "?$expand=roleDefinition($select=displayName)"
    "&$top=100"
)

_SKIP_STATUSES = {403, 404}


def _resolve_principal_names(principal_ids, transport):
    """Return a mapping {principalId -> displayName} for the given ids.

    Ids that cannot be resolved (missing permission, unknown object) are
    silently omitted from the returned dict.
    """
    names = {}
    for pid in principal_ids:
        try:
            obj = transport.get_json("/v1.0/directoryObjects/{}".format(pid))
            display_name = obj.get("displayName")
            if display_name:
                names[pid] = display_name
        except GraphHttpError:
            pass
    return names


def collect_and_persist_entra_pim(*, tenant_id, transport: GraphTransport, connection):
    observed_at = datetime.now(timezone.utc)
    raw_items = []
    url = _ASSIGNMENTS_PATH

    try:
        payload = transport.get_json(url)
    except GraphHttpError as exc:
        if exc.status in _SKIP_STATUSES:
            return {
                "assignments_fetched": 0,
                "observed_at": observed_at.isoformat(),
                "skipped": True,
                "skip_reason": (
                    "roleAssignments endpoint returned HTTP {} -- "
                    "check RoleManagement.Read.Directory permission".format(exc.status)
                ),
            }
        raise

    while True:
        raw_items.extend(payload.get("value", []))
        next_link = payload.get("@odata.nextLink")
        if not next_link:
            break
        try:
            payload = transport.get_json(next_link)
        except GraphHttpError as exc:
            if exc.status in _SKIP_STATUSES:
                break
            raise

    unique_principal_ids = {item.get("principalId") for item in raw_items if item.get("principalId")}
    principal_names = _resolve_principal_names(unique_principal_ids, transport)

    rows = []
    for item in raw_items:
        pid = item.get("principalId")
        role_def = item.get("roleDefinition") or {}
        rows.append((
            item.get("id"),
            tenant_id,
            principal_names.get(pid) if pid else None,
            role_def.get("displayName"),
            "Assigned",
            item.get("startDateTime"),
            item.get("endDateTime"),
            observed_at,
        ))

    with connection.cursor() as cur:
        for row in rows:
            cur.execute(
                """INSERT INTO core.entra_pim_assignment
                    (assignment_id, tenant_id, principal_display_name, role_display_name,
                     assignment_type, start_datetime, end_datetime, observed_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (tenant_id, assignment_id) DO UPDATE SET
                     principal_display_name = EXCLUDED.principal_display_name,
                     role_display_name      = EXCLUDED.role_display_name,
                     assignment_type        = EXCLUDED.assignment_type,
                     start_datetime         = EXCLUDED.start_datetime,
                     end_datetime           = EXCLUDED.end_datetime,
                     observed_at            = EXCLUDED.observed_at""",
                row,
            )
    connection.commit()
    return {"assignments_fetched": len(rows), "observed_at": observed_at.isoformat()}
