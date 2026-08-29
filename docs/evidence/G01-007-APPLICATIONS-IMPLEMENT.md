# G01-007 Applications CURRENT Implementation Evidence

- **Usage mark:** `G01-007-APPLICATIONS-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/applications`.
- Permission: `Application.Read.All`.
- Inventory contract: application auth, paginated collection, approved `$select` fields `id`, `appId`, `displayName`, `createdDateTime`, and `signInAudience`.
- Adapter: `collectors/workloads/directory/applications.py`.
- Registry: `G01-007` -> `CURRENT`, owner `directory`, adapter `directory.applications`, target `core.application`, retention `REFERENCE`.
- Persistence: existing dispatcher, security boundary, parameter-bound current writer, and one-transaction `CollectionWriter`.
- Conflict key: `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE` replay behavior.

## Field Boundary

The normalized application row retains only the approved Graph fields mapped as follows:

- `id` -> `source_object_id`
- `appId` -> `app_id`
- `displayName` -> `display_name`
- `createdDateTime` -> `created_date_time`
- `signInAudience` -> `sign_in_audience`

Unknown properties, `passwordCredentials`, `keyCredentials`, `publicClient`, `web`, `spa`, `requiredResourceAccess`, tokens, and authorization material are not copied. Missing optional fields remain nullable; missing `id` and malformed objects fail closed.

## Tests Executed

```text
python3 -m unittest tests.workloads.directory.test_directory_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

Result: **250 tests passed**.

Coverage includes successful normalization, optional fields, missing ID, malformed payload, unknown-field and credential/key exclusion, `@odata.nextLink` traversal, empty results, malformed later-page failure without writer invocation, registry metadata, parameter-bound current upsert, deterministic replay, tenant mismatch rejection, and rollback preservation.

## Architecture Boundary

The implementation follows the frozen flow without redesign:

```text
Graph Collector -> Directory Adapter -> Registry -> Persistence Dispatcher
    -> Security Boundary -> CURRENT Writer -> Database
```

The Applications production adapter, registry entry, persistence mapping, dispatcher, and writer were already present and aligned with the approved contract. This implementation added explicit G01-007 handoff and failure-path coverage rather than duplicating foundation components.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
