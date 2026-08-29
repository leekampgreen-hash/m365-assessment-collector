# G01-003 Organization CURRENT Implementation Evidence

- **Usage mark:** `G01-003-ORGANIZATION-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/organization`.
- Documented permission: `Organization.Read.All`.
- Inventory contract: application auth, `pagination: false`, approved `$select` fields, enabled endpoint.
- Adapter: `collectors/workloads/directory/organization.py`.
- Registry: `G01-003` -> `CURRENT`, owner `directory`, adapter `directory.organization`, target `core.organization`.
- Persistence: existing `dispatch_persistence` and current writer; no new writer, migration, or SQL architecture change.
- Conflict key: `(tenant_id)`; replay updates `source_object_id`, approved organization fields, observation timestamp, and retention class for the existing tenant row.

## Field Boundary

The normalized organization row retains only the approved Graph fields `id`, `displayName`, `verifiedDomains`, `countryLetterCode`, and `tenantType`, represented as `source_object_id`, `display_name`, `verified_domains`, `country_letter_code`, and `tenant_type`. Trusted lineage and retention metadata are added by the established adapter contract. Unknown Graph fields, credentials, tokens, and authorization material are not copied.

## Tests Executed

```text
python3 -m unittest tests.workloads.directory.test_directory_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

Result: **228 tests passed**.

Coverage includes successful normalization, single-object runtime handoff, malformed response failure, missing `id` failure, optional fields, unknown-field exclusion, registry validation, CURRENT dispatch, tenant boundary, deterministic idempotent persistence replay, and credential exclusion.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance. The documented Organization permission anomaly remains preserved in the existing permission documentation and was not changed by this implementation.
