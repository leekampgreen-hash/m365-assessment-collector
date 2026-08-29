# STD-15G2C Exchange DB RCA and Analytical View

- **Task ID:** `STD-15G2C-EXCHANGE-DB-RCA-AND-ANALYTICAL-VIEW-001`
- **Date:** 2026-08-28
- **Project:** graph-agent
- **Role:** `DATABASE_RCA_AND_SEMANTIC_LAYER`
- **Result:** `STD_15G2C_PASS`
- **Scope:** Exchange only.

## Phase A — Database RCA

### Authoritative PostgreSQL target (proven without printing credentials)

| Concern | migrator | collector runtime | analytics/API runtime |
|---|---|---|---|
| `PGHOST` | `postgres` | `postgres` | `postgres` |
| `PGPORT` | `5432` | `5432` | `5432` |
| `PGDATABASE` | `graph_agent` | `graph_agent` | `graph_agent` |
| `PGUSER` | `graph_agent_migrator` | `graph_agent_runtime` | `graph_agent_runtime` |
| `current_database()` | `graph_agent` | `graph_agent` | `graph_agent` |
| `current_user` | `graph_agent_migrator` | `graph_agent_runtime` | `graph_agent_runtime` |
| `search_path` | `"$user", public` | `"$user", public` | `"$user", public` |

All three runtimes resolve the same authoritative database: `graph_agent`. The
migrator (schema owner) and runtime (read/write) roles are distinct but both
operate on `graph_agent`. `same_target = YES`.

### Authoritative Exchange tables

- current: `core.usage_exchange_mailbox_usage`
- snapshot: `core.usage_exchange_mailbox_usage_snapshot`

Migration 014 (`014_exchange_mailbox_quota.sql`) was verified applied to the
authoritative `graph_agent` database. All three quota columns exist as
nullable `BIGINT` on **both** current and snapshot tables:

- `issue_warning_quota BIGINT`
- `prohibit_send_quota BIGINT`
- `prohibit_send_receive_quota BIGINT`

### Root-cause classification of the previous mismatch

The migration was **correctly applied**. The earlier inability to reconcile was
a combination of two distinct issues:

1. **Wrong verification database:** the STD-15G2 reconciliation step queried
   under the bootstrap database (`postgres`) / a disposable database instead of
   the production `graph_agent` database, so it "found no matching Exchange
   columns" even though the columns existed in `graph_agent`. (The disposable
   databases also genuinely lacked the migration 014 columns.)
2. **Persistence wiring defect (the real production cause):** the usage-report
   adapter header mapping in `collectors/usage_reports/registry.py` only listed
   plural `(Bytes)` quota headers, but the live `getMailboxUsageDetail` CSV uses
   singular `(Byte)` headers (`Issue Warning Quota (Byte)`, `Prohibit Send Quota
   (Byte)`, `Prohibit Send/Receive Quota (Byte)`). Because the header match uses
   exact casefold membership, the three quota fields normalized to `NULL` and
   were written as `NULL` into the authoritative tables. This is why a PASS
   collection (30 rows) still produced `0/30` quota-populated rows.

- **root_cause:** wrong verification query/database during reconciliation, PLUS
  adapter header-name mismatch causing NULL quota persistence.
- **migration bookkeeping:** the `public.graph_agent_migration_state` table is
  incomplete (records 1-7, 9, 10; missing 008, 011-014) but the 014 DDL is
  present. History was not modified; the gap is documented as controlled debt.

## Phase B — Production data proof

One bounded `USAGE-003` collection ran in `graph-agent-collector-dev`
(`--granted-graph-permissions Reports.Read.All`):
`status=PASS, source_rows=30, persisted_rows=30`.

After correcting the adapter header mapping and re-collecting, authoritative
`graph_agent` data:

| Metric | current | snapshot (current refresh `2026-08-25`) |
|---|---:|---:|
| total rows | 30 | 30 |
| `storage_used` populated | 30 | 30 |
| `report_refresh_date` populated | 30 | 30 |
| `issue_warning_quota` populated | 30 | 30 |
| `prohibit_send_quota` populated | 30 | 30 |
| `prohibit_send_receive_quota` populated | 30 | 30 |

