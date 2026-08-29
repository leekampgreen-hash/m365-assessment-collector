# EX-P04 Exchange Persistence History Reconciliation

- **Task ID:** `EX-P04-EXCHANGE-PERSISTENCE-HISTORY-RECONCILIATION-001`
- **Date:** 2026-08-29
- **Result:** `EX_P04_BLOCKED`

## Scope and evidence

The reviewed path is `collectors/usage_reports/registry.py` → `collectors/usage_reports/persistence.py` → `collectors/persistence/core.py` and migrations `008_usage_reports.sql`, `013_usage_reports_current_delete.sql`, `014_exchange_mailbox_quota.sql`, and `015_exchange_mailbox_capacity.sql`. Offline usage-report tests pass. Live PostgreSQL was queried without changing data.

## CURRENT_TABLE

- **table:** `core.usage_exchange_mailbox_usage`
- **business_key:** normalized, case-folded `entity_key` (UPN for mailbox rows)
- **tenant_key:** `tenant_id`, required foreign key to `core.tenant`
- **uniqueness:** primary key `usage_id`; unique `(tenant_id, entity_key)`; this guarantees one current row per tenant/mailbox
- **replacement_semantics:** `write_usage_report` opens one transaction; non-empty input deletes all current rows for each input tenant, then upserts rows by `(tenant_id, entity_key)`
- **disappearing_mailbox_semantics:** omitted mailboxes are deleted during a non-empty replacement; empty reports are a safe no-op
- **partial_collection_semantics:** no completeness signal exists; any non-empty partial input is treated as a complete replacement and can delete valid current rows (BLOCKING)

`storage_used`, `issue_warning_quota`, `prohibit_send_quota`, and authoritative `prohibit_send_receive_quota` are BIGINT columns. Normalization parses them as integers and invalid values become NULL. Capacity is derived only from `prohibit_send_receive_quota`.

## SNAPSHOT

- **table:** `core.usage_exchange_mailbox_usage_snapshot`
- **snapshot_key:** primary key `usage_id`; logical identity `snapshot_identity = tenant_id:entity_key:report_refresh_date`
- **generation_key:** `(tenant_id, entity_key, report_refresh_date)`
- **append_semantics:** insert-only; `ON CONFLICT ... DO NOTHING`
- **duplicate_prevention:** unique `(tenant_id, entity_key, report_refresh_date)`; live schema also contains a redundant duplicate unique index from migration history (NON_BLOCKING)
- **repeated_generation:** same generation is ignored; current replacement still runs
- **historical_immutability:** application writer does not update or delete snapshots; shared transaction rollback protects them on failure
- **retention:** no retention policy found

Older rows with NULL quota fields are legitimate historical artifacts predating migration 014 and are preserved.

## LIVE_DATA

- **current_rows:** 30
- **unique_mailboxes:** 30 (`entity_key`; all live rows are tenant 2)
- **duplicate_keys:** 0
- **null_identity:** 0
- **null_storage_used:** 0
- **null_capacity:** 0
- **invalid_numeric:** 0
- **zero_capacity:** 0
- **latest_refresh:** 2026-08-25
- **snapshot_rows:** 90
- **snapshot_generations:** 3 dates: 2026-08-23, 2026-08-24, 2026-08-25; 30 rows each
- **historical_artifacts:** generations before quota support are represented by NULL quota values where present; no rewrite is warranted

The current table has one `observed_at` generation in live data (`2026-08-28T04:48:45.596086Z`).

## IDEMPOTENCY

- **repeated_generation:** snapshot deduplication is controlled; current state is deterministic for unique source keys
- **duplicate_source_row:** duplicate source keys are not rejected or explicitly deduplicated; final current values depend on input order, while snapshot conflict handling keeps one history row (BLOCKING)
- **retry:** `write_usage_report` transaction rolls back all current and snapshot writes on failure; retry is safe for accepted complete input
- **cross_tenant:** tenant is validated by `write_usage_report`; all keys and conflicts include `tenant_id`; no cross-tenant collision observed

## FAILURE_SEMANTICS

- **transaction_boundary:** Graph acquisition is outside the database transaction; current delete/upserts and snapshot inserts are in one DB transaction
- **current_snapshot_consistency:** DB write failure rolls back both. The writer cannot commit current without snapshot or snapshot without current. Graph success followed by DB failure leaves prior DB state intact.
- **empty_report:** no-op; current and history remain unchanged
- **schema_drift:** CSV required-column validation rejects missing required fields; optional missing fields become NULL. Database schema/column drift raises and rolls back. There is no explicit report completeness or source duplicate validation.

## GAP CLASSIFICATION

### BLOCKING

1. Non-empty partial collections are indistinguishable from complete reports and delete omitted current mailboxes. Smallest EX-P04A correction: add an explicit completeness/collection-success contract at the usage-report persistence boundary and refuse current replacement unless the report is proven complete; retain snapshot behavior only according to that explicit policy.
2. Duplicate mailbox source rows are accepted and last-write-wins by source order. Smallest EX-P04A correction: reject duplicate `(tenant_id, entity_key)` rows before any delete/write, causing the transaction to fail closed.

### NON_BLOCKING

- Redundant duplicate snapshot unique index (`usage_exchange_mailbox_usage_snap_refresh_key` and `...snapshot_refresh_key`).
- No configured snapshot retention policy; history is currently retained indefinitely.

### HISTORICAL_ARTIFACTS

- Older snapshot generations with NULL quota values legitimately predate quota support and must remain unchanged.

### DEFERRED

- EX-P05 collector/normalization production-wiring validation after the persistence blockers are corrected.

## Final status

- **PERSISTENCE_READY:** NO
- **RECOMMENDED_NEXT_TASK:** `EX-P04A` smallest correction for completeness gating and duplicate-source rejection
- **FILES_CHANGED:** `docs/evidence/EX-P04-EXCHANGE-PERSISTENCE-HISTORY-RECONCILIATION-001.md`
- **FINAL_STATUS:** `EX_P04_BLOCKED`

No token or credit data is recorded.
