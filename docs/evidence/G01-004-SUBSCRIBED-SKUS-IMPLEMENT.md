# G01-004 Subscribed SKUs Implementation Evidence

- **Usage mark:** `G01-004-SUBSCRIBED-SKUS-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/subscribedSkus`.
- Documented permission: `LicenseAssignment.Read.All`.
- Inventory contract: application auth, `pagination: true`, approved `$select` fields, enabled endpoint.
- Adapter: `collectors/workloads/directory/subscribed_skus.py`.
- Registry: `G01-004` -> `CURRENT_WITH_SNAPSHOT`, owner `directory`, adapter `directory.subscribed_skus`, current target `core.subscribed_sku`, snapshot target `core.subscribed_sku_snapshot`.
- Persistence: existing `dispatch_persistence`, security boundary, and `write_snapshot_record`; no new writer, migration, or dispatcher change.
- Current conflict key: `(tenant_id, source_object_id)`.
- Snapshot conflict key: `(tenant_id, source_object_id, collection_run_id)` with `DO NOTHING` replay semantics.
- Atomicity: `CollectionWriter` executes current and snapshot statements in one transaction and rolls back on post-`BEGIN` writer failure.

## Field Boundary

The adapter retains only the approved Graph fields `id`, `skuId`, `skuPartNumber`, `capabilityStatus`, `consumedUnits`, `prepaidUnits`, and `servicePlans`, represented in normalized rows as `source_object_id`, `sku_id`, `sku_part_number`, `capability_status`, `consumed_units`, `prepaid_units`, and `service_plans`. Trusted lineage and retention metadata are added by the established adapter contract. Unknown fields, tokens, credentials, and authorization material are not copied.

`prepaidUnits` is normalized to one scalar integer: `enabled + suspended + warning`. Missing, non-object, and non-integer subfields are safely treated as zero; boolean values are not counted as integers.

## Tests Executed

```text
python3 -m unittest tests.workloads.directory.test_directory_adapters tests.workloads.test_integration tests.workloads.test_registry tests.persistence.test_core tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff
```

Result: **233 tests passed**.

Coverage includes pagination, empty response, malformed response, missing `id`, optional fields, all prepaid-unit variations, unknown-field exclusion, credential exclusion, registry mapping, current and snapshot SQL writes, conflict/replay behavior, tenant boundary validation, and rollback behavior.

## Files Changed

- `tests/workloads/test_integration.py`
- `tests/core/test_g09_r2_normalization_handoff.py`
- `docs/PROJECT_PROGRESS.md`
- `docs/CHANGELOG.md`
- `docs/AI_USAGE_LOG.md`
- `docs/evidence/G01-004-SUBSCRIBED-SKUS-IMPLEMENT.md`

The production collection, adapter, registry, dispatcher, security boundary, and persistence writer were already present and matched the accepted G01-002/G01-003 architecture; they were validated and reused without modification.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
