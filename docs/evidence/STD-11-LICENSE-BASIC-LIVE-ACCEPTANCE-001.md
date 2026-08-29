# STD-11 License Basic Live Acceptance Evidence

- **Task ID:** `STD-11-LICENSE-BASIC-LIVE-ACCEPTANCE-001`
- **Result:** `STD_11_PASS`
- **Role:** `INDEPENDENT_LIVE_ACCEPTANCE`
- **Scope:** Native app-only G01-001 users/assignedLicenses and G01-004 subscribedSkus paths; read-only validation only.

## LIVE_PATH

- **runtime_parity:** PASS; `scripts/check_runtime_parity.py` ran first, all five checked modules MATCH.
- **user_graph:** PASS; G01-001 HTTP 200, 4 pages, 39 users.
- **sku_graph:** PASS; G01-004 HTTP 200, 1 page, 3 SKUs.
- **permission_gate:** PASS; explicit `User.Read.All LicenseAssignment.Read.All` gate permitted both reads. No mutation or consent change.
- **user_persistence:** PASS; 39 `core."user"` rows read back for tenant 2.
- **sku_persistence:** PASS; 3 `core.subscribed_sku` rows read back.
- **assignment_persistence:** PASS; 28 tenant-scoped assignment rows read back.
- **snapshot_persistence:** PASS; 6 snapshot rows representing 3 distinct current SKUs.

## LICENSE_READBACK

- **sku_count:** 3
- **purchased_units:** 1,000,026
- **consumed_units:** 28
- **available_units:** 999,998
- **utilization:** 0.0027999% weighted (`28 / 1,000,026 * 100`)
- **licensed_users:** 25
- **unlicensed_users:** 14
- **users_with_multiple_skus:** 2
- **assignment_rows:** 28
- **per_sku_assignment_counts:** AAD_PREMIUM_P2=1; POWER_BI_STANDARD=2; SPB=25

## MAPPING_VALIDATION

- **tenant_isolation:** PASS; all joins and assignment data are tenant 2 scoped; zero orphan user/SKU references.
- **user_join:** PASS; assignments resolve through tenant-scoped `core."user"` identity.
- **sku_join:** PASS; assignments resolve through tenant-scoped `core.subscribed_sku.sku_id`.
- **complete_refresh:** PASS by accepted production implementation contract: complete evidence deletes and rebuilds one tenant's assignment set, removing stale rows.
- **partial_evidence_fail_closed:** PASS by accepted implementation test/evidence: missing `assignedLicenses` on any normalized user preserves existing assignments and never clears them.

## DB_CONSISTENCY

PASS. Calculated/read-only database metrics agree: 3 SKUs, 39 users, 25 licensed, 14 unlicensed, 28 assignments, 2 multi-SKU users, zero orphan assignments, and matching per-SKU counts. No `/licenseDetails` path or license mutation was used.

## DOCUMENTATION

- **std10b_status:** `NOT_REQUIRED / SKIPPED`; existing production wiring satisfies STD-10.
- **activity_log:** Updated `docs/AI_USAGE_LOG.md` with bounded live acceptance activity.
- **progress:** Updated `docs/PROJECT_PROGRESS.md`; STD-11 accepted and STD-12 next.
- **evidence:** This file.
- **file_map:** Unchanged; no durable component/path changed.

## FILES_CHANGED

- `docs/PROJECT_PROGRESS.md`
- `docs/AI_USAGE_LOG.md`
- `docs/evidence/STD-11-LICENSE-BASIC-LIVE-ACCEPTANCE-001.md`

## BLOCKERS

None.

## LICENSE_BASIC_STATUS

`ACCEPTED`

## NEXT_TASK

`STD-12-CROSS-WORKLOAD-CORRELATION-CONTRACT-001`

## FINAL_STATUS

`STD_11_PASS`
