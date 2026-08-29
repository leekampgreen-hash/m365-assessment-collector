"""Catalog integration models for the Scenario Agent framework.

This module defines typed containers that bridge the accepted G08-B
machine-readable scenario catalog with the deterministic G08-A
Scenario Agent framework. The wrapper approach is used deliberately:

* :class:`ScenarioDefinition` is not modified. Its closed shape stays
  the single contract the engine plans against.
* Catalog-only semantics that are not represented on
  :class:`ScenarioDefinition` (observability classification, correlation
  strategy, cleanup behavior, actor metadata, permission pack
  reference, ...) are carried by a thin wrapper.

Vocabulary and mappings are explicit, tested, and reject unknown
inputs. The module performs no I/O; it is pure data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


# ---------------------------------------------------------------------------
# Closed vocabulary constants (catalog-side)
# ---------------------------------------------------------------------------

# Observability classifications (mirror observability_map.json)
OBSERVABILITY_DIRECTLY_OBSERVABLE = "DIRECTLY_OBSERVABLE"
OBSERVABILITY_INDIRECTLY_OBSERVABLE = "INDIRECTLY_OBSERVABLE"
OBSERVABILITY_NOT_COVERED = "NOT_COVERED_BY_CURRENT_G01_INVENTORY"

OBSERVABILITY_CLASSIFICATIONS: Tuple[str, ...] = (
    OBSERVABILITY_DIRECTLY_OBSERVABLE,
    OBSERVABILITY_INDIRECTLY_OBSERVABLE,
    OBSERVABILITY_NOT_COVERED,
)


# Cleanup behavior vocabulary
CLEANUP_AUTO = "AUTO_CLEANUP_SUPPORTED"
CLEANUP_MANUAL = "MANUAL_CLEANUP"
CLEANUP_NONE = "NO_CLEANUP_REQUIRED"

CLEANUP_BEHAVIORS: Tuple[str, ...] = (CLEANUP_AUTO, CLEANUP_MANUAL, CLEANUP_NONE)


# Permission readiness status (OFFLINE evaluation only)
PERMISSION_READY = "READY"
PERMISSION_MISSING = "MISSING_PERMISSION"
PERMISSION_DISABLED = "DISABLED"

PERMISSION_READINESS_STATES: Tuple[str, ...] = (
    PERMISSION_READY,
    PERMISSION_MISSING,
    PERMISSION_DISABLED,
)


# ---------------------------------------------------------------------------
# Risk vocabulary normalization (catalog -> framework)
# ---------------------------------------------------------------------------

# Catalog uses LOW / MODERATE / HIGH.
# Framework canonical runtime vocabulary is LOW / MEDIUM / HIGH.
# The mapping is explicit and closed.

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

CATALOG_RISK_TO_FRAMEWORK: Dict[str, str] = {
    "LOW": RISK_LOW,
    "MODERATE": RISK_MEDIUM,
    "HIGH": RISK_HIGH,
}


# ---------------------------------------------------------------------------
# Action vocabulary normalization (catalog -> framework)
# ---------------------------------------------------------------------------

# Catalog action types are normalized to framework action types via an
# explicit, closed mapping. Unknown catalog action types are rejected.

CATALOG_ACTION_TO_FRAMEWORK: Dict[str, str] = {
    "SEND_MAIL": "SEND_MAIL",
    "CREATE_EVENT": "CREATE_CALENDAR_EVENT",
    "UPDATE_EVENT": "UPDATE_CALENDAR_EVENT",
    "DELETE_EVENT": "DELETE_CALENDAR_EVENT",
    "CREATE_FILE": "CREATE_FILE",
    "UPDATE_FILE": "UPDATE_FILE",
    "DELETE_FILE": "DELETE_FILE",
    "INTERACTIVE_SIGNIN": "INTERACTIVE_SIGNIN",
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogMetadata:
    """Catalog-only metadata preserved alongside a framework definition.

    The wrapper carries every catalog field that is not represented on
    :class:`agents.scenario.models.ScenarioDefinition`. The framework
    definition remains the planning-time contract; the catalog metadata
    is observability / catalog-traversal information.

    No credential-shaped fields are ever stored here.
    """

    catalog_scenario_id: str
    domain: str
    risk: str
    cleanup_behavior: str
    observability_classification: str
    expected_observable_sources: Tuple[str, ...]
    correlation_strategy: str
    correlation_token_field: str
    destructive: bool
    permission_pack: Optional[str]
    actor_required_alias: str
    peer_actor_required_alias: Optional[str]
    no_recipient: bool
    catalog_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "catalog_scenario_id": self.catalog_scenario_id,
            "domain": self.domain,
            "risk": self.risk,
            "cleanup_behavior": self.cleanup_behavior,
            "observability_classification": self.observability_classification,
            "expected_observable_sources": list(self.expected_observable_sources),
            "correlation_strategy": self.correlation_strategy,
            "correlation_token_field": self.correlation_token_field,
            "destructive": self.destructive,
            "permission_pack": self.permission_pack,
            "actor_required_alias": self.actor_required_alias,
            "peer_actor_required_alias": self.peer_actor_required_alias,
            "no_recipient": self.no_recipient,
            "catalog_notes": self.catalog_notes,
        }


@dataclass(frozen=True)
class LoadedScenario:
    """Framework definition + preserved catalog metadata.

    A thin integration wrapper. The framework ``definition`` is the
    object the engine plans against. ``catalog_metadata`` carries the
    catalog-only semantics (observability, cleanup behavior, ...)
    alongside it.
    """

    definition: Any  # agents.scenario.models.ScenarioDefinition (avoid import cycle)
    catalog_metadata: CatalogMetadata

    @property
    def scenario_id(self) -> str:
        return self.definition.scenario_id

    @property
    def enabled(self) -> bool:
        return self.definition.enabled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "catalog_metadata": self.catalog_metadata.to_dict(),
        }


@dataclass(frozen=True)
class PermissionReadiness:
    """OFFLINE permission readiness evaluation for one scenario.

    Distinct fields keep "what the scenario declares" separate from
    "what is currently available" so the caller can distinguish
    additional required scope from effective runtime permission set.
    """

    scenario_id: str
    enabled: bool
    required_scenario_permissions: Tuple[str, ...]
    effective_required_permissions: Tuple[str, ...]
    currently_available_permissions: Tuple[str, ...]
    missing_permissions: Tuple[str, ...]
    status: str  # one of PERMISSION_READINESS_STATES
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "enabled": self.enabled,
            "required_scenario_permissions": list(self.required_scenario_permissions),
            "effective_required_permissions": list(self.effective_required_permissions),
            "currently_available_permissions": list(self.currently_available_permissions),
            "missing_permissions": list(self.missing_permissions),
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CatalogLoadResult:
    """Summary of one catalog load.

    Returned by :func:`agents.scenario.catalog_loader.load_scenario_catalog`.
    Provides deterministic, framework-ready representations together
    with enough diagnostics to assert structural correctness in tests.
    """

    catalog_id: str
    catalog_version: str
    loaded_scenarios: Tuple[LoadedScenario, ...]
    actors: Tuple[Any, ...]  # ScenarioActor instances
    current_baseline_permissions: Tuple[str, ...]
    additional_permissions_required: Tuple[Dict[str, Any], ...]
    duplicates: Tuple[str, ...]
    malformed: Tuple[str, ...]
    g01_inventory_id_range: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "loaded_scenarios": [ls.to_dict() for ls in self.loaded_scenarios],
            "actors": [a.to_dict() for a in self.actors],
            "current_baseline_permissions": list(self.current_baseline_permissions),
            "additional_permissions_required": list(self.additional_permissions_required),
            "duplicates": list(self.duplicates),
            "malformed": list(self.malformed),
            "g01_inventory_id_range": list(self.g01_inventory_id_range),
        }


@dataclass(frozen=True)
class CatalogRegistryResult:
    """Result of binding a :class:`CatalogLoadResult` to a registry.

    Distinct from the underlying :class:`ScenarioRegistry` because it
    also carries the catalog-only metadata wrappers and a stable
    ordering of the loaded scenario ids.
    """

    registry: Any  # agents.scenario.registry.ScenarioRegistry
    loaded_scenarios: Tuple[LoadedScenario, ...]
    enabled_ids: Tuple[str, ...]
    disabled_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "registry_snapshot": self.registry.to_dict(),
            "enabled_ids": list(self.enabled_ids),
            "disabled_ids": list(self.disabled_ids),
        }


__all__ = [
    "CATALOG_ACTION_TO_FRAMEWORK",
    "CATALOG_RISK_TO_FRAMEWORK",
    "CatalogLoadResult",
    "CatalogMetadata",
    "CatalogRegistryResult",
    "CLEANUP_AUTO",
    "CLEANUP_BEHAVIORS",
    "CLEANUP_MANUAL",
    "CLEANUP_NONE",
    "LoadedScenario",
    "OBSERVABILITY_CLASSIFICATIONS",
    "OBSERVABILITY_DIRECTLY_OBSERVABLE",
    "OBSERVABILITY_INDIRECTLY_OBSERVABLE",
    "OBSERVABILITY_NOT_COVERED",
    "PERMISSION_DISABLED",
    "PERMISSION_MISSING",
    "PERMISSION_READINESS_STATES",
    "PERMISSION_READY",
    "PermissionReadiness",
    "RISK_HIGH",
    "RISK_LOW",
    "RISK_MEDIUM",
]