"""Bounded read-only collector for Entra Global Administrator assignments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlsplit

from collectors.core.errors import API_ERROR, PERMISSION_REQUIRED
from collectors.core.models import utcnow_iso
from collectors.core.transport import GraphHttpError, GraphNetworkError, GraphTransport
from security import DeterministicSecurityFindingService, SecurityFinding, SecurityObservation
from security.rules.entra_global_admin_001 import RULE_ID

GLOBAL_ADMIN_ROLE_DEFINITION_ID = "62e90394-69f5-4237-9190-012177145e10"
GLOBAL_ADMIN_ASSIGNMENTS_ENDPOINT = "/roleManagement/directory/roleAssignments"
GLOBAL_ADMIN_ASSIGNMENTS_PATH = "/v1.0" + GLOBAL_ADMIN_ASSIGNMENTS_ENDPOINT
GLOBAL_ADMIN_PERMISSION = "RoleManagement.Read.Directory"
SOURCE_TYPE = "entra_directory_role_assignments"
NORMALIZED_FIELD = "global_admin_assignment_count"
_FILTER = f"roleDefinitionId eq '{GLOBAL_ADMIN_ROLE_DEFINITION_ID}'"


@dataclass(frozen=True)
class EntraGlobalAdminResult:
    http_status: Optional[int]
    pages_read: int
    assignment_count: Optional[int]
    distinct_principal_count: Optional[int]
    observation: SecurityObservation
    finding: SecurityFinding
    error_classification: Optional[str] = None


def _valid_next_link(link: Any) -> bool:
    if not isinstance(link, str):
        return False
    parsed = urlsplit(link)
    return (parsed.scheme == "https" and parsed.hostname == "graph.microsoft.com" and
            parsed.port is None and parsed.username is None and parsed.password is None and
            parsed.path == GLOBAL_ADMIN_ASSIGNMENTS_PATH and not parsed.fragment)


class EntraGlobalAdminCollector:
    def __init__(self, transport: GraphTransport, *, finding_service=None):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()

    def collect(self) -> EntraGlobalAdminResult:
        observed_at, status, error = utcnow_iso(), None, None
        pages, assignments, seen_ids, principals = 0, [], set(), set()
        next_url: Any = None
        try:
            while True:
                response = self.transport.get(
                    next_url or GLOBAL_ADMIN_ASSIGNMENTS_PATH,
                    params=None if next_url else {"$filter": _FILTER},
                )
                status, pages = response.status, pages + 1
                payload = response.payload
                if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
                    raise ValueError("malformed result set")
                for assignment in payload["value"]:
                    if not isinstance(assignment, dict):
                        raise ValueError("malformed assignment")
                    assignment_id = assignment.get("id")
                    principal_id = assignment.get("principalId")
                    if not isinstance(assignment_id, str) or not assignment_id or not isinstance(principal_id, str) or not principal_id:
                        raise ValueError("malformed assignment")
                    if assignment_id in seen_ids:
                        continue
                    seen_ids.add(assignment_id)
                    assignments.append(assignment_id)
                    principals.add(principal_id)
                next_url = payload.get("@odata.nextLink")
                if next_url is None:
                    break
                if not _valid_next_link(next_url):
                    raise ValueError("invalid next link")
        except GraphHttpError as exc:
            status, error = exc.status, (PERMISSION_REQUIRED if exc.status == 403 else API_ERROR)
        except GraphNetworkError:
            error = "NETWORK_ERROR"
        except ValueError:
            error = API_ERROR
        available = error is None
        value = {"global_admin_assignment_count": len(assignments), "distinct_global_admin_principals": len(principals)} if available else None
        observation = SecurityObservation(
            rule_id=RULE_ID, value=value, source_available=available, observed_at=observed_at,
            source_type=SOURCE_TYPE, graph_endpoint=GLOBAL_ADMIN_ASSIGNMENTS_ENDPOINT,
            normalized_field=NORMALIZED_FIELD,
        )
        finding = self.finding_service.evaluate(observation)
        return EntraGlobalAdminResult(status, pages, len(assignments) if available else None,
                                      len(principals) if available else None, observation, finding, error)


__all__ = ["EntraGlobalAdminCollector", "EntraGlobalAdminResult", "GLOBAL_ADMIN_ASSIGNMENTS_ENDPOINT", "GLOBAL_ADMIN_ASSIGNMENTS_PATH", "GLOBAL_ADMIN_PERMISSION", "GLOBAL_ADMIN_ROLE_DEFINITION_ID"]
