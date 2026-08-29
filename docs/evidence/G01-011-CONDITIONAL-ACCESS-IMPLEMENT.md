# G01-011 Conditional Access Policies CURRENT_WITH_SNAPSHOT Implementation Evidence

- **Usage mark:** `G01-011-CONDITIONAL-ACCESS-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/identity/conditionalAccess/policies`.
- Permission: application `Policy.Read.All`.
- Inventory contract: paginated collection, `$top=100`, and approved `$select` fields `id`, `displayName`, `state`, `createdDateTime`, and `modifiedDateTime`.
- Adapter: `collectors/workloads/security_service/adapters.py`, `conditional_access_policies`.
- Registry: `G01-011` -> `CURRENT_WITH_SNAPSHOT`, owner `security_service`, current target `core.conditional_access_policy`, snapshot target `core.conditional_access_policy_snapshot`, retention `REFERENCE`.

## Field Boundary

The adapter maps only `id` -> `source_object_id`, `displayName` -> `display_name`, `state` -> `state`, `createdDateTime` -> `created_date_time`, and `modifiedDateTime` -> `modified_date_time`. Trusted runtime lineage is added by the adapter boundary. Conditions, grant controls, session controls, unknown fields, credentials, tokens, authorization material, and raw Graph objects are not persisted.

Missing IDs and malformed records fail closed. Optional approved fields remain nullable. Policy payload tenant-shaped fields cannot replace the trusted runtime tenant.

## Persistence Verified

- Current writes use the closed `G01-011` SQL mapping, parameter-bound values, conflict key `(tenant_id, source_object_id)`, and `ON CONFLICT DO UPDATE`.
- Snapshot writes use conflict key `(tenant_id, source_object_id, collection_run_id)` and `ON CONFLICT DO NOTHING` for replay safety.
- `CollectionWriter` validates tenant, endpoint, and mode before transaction start and rolls back post-`BEGIN` failures without committing partial current/snapshot writes.
- Retention decision: `STANDARD -> REFERENCE`, aligned with `docs/data-catalog.md` and the schema reconciliation.

## Tests Executed

```text
python3 -m unittest tests.workloads.security_service.test_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

Result: **213 tests passed**. Coverage includes valid normalization, optional fields, missing IDs, malformed records, field exclusion, multi-page traversal, empty response, malformed page and next link, no-partial-write behavior, registry mapping, parameter-bound current upsert, snapshot insert, replay, tenant mismatch, and rollback.

## Architecture Boundary

```text
Graph Collector -> Security-Service Adapter -> Registry -> Persistence Dispatcher
    -> Security Boundary -> CURRENT_WITH_SNAPSHOT Writer -> Database
```

The implementation reused the existing adapter, trusted tenant resolver, paginator, registry dispatch, dispatcher, security boundary, snapshot/current writer, and transactional `CollectionWriter`. No new writer, migration redesign, dispatcher redesign, or architecture change was introduced.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
