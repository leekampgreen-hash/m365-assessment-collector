# G08-C Scenario Catalog / Framework Integration

This document describes the G08-C integration between the G08-B
machine-readable scenario catalog (`config/scenarios/`) and the G08-A
deterministic Scenario Agent framework (`agents/scenario/`). It
captures the boundary contracts, the vocabulary normalisation rules,
the OFFLINE permission readiness model, the actor-alias model, and
the explicit no-live-Graph invariant.

The integration is OFFLINE only. No live Microsoft Graph call is made.
No permission is granted. No actor UPN is resolved. No secret is read.

---

## 1. Scope

* Load the accepted G08-B catalog (`config/scenarios/catalog.json`)
  and the nine referenced scenario JSON files.
* Normalise catalog-side vocabulary into the framework's closed
  vocabulary without losing catalog-only semantics.
* Bind a deterministic `ScenarioRegistry` that contains both the
  framework's built-in scenarios and the catalog scenarios.
* Provide an OFFLINE permission-readiness evaluation per scenario.
* Provide a dry-run end-to-end path for `SCN-AUTH-001` and a clear
  BLOCKED path for every disabled scenario.

Out of scope (G08-C explicitly does not):

* Call Microsoft Graph.
* Modify Entra ID.
* Resolve real UPNs or load credentials.
* Connect to PostgreSQL or any other backing service.
* Grant permissions.
* Run a live executor.

---

## 2. Files added

| Path | Purpose |
|------|---------|
| `agents/scenario/catalog_models.py` | Pure-data integration types (`LoadedScenario`, `CatalogMetadata`, `PermissionReadiness`, `CatalogLoadResult`, `CatalogRegistryResult`) and the closed vocabulary tables for vocabulary normalisation. |
| `agents/scenario/catalog_loader.py` | `load_scenario_catalog`, `build_catalog_registry`, `evaluate_permission_readiness`, `scenario_ids_in_deterministic_order`, `validate_observability_g01_references`. Pure JSON parsing; no I/O outside the catalog directory. |
| `tests/scenario/integration/test_catalog_load.py` | Loader / duplicate / malformed behaviour. |
| `tests/scenario/integration/test_vocabulary_risk.py` | LOW / MODERATE / HIGH mapping; unknown risk rejection. |
| `tests/scenario/integration/test_vocabulary_actions.py` | Catalog action -> framework action mapping. |
| `tests/scenario/integration/test_permissions.py` | Baseline / missing / readiness contract. |
| `tests/scenario/integration/test_actor_loading.py` | Alias-only actor loading with no credentials. |
| `tests/scenario/integration/test_cleanup_semantics.py` | `cleanup_behavior` preserved; no numeric-id adjacency inference. |
| `tests/scenario/integration/test_observability.py` | G01-001..G01-019 only; classification preserved. |
| `tests/scenario/integration/test_registry_integration.py` | Pure registry build; no global mutation. |
| `tests/scenario/integration/test_e2e_dry_run.py` | SCN-AUTH-001 full path; disabled-scenario BLOCKED path. |

Framework files modified:

| Path | Change |
|------|--------|
| `agents/scenario/actions.py` | Added four framework action types: `UPDATE_CALENDAR_EVENT`, `DELETE_CALENDAR_EVENT`, `DELETE_FILE`, `INTERACTIVE_SIGNIN`. Each carries its own closed parameter-key set and declared delegated permissions. |
| `agents/scenario/__init__.py` | Re-exports new action constants and the new loader / integration API. |
| `tests/scenario/framework/test_actions.py` | Updated `test_supported_action_types_are_documented` to include the new action types. |

Protected files remain unchanged:

* `collectors/**`
* `database/**`
* `config/api_inventory.json`
* `agents/discovery/**`
* `data/discovery/**`
* `secrets/**`
* `config/scenarios/**` (G08-B catalog files are not modified).

---

## 3. Catalog loading

`load_scenario_catalog()` reads:

