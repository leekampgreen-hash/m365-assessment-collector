"""Catalog loader / integration module for the Scenario Agent.

This module is the G08-C integration seam between:

* the accepted G08-B machine-readable scenario catalog under
  ``config/scenarios/`` (pure JSON, no credentials, no live Graph
  references); and
* the deterministic G08-A Scenario Agent framework under
  ``agents/scenario/``.

The loader is strictly OFFLINE. It performs no I/O outside reading the
JSON files on disk. It never reads secrets, never resolves actors to
credentials, never contacts Entra or the database.

Public surface:

* :func:`load_scenario_catalog` -- parse the catalog index, each
  referenced scenario JSON, the actor model, and the observability
  map; produce a :class:`CatalogLoadResult`.
* :func:`build_catalog_registry` -- bind a :class:`CatalogLoadResult`
  to a :class:`ScenarioRegistry`, returning a
  :class:`CatalogRegistryResult`.
* :func:`evaluate_permission_readiness` -- OFFLINE permission
  readiness evaluation per loaded scenario.
* :func:`scenario_ids_in_deterministic_order` -- stable ordering
  helper used by tests and the registry integration.
* :func:`validate_observability_g01_references` -- validate that
  every catalog observability reference is inside the G01 inventory
  range and a member of the closed classification vocabulary.

The loader uses explicit, closed vocabularies. Unknown risk values,
unknown catalog action types, or unknown observability classifications
are rejected.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

from .actions import is_supported_action_type
from .catalog_models import (
    CATALOG_ACTION_TO_FRAMEWORK,
    CATALOG_RISK_TO_FRAMEWORK,
    CLEANUP_BEHAVIORS,
    CatalogLoadResult,
    CatalogMetadata,
    CatalogRegistryResult,
    LoadedScenario,
    OBSERVABILITY_CLASSIFICATIONS,
    PERMISSION_DISABLED,
    PERMISSION_MISSING,
    PERMISSION_READY,
    PermissionReadiness,
)
from .models import (
    IDENTITY_REQUIRED,
    ScenarioActor,
    ScenarioDefinition,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CatalogLoaderError(ValueError):
    """Raised when the catalog loader rejects a record.

    Subclasses of this error type carry no caller-supplied payload
    that resembles a credential or token. The ``code`` attribute is a
    stable, closed identifier suitable for assertions in tests.
    """

    code = "CATALOG_LOADER_ERROR"

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_G01_PATTERN = re.compile(r"^G01-([0-9]{3})$")


def _require_str(payload: Mapping[str, Any], key: str, *, where: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise CatalogLoaderError(
            "CATALOG_FIELD_MISSING",
            "{0}: field {1!r} must be a non-empty string".format(where, key),
        )
    return value


def _require_bool(payload: Mapping[str, Any], key: str, *, where: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise CatalogLoaderError(
            "CATALOG_FIELD_MISSING",
            "{0}: field {1!r} must be a boolean".format(where, key),
        )
    return value


def _require_list_of_str(
    payload: Mapping[str, Any],
    key: str,
    *,
    where: str,
) -> Tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise CatalogLoaderError(
            "CATALOG_FIELD_MISSING",
            "{0}: field {1!r} must be a list".format(where, key),
        )
    out: List[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise CatalogLoaderError(
                "CATALOG_FIELD_MISSING",
                "{0}: field {1!r} must contain non-empty strings only".format(
                    where, key
                ),
            )
        out.append(item)
    return tuple(out)


def _optional_str(payload: Mapping[str, Any], key: str, *, where: str) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CatalogLoaderError(
            "CATALOG_FIELD_MISSING",
            "{0}: field {1!r} must be a string or null".format(where, key),
        )
    return value


def _normalize_risk(catalog_risk: str, *, where: str) -> str:
    """Map a catalog risk value to the framework canonical risk.

    Unknown catalog risk values are rejected. No aliases are accepted.
    """
    if not isinstance(catalog_risk, str):
        raise CatalogLoaderError(
            "CATALOG_RISK_UNKNOWN",
            "{0}: risk must be a string".format(where),
        )
    if catalog_risk not in CATALOG_RISK_TO_FRAMEWORK:
        raise CatalogLoaderError(
            "CATALOG_RISK_UNKNOWN",
            "{0}: unknown catalog risk {1!r}".format(where, catalog_risk),
        )
    return CATALOG_RISK_TO_FRAMEWORK[catalog_risk]


def _normalize_action_type(catalog_action: str, *, where: str) -> str:
    """Map a catalog action_type to the framework action vocabulary.

    Unknown catalog action types are rejected. No aliases are accepted.
    """
    if not isinstance(catalog_action, str):
        raise CatalogLoaderError(
            "CATALOG_ACTION_UNKNOWN",
            "{0}: action_type must be a string".format(where),
        )
    if catalog_action not in CATALOG_ACTION_TO_FRAMEWORK:
        raise CatalogLoaderError(
            "CATALOG_ACTION_UNKNOWN",
            "{0}: unknown catalog action {1!r}".format(where, catalog_action),
        )
    framework_action = CATALOG_ACTION_TO_FRAMEWORK[catalog_action]
    if not is_supported_action_type(framework_action):
        raise CatalogLoaderError(
            "CATALOG_ACTION_NOT_IN_FRAMEWORK",
            (
                "{0}: mapped framework action {1!r} is not present in "
                "the closed framework vocabulary"
            ).format(where, framework_action),
        )
    return framework_action


def _validate_cleanup_behavior(behavior: str, *, where: str) -> str:
    if behavior not in CLEANUP_BEHAVIORS:
        raise CatalogLoaderError(
            "CATALOG_CLEANUP_UNKNOWN",
            "{0}: unknown cleanup_behavior {1!r}".format(where, behavior),
        )
    return behavior


def _validate_observability_classification(value: str, *, where: str) -> str:
    if value not in OBSERVABILITY_CLASSIFICATIONS:
        raise CatalogLoaderError(
            "CATALOG_OBSERVABILITY_UNKNOWN",
            "{0}: unknown observability_classification {1!r}".format(where, value),
        )
    return value


def _validate_g01_endpoint(endpoint: str, *, where: str, allowed_ids: set) -> None:
    """Validate that ``endpoint`` is a G01-NNN reference inside the inventory.

    The validation is conservative: unknown endpoint ids are rejected
    explicitly. Endpoints outside the G01-001..G01-019 range or with
    malformed format are rejected.
    """
    if not isinstance(endpoint, str):
        raise CatalogLoaderError(
            "CATALOG_OBSERVABILITY_BAD_REFERENCE",
            "{0}: expected_observable_sources entries must be strings".format(where),
        )
    match = _G01_PATTERN.match(endpoint)
    if match is None:
        raise CatalogLoaderError(
            "CATALOG_OBSERVABILITY_BAD_REFERENCE",
            "{0}: endpoint {1!r} is not a G01-NNN reference".format(where, endpoint),
        )
    if endpoint not in allowed_ids:
        raise CatalogLoaderError(
            "CATALOG_OBSERVABILITY_BAD_REFERENCE",
            "{0}: endpoint {1!r} is outside the declared G01 inventory".format(
                where, endpoint
            ),
        )


def _validate_no_credentials_in_record(payload: Mapping[str, Any], where: str) -> None:
    """Conservative check: reject records that smell like credentials.

    This mirrors the framework safety gate's ``_TOKEN_LIKE_KEYS`` set
    so the loader never silently accepts a credential-shaped string.
    """
    forbidden_keys = {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "bearer",
        "client_secret",
        "secret",
        "api_key",
        "authorization_header",
    }
    for key in payload.keys():
        if not isinstance(key, str):
            continue
        if key.lower() in forbidden_keys:
            raise CatalogLoaderError(
                "CATALOG_FORBIDDEN_FIELD",
                "{0}: forbidden credential-shaped field {1!r}".format(where, key),
            )


# ---------------------------------------------------------------------------
# Scenario JSON parsing
# ---------------------------------------------------------------------------


def _parse_scenario_payload(
    payload: Mapping[str, Any],
    *,
    allowed_g01_ids: set,
) -> Tuple[ScenarioDefinition, CatalogMetadata]:
    """Parse one scenario JSON payload into (definition, catalog_metadata)."""
    where = "scenario/{0}".format(payload.get("scenario_id", "<unknown>"))

    _validate_no_credentials_in_record(payload, where)

    catalog_scenario_id = _require_str(payload, "scenario_id", where=where)
    name = _require_str(payload, "name", where=where)
    description = _require_str(payload, "description", where=where)
    domain = _require_str(payload, "domain", where=where)
    risk_catalog = _require_str(payload, "risk", where=where)
    risk_framework = _normalize_risk(risk_catalog, where=where)
    action_catalog = _require_str(payload, "action_type", where=where)
    action_framework = _normalize_action_type(action_catalog, where=where)
    cleanup_behavior = _validate_cleanup_behavior(
        _require_str(payload, "cleanup_behavior", where=where),
        where=where,
    )
    observability_classification = _validate_observability_classification(
        _require_str(payload, "observability_classification", where=where),
        where=where,
    )
    expected_observable_sources = _require_list_of_str(
        payload, "expected_observable_sources", where=where
    )
    for endpoint in expected_observable_sources:
        _validate_g01_endpoint(
            endpoint, where=where, allowed_ids=allowed_g01_ids
        )

    correlation_strategy = _require_str(payload, "correlation_strategy", where=where)
    correlation_token_field = _require_str(
        payload, "correlation_token_field", where=where
    )
    destructive = _require_bool(payload, "destructive", where=where)
    enabled = _require_bool(payload, "enabled", where=where)
    permission_pack = _optional_str(payload, "permission_pack", where=where)
    actor_required_alias = _require_str(payload, "actor_required", where=where)
    peer_actor_required = _optional_str(
        payload, "peer_actor_required", where=where
    )
    no_recipient = _require_bool(payload, "no_recipient", where=where)
    catalog_notes = _require_str(payload, "notes", where=where)
    required_permissions = _require_list_of_str(
        payload, "required_delegated_permissions", where=where
    )

    cleanup_scenario_id: Optional[str] = None
    cleanup_required = bool(payload.get("cleanup_required", False))
    if not isinstance(payload.get("cleanup_required", False), bool):
        raise CatalogLoaderError(
            "CATALOG_FIELD_MISSING",
            "{0}: field 'cleanup_required' must be a boolean".format(where),
        )

    # The catalog may declare an empty required_delegated_permissions list
    # when the scenario relies only on the existing User.Read baseline
    # (e.g. INTERACTIVE_SIGNIN). The framework registry, however, requires
    # every ScenarioDefinition to declare at least one permission. We close
    # the gap by surfacing the baseline permission in the framework-level
    # declaration only when the action_type implies it and the catalog
    # lists no additional permission. The catalog_metadata.required set
    # remains the source of truth for catalog-level reasoning.
    from .actions import declared_permissions_for

    framework_declared = list(required_permissions)
    if not framework_declared:
        # Use the action's framework-level declared permissions as a
        # baseline contract. For INTERACTIVE_SIGNIN this resolves to
        # (User.Read,) so the registry check passes.
        framework_declared = list(declared_permissions_for(action_framework))

    definition = ScenarioDefinition(
        scenario_id=catalog_scenario_id,
        name=name,
        description=description,
        workload=domain.lower(),
        action_type=action_framework,
        identity_requirement=IDENTITY_REQUIRED,
        required_delegated_permissions=framework_declared,
        expected_observable_evidence=list(expected_observable_sources),
        cleanup_required=cleanup_required,
        risk_level=risk_framework,
        destructive=destructive,
        enabled=enabled,
        cleanup_scenario_id=cleanup_scenario_id,
    )

    catalog_metadata = CatalogMetadata(
        catalog_scenario_id=catalog_scenario_id,
        domain=domain,
        risk=risk_catalog,
        cleanup_behavior=cleanup_behavior,
        observability_classification=observability_classification,
        expected_observable_sources=tuple(expected_observable_sources),
        correlation_strategy=correlation_strategy,
        correlation_token_field=correlation_token_field,
        destructive=destructive,
        permission_pack=permission_pack,
        actor_required_alias=actor_required_alias,
        peer_actor_required_alias=peer_actor_required,
        no_recipient=no_recipient,
        catalog_notes=catalog_notes,
    )
    return definition, catalog_metadata


# ---------------------------------------------------------------------------
# Actor JSON parsing
# ---------------------------------------------------------------------------


_FORBIDDEN_ACTOR_FIELDS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "bearer",
    "client_secret",
    "secret",
    "api_key",
    "authorization_header",
}


def _parse_actor_payload(
    payload: Mapping[str, Any],
    *,
    catalog_id: str,
) -> ScenarioActor:
    """Parse one actor alias record into a :class:`ScenarioActor`."""
    where = "actor/{0}".format(payload.get("alias", "<unknown>"))
    alias = _require_str(payload, "alias", where=where)
    role = _require_str(payload, "role", where=where)
    description = _require_str(payload, "description", where=where)
    upn_resolution = _require_str(payload, "upn_resolution", where=where)

    # No credentials / secrets / UPN strings are ever stored on the
    # actor. The upn_resolution field is preserved only as a literal
    # string ("DEFERRED_TO_RUNTIME_CONFIG"); no resolution is performed.
    if upn_resolution != "DEFERRED_TO_RUNTIME_CONFIG":
        raise CatalogLoaderError(
            "CATALOG_ACTOR_UPN_RESOLVED",
            (
                "{0}: actor {1!r} has upn_resolution {2!r}; "
                "UPN resolution must remain deferred"
            ).format(where, alias, upn_resolution),
        )

    # Reject any actor alias that ships credential-shaped fields.
    for key in payload.keys():
        if not isinstance(key, str):
            continue
        if key.lower() in _FORBIDDEN_ACTOR_FIELDS:
            raise CatalogLoaderError(
                "CATALOG_ACTOR_FORBIDDEN_FIELD",
                "{0}: forbidden credential-shaped field {1!r}".format(where, key),
            )

    return ScenarioActor(
        actor_id=alias,
        user_principal_name=None,
        object_id=None,
        allowed_scenario_ids=None,
        allowed_workloads=None,
        enabled=True,
        description="{0} (role={1}, catalog={2})".format(description, role, catalog_id),
    )


# ---------------------------------------------------------------------------
# Top-level load
# ---------------------------------------------------------------------------


def _default_catalog_root() -> Path:
    """Resolve the default catalog root from the project root."""
    return Path(__file__).resolve().parents[2] / "config" / "scenarios"


def _default_inventory_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "api_inventory.json"


def _load_observability_inventory_ids(path: Path) -> set:
    """Load G01 inventory ids from ``config/api_inventory.json``."""
    if not path.exists():
        # Conservative default: empty set. The caller may override by
        # passing allowed_g01_ids explicitly to load_scenario_catalog.
        return set()
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise CatalogLoaderError(
            "CATALOG_INVENTORY_MALFORMED",
            "G01 inventory file must be a JSON list of items",
        )
    ids = set()
    for item in payload:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.add(item["id"])
    return ids


def _validate_total_consistency(
    catalog_index: Mapping[str, Any],
    loaded_ids: Sequence[str],
    *,
    malformed_count: int,
    duplicates_count: int,
) -> None:
    """Validate catalog totals match what we actually loaded.

    The check is tolerant of malformed / duplicate records: if the
    catalog declared ``total_scenarios`` is greater than the loaded
    count, the difference must equal the number of malformed records
    (duplicates are not added to the loaded set, so they also count
    as "missing" from the loaded count). When the totals block is
    internally inconsistent, the loader raises.
    """
    totals = catalog_index.get("totals", {})
    if not isinstance(totals, dict):
        raise CatalogLoaderError(
            "CATALOG_TOTALS_MALFORMED",
            "catalog.json totals block must be a JSON object",
        )
    expected_total = totals.get("total_scenarios")
    expected_enabled = totals.get("enabled_scenarios")
    expected_disabled = totals.get("disabled_scenarios")

    if isinstance(expected_total, int):
        # The loaded count plus malformed plus duplicates (because
        # duplicates are kept in the index but only added once) must
        # equal expected_total.
        if (
            len(loaded_ids) + malformed_count + duplicates_count
            != expected_total
        ):
            raise CatalogLoaderError(
                "CATALOG_TOTALS_INCONSISTENT",
                (
                    "catalog totals.total_scenarios={0!r} does not match "
                    "loaded+malformed+duplicates count={1!r}"
                ).format(
                    expected_total,
                    len(loaded_ids) + malformed_count + duplicates_count,
                ),
            )
    if isinstance(expected_enabled, int) and isinstance(expected_disabled, int):
        if expected_total != expected_enabled + expected_disabled:
            raise CatalogLoaderError(
                "CATALOG_TOTALS_INCONSISTENT",
                (
                    "catalog totals inconsistent: total={0}, enabled={1}, "
                    "disabled={2}"
                ).format(expected_total, expected_enabled, expected_disabled),
            )


def load_scenario_catalog(
    catalog_root: Optional[Path] = None,
    *,
    allowed_g01_ids: Optional[Iterable[str]] = None,
) -> CatalogLoadResult:
    """Load the scenario catalog from disk.

    The loader performs pure JSON parsing; it does not contact Entra,
    the database, or any external service. It does not read secrets
    or resolve actor UPNs.
    """
    root = Path(catalog_root) if catalog_root is not None else _default_catalog_root()
    catalog_path = root / "catalog.json"
    actor_path = root / "actor_model.json"
    observability_path = root / "observability_map.json"
    scenarios_dir = root / "scenarios"

    if not catalog_path.exists():
        raise CatalogLoaderError(
            "CATALOG_MISSING",
            "catalog.json not found at {0}".format(catalog_path),
        )

    catalog_index = json.loads(catalog_path.read_text())
    if not isinstance(catalog_index, dict):
        raise CatalogLoaderError(
            "CATALOG_MALFORMED",
            "catalog.json root must be a JSON object",
        )

    catalog_id = _require_str(catalog_index, "catalog_id", where="catalog.json")
    catalog_version = _require_str(catalog_index, "version", where="catalog.json")

    if allowed_g01_ids is None:
        g01_ids = _load_observability_inventory_ids(_default_inventory_path())
    else:
        g01_ids = set(allowed_g01_ids)

    current_baseline = tuple(
        catalog_index.get(
            "current_scenario_app_delegated_permissions", ("User.Read",)
        )
    )

    additional_permissions_required_raw = catalog_index.get(
        "additional_permissions_required", []
    )
    if not isinstance(additional_permissions_required_raw, list):
        raise CatalogLoaderError(
            "CATALOG_MALFORMED",
            "catalog.json additional_permissions_required must be a list",
        )
    additional_permissions_required: List[Dict[str, Any]] = []
    for entry in additional_permissions_required_raw:
        if isinstance(entry, dict):
            additional_permissions_required.append(dict(entry))

    duplicates: List[str] = []
    malformed: List[str] = []
    seen_ids: set = set()
    loaded_pairs: List[Tuple[ScenarioDefinition, CatalogMetadata]] = []

    scenarios_index = catalog_index.get("scenarios", [])
    if not isinstance(scenarios_index, list):
        raise CatalogLoaderError(
            "CATALOG_MALFORMED",
            "catalog.json scenarios must be a list",
        )

    for entry in scenarios_index:
        if not isinstance(entry, dict):
            malformed.append("<non-dict scenario entry>")
            continue
        scenario_id = entry.get("scenario_id")
        file_path = entry.get("file")
        if not isinstance(scenario_id, str) or not isinstance(file_path, str):
            malformed.append(str(scenario_id))
            continue
        if scenario_id in seen_ids:
            duplicates.append(scenario_id)
            continue
        full_path = root / file_path
        if not full_path.exists():
            malformed.append(scenario_id)
            continue
        try:
            payload = json.loads(full_path.read_text())
        except json.JSONDecodeError:
            malformed.append(scenario_id)
            continue
        try:
            definition, metadata = _parse_scenario_payload(
                payload, allowed_g01_ids=g01_ids
            )
        except CatalogLoaderError:
            malformed.append(scenario_id)
            continue
        if definition.scenario_id in seen_ids:
            duplicates.append(definition.scenario_id)
            continue
        seen_ids.add(definition.scenario_id)
        loaded_pairs.append((definition, metadata))

    # Deterministic order: sort by scenario_id.
    loaded_pairs.sort(key=lambda pair: pair[0].scenario_id)
    loaded_scenarios = tuple(
        LoadedScenario(definition=definition, catalog_metadata=metadata)
        for definition, metadata in loaded_pairs
    )

    _validate_total_consistency(
        catalog_index,
        [ls.scenario_id for ls in loaded_scenarios],
        malformed_count=len(malformed),
        duplicates_count=len(duplicates),
    )

    # Load actors (optional: do not fail the load if actor_model.json is
    # missing; the catalog may have actors inlined elsewhere in a future
    # revision). For G08-C the file is present and required for actor tests.
    actors: List[ScenarioActor] = []
    if actor_path.exists():
        actor_payload = json.loads(actor_path.read_text())
        if not isinstance(actor_payload, dict):
            raise CatalogLoaderError(
                "CATALOG_MALFORMED",
                "actor_model.json root must be a JSON object",
            )
        aliases = actor_payload.get("actor_aliases", [])
        if not isinstance(aliases, list):
            raise CatalogLoaderError(
                "CATALOG_MALFORMED",
                "actor_model.json actor_aliases must be a list",
            )
        for alias_entry in aliases:
            if not isinstance(alias_entry, dict):
                malformed.append("actor/<non-dict>")
                continue
            actors.append(_parse_actor_payload(alias_entry, catalog_id=catalog_id))

    g01_inventory_id_range = (
        str(catalog_index.get("g01_inventory_id_range", "G01-001..G01-019"))
        if isinstance(catalog_index.get("g01_inventory_id_range"), str)
        else "G01-001..G01-019"
    )

    return CatalogLoadResult(
        catalog_id=catalog_id,
        catalog_version=catalog_version,
        loaded_scenarios=tuple(loaded_scenarios),
        actors=tuple(actors),
        current_baseline_permissions=current_baseline,
        additional_permissions_required=tuple(additional_permissions_required),
        duplicates=tuple(duplicates),
        malformed=tuple(malformed),
        g01_inventory_id_range=(g01_inventory_id_range,),
    )


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def build_catalog_registry(
    catalog_load: CatalogLoadResult,
) -> CatalogRegistryResult:
    """Bind a :class:`CatalogLoadResult` to a :class:`ScenarioRegistry`.

    The returned registry contains:

    * the framework's built-in scenarios (from the G08-A framework); and
    * every catalog scenario, including disabled ones.

    Disabled catalog scenarios are registered but their ``enabled``
    flag remains ``False`` so the safety gate continues to refuse
    them. The registry enforces uniqueness of ``scenario_id`` across
    built-in and catalog entries; collisions raise
    :class:`CatalogLoaderError`.
    """
    # Imported here to keep the module top-level clean and to avoid an
    # import cycle with the framework.
    from .registry import ScenarioRegistry

    built_in_registry = ScenarioRegistry()
    built_in_ids = set(built_in_registry.scenario_ids())

    catalog_definitions = [ls.definition for ls in catalog_load.loaded_scenarios]
    collisions = [d.scenario_id for d in catalog_definitions if d.scenario_id in built_in_ids]
    if collisions:
        raise CatalogLoaderError(
            "CATALOG_ID_COLLISION",
            "catalog scenario_id(s) collide with built-in registry: {0}".format(
                ", ".join(sorted(collisions))
            ),
        )

    full_registry = ScenarioRegistry(extra=catalog_definitions)

    enabled_ids = tuple(
        sorted(
            ls.scenario_id
            for ls in catalog_load.loaded_scenarios
            if ls.definition.enabled
        )
    )
    disabled_ids = tuple(
        sorted(
            ls.scenario_id
            for ls in catalog_load.loaded_scenarios
            if not ls.definition.enabled
        )
    )

    return CatalogRegistryResult(
        registry=full_registry,
        loaded_scenarios=catalog_load.loaded_scenarios,
        enabled_ids=enabled_ids,
        disabled_ids=disabled_ids,
    )


# ---------------------------------------------------------------------------
# Permission readiness
# ---------------------------------------------------------------------------


def evaluate_permission_readiness(
    loaded: LoadedScenario,
    *,
    available_permissions: Sequence[str],
) -> PermissionReadiness:
    """OFFLINE permission readiness evaluation for one scenario.

    The function never contacts Entra. It computes, deterministically,
    whether the scenario's declared delegated permissions are present
    in the supplied ``available_permissions`` set.

    Status semantics:

    * ``DISABLED`` -- the scenario is not enabled in the catalog.
    * ``READY`` -- all required scenario permissions are present in the
      available baseline; no additional grant is required.
    * ``MISSING_PERMISSION`` -- one or more required scenario
      permissions are not present; they are reported as
      ``missing_permissions``.

    The "effective required permissions" field reports the union of
    scenario-declared permissions that must be granted before this
    scenario can execute. It does not include baseline permissions
    that are already granted.
    """
    available = tuple(sorted(set(available_permissions)))
    required = tuple(loaded.definition.required_delegated_permissions)
    available_set = set(available)

    if not loaded.definition.enabled:
        return PermissionReadiness(
            scenario_id=loaded.scenario_id,
            enabled=False,
            required_scenario_permissions=required,
            effective_required_permissions=required,
            currently_available_permissions=available,
            missing_permissions=required,
            status=PERMISSION_DISABLED,
            reason=(
                "Scenario {0!r} is disabled in the catalog; readiness is "
                "not evaluated."
            ).format(loaded.scenario_id),
        )

    missing = tuple(sorted(perm for perm in required if perm not in available_set))
    if missing:
        return PermissionReadiness(
            scenario_id=loaded.scenario_id,
            enabled=True,
            required_scenario_permissions=required,
            effective_required_permissions=required,
            currently_available_permissions=available,
            missing_permissions=missing,
            status=PERMISSION_MISSING,
            reason=(
                "Scenario {0!r} is missing required delegated "
                "permission(s): {1}"
            ).format(loaded.scenario_id, ", ".join(missing)),
        )

    return PermissionReadiness(
        scenario_id=loaded.scenario_id,
        enabled=True,
        required_scenario_permissions=required,
        effective_required_permissions=required,
        currently_available_permissions=available,
        missing_permissions=(),
        status=PERMISSION_READY,
        reason=(
            "Scenario {0!r} is READY: all declared permissions are "
            "present in the available baseline."
        ).format(loaded.scenario_id),
    )


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def scenario_ids_in_deterministic_order(
    loaded: Iterable[LoadedScenario],
) -> Tuple[str, ...]:
    """Return the loaded scenario ids in a stable, sorted order."""
    return tuple(sorted(ls.scenario_id for ls in loaded))


# ---------------------------------------------------------------------------
# Observability validation
# ---------------------------------------------------------------------------


def validate_observability_g01_references(
    catalog_load: CatalogLoadResult,
    *,
    allowed_g01_ids: Iterable[str],
) -> None:
    """Validate every catalog observability reference is in G01-001..G01-019.

    Raises :class:`CatalogLoaderError` on the first invalid reference.
    This is a defensive second-pass check; the loader already rejects
    invalid references during parsing. The helper exists so callers
    can re-validate after the catalog is loaded.
    """
    allowed = set(allowed_g01_ids)
    for ls in catalog_load.loaded_scenarios:
        for endpoint in ls.catalog_metadata.expected_observable_sources:
            _validate_g01_endpoint(
                endpoint,
                where="catalog/{0}".format(ls.scenario_id),
                allowed_ids=allowed,
            )


__all__ = [
    "CATALOG_LOADER_DEFAULT_ROOT",
    "CatalogLoaderError",
    "build_catalog_registry",
    "evaluate_permission_readiness",
    "load_scenario_catalog",
    "scenario_ids_in_deterministic_order",
    "validate_observability_g01_references",
]


CATALOG_LOADER_DEFAULT_ROOT = _default_catalog_root()