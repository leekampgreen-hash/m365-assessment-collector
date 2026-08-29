# STD-06 OneDrive Basic Live Acceptance

- **Task ID:** `STD-06-ONEDRIVE-BASIC-LIVE-ACCEPTANCE-001`
- **Date:** 2026-08-27
- **Project:** graph-agent
- **Role:** INDEPENDENT_LIVE_ACCEPTANCE
- **Purpose:** Prove OneDrive Basic end-to-end on the real production path.
- **Result:** `ACCEPTED` — after the STD-06A runtime parity correction and the
  STD-06B migration-regression closure, a final native production-path rerun
  (`STD-06-RERUN-ONEDRIVE-BASIC-LIVE-ACCEPTANCE-001`) passes the full OneDrive
  Basic slice end-to-end: permission gate → real Graph → normalization →
  current/snapshot persistence → analytics → API readback, with DB ↔ API
  consistency for all six locked KPIs. `ONEDRIVE_BASIC_STATUS=ACCEPTED`,
  `FINAL_STATUS=STD_06_PASS`.

## Locked KPI scope (STD-05)

OneDrive "basic usage" is grounded in the two-report pair `USAGE-004`
(`onedrive_activity` / `getOneDriveActivityUserDetail`) and `USAGE-005`
(`onedrive_account_usage` / `getOneDriveUsageAccountDetail`), period `D7`.

- Active users — from `USAGE-004` evidence only: `usage_onedrive_activity` rows
  that are not deleted and have a non-empty `last_activity_date`.
- Active accounts — from `USAGE-005` evidence only: non-deleted
  `usage_onedrive_account_usage` rows with a non-empty `last_activity_date`.
- Latest activity — max `last_activity_date` over the active set.
- Total storage used — sum of `storage_used` across the current
  `usage_onedrive_account_usage` set.
- Total file count — sum of `file_count` across the current
  `usage_onedrive_account_usage` set.
- Storage utilization — `storage_used / storage_allocated` (per account and
  aggregate), from the locked report schema.

Out of scope: sharing/oversharing, per-file detail, permission analysis,
DLP/Purview, and activity-count (viewed/synced) thresholds.

## Live path executed

One bounded native production-path acceptance of `USAGE-004` and `USAGE-005` via
the production CLI in the `graph-agent-collector-dev` container:

```
python -m collectors.run_collector --endpoint USAGE-004 --granted-graph-permissions Reports.Read.All --json
python -m collectors.run_collector --endpoint USAGE-005 --granted-graph-permissions Reports.Read.All --json
```

### permission_gate
`COLLECT`. The fail-closed capability gate returned `COLLECT` (no
`SKIP_PERMISSION_REQUIRED`) when `Reports.Read.All` was declared via
`--granted-graph-permissions`. Both endpoints proceeded to execute against the
real tenant. When `Reports.Read.All` was withheld (only `User.Read.All`
declared), the gate returned `SKIP_PERMISSION_REQUIRED` / status `SKIPPED` with
no Graph call, no rows, and no persistence — `Reports.Read.All` remains
fail-closed.

### activity_graph
Real Microsoft Graph request `GET /v1.0/reports/getOneDriveActivityUserDetail(period='D7')`
succeeded. Run summary reported `source_rows: 30`, `rows: 30`, `pages: 1`,
`status: PASS`.

### account_usage_graph
Real Microsoft Graph request `GET /v1.0/reports/getOneDriveUsageAccountDetail(period='D7')`
succeeded. Run summary reported `source_rows: 26`, `rows: 26`, `pages: 1`,
`status: PASS`.

### rows_collected
56 normalized rows total (30 onedrive_activity + 26 onedrive_account_usage) from
the live Graph payloads.

### normalization
`PASS`. 30 + 26 rows normalized with no `ENTITY_IDENTITY_UNAVAILABLE` and no CSV
schema error. OneDrive malformed `Is Deleted` flags fail closed to deleted: a
row with `Is Deleted = "maybe"` normalizes to `is_deleted=True`, so malformed
rows cannot inflate active counts.

### current_persistence
`PASS`. Both runs persisted to current tables via the `DELETE + INSERT`
replacement contract (migration `013_usage_reports_current_delete.sql` grants
`DELETE` on the current usage tables). Newest `observed_at` set:
`usage_onedrive_activity` = 30 rows, `usage_onedrive_account_usage` = 26 rows.

### snapshot_persistence
`PASS`. Each run appended a new snapshot generation:
`usage_onedrive_activity_snapshot` += 30, `usage_onedrive_account_usage_snapshot`
+= 26.

### analytics
`PASS` on the current host source; `FAIL` in the running API deployment. The
host `analytics/operations.py::onedrive_adoption()` (STD-05B) derives the six
locked KPIs from `last_activity_date` presence on non-deleted rows and surfaces
`storage_utilization` from `onedrive_account_usage`. The running API container
serves a stale pre-STD-05B `onedrive_adoption()` that derives `active_users`
from `viewed_count`/`synced_count` and does not emit `active_accounts`,
`latest_activity`, `total_storage_used`, `total_file_count`, or
`storage_utilization`.

### api_readback
`GET /api/operations/adoption/onedrive` (running API container) returned
pre-STD-05B KPIs: `active_users: 0`, `inactive_users: 30`, and only a nested
`account_usage` with `storage_used`/`file_count`; `active_accounts`,
`latest_activity`, `total_storage_used`, `total_file_count`, and
`storage_utilization` are ABSENT.

### runtime_parity
`FAIL`. The running API container (`graph-agent-operations-api-dev`) was built
at `2026-08-27T21:55:55+07:00` from pre-STD-05B source, while the host
`analytics/operations.py` was finalized at `2026-08-27 22:56:35 +0700`. md5
comparison against the running API container:

| module | host md5 | api container md5 | match |
|---|---|---|---|
| `analytics/operations.py` | `23040851…` | `0d8b6cc8…` | MISMATCH |
| `collectors/usage_reports/registry.py` | `acbc5fe8…` | `092e8e48…` | MISMATCH |
| `api/operations.py` | `9b7d26bf…` | `9b7d26bf…` | match |
| `collectors/persistence/core.py` | `544fc93f…` | `544fc93f…` | match |
| `collectors/core/runtime.py` | `51c1db79…` | `51c1db79…` | match |

The API container's `registry.py` also lacks the OneDrive malformed-delete
fail-closed block present on the host.

## KPI_READBACK (host STD-05B analytics on live DB vs running API)

Computed with the current host `onedrive_adoption()` against the live DB
(`core.usage_onedrive_activity` / `core.usage_onedrive_account_usage`, tenant 2,
newest observed_at) and cross-checked via SQL:

| KPI | DB evidence / host analytics | Running API readback | Match |
|---|---|---|---|
| active_users | 23 | 0 | NO |
| active_accounts | 23 | ABSENT | NO |
| latest_activity | 2026-06-26 | ABSENT | NO |
| total_storage_used | 113,932,223 | ABSENT (nested `account_usage.storage_used` only) | NO |
| total_file_count | 156 | ABSENT (nested `account_usage.file_count` only) | NO |
| storage_utilization | 3.9854e-06 | ABSENT | NO |

SQL cross-check: `usage_onedrive_activity` 30 rows (0 deleted, 23 with
`last_activity_date`); `usage_onedrive_account_usage` 26 rows (0 deleted, 23 with
`last_activity_date`), `sum(storage_used)=113932223`,
`sum(file_count)=156`, `sum(storage_allocated)=28587302322176`.

## STD-06A_RUNTIME_CORRECTION

`STD-06A-ONEDRIVE-RUNTIME-PARITY-CORRECTION-001` rebuilt `graph-agent-collector:dev` from current source and recreated only `graph-agent-collector-dev` and `graph-agent-operations-api-dev`. The stale runtime was caused by image-copied production source plus no API source bind mount; the existing process reused its pre-STD-05B image. All five checked production modules (`analytics/operations.py`, `collectors/usage_reports/registry.py`, `api/operations.py`, `collectors/persistence/core.py`, `collectors/core/runtime.py`) now match host hashes. API `/health` returned `READY`/`READY`. OneDrive API readback exposes all six locked KPIs and matches existing DB evidence: 23, 23, `2026-06-26`, `113932223`, `156`, `3.985413583835068e-06`.

## DB_API_CONSISTENCY
PASS after STD-06A runtime correction — the rebuilt API readback matches the existing OneDrive DB evidence for all six locked KPIs.

## Edge-case verification (deleted/malformed, zero/missing allocation)

- Deleted/malformed rows do not inflate active counts: `is_deleted=True` rows and
  missing-`last_activity_date` rows are excluded from `active_users` /
  `active_accounts` (host logic plus `test_onedrive_locked_basic_kpis_filter_deleted_and_missing_activity`).
  Malformed `Is Deleted` flags fail closed to deleted.
- Utilization handles zero/missing allocation safely: `storage_utilization`
  returns `None` when total allocation is `0` or missing
  (`test_onedrive_utilization_fails_closed_for_zero_or_missing_allocation`).
- Full analytics suite: `python -m unittest tests.analytics.test_operations`
  → 19 tests OK.

## Defect found (classified, not fixed)

### Defect B — runtime/container parity (KPI source-contract violation, recurring)
The running `graph-agent-operations-api-dev` container serves stale pre-STD-05B
`analytics/operations.py` and `collectors/usage_reports/registry.py`. Its
`onedrive_adoption()` derives `active_users` from `viewed_count`/`synced_count`
thresholds and omits `active_accounts`, `latest_activity`,
`total_storage_used`, `total_file_count`, and `storage_utilization`, violating
the locked STD-05 KPI source rule. Classification: runtime parity / KPI
source-contract violation. This is the same class of defect recorded as STD-04
Defect B; OneDrive Basic cannot be ACCEPTED until the API container is rebuilt
from current host source and re-verified. Persistence (STD-04 Defect A) is
resolved for OneDrive by migration 013 and is no longer a blocker.

## Safety
No tenant permissions changed, no Graph writes, no migrations, no endpoints, no
sharing/oversharing implementation, no SharePoint, no source code change was
performed. The only host-side artifacts produced by this acceptance are this
evidence document and the corresponding progress/usage-log records.

## Scope accounting
Acceptance-only. The production collection path and host STD-05B implementation
were exercised read-only; no production Python, database grants, migrations,
inventory, or runtime source were modified.

---

# RERUN — STD-06-RERUN-ONEDRIVE-BASIC-LIVE-ACCEPTANCE-001 (ACCEPTED)

- **Task ID:** `STD-06-RERUN-ONEDRIVE-BASIC-LIVE-ACCEPTANCE-001`
- **Date:** 2026-08-27
- **Result:** `PASS` / `STD_06_PASS`; `ONEDRIVE_BASIC_STATUS=ACCEPTED`.
- **Role:** INDEPENDENT_LIVE_ACCEPTANCE (fresh session).
- **Gate:** `scripts/check_runtime_parity.py` was run FIRST and PASSED before any
  API acceptance: all five checked production modules match host hashes
  (`analytics/operations.py`, `collectors/usage_reports/registry.py`,
  `api/operations.py`, `collectors/persistence/core.py`,
  `collectors/core/runtime.py`). Exit code `0`.

## LIVE_PATH

