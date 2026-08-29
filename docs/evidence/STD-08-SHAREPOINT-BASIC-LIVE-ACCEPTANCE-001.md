# STD-08 SharePoint Basic Live Acceptance

- **Task ID:** `STD-08-RERUN-SHAREPOINT-BASIC-LIVE-ACCEPTANCE-001`
- **Date:** 2026-08-28
- **Role:** `INDEPENDENT_LIVE_ACCEPTANCE`
- **Purpose:** One bounded native production-path acceptance of USAGE-006 and USAGE-007 after the USAGE-007 site identity correction.
- **Result:** `ACCEPTED` / `STD_08_PASS`.

## LIVE_PATH

- **runtime_parity:** PASS. `python3 scripts/check_runtime_parity.py graph-agent-operations-api-dev` ran first; all five checked modules matched host hashes, exit 0.
- **permission_gate:** PASS. With `Reports.Read.All`, decision was `COLLECT`. Withholding it (`User.Read.All` only) returned `SKIP_PERMISSION_REQUIRED` / `PERMISSION_REQUIRED` for both endpoints, with zero rows, Graph calls, and persistence.
- **user_activity_graph:** PASS. Native `USAGE-006` / `getSharePointActivityUserDetail(D7)` returned 30 source rows, 30 normalized/persisted rows, one page.
- **site_usage_graph:** PASS. Native `USAGE-007` / `getSharePointSiteUsageDetail(D7)` returned 12 source rows, 12 normalized/persisted rows, one page, `identity_unavailable=false`.
- **rows_collected:** 30 user rows and 12 site rows.
- **normalization:** PASS for both endpoints; Site Id supplied canonical site identity despite blank Site URL.
- **current_persistence:** PASS; 30 user rows and 12 site rows persisted.
- **snapshot_persistence:** PASS; current/snapshot persistence completed, with 13 site snapshot rows present.
- **analytics:** PASS; active status uses only non-deleted rows with non-empty `last_activity_date`; viewed/synced/page-view thresholds do not drive status.
- **api_readback:** PASS; both SharePoint adoption routes returned HTTP 200 and agreed with current DB values.

## IDENTITY_VALIDATION

- **canonical_site_identity:** PASS. Site Id is the canonical `entity_key`; Site URL remains secondary and may be blank.
- **distinct_site_keys:** PASS. 12 current site rows have 12 distinct Site Id entity keys.
- **identity_fail_closed:** PASS. Identity-less rows remain rejected as `ENTITY_IDENTITY_UNAVAILABLE`; no fabricated or collapsed identity is accepted.

## KPI_READBACK

API and DB readback for tenant 2:

- **active_users:** 24
- **active_sites:** 3
- **latest_activity:** 2026-06-26
- **total_storage_used:** 36964667
- **total_file_count:** 43
- **storage_utilization:** 1.1206389596433534e-07

## DB_API_CONSISTENCY

`PASS`

## Safety

No source code, database schema/grants, permissions, credentials, or Graph writes were modified. No token or credit usage was logged. No sharing/oversharing, Purview, or License work was performed.

## DOCUMENTATION

- Updated this final STD-08 acceptance evidence.
- Updated `docs/PROJECT_PROGRESS.md` and `docs/AI_USAGE_LOG.md` with the rerun result.
- `docs/PROJECT_FILE_MAP.md` unchanged; no durable path/component changed.

## BLOCKERS

None.

## Final

- **SHAREPOINT_BASIC_STATUS:** `ACCEPTED`
- **NEXT_TASK:** `STD-09-LICENSE-INVENTORY-BASELINE-001`
- **FINAL_STATUS:** `STD_08_PASS`
