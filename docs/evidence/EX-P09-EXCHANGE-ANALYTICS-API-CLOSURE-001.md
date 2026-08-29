# EX-P09 Exchange Analytics/API Closure

- **Task ID:** `EX-P09-EXCHANGE-ANALYTICS-API-CLOSURE-001`
- **Date:** 2026-08-29
- **Project:** graph-agent
- **Role:** `INTEGRATION/WIRING`
- **Result:** `EX_P09_PASS`

## SEMANTIC_LAYER

- **source:** `core.usage_exchange_mailbox_usage` -> `analytics.exchange_mailbox_capacity` -> `analytics/operations.py` -> `api/operations.py` -> `operations-api`.
- **rows:** 30 semantic rows; one per current tenant/mailbox row.
- **tenant_scope:** The SQL view groups/selects newest `observed_at` per tenant; `from_connection` filters the view and current usage queries by configured tenant ID; API tenant is `GRAPH_TENANT_DB_ID=2`.
- **capacity_source:** `prohibit_send_receive_quota` only; no license inference.
- **utilization_source:** View-derived `storage_used / mailbox_capacity * 100`, rounded to two decimals in SQL; API does not recompute it.
- **threshold_source:** View-derived LOW/MEDIUM/HIGH/NO_DATA CASE expression (`<50`, `>=50/<80`, `>=80`, invalid/non-positive denominator or missing data).
- **refresh_source:** `report_refresh_date` from the usage report/persistence source; Last Activity is not substituted.

## LIVE_CONSISTENCY

- **current_rows:** 30.
- **semantic_rows:** 30.
- **duplicate_rows:** 0; 30 unique `(tenant_id, entity_key)` current keys and 30 unique semantic mailbox references.
- **latest_refresh:** `2026-08-26`.
- **LOW:** 30.
- **MEDIUM:** 0.
- **HIGH:** 0.
- **NO_DATA:** 0.
- Storage, authoritative capacity, and refresh comparisons against current persistence: 0 mismatches.
- Utilization recomputation and threshold comparisons against the view: 0 mismatches.

## API

- **endpoint:** `GET /api/operations/kpi` is the summary/KPI production endpoint; `GET /api/operations/adoption/exchange` exposes the same Exchange capacity summary and detail contract.
- **summary_contract:** `exchange.capacity_usage` exposes LOW/MEDIUM/HIGH/NO_DATA counts; `exchange.data_last_refreshed` exposes report freshness; `exchange.mailbox_capacity_risk` exposes the HIGH count metric.
- **detail_contract:** `exchange.mailbox_details[]` exposes readable `identity_value`/`user_principal_name`, `storage_used`, `mailbox_capacity`, view-derived `utilization_percent`, view-derived `usage_level`, and `report_refresh_date`. `user_ref` remains available as an opaque technical compatibility field.
- **detail_rows:** 30.
- **dependency_status:** READY with current semantic data. Empty or unavailable semantic view returns `DATA_DEPENDENCY_UNAVAILABLE`, null risk, no fabricated detail rows; NO_DATA rows remain visible as NO_DATA rather than healthy values. Stale but valid view data remains readable with its source refresh date.

Legacy activity counters, Last Activity, and mailbox item totals remain exposed for backward compatibility only and are not required by the Exchange capacity contract (`LEGACY_NON_BLOCKING`).

## MAILBOX_CAPACITY_RISK

- **value:** 0 HIGH mailboxes.
- **source:** `analytics.exchange_mailbox_capacity.usage_level`, counted in the Operations query service and scoped to the configured tenant.
- **duplicate_formula_present:** NO. No second utilization or threshold implementation was added to API code.

## TENANT_ISOLATION

- **analytics:** PASS. Every production capacity/current query includes `tenant_id=%s`; the view selects newest generations grouped by tenant. Existing isolated same-identity tenant tests pass.
- **api:** PASS. Operations API obtains tenant ID only from `GRAPH_TENANT_DB_ID` and loads all analytics through tenant-scoped `from_connection` queries.
- **kpi:** PASS. Summary and HIGH risk count are computed only from the tenant-filtered semantic view.

## FAIL_CLOSED

- **empty_data:** PASS. Capacity detail is empty, refresh is null, and dependency-backed values are unavailable rather than healthy zero.
- **no_data_rows:** PASS. Rows classify as NO_DATA and count in the NO_DATA bucket; risk is based only on HIGH rows.
- **dependency_failure:** PASS. API returns HTTP 503 with `DATA_DEPENDENCY_UNAVAILABLE` and does not expose exception details.
- **stale_valid_data:** PASS. Valid persisted rows remain exposed with their source `report_refresh_date`; no Last Activity substitution or fabricated freshness occurs.

## TESTS

- **focused:** `python3 -m unittest tests.analytics.test_operations tests.analytics.test_operations_api tests.integration.test_exchange_production_path` -> 41 tests, OK, 1 environment skip. Added coverage for all four semantic levels, readable detail identity/refresh mapping, and HIGH risk count. Host compile validation passed.
- **container:** `operations-api` rebuilt and recreated only after production analytics code changed; PostgreSQL remained the authoritative Compose database. One existing DB-backed integration test was skipped because host execution lacked production credentials.
- **api_contract:** PASS for summary, detail mapping, empty/no-data/failure behavior, backward-compatible legacy fields, tenant-scoped query construction, and production path.

## LIVE_API

- **http_status:** 200.
- **summary:** READY; LOW 30, MEDIUM 0, HIGH 0, NO_DATA 0; report refresh `2026-08-26`.
- **risk:** 0.
- **detail_count:** 30.
- **db_view_consistency:** PASS; API values match the authoritative view and current persistence for row count, storage, capacity, utilization, usage level, and refresh date.

## RUNTIME_PARITY

PASS after rebuilding/recreating only `operations-api`. Host and deployed hashes matched for `analytics/operations.py`, `collectors/usage_reports/registry.py`, `api/operations.py`, `collectors/persistence/core.py`, and `collectors/core/runtime.py`.

## GAP CLASSIFICATION

- **BLOCKING:** None.
- **LEGACY_NON_BLOCKING:** Existing activity counters, Last Activity, mailbox item count, opaque `user_ref`, and legacy adoption fields remain for compatibility but are not dependencies of the new/basic capacity contract.
- **NON_BLOCKING_TECH_DEBT:** None introduced. Historical redundant snapshot index/retention observations remain outside P09.
- **DEFERRED:** EX-P03 protection-source gaps, Defender telemetry, message-level metrics, and UX remain deferred and are not reopened.
- **BLOCKERS:** None.

## FINAL

- **EXCHANGE_ANALYTICS_API_READY:** YES
- **EXCHANGE_EX_PXX_READY_FOR_INDEPENDENT_REVIEW:** YES
- **FILES_CHANGED:** `database/migrations/015_exchange_mailbox_capacity.sql`, `analytics/operations.py`, `tests/analytics/test_operations.py`, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, `docs/evidence/EX-P09-EXCHANGE-ANALYTICS-API-CLOSURE-001.md`
- **FINAL_STATUS:** `EX_P09_PASS`

No token or credit data is recorded.
