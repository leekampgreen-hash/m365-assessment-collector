# G01-009 Devices CURRENT Implementation Evidence

- **Usage mark:** `G01-009-DEVICES-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/devices`.
- Permission: `Device.Read.All`.
- Inventory contract: application authentication, paginated collection, approved `$select` fields `id`, `deviceId`, `accountEnabled`, `operatingSystem`, `operatingSystemVersion`, `trustType`, and `approximateLastSignInDateTime`.
- Adapter: `collectors/workloads/directory/devices.py`.
- Registry: `G01-009` -> `CURRENT`, owner `directory`, adapter `directory.devices`, target `core.device`, retention `REFERENCE`.
- Persistence: existing dispatcher, security boundary, parameter-bound current writer, and one-transaction `CollectionWriter`.
- Conflict key: `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE` replay behavior.

## Field Boundary

The normalized device row retains only the approved Graph fields mapped as follows:

- `id` -> `source_object_id`
- `deviceId` -> `device_graph_id`
- `accountEnabled` -> `account_enabled`
- `operatingSystem` -> `operating_system`
- `operatingSystemVersion` -> `operating_system_version`
- `trustType` -> `trust_type`
- `approximateLastSignInDateTime` -> `approximate_last_sign_in_date_time`

Unknown properties, credential material, token material, authorization data, and other unapproved fields are not copied. Missing optional fields remain nullable; missing `id` and malformed objects fail closed.

## Tests Executed

```text
python3 -m unittest tests.workloads.directory.test_directory_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

Result: **260 tests passed**.

Coverage includes successful normalization, missing ID, malformed object, optional fields, closed field mapping, credential exclusion, `@odata.nextLink` traversal, empty results, malformed later-page failure without writer invocation, registry metadata, parameter-bound current upsert, deterministic replay, tenant mismatch rejection, and rollback preservation.

The migration/discovery regression command passed 100 tests. Full offline discovery ran 609 tests: 606 passed and 3 unrelated `scenario.live` operator-entrypoint tests failed because interactive authentication/network expectations were unavailable. No G01-009 test failed.

## Architecture Boundary

The implementation follows the frozen flow without redesign:

```text
Graph Collector -> Directory Adapter -> Registry -> Persistence Dispatcher
    -> Security Boundary -> CURRENT Writer -> Database
```

The existing G01-009 inventory entry, adapter, registry entry, closed persistence mapping, paginator, dispatcher, security boundary, and writer were verified and reused. Changes were limited to explicit G01-009 validation coverage and documentation evidence.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance. `docs/TECHNICAL_DEBT.md` and `docs/FUTURE_VALIDATION_BACKLOG.md` were requested but are not present in the workspace.