| step | result |
|---|---|
| permission_gate | `COLLECT` with `Reports.Read.All`. Withholding it (only `User.Read.All`) returns `SKIPPED` / `SKIP_PERMISSION_REQUIRED` / `feature_status=PERMISSION_REQUIRED`, zero Graph calls, zero rows, zero persistence — fail-closed confirmed. |
| activity_graph | Real `GET /v1.0/reports/getOneDriveActivityUserDetail(period='D7')` → `status=PASS`, `source_rows=30`, `rows=30`, `persisted_rows=30`, `pages=1`. |
| account_usage_graph | Real `GET /v1.0/reports/getOneDriveUsageAccountDetail(period='D7')` → `status=PASS`, `source_rows=26`, `rows=26`, `persisted_rows=26`, `pages=1`. |
| rows_collected | 56 normalized rows total (30 onedrive_activity + 26 onedrive_account_usage). |
| normalization | PASS; no `ENTITY_IDENTITY_UNAVAILABLE`, no CSV schema error. Malformed OneDrive `Is Deleted` flags fail closed to `is_deleted=True`. |
| current_persistence | PASS via the DELETE+INSERT replacement contract (migration `013`). Newest `observed_at` set: `usage_onedrive_activity` = `2026-08-27 16:30:42+00` (30 rows), `usage_onedrive_account_usage` = `2026-08-27 16:31:14+00` (26 rows). |
| snapshot_persistence | PASS. 30 activity + 26 account snapshot rows present for the `2026-08-27` refresh generation; snapshot `snapshot_identity` idempotency (`tenant:entity_key:refresh_date`, `ON CONFLICT DO NOTHING`) preserved. |
| runtime_parity | PASS (before API acceptance). All five modules MATCH. |
| analytics | PASS — deployed `analytics/operations.py::onedrive_adoption()` derives all six locked KPIs from non-deleted rows with a non-empty `last_activity_date` and from `onedrive_account_usage` storage/file/allocation. |
| api_readback | `GET /api/operations/adoption/onedrive` returns `READY` and all six locked KPIs (see KPI_READBACK). |

## KPI_READBACK (API vs live DB, tenant 2, newest observed_at)

| KPI | API readback | DB SQL cross-check | Match |
|---|---|---|---|
| active_users | 23 | 23 | YES |
| active_accounts | 23 | 23 | YES |
| latest_activity | 2026-06-26 | 2026-06-26 | YES |
| total_storage_used | 113932223 | 113932223 | YES |
| total_file_count | 156 | 156 | YES |
| storage_utilization | 3.985413583835068e-06 | 0.00000398541358383507 | YES |

SQL cross-check (newest current generation, non-deleted):
`active_users` = 23 non-deleted activity rows with `last_activity_date`;
`active_accounts` = 23 non-deleted account rows with `last_activity_date`;
`max(last_activity_date)` = `2026-06-26`;
`sum(storage_used)` = `113932223`; `sum(file_count)` = `156`;
`sum(storage_allocated)` = `28587302322176`.

## DB_API_CONSISTENCY
`PASS` — the deployed API readback matches the live DB evidence for all six
locked KPIs.

## Fail-closed / edge-case confirmation

- Malformed `Is Deleted` flags fail closed to deleted
  (`_as_bool` returns `None` for ambiguous text; OneDrive rows with a non-empty
  but unrecognized flag become `is_deleted=True`). Deleted and missing-activity
  rows are excluded from `active_users`/`active_accounts`
  (`test_onedrive_locked_basic_kpis_filter_deleted_and_missing_activity`).
- `storage_utilization` fails closed to `None` for zero/missing allocation
  (`test_onedrive_utilization_fails_closed_for_zero_or_missing_allocation`).
- No viewed/synced thresholds drive the active-user KPI: the API reports
  `viewed_count=0` and `synced_count=0`, while `active_users=23` is derived only
  from `last_activity_date` presence on non-deleted `onedrive_activity` rows.
  `account_usage.file_count` is not treated as user-activity evidence
  (`test_onedrive_account_file_count_is_not_user_activity_evidence`).
- Full analytics suite `tests.analytics.test_operations` = 19 tests PASS.
  Usage-report normalization suite `tests.usage_reports.test_usage_reports`
  = 17 tests PASS (including malformed-delete fail-closed and snapshot
  idempotency contract).

## Safety

No tenant permissions changed, no Graph writes, no migrations, no DB grants, no
credentials, no SharePoint, no sharing/oversharing, no broad source fix. The only
host-side artifacts produced by this rerun are this evidence update, the activity
log record, and the progress status update.

## Scope accounting

Acceptance-only. Production Python, migrations, database grants, inventory,
permissions, credentials, and runtime source were not modified.
