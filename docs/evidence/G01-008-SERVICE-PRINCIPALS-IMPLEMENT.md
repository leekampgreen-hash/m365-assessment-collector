# G01-008 Service Principals CURRENT Implementation Evidence

- **Usage mark:** `G01-008-SERVICE-PRINCIPALS-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/servicePrincipals`.
- Permission: `Application.Read.All`.
- Inventory contract: application authentication, paginated collection, approved `$select` fields `id`, `appId`, `displayName`, `accountEnabled`, and `servicePrincipalType`.
- Adapter: `collectors/workloads/directory/service_principals.py`.
- Registry: `G01-008` -> `CURRENT`, owner `directory`, adapter `directory.service_principals`, target `core.service_principal`, retention `REFERENCE`.
- Persistence: existing dispatcher, security boundary, parameter-bound current writer, and one-transaction `CollectionWriter`.
- Conflict key: `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE` replay behavior.

## Field Boundary

The normalized service-principal row retains only the approved Graph fields mapped as follows:

- `id` -> `source_object_id`
- `appId` -> `app_id`
- `displayName` -> `display_name`
- `accountEnabled` -> `account_enabled`
- `servicePrincipalType` -> `service_principal_type`

Unknown properties, `keyCredentials`, `passwordCredentials`, `appRoleAssignments`, `oauth2PermissionGrants`, permission payloads, tokens, secrets, and authorization material are not copied. Missing optional fields remain nullable; missing `id` and malformed objects fail closed.

## Tests Executed

```text
python3 -m unittest tests.workloads.directory.test_directory_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

Result: **256 tests passed**.

Coverage includes successful normalization, optional fields, missing ID, malformed objects, approved-field and credential exclusion, `@odata.nextLink` traversal, empty results, malformed later-page failure without writer invocation, registry metadata, parameter-bound current upsert, deterministic replay, tenant mismatch rejection, and rollback preservation.

The broader offline discovery and migration regression command passed 100 tests. Full test discovery ran 608 tests: 605 passed and 3 unrelated `scenario.live` operator-entrypoint tests failed because interactive authentication/network expectations were unavailable (`AUTH_DEVICE_CODE_ERROR` and socket/request expectation failures). No G01-008 test failed.

## Architecture Boundary

The implementation follows the frozen flow without redesign:

```text
Graph Collector -> Directory Adapter -> Registry -> Persistence Dispatcher
    -> Security Boundary -> CURRENT Writer -> Database
```

The Service Principals production adapter, inventory entry, G01-008 registry entry, persistence mapping, paginator, dispatcher, and writer were already present and aligned with the approved contract. This implementation added explicit G01-008 handoff and failure-path coverage rather than duplicating foundation components.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