* `config/scenarios/catalog.json` (the index)
* `config/scenarios/actor_model.json` (logical actor aliases)
* `config/scenarios/observability_map.json` (classification source)
* `config/scenarios/scenarios/SCN-*.json` (the nine scenarios)

The loader:

1. Parses the catalog index.
2. Reads every scenario JSON, validates required fields, normalises
   vocabulary (risk, action, observability, cleanup behavior).
3. Rejects unknown risk values and unknown catalog action types.
4. Rejects duplicate `scenario_id` values within the catalog.
5. Records any malformed scenario as a non-fatal entry in
   `CatalogLoadResult.malformed`.
6. Verifies catalog totals match the loaded + malformed + duplicate
   counts.
7. Produces a deterministic ordering (sorted by `scenario_id`).

The loader never reads secrets and never resolves actors to UPNs.
The `user_principal_name` field on every `ScenarioActor` produced by
the loader is `None`.

---

## 4. Vocabulary normalisation

### 4.1 Risk

| Catalog | Framework |
|---------|-----------|
| `LOW` | `LOW` |
| `MODERATE` | `MEDIUM` |
| `HIGH` | `HIGH` |

Unknown values (including `low`, `Medium`, `MOD`, `INTERMEDIATE`,
etc.) are rejected. The mapping is explicit, closed, and case
sensitive.

### 4.2 Action

| Catalog action | Framework action |
|----------------|------------------|
| `SEND_MAIL` | `SEND_MAIL` |
| `CREATE_EVENT` | `CREATE_CALENDAR_EVENT` |
| `UPDATE_EVENT` | `UPDATE_CALENDAR_EVENT` |
| `DELETE_EVENT` | `DELETE_CALENDAR_EVENT` |
| `CREATE_FILE` | `CREATE_FILE` |
| `UPDATE_FILE` | `UPDATE_FILE` |
| `DELETE_FILE` | `DELETE_FILE` |
| `INTERACTIVE_SIGNIN` | `INTERACTIVE_SIGNIN` |

Unknown catalog action types are rejected. `INTERACTIVE_SIGNIN` is
semantically distinct from `NOOP_VALIDATION` and performs no Microsoft
Graph write.

### 4.3 Observability classification

Closed vocabulary:

* `DIRECTLY_OBSERVABLE`
* `INDIRECTLY_OBSERVABLE`
* `NOT_COVERED_BY_CURRENT_G01_INVENTORY`

The classification is preserved verbatim on `CatalogMetadata`.
`INDIRECTLY_OBSERVABLE` is never silently upgraded to
`DIRECTLY_OBSERVABLE`. Mail / calendar / files content is never
classified as directly observable because the G01 inventory does not
collect those workloads.

### 4.4 Cleanup behavior

Closed vocabulary:

* `AUTO_CLEANUP_SUPPORTED`
* `MANUAL_CLEANUP`
* `NO_CLEANUP_REQUIRED`

The behavior is preserved verbatim. The framework
`cleanup_scenario_id` field on `ScenarioDefinition` stays `None`
unless the catalog explicitly declares a pairing. The loader must
never infer a pairing from numeric ID adjacency.

---

## 5. Permission readiness

The integration introduces an OFFLINE readiness evaluation
(`evaluate_permission_readiness`) that distinguishes three states:

* `READY` -- the scenario is enabled and all required delegated
  permissions are present in the supplied available baseline.
* `MISSING_PERMISSION` -- the scenario is enabled but one or more
  required permissions are not present; the missing permissions are
  reported.
* `DISABLED` -- the scenario is not enabled in the catalog;
  permissions are still reported for documentation but the scenario
  cannot be planned.

The current available baseline for the Scenario Agent App is
`User.Read` only (from `permission_packs.json` and
`catalog.json`). Outcomes under that baseline:

