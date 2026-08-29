# STD-12C Cross-workload Correlation Live Acceptance Evidence

- **Task ID:** `STD-12C-CROSS-WORKLOAD-CORRELATION-LIVE-ACCEPTANCE-001`
- **Result:** `STD_12C_PASS` (rerun after STD-12D correction; correlation ACCEPTED)
- **Role:** `INDEPENDENT_LIVE_ACCEPTANCE`
- **Scope:** Read-only acceptance of `GET /api/operations/correlation/users` against the existing live DB, with independent DB evidence cross-check. No Graph reads/writes, no collectors rerun, no source mutation.
- **Model:** `bbb/kl/deepseek-v4-flash`
- **Session:** `NEW`

## RUNTIME

- **parity:** PASS; `scripts/check_runtime_parity.py` ran first; all five checked production modules MATCH host hashes (exit `0`):
  `analytics/operations.py`, `collectors/usage_reports/registry.py`, `api/operations.py`, `collectors/persistence/core.py`, `collectors/core/runtime.py` — all `MATCH`.
- **api_health:** PASS; `/health` → `{"status":"READY","database":"READY"}` (HTTP 200).

## STD-12D FIX VERIFIED IN PLACE

`analytics/operations.py::OperationsAnalyticsQueryService.from_connection` now selects
`tenant_id` onto canonical user rows:

```sql
SELECT tenant_id, user_id, source_object_id, user_principal_name, account_enabled FROM core."user" WHERE tenant_id = %s
```

The tenant-scoped workload guard in `cross_workload_user_status`
(`row.get("tenant_id", user.get("tenant_id")) == user.get("tenant_id")`) is preserved and now
evaluates `2 == 2` for same-tenant rows instead of `2 == None`. License/assigned-SKU correlation
(via the `user_id` FK) is unaffected.

## CORRELATION_READBACK

Live `GET /api/operations/correlation/users` returned `{"status":"READY","as_of":"2026-08-27", ...}` with 39 canonical user rows.

- **canonical_users:** 39 (matches `core."user"` tenant 2 count).
- **licensed_users:** 25 (matches DB).
- **unlicensed_users:** 14 (matches DB).
- **multiple_sku_users:** 2 (user_id 3 = 3 SKUs: AAD_PREMIUM_P2, POWER_BI_STANDARD, SPB; user_id 39 = 2 SKUs: POWER_BI_STANDARD, SPB) — matches DB.
- **assignment_rows:** 28 (matches DB).
- **per_sku_assignment_counts:** AAD_PREMIUM_P2=1; POWER_BI_STANDARD=2; SPB=25 (matches DB).

## WORKLOAD_STATUS (live API readback)

With the STD-12D fix deployed, the live API now reports the correct ACTIVE/INACTIVE/UNKNOWN mix:

| workload | active | inactive | unknown |
|---|---|---|---|
| exchange | 23 | 7 | 9 |
| onedrive | 23 | 7 | 9 |
| sharepoint | 24 | 6 | 9 |

`*_last_activity` non-null counts: exchange 23, onedrive 23, sharepoint 24.

An independent read-only SQL cross-check (same casefolded-UPN join and fail-safe status semantics)
reproduced **exactly** these values from the live DB:

- canonical_users 39; licensed 25; unlicensed 14; assignment_rows 28; multi-SKU 2
  (user_id 3 = 3 SKUs, user_id 39 = 2 SKUs); per-SKU AAD_PREMIUM_P2=1 / POWER_BI_STANDARD=2 / SPB=25.
- exchange_status 23/7/9; onedrive_status 23/7/9; sharepoint_status 24/6/9.

The API readback and the independent DB cross-check are fully consistent with each other and with
the accepted DB evidence (exchange 23/7/9, onedrive 23/7/9, sharepoint 24/6/9).

## VALIDATION (all 11 points)

- **user_coverage:** PASS — 39 canonical users match `core."user"` tenant 2 (the only tenant in the DB).
- **license_mapping:** PASS — 25 licensed / 14 unlicensed; 28 assignment rows; per-SKU counts AAD_PREMIUM_P2=1 / POWER_BI_STANDARD=2 / SPB=25; both multi-SKU users (admin=3 SKUs, william.tan=2 SKUs) — all match `core.user_license_assignment` and `core.subscribed_sku`.
- **same_tenant_join:** PASS — per-user workload join now fires; ACTIVE/INACTIVE/UNKNOWN mix is populated live and matches DB.
- **cross_tenant_block:** PASS — tenant guard preserved; all queries tenant-scoped (`WHERE tenant_id = 2`); live DB holds only tenant 2, so cross-tenant is structurally blocked; the STD-12D regression test verifies a tenant-2 user does NOT inherit a same-UPN tenant-1 workload row (classified UNKNOWN).
- **workload_status:** PASS — Exchange 23/7/9, OneDrive 23/7/9, SharePoint 24/6/9 match DB evidence and the independent SQL cross-check.
- **unknown_fail_safe:** PASS — the 9 users UNKNOWN per workload each have zero rows in that workload table (verified); absence of evidence → UNKNOWN. No live masked canonical user currently exists; fail-safe contract (masked/unresolvable → UNKNOWN) is enforced.
- **deleted_semantics:** PASS — the deleted exchange row (`AdeleV@...`, `is_deleted=true`, even with a non-null last_activity_date) is classified INACTIVE, exercising the delete-over-active rule live.
- **masked_identity:** PASS — no masked canonical users in live data; contract/semantics keep masked/unresolvable identities UNKNOWN (never INACTIVE). Confirmed by regression test.
- **casefolded_upn_deterministic:** PASS — 33 of 39 canonical users and 24 workload rows carry mixed-case UPNs (e.g. `Adams@M365B899688.OnMicrosoft.com` vs `adams@m365b899688.onmicrosoft.com`); all 30 distinct exchange identities correlate deterministically via `lower()` casefold.
- **db_api_consistency:** PASS — the live API readback equals the independent DB cross-check equals the accepted DB evidence for license mapping, SKU mapping, and all three workload status distributions.
- **multiple_sku_users:** PASS — both multi-SKU users are correctly represented (assigned_sku_count=3 and =2, with correct sku_part_number lists).

## DOCUMENTATION

- **activity_log:** Added this STD-12C rerun acceptance entry to `docs/AI_USAGE_LOG.md`.
- **progress:** Updated `docs/PROJECT_PROGRESS.md`; STD-12C now `ACCEPTED` (`STD_12C_PASS`); correlation ACCEPTED.
- **evidence:** This file.
- **file_map:** Unchanged; no durable path/component changed (read-only acceptance; no source fix performed during acceptance).

## FILES_CHANGED

- `docs/PROJECT_PROGRESS.md`
- `docs/AI_USAGE_LOG.md`
- `docs/evidence/STD-12C-CROSS-WORKLOAD-CORRELATION-LIVE-ACCEPTANCE-001.md`

No production source, migration, permission, or runtime change was made during this acceptance.

## BLOCKERS

None. The STD-12D correction resolved the workload-join defect; runtime parity passes and the live
API readback matches the independent DB evidence.

## CORRELATION_STATUS

`ACCEPTED`

## NEXT_TASK

`STD-13-STANDARD-KPI-ENGINE-CONTRACT-001`

## FINAL_STATUS

`STD_12C_PASS`
