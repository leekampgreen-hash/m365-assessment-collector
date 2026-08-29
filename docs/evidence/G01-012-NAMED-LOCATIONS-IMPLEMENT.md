# G01-012 Named Locations CURRENT Implementation Evidence

- **Usage mark:** `G01-012-RETENTION-ALIGNMENT-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/identity/conditionalAccess/namedLocations`.
- Permission: application `Policy.Read.All`.
- Inventory contract: paginated collection, `$top=100`, and approved fields `id`, `displayName`, `createdDateTime`, and `modifiedDateTime`.
- Adapter: `collectors/workloads/security_service/adapters.py`, `named_locations`.
- Registry: `G01-012` -> `CURRENT`, owner `security_service`, adapter `security_service.named_locations`, target `core.named_location`, retention `REFERENCE`.

## Field Boundary

The adapter maps only `id` -> `source_object_id`, `displayName` -> `display_name`, `createdDateTime` -> `created_date_time`, and `modifiedDateTime` -> `modified_date_time`. Trusted runtime lineage is added by the adapter boundary. `ipRanges`, `countriesAndRegions`, unknown fields, credentials, tokens, authorization material, and raw Graph objects are not persisted.

Missing IDs and malformed records fail closed. Optional approved fields remain nullable. Payload tenant-shaped data cannot replace the trusted runtime tenant.

## Persistence Verified

- Current writes use the closed `G01-012` SQL mapping, parameter-bound values, conflict key `(tenant_id, source_object_id)`, and `ON CONFLICT DO UPDATE`.
- `CollectionWriter` validates tenant, endpoint, and mode before transaction start and rolls back post-`BEGIN` failures without committing partial writes.
- Retention decision: `STANDARD -> REFERENCE`, aligned with `docs/data-catalog.md` and the schema reconciliation.

## Tests Executed

```text
python3 -m unittest tests.workloads.security_service.test_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

Result: **220 tests passed**. Coverage includes valid normalization, optional fields, missing IDs, malformed records, field exclusion, multi-page traversal, empty response, malformed page and next link, no-partial-write behavior, registry mapping, parameter-bound current upsert, replay, tenant mismatch, and rollback.

## Architecture Boundary

```text
Graph Collector -> Security-Service Adapter -> Registry -> Persistence Dispatcher
    -> Security Boundary -> CURRENT Writer -> Database
```

The implementation reused the existing adapter, trusted tenant resolver, paginator, registry dispatch, dispatcher, security boundary, current writer, SQL mapping, and transactional `CollectionWriter`. No new writer, migration redesign, dispatcher redesign, or architecture change was introduced.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