| Scenario | Status | Missing |
|----------|--------|---------|
| `SCN-AUTH-001` | `READY` | `[]` |
| `SCN-MAIL-001` | `DISABLED` | `[Mail.Send]` |
| `SCN-MAIL-002` | `DISABLED` | `[Mail.Send]` |
| `SCN-CALENDAR-001` | `DISABLED` | `[Calendars.ReadWrite]` |
| `SCN-CALENDAR-002` | `DISABLED` | `[Calendars.ReadWrite]` |
| `SCN-CALENDAR-003` | `DISABLED` | `[Calendars.ReadWrite]` |
| `SCN-FILE-001` | `DISABLED` | `[Files.ReadWrite]` |
| `SCN-FILE-002` | `DISABLED` | `[Files.ReadWrite]` |
| `SCN-FILE-003` | `DISABLED` | `[Files.ReadWrite]` |

The readiness evaluator never contacts Entra; it uses the configured
baseline as the source of truth. It also never silently grants a
missing permission.

---

## 6. Actor alias boundary

Actors are loaded from `config/scenarios/actor_model.json`. The
loader:

* Sets `actor_id` to the alias (e.g. `test-user-01`).
* Leaves `user_principal_name` and `object_id` as `None`.
* Sets `enabled = True` for every alias (the catalog invariant
  `alias_set_is_closed` implies all aliases are usable; the safety
  gate handles scenario-level disabled state).
* Rejects any record that ships a credential-shaped field
  (`password`, `token`, `secret`, `api_key`, `client_secret`,
  `access_token`, `refresh_token`, `authorization_header`, ...).
* Rejects any record whose `upn_resolution` is not
  `DEFERRED_TO_RUNTIME_CONFIG`.

UPN resolution is deferred to a future live integration layer. The
G08-C loader never fabricates UPN values.

---

## 7. Registry integration

`build_catalog_registry(load_result)` returns a `CatalogRegistryResult`
containing a `ScenarioRegistry` that includes:

* The seven built-in framework scenarios.
* All nine catalog scenarios.

The registry build is:

* Pure -- calling it twice yields equivalent registries.
* Deterministic -- the scenario ids are stable across instances.
* Safe -- it raises `CatalogLoaderError` if any catalog scenario id
  collides with a built-in id (currently: no collisions).

The framework's global `ScenarioRegistry()` is not mutated as a side
effect of the load.

---

## 8. Dry-run end-to-end path for SCN-AUTH-001

```
catalog
  -> load_scenario_catalog()
  -> LoadedScenario (definition + catalog_metadata)
  -> build_catalog_registry()
  -> ScenarioRegistry
  -> ScenarioAgent.plan(ScenarioRequest(scenario_id="SCN-AUTH-001",
                                         actor=test-user-01))
     -> evaluate_safety(...)    # passes: enabled, identity supplied,
                                # permissions declared, action supported
     -> ScenarioPlan
  -> ScenarioAgent.execute(plan, actor=...)
     -> DryRunScenarioExecutor.execute(step, actor, plan)
        -> ScenarioStepResult(status=SUCCESS,
                              evidence=[...], action=INTERACTIVE_SIGNIN)
     -> ScenarioExecutionResult(status=SUCCESS,
                                correlation_id="GA-SCENARIO-exec-<uuid>",
                                final_evidence=[...])
```

Properties verified offline:

* `correlation_id` starts with `GA-SCENARIO-`.
* `risk_level = LOW`, `destructive = False`,
  `cleanup_required = False`.
* `INTERACTIVE_SIGNIN` action is distinct from `NOOP_VALIDATION`.
* `required_delegated_permissions` recognises the existing
  `User.Read` baseline (no additional permission grant required).
* Permission readiness reports `READY`, `missing = []`.
* Zero network calls; zero Graph calls; zero tenant changes.
* Disabled scenarios raise `ScenarioBlockedError` with reason code
  `SCENARIO_DISABLED` and never reach the executor.

---

## 9. Next boundary

The integration is intentionally ready for a future live executor
without requiring any change to the framework:

* A live `ScenarioActionExecutor` implementation can be injected into
  `ScenarioAgent(executor=...)` without modifying the loader.
* Permission granting, real UPN resolution, and any contact with
  Entra remain outside the scope of G08-C. They are explicitly
  referenced in `docs/g08-scenario-permission-matrix.md` and must be
  performed by a separate, approved task.