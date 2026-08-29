"""Generic production orchestration for license-aware Security rules.

This module deliberately contains no rule semantics.  A registration binds a
rule to an allowlisted inventory source and collector; the Security service
remains the sole evaluator and the Security writer remains the sole storage
boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from capabilities import CollectionDecision, plan_collection
from capabilities.persistence import CapabilityQueryService
from collectors.core.models import CollectionResult, EndpointSpec
from collectors.security.entra_ca_enforcement import (
    ConditionalAccessEnforcementCollector,
    ENFORCEMENT_ENDPOINT_ID,
)
from security.rules.entra_ca_mfa_001 import RULE_ID as CA_MFA_RULE_ID
from security import DeterministicSecurityFindingService
from security.persistence import SecurityPersistenceWriter
from security.rules.entra_ca_enforcement_001 import RULE_ID as CA_ENFORCEMENT_RULE_ID
from security.rules.entra_ca_legacy_auth_001 import RULE_ID as CA_LEGACY_AUTH_RULE_ID
from collectors.security.entra_mfa_registration import MfaRegistrationCollector, MFA_REGISTRATION_ENDPOINT_ID
from security.rules.entra_mfa_registration_001 import RULE_ID as MFA_REG_RULE_ID
from security.rules.entra_admin_mfa_registration_001 import RULE_ID as ADMIN_MFA_REG_RULE_ID


@dataclass(frozen=True)
class SecurityExecutionSpec:
    """Source binding for a deterministic Security rule.

    Capabilities and permissions are intentionally not repeated here: they
    remain owned by ``SecurityRule``.
    """

    rule_id: str
    endpoint_id: str
    collector_factory: Callable[[Any, Any], Any]


def _conditional_access_collector(transport: Any, service: Any, **_: Any) -> Any:
    return ConditionalAccessEnforcementCollector(transport, finding_service=service)


def _conditional_access_mfa_collector(transport: Any, service: Any, **_: Any) -> Any:
    return ConditionalAccessEnforcementCollector(transport, finding_service=service, rule_id=CA_MFA_RULE_ID)


def _mfa_registration_collector(transport: Any, service: Any, *, connection: Any = None, tenant_id: Any = None, **_: Any) -> Any:
    return MfaRegistrationCollector(transport, finding_service=service, connection=connection, tenant_id=tenant_id)


def _admin_mfa_registration_collector(transport: Any, service: Any, **_: Any) -> Any:
    return MfaRegistrationCollector(transport, finding_service=service, rule_id=ADMIN_MFA_REG_RULE_ID)


_EXECUTIONS = {
    CA_ENFORCEMENT_RULE_ID: SecurityExecutionSpec(
        rule_id=CA_ENFORCEMENT_RULE_ID,
        endpoint_id=ENFORCEMENT_ENDPOINT_ID,
        collector_factory=_conditional_access_collector,
    ),
    CA_MFA_RULE_ID: SecurityExecutionSpec(
        rule_id=CA_MFA_RULE_ID, endpoint_id=ENFORCEMENT_ENDPOINT_ID,
        collector_factory=_conditional_access_mfa_collector,
    ),
    CA_LEGACY_AUTH_RULE_ID: SecurityExecutionSpec(
        rule_id=CA_LEGACY_AUTH_RULE_ID, endpoint_id=ENFORCEMENT_ENDPOINT_ID,
        collector_factory=lambda transport, service, **_: ConditionalAccessEnforcementCollector(
            transport, finding_service=service, rule_id=CA_LEGACY_AUTH_RULE_ID),
    ),
    MFA_REG_RULE_ID: SecurityExecutionSpec(
        rule_id=MFA_REG_RULE_ID, endpoint_id=MFA_REGISTRATION_ENDPOINT_ID,
        collector_factory=_mfa_registration_collector,
    ),
    ADMIN_MFA_REG_RULE_ID: SecurityExecutionSpec(
        rule_id=ADMIN_MFA_REG_RULE_ID, endpoint_id=MFA_REGISTRATION_ENDPOINT_ID,
        collector_factory=_admin_mfa_registration_collector,
    ),
}


class SecurityOrchestrationError(ValueError):
    pass


class SecurityOrchestrator:
    """Execute one registered Security source using the Collector runtime stack."""

    def __init__(self, runtime: Any, connection: Any, *, granted_graph_permissions: tuple[str, ...] = (),
                 finding_service: Any = None, persistence_writer: Any = None):
        self.runtime = runtime
        self.connection = connection
        self.granted_graph_permissions = tuple(granted_graph_permissions)
        self.finding_service = finding_service or DeterministicSecurityFindingService()
        self.persistence_writer = persistence_writer or SecurityPersistenceWriter(connection)

    def execution_spec(self, rule_id: str) -> SecurityExecutionSpec:
        spec = _EXECUTIONS.get(rule_id)
        if spec is None:
            raise SecurityOrchestrationError("Security rule is not registered for collection: " + rule_id)
        return spec

    def run(self, rule_id: str) -> dict[str, Any]:
        execution = self.execution_spec(rule_id)
        rule = self.finding_service.resolve_rule(rule_id)
        if rule is None:
            raise SecurityOrchestrationError("Security rule is not recognized: " + rule_id)
        source = self.runtime.find_spec(execution.endpoint_id)
        config = self.runtime.build_auth_config()
        tenant_id = self.runtime._resolve_trusted_tenant(config)
        capabilities = CapabilityQueryService.from_connection(self.connection, tenant_id).capabilities()
        entitlements = {item["capability"]: item["entitlement"] for item in capabilities}
        plan = plan_collection(
            rule.required_capabilities, rule.required_graph_permissions,
            entitlements, self.granted_graph_permissions,
        )
        if plan.decision is not CollectionDecision.COLLECT:
            return {"rule_id": rule_id, "plan": plan, "collection": CollectionResult(
                endpoint_id=source.endpoint_id, status="SKIPPED", feature_status=plan.feature_status.value,
                capability_decision=plan.decision.value, error_message=plan.decision.value,
            ), "observation": None, "finding": None, "persistence": None}

        writer = self.runtime.options.collection_writer
        collection_run_id = None
        endpoint_run_id = None
        result = None
        try:
            if writer is not None:
                collection_run_id = writer.begin_collection_run(tenant_id=tenant_id, endpoint_ids=[source.endpoint_id])
                endpoint_run_id = writer.begin_endpoint_run(
                    collection_run_id=collection_run_id, tenant_id=tenant_id, spec=source,
                )
            token_provider = self.runtime.build_token_provider(config)
            token_provider.get_token()
            transport = self.runtime.build_transport(token_provider.get_token)
            collector = execution.collector_factory(
                transport, self.finding_service, connection=self.connection, tenant_id=tenant_id,
            )
            collected = collector.collect(
                source, plan, retry_policy=self.runtime.build_retry_policy(),
                collection_run_id=str(collection_run_id or ""), endpoint_run_id=str(endpoint_run_id or ""),
            )
            result = collected.collection.result
            # Source errors deliberately evaluate as NOT_EVALUATED, never OPEN.
            persistence = None
            if collected.observation is not None and collected.finding is not None:
                try:
                    # A transaction failure may be transient. Retry the same
                    # already-collected observation once; never recollect Graph.
                    for attempt in range(2):
                        try:
                            persistence = self.persistence_writer.persist_authenticated(
                                config=config, observation=collected.observation, finding=collected.finding,
                            )
                            break
                        except Exception:
                            if attempt:
                                raise
                except Exception:
                    # Graph collection is already complete. Preserve that fact in
                    # its result, while exposing the analytical write failure.
                    result.error_classification = "PERSISTENCE_ERROR"
                    result.error_message = "PERSISTENCE_ERROR"
                    # The security write failed after a successful source
                    # collection; lifecycle exposes this terminal persistence
                    # failure without relabelling it as a Graph/API failure.
                    result.status = "ERROR"
            return {"rule_id": rule_id, "plan": plan, "collection": result,
                    "observation": collected.observation, "finding": collected.finding,
                    "persistence": persistence}
        finally:
            if writer is not None and collection_run_id is not None:
                if result is None:
                    result = CollectionResult(endpoint_id=source.endpoint_id, status="ERROR",
                                              error_classification="PERSISTENCE_ERROR", error_message="PERSISTENCE_ERROR")
                if endpoint_run_id is not None:
                    writer.complete_endpoint_run(endpoint_run_id=endpoint_run_id, result=result)
                writer.complete_collection_run(collection_run_id=collection_run_id, results=[result])


__all__ = ["SecurityExecutionSpec", "SecurityOrchestrationError", "SecurityOrchestrator"]
