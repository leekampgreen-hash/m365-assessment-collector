# STD-04 Exchange Basic Live Acceptance

- **Task ID:** `STD-04-EXCHANGE-BASIC-LIVE-ACCEPTANCE-001`
- **Date:** 2026-08-27
- **Project:** graph-agent
- **Role:** LIVE_ACCEPTANCE_AND_WIRING_VALIDATION
- **Purpose:** Prove the Exchange Standard basic slice end-to-end on the real production path.
- **Result:** `BLOCKED` — two live production-path defects found. Defects are classified; no broad fix was performed in this acceptance task.

## Locked KPI scope (STD-03)

Exchange "basic usage" is grounded in `USAGE-003` / `getMailboxUsageDetail` (period `D7`):
active users, latest activity, total mailbox storage used, total mailbox item count.
Derivation must be from `core.usage_exchange_mailbox_usage` only. No send/receive/read
message-count evidence may drive the basic KPI.

## Live path executed

One bounded native production-path acceptance of `USAGE-003` via the production CLI in the
`graph-agent-collector-dev` container:

```
python -m collectors.run_collector --endpoint USAGE-003 --granted-graph-permissions Reports.Read.All --json
```

### permission_gate
`COLLECT`. The fail-closed capability gate returned `COLLECT` (no `SKIP_PERMISSION_REQUIRED`)
when `Reports.Read.All` was declared via `--granted-graph-permissions`. The endpoint proceeded
to execute against the real tenant.

### graph
Real Microsoft Graph request `GET /v1.0/reports/getMailboxUsageDetail(period='D7')` succeeded.
Run summary reported `source_rows: 30`, `rows: 30`, `pages: 1`. This proves `Reports.Read.All`
is live-effective on the token (the recorded STD-01 baseline did not include it; live execution
now demonstrates it is granted).

### rows_collected
30 normalized mailbox-usage rows returned from the live Graph payload.

### normalization
Normalization succeeded (30 rows, no `ENTITY_IDENTITY_UNAVAILABLE`, no CSV schema error).

### current_persistence
FAIL. The run failed at persistence with `error_classification: PERSISTENCE_ERROR`,
`error_message: InsufficientPrivilege`. No rows from this live run were persisted.

### snapshot_persistence
FAIL. Same transaction aborts (rollback); no snapshot rows from this live run were written.

### analytics
FAIL (in the running deployment). The running API container serves a stale `analytics/operations.py`
whose `exchange_adoption()` derives `active_users` from `core.usage_exchange_email_activity`
(send/receive/read), not from mailbox usage, and does not emit `last_activity` or
`total_storage_used`. This violates the locked STD-03 KPI source rule.

### api_readback
`GET /api/operations/adoption/exchange` returned:
- `active_users: 0` (DB mailbox evidence says 23)
- `last_activity`: ABSENT (not emitted)
- `mailbox_usage.value`: `{mailbox_item_count: 56340}` only — `total_storage_used` ABSENT
- Exposes `send_count`, `receive_count`, `read_count` (email-activity source)

### runtime_parity
FAIL. Container images are stale relative to host source (md5 comparison):
- `analytics/operations.py`: host `0d8b6cc8…` vs collector/api containers `6d373145…` (stale)
- `collectors/usage_reports/registry.py`: host/collector `092e8e48…` vs api container `060cfe4f…`
- `collectors/core/runtime.py`: host/collector `51c1db79…` vs api container `4dcbe9ac…`
- `api/operations.py`: host/collector `9b7d26bf…` vs api container `228596ed…`

The running API therefore serves the pre-STD-03 analytics rather than the current host source.

## KPI cross-check (DB mailbox evidence vs API readback)

Computed from `core.usage_exchange_mailbox_usage` (tenant 2, newest observed_at):

| KPI | DB mailbox evidence | Running API readback | Match |
|---|---|---|---|
| active_users | 23 (is_deleted false, last_activity set) | 0 (from email-activity source) | NO |
| latest_activity | 2026-07-25 | ABSENT | NO |
| total_storage_used | 149,438,006 | ABSENT | NO |
| total_mailbox_item_count | 56,340 | 56,340 | YES |

## DB_API_CONSISTENCY
FAIL — the running API does not match the mailbox-usage DB evidence for three of the four locked KPIs.

## Defects found (classified, not fixed)

### Defect A — DB privilege contract mismatch (persistence blocker)
`collectors/usage_reports/persistence.py::write_report_rows` issues
`DELETE FROM {table} WHERE tenant_id = %s` to replace the current set, but migration
`008_usage_reports.sql` grants `graph_agent_runtime` only `SELECT, INSERT, UPDATE` (no DELETE).
Live collection fails at persistence with `psycopg.errors.InsufficientPrivilege`.
Classification: persistence / schema-grant contract mismatch. Blocks current and snapshot
persistence of the live run.

### Defect B — Runtime/container parity and KPI derivation mismatch
The running `graph-agent-collector-dev` and `graph-agent-operations-api-dev` containers run stale
builds of key modules. The API container's `exchange_adoption()` derives the basic Exchange
`active_users` from `exchange_email_activity` (send/receive/read) and does not emit
`last_activity` or `total_storage_used`, violating the locked STD-03 rule that basic KPIs are
derived only from mailbox usage evidence.
Classification: runtime parity / KPI source-contract violation.

## Safety
No tenant permissions changed, no Graph writes, no migrations, no endpoints, no Basic
Protection, no archive collection, no code fix was performed. `FILES_CHANGED`: this evidence
document only.

## Scope accounting
Documentation-only acceptance evidence. Production Python, database grants, migrations, inventory,
and runtime were not modified.
