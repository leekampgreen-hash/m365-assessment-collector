# EX-P05 Exchange Collector Normalization Wiring

- **Task ID:** `EX-P05-EXCHANGE-COLLECTOR-NORMALIZATION-WIRING-001`
- **Date:** 2026-08-29
- **Result:** `EX_P05_PASS`

## Production wiring

- **Inventory:** `config/api_inventory.json` binds `USAGE-003` to `exchange_mailbox_usage`, `USAGE_REPORT_CSV`, D7, and `/v1.0/reports/getMailboxUsageDetail(period='D7')`.
- **Permission:** application `Reports.Read.All`; runtime capability gate is enforced before collection.
- **Collector binding:** `collectors/usage_reports/transport.py` performs the Graph report request and explicit approved download redirect; `adapters.exchange_mailbox_usage` invokes the production normalizer.
- **Runtime:** `collectors/run_collector.py` constructs `CollectorRuntime` with database persistence; `collectors/core/runtime.py:_execute_usage_report` invokes the report transport, adapter, and writer.
- **Persistence:** `CollectionWriter.write_usage_report` delegates to current/snapshot usage persistence in one transaction. The completeness argument is now propagated to `write_report_rows`.

## Source and normalization contract

- Headers supported: `User Principal Name`/`UPN`; `Storage Used (Byte)`, `Storage Used (Bytes)`, `Storage Used`; `Prohibit Send/Receive Quota`, `(Byte)`, `(Bytes)`; `Report Refresh Date`.
- `prohibit_send_receive_quota` is the only authoritative mailbox capacity denominator; no license inference exists in this path.
- UPN is required for Exchange mailbox rows; missing, blank, masked, or unavailable identity fails closed. Identity keys are stripped and case-folded; duplicates are checked after normalization by persistence.
- Numeric fields parse to integers or NULL. Invalid numeric values are not coerced. Required report refresh date is rejected when blank; storage/capacity remain nullable and downstream derived status handles missing values.
- Snapshot and current rows carry `report_refresh_date`; normalized values match the EX-P03 BIGINT/date/text contract.

## Completeness and safety

A successful fully acquired report reaches persistence with `complete=True`. HTTP, network, CSV/schema, identity, normalization, or persistence failures do not write rows. Incomplete acquisition passed to the persistence boundary is rejected before SQL; unknown completeness is not converted to complete by the runtime. Current replacement therefore cannot occur from a partial report.

## Packaging and tests

`Dockerfile.collector` copies `collectors` into `/workspace/collectors`; Compose uses `graph-agent-collector:dev` for both `collector` and `operations-api`, with the collector source mounted for the collector service and the API using the rebuilt image. Runtime parity after rebuild/recreate: PASS for analytics, usage registry, API, persistence, and runtime modules.

Focused production-container suite: `33 tests`, `OK`. Coverage included complete report runtime path, singular `(Byte)`, plural `(Bytes)`, invalid numeric NULL behavior, normalized duplicate rejection, incomplete persistence rejection, missing identity rejection, and refresh-date propagation. Python compileall passed.

## Live read-only check

A bounded native `USAGE-003` run was performed through `graph-agent-collector-dev` with `Reports.Read.All`. It returned `PASS`, `pages=1`, `source_rows=30`, `rows=30`, and `persisted_rows=30`. Existing proven report/database evidence confirms 30 populated identities, storage, capacity, and refresh date (`2026-08-25`). No synthetic business rows were committed.

## Classification

- **BLOCKING:** None.
- **NON_BLOCKING_TECH_DEBT:** None introduced or required.
- **HISTORICAL_ARTIFACT:** Prior stale image parity mismatch before rebuild; resolved by rebuild/recreate. Existing unrelated historical fixture notes remain unchanged.
- **DEFERRED:** Final broad live acceptance remains EX-P08 scope; protection gaps and UX remain out of scope.

- **COLLECTOR_WIRING_READY:** YES
- **READY_FOR_EX_P06:** YES
- **FINAL_STATUS:** `EX_P05_PASS`

No token or credit data is recorded.
