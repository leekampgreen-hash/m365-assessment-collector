# STD-04 Exchange Basic Live Acceptance — RERUN

- **Task ID:** `STD-04-RERUN-EXCHANGE-BASIC-LIVE-ACCEPTANCE-001`
- **Date:** 2026-08-27
- **Project:** graph-agent
- **Role:** `INDEPENDENT_LIVE_ACCEPTANCE`
- **Purpose:** Re-run Exchange Basic live acceptance after STD-04A corrected the usage
  current-table DELETE privilege contract, collector/API runtime parity, and the deployed
  mailbox-based Exchange KPI logic.
- **Result:** `ACCEPTED` — one bounded native production-path acceptance passed end-to-end.

## Preconditions verified (STD-04A fixes confirmed deployed)

- **DB privilege contract:** `graph_agent_runtime` now holds `SELECT, INSERT, UPDATE, DELETE`
  on current usage tables (`core.usage_exchange_mailbox_usage`, `..._email_activity`,
  `..._office365_active_user`) and only `SELECT, INSERT, UPDATE` (no DELETE) on the
  corresponding `_snapshot` tables. Confirmed via `information_schema.role_table_grants`.
  Source of the grant: `database/migrations/013_usage_reports_current_delete.sql`.
- **Runtime parity:** md5 of `analytics/operations.py`, `api/operations.py`,
  `collectors/usage_reports/registry.py`, `collectors/usage_reports/persistence.py`, and
  `collectors/core/runtime.py` are identical between host, `graph-agent-collector-dev`, and
  `graph-agent-operations-api-dev`. Containers were rebuilt to the current host source.

## Live path executed

One bounded native production-path acceptance of `USAGE-003` via the production CLI in the
`graph-agent-collector-dev` container:

```
python -m collectors.run_collector --endpoint USAGE-003 --granted-graph-permissions Reports.Read.All --json
```

Run result: `status=PASS`, `pages=1`, `source_rows=30`, `rows=30`, `persisted_rows=30`,
`error_classification=PASS`, `identity_unavailable=false`, `http_status=null`.

### permission_gate
`COLLECT`. `plan_collection(required_capabilities=(), required_graph_permissions=['Reports.Read.All'],
entitlements={}, granted_graph_permissions=['Reports.Read.All'])` returned
`decision=COLLECT`, `collector_status=PLANNED`, `feature_status=AVAILABLE`. The endpoint
executed against the real tenant.

### graph
Real Microsoft Graph request `GET /v1.0/reports/getMailboxUsageDetail(period='D7')` succeeded
(`source_rows: 30`, `rows: 30`, `pages: 1`). Live `Reports.Read.All` token is effective.

### rows_collected
30 normalized mailbox-usage rows from the live Graph payload.

### normalization
Normalization succeeded (30 rows, `identity_unavailable=false`, no CSV schema error, no
`ENTITY_IDENTITY_UNAVAILABLE`).

### current_persistence
PASS. The usage current-table DELETE-then-INSERT contract executed without
`InsufficientPrivilege`. `core.usage_exchange_mailbox_usage` now holds exactly 30 current rows
(all `observed_at = 2026-08-27 15:44:29`, `report_refresh_date = 2026-08-24`), replacing the
prior 60-row set. `persisted_rows=30`.

### snapshot_persistence
PASS (idempotent by refresh-date contract). The snapshot INSERT ran inside the same committed
transaction without privilege error (snapshot grants retain `INSERT, SELECT, UPDATE`).
`core.usage_exchange_mailbox_usage_snapshot` holds 60 snapshot rows keyed by
`(tenant_id, entity_key, report_refresh_date)`. This run's report refresh date
(2026-08-24) already existed in the snapshot set, so the insert was a designed
`ON CONFLICT DO NOTHING` no-op, not a failure.

### analytics
PASS. The deployed mailbox-based `analytics/operations.py::exchange_adoption()` derives basic
Exchange KPIs only from `exchange_mailbox_usage`:
- `active_users` = distinct non-deleted rows with a set `last_activity_date`;
- `last_activity` = max `last_activity_date` over active rows;
- `mailbox_usage.total_storage_used` = sum `storage_used`;
- `mailbox_usage.mailbox_item_count` = sum `mailbox_item_count`.
Legacy send/receive/read counts remain exposed only as legacy source metrics, not as basic KPIs.

### api_readback
`GET /api/operations/adoption/exchange` returned `status=READY` with:
- `active_users.value = 23`
- `last_activity.value = "2026-07-25"`
- `mailbox_usage.value = {total_storage_used: 149438006, mailbox_item_count: 56340}`
- `source_refresh_date = 2026-08-24`

### runtime_parity
PASS. Host/collector/api md5 identical for all five checked modules.

## KPI cross-check (DB mailbox evidence vs API readback)

Computed from `core.usage_exchange_mailbox_usage` (tenant 2, current run):

| KPI | DB mailbox evidence | API readback | Match |
|---|---|---|---|
| active_users | 23 | 23 | YES |
| latest_activity | 2026-07-25 | 2026-07-25 | YES |
| total_storage_used | 149,438,006 | 149,438,006 | YES |
| total_mailbox_item_count | 56,340 | 56,340 | YES |

`active_users` derivation confirmed against DB: 23 distinct `entity_key` from
`is_deleted = false AND last_activity_date IS NOT NULL`; 29 applicable (non-deleted), 1 deleted,
23 active + 6 inactive = 29. Matches API `active_users`, `inactive_users`, `applicable_users`,
and `adoption_rate` (79.31%).

## DB_API_CONSISTENCY
PASS — API readback matches the mailbox-usage DB evidence for all four locked KPIs.

## Files changed
- `docs/evidence/STD-04-EXCHANGE-BASIC-LIVE-ACCEPTANCE-RERUN-001.md` (created, this record)

No source, database grant/migration, permission, Graph write, Basic Protection, or OneDrive
behavior was modified.

## Blockers
None.

## EXCHANGE_BASIC_STATUS
ACCEPTED

## NEXT_TASK
STD-05-ONEDRIVE-BASIC-CONTRACT-001

## FINAL_STATUS
STD_04_PASS
