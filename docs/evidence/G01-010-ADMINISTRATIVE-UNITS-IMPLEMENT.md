# G01-010 Administrative Units CURRENT Implementation Evidence

- **Usage mark:** `G01-010-ADMINISTRATIVE-UNITS-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/directory/administrativeUnits`.
- Permission: `AdministrativeUnit.Read.All`.
- Inventory contract: application authentication, paginated collection, approved `$select` fields `id`, `displayName`, `description`, and `visibility`.
- Adapter: `collectors/workloads/directory/administrative_units.py`.
- Registry: `G01-010` -> `CURRENT`, owner `directory`, adapter `directory.administrative_units`, target `core.administrative_unit`, retention `REFERENCE`.
- Persistence: existing dispatcher, security boundary, parameter-bound current writer, and one-transaction `CollectionWriter`.
- Conflict key: `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE` replay behavior.

## Field Boundary

The normalized current row retains only the approved Graph fields mapped as follows:

- `id` -> `source_object_id`
- `displayName` -> `display_name`
- `description` -> `description`
- `visibility` -> `visibility`

Trusted tenant and collection lineage plus `last_observed_at` and `retention_class` are retained as persistence metadata. Unknown properties, credential material, token material, and authorization data are not copied. Missing optional fields remain nullable; missing `id` and malformed objects fail closed.

## Tests Executed

```text
python3 -m unittest tests.workloads.directory.test_directory_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

The focused suite covers normalization, missing IDs, malformed objects, optional fields, closed field mapping, credential exclusion, `@odata.nextLink` traversal, multi-page collection, empty results, malformed pages, malformed next links, no-partial-write behavior, registry metadata, parameter-bound current upsert, deterministic replay, tenant mismatch rejection, and rollback preservation.

Result: **266 tests passed**. The migration/discovery regression command passed **100 tests**. Full offline discovery ran **611 tests: 608 passed and 3 unrelated `scenario.live` operator-entrypoint authentication/network tests failed**; no G01-010 test failed.

## Architecture Boundary

The implementation follows the frozen flow without redesign:

```text
Graph Collector -> Directory Adapter -> Registry -> Persistence Dispatcher
    -> Security Boundary -> CURRENT Writer -> Database
```

The existing G01-010 inventory entry, adapter, registry, closed persistence mapping, paginator, dispatcher, security boundary, and writer were verified and reused. Changes were limited to explicit G01-010 validation coverage and documentation evidence.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