All 30 mailbox capacities (`prohibit_send_receive_quota`) are positive. No
quota was inferred from license/SKU. Historical snapshot generations
(`2026-08-23`, `2026-08-24`) were captured before the fix and retain `NULL`
quota as documented historical artifacts; the current refresh generation was
corrected from the authoritative current data.

## Phase C — Analytical view

Forward-only migration `015_exchange_mailbox_capacity.sql` creates:

- **name:** `analytics.exchange_mailbox_capacity`
- **type:** VIEW (not a physical table; no derived columns duplicated)
- **row_count:** 30 (reconciles exactly with `core.usage_exchange_mailbox_usage` current rows)
- Exposes one row per authoritative current Exchange mailbox record (newest
  `observed_at` per tenant) with:
  - `tenant_id`
  - `user_ref` — tenant-safe `user-<sha256[:16]>` matching the existing
    analytics `_user_ref` contract (uses `pgcrypto`)
  - `identity_is_masked`
  - `storage_used`
  - `mailbox_capacity` = `prohibit_send_receive_quota`
  - `utilization_percent` = `storage_used * 100.0 / mailbox_capacity`
    (NULL when denominator missing/zero/invalid)
  - `usage_level` = `LOW` (<50), `MEDIUM` (>=50 and <80), `HIGH` (>=80),
    `NO_DATA` (denominator missing/zero/invalid)
  - `report_refresh_date` (Data Last Refreshed)
  - `last_activity_date` (Last Email Activity)

Threshold boundaries verified live: `49.99 → LOW`, `50 → MEDIUM`,
`79.99 → MEDIUM`, `80 → HIGH`, `NULL → NO_DATA`. NO_DATA fails closed when the
capacity denominator is missing, zero, or invalid.

`pgcrypto` is enabled at database bootstrap
(`database/runtime/init/00-create-graph-agent-database.sh`) so the view's
sha256 `user_ref` matches the existing Python `_user_ref` and preserves
cross-workload correlation parity.

## Phase D — Consumer contract

- `analytics/operations.py` now loads `analytics.exchange_mailbox_capacity`
  via `from_connection` and `exchange_capacity()` reads `utilization_percent`
  and `usage_level` directly from the view (no Python formula recomputation).
- The duplicate utilization/classification formula was removed from Python.
- `api/operations.py` (unchanged) exposes the view-backed data through the
  existing `/api/operations/adoption/exchange`, `/api/operations/kpi`, and
  `/api/operations/correlation/users` routes.

Deployed runtime parity PASS for `analytics/operations.py`,
`collectors/usage_reports/registry.py`, `api/operations.py`,
`collectors/persistence/core.py`, `collectors/core/runtime.py`.

## Validation

- migration/view creation: PASS (015 applied; migration + view contract tests pass)
- view row count reconciles with Exchange current rows: PASS (30 = 30)
- threshold boundaries: PASS (49.99 LOW / 50 MEDIUM / 79.99 MEDIUM / 80 HIGH)
- NO_DATA fail closed: PASS
- report refresh date: PASS (`2026-08-25`)
- runtime parity: PASS
- API/view counts reconcile: PASS (capacity_usage low=30, mailbox_details=30,
  cross-workload exchange utilization on 30 users)

## Files changed

- `collectors/usage_reports/registry.py` — quota header aliases now include
  singular `(Byte)` to match the live report.
- `analytics/operations.py` — load the view; `exchange_capacity()` consumes the
  view as the single capacity contract; Decimal-safe numeric normalization.
- `database/migrations/015_exchange_mailbox_capacity.sql` — new forward-only
  view migration.
- `database/runtime/init/00-create-graph-agent-database.sh` — enable `pgcrypto`.
- `tests/database/test_migrations.py` — register migration 015 + view contract tests.
- `tests/analytics/test_operations.py` — view-backed capacity tests.
- `docs/PROJECT_FILE_MAP.md`, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`,
  this evidence file.

## Scope note

OneDrive, SharePoint, license semantics, SEND_MAIL, and Exchange thresholds were
not modified. The single pre-existing offline test failure
(`test_all_seven_adapters_preserve_commercial_fields`, `storage_used` string vs
int) remains and is unrelated to this task; production correctly stores
`storage_used` as BIGINT.
