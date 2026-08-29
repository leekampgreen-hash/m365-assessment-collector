# STD-15H2 OneDrive Capacity Data Wiring

- **Task:** `STD-15H2-ONEDRIVE-CAPACITY-DATA-WIRING-001`
- **Result:** `STD_15H2A_PASS`
- **Scope:** OneDrive raw per-account capacity data through existing adoption analytics/API.

## Data wiring

`OperationsAnalyticsQueryService.onedrive_adoption()` now returns `account_details` preserving account identity/UPN, opaque `user_ref`, `storage_used`, `storage_allocated`, `file_count`, and `report_refresh_date`. Existing aggregate metrics and storage utilization semantics are unchanged. Directory enrichment uses existing casefolded UPN correlation; canonical joins are unchanged.

The existing endpoint `GET /api/operations/adoption/onedrive` carries the new `account_details` payload.

## Validation

- Focused analytics/API tests: PASS (36 tests).
- Python compile checks: PASS.
- Deployment: rebuilt `graph-agent-collector:dev` and recreated only `collector` and `operations-api`; no source changes made for acceptance.
- Runtime parity: PASS; all five checked production modules matched host/runtime hashes.
- Database reconciliation: PASS; tenant 2 authoritative table contains 26 rows, with storage_used 26/26, storage_allocated 26/26, file_count 26/26, and report_refresh_date 26/26.
- API reconciliation: PASS; `account_details` contains 26 rows matching the DB, all 26 preserve storage_used, storage_allocated, file_count, report_refresh_date, display_name, user_principal_name, and user_ref. Aggregate values remain 23 active users, 23 active accounts, latest activity 2026-06-26, total storage used 113932223, total file count 156, and storage utilization 3.985413583835068e-06.
- No SKU/license capacity inference, migration, utilization semantic layer, thresholds, UI, or browser tests performed.

## Acceptance

- **H2 status:** `ACCEPTED`
- **Next task:** `STD-15H3-ONEDRIVE-CAPACITY-SEMANTIC-VIEW-001`
