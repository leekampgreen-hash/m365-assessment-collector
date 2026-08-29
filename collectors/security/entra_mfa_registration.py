"""Bounded, read-only collector for MFA registration coverage."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from capabilities.gates import CollectionDecision, CollectionPlan
from collectors.core.collector import BaseCollector
from collectors.core.errors import API_ERROR, PERMISSION_REQUIRED
from collectors.core.models import EndpointSpec
from collectors.core.retry import RetryPolicy
from collectors.core.transport import GraphHttpError, GraphNetworkError, GraphTransport
from security import DeterministicSecurityFindingService, SecurityFinding, SecurityObservation
from security.rules.entra_mfa_registration_001 import GRAPH_ENDPOINT, RULE_ID, SOURCE_TYPE
from security.rules.entra_admin_mfa_registration_001 import (
    GRAPH_ENDPOINT as ADMIN_GRAPH_ENDPOINT, RULE_ID as ADMIN_RULE_ID,
    SOURCE_TYPE as ADMIN_SOURCE_TYPE,
)

MFA_REGISTRATION_ENDPOINT_ID = "G01-021"


@dataclass(frozen=True)
class MfaRegistrationResult:
    collection: Any
    observation: SecurityObservation
    finding: SecurityFinding


def _enabled_users(connection: Any, tenant_id: int) -> list[tuple[str, Optional[str]]]:
    cursor = connection.cursor()
    cursor.execute('SELECT source_object_id, user_principal_name FROM core."user" WHERE tenant_id = %s AND account_enabled IS TRUE', (tenant_id,))
    return list(cursor.fetchall())


class MfaRegistrationCollector:
    def __init__(self, transport: GraphTransport, *, finding_service=None, connection=None, tenant_id=None,
                 rule_id=RULE_ID):
        if not isinstance(transport, GraphTransport):
            raise TypeError("transport must be a GraphTransport")
        self.transport = transport
        self.finding_service = finding_service or DeterministicSecurityFindingService()
        self.connection, self.tenant_id = connection, tenant_id
        self.rule_id = rule_id

    def collect(self, spec: EndpointSpec, plan: CollectionPlan, *, retry_policy: Optional[RetryPolicy] = None,
                collection_run_id: str = "", endpoint_run_id: str = "") -> MfaRegistrationResult:
        if plan.decision is not CollectionDecision.COLLECT:
            raise ValueError("collector must not be constructed for a skipped plan")
        observed_at = None
        run = BaseCollector(spec, self.transport, retry_policy=retry_policy).collect()
        complete = run.result.status == "PASS"
        counts = None
        if self.rule_id == ADMIN_RULE_ID:
            admin_count = registered = 0
            for record in run.records:
                if (not isinstance(record, dict) or not isinstance(record.get("isAdmin"), bool)
                        or not isinstance(record.get("isMfaRegistered"), bool)):
                    complete = False
                    continue
                if record["isAdmin"]:
                    admin_count += 1
                    registered += record["isMfaRegistered"]
            counts = {
                "admin_user_count": admin_count,
                "admin_mfa_registered_count": registered,
                "admin_mfa_not_registered_count": admin_count - registered,
                "admin_registration_coverage_percent": round(registered / admin_count * 100, 2) if admin_count else 0.0,
            }
            observation = SecurityObservation(rule_id=ADMIN_RULE_ID, value=counts,
                source_available=complete, observed_at=run.result.completed_at,
                source_type=ADMIN_SOURCE_TYPE, graph_endpoint=ADMIN_GRAPH_ENDPOINT,
                collection_run_id=collection_run_id, endpoint_run_id=endpoint_run_id,
                normalized_field="admin_mfa_registration_coverage")
            finding = self.finding_service.evaluate(observation)
            return MfaRegistrationResult(run, observation, finding)
        try:
            users = _enabled_users(self.connection, self.tenant_id)
            keys = {row[0] for row in users if isinstance(row, (tuple, list)) and row and isinstance(row[0], str)}
            upns = {row[1].casefold() for row in users if isinstance(row, (tuple, list)) and len(row) > 1 and isinstance(row[1], str)}
            registered = capable = 0
            matched = 0
            for record in run.records:
                if not isinstance(record, dict) or not isinstance(record.get("isMfaRegistered"), bool) or not isinstance(record.get("isMfaCapable"), bool):
                    complete = False
                    continue
                key = record.get("id")
                upn = record.get("userPrincipalName")
                if not ((isinstance(key, str) and key in keys) or (isinstance(upn, str) and upn.casefold() in upns)):
                    continue
                matched += 1
                registered += record["isMfaRegistered"]
                capable += record["isMfaCapable"]
            gap = abs(len(keys) - matched)
            counts = {"enabled_user_count": len(keys), "registration_row_count": len(run.records), "matched_enabled_user_count": matched,
                      "unexplained_population_gap": gap, "mfa_registered_count": registered,
                      "mfa_not_registered_count": matched - registered,
                      "registration_coverage_percent": round(registered / len(keys) * 100, 2) if keys else 100.0}
            complete = complete and gap == 0 and matched == len(keys) and len(run.records) == matched
        except Exception:
            complete, counts = False, None
        observation = SecurityObservation(rule_id=RULE_ID, value=counts, source_available=complete,
            observed_at=run.result.completed_at, source_type=SOURCE_TYPE, graph_endpoint=GRAPH_ENDPOINT,
            collection_run_id=collection_run_id, endpoint_run_id=endpoint_run_id,
            normalized_field="mfa_registration_coverage")
        finding = self.finding_service.evaluate(observation)
        return MfaRegistrationResult(run, observation, finding)


__all__ = ["MFA_REGISTRATION_ENDPOINT_ID", "MfaRegistrationCollector", "MfaRegistrationResult"]
