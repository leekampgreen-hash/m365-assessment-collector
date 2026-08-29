# EX-P08 Exchange Bounded Live Acceptance

- **Task ID:** `EX-P08-EXCHANGE-BOUNDED-LIVE-ACCEPTANCE-001`
- **Date:** 2026-08-29
- **Project:** graph-agent
- **Role:** `TEST/VALIDATION`
- **Result:** `EX_P08_PASS`

## Runtime

- **Collector service:** `graph-agent-collector-dev`, production entrypoint `python -m collectors.run_collector`.
- **Operations/parity service:** healthy `graph-agent-operations-api-dev`; required runtime parity PASS for `analytics/operations.py`, `collectors/usage_reports/registry.py`, `api/operations.py`, `collectors/persistence/core.py`, and `collectors/core/runtime.py`.
- **Database:** authoritative `graph_agent` / `graph_agent_runtime`.
- **Permission/inventory:** `Reports.Read.All` gate resolved; `USAGE-003` bound to `exchange_mailbox_usage`, `USAGE_REPORT_CSV`, D7, and `getMailboxUsageDetail(period='D7')`.

## Baseline

- Current: 30 rows; 30 unique tenant/mailbox keys; duplicate keys 0.
- Snapshot: 120 rows across four generations: `2026-08-23`, `2026-08-24`, `2026-08-25`, `2026-08-26`, 30 rows each.
- Latest refresh: `2026-08-26`.
- Current nulls: identity 0, storage 0, authoritative capacity 0.
- Analytics: 30 rows, `LOW=30`, `MEDIUM=0`, `HIGH=0`, `NO_DATA=0`.

## Bounded Live Collection

Exactly one production USAGE-003 execution was performed after parity PASS. It returned:

- HTTP/source: PASS; one page; 30 source rows.
- Normalized rows: 30.
- Completeness: complete; no retry; no error classification.
- Report refresh date: `2026-08-26`.
- Persistence: PASS; 30 rows reported persisted.
- Terminal status: `USAGE-003|PASS|PASS`; collection status `SUCCESS`.

## Data Acceptance

- Current remained one row per tenant/mailbox: 30 rows, 30 unique keys, 0 duplicates.
- Identity, storage, and `prohibit_send_receive_quota` remained populated; invalid/negative/zero accepted values: 0.
- Current refresh date was consistent at `2026-08-26`.
- Snapshot remained 120 rows across the four historical generations; no duplicate `(tenant, mailbox, refresh)` key.
- Historical generations and pre-quota NULL artifacts were not modified.
- The live report was the same generation as the existing latest generation, so current state remained deterministic and snapshot delta was 0. This is the required SAME-generation result; no newer or stale-generation mutation was induced.

## Analytics

`analytics.exchange_mailbox_capacity` remained read-only with 30 rows. All rows matched current storage, authoritative mailbox capacity (`prohibit_send_receive_quota`), refresh date, rounded utilization, and fail-closed usage-level contract. Distribution: `LOW=30`, `MEDIUM=0`, `HIGH=0`, `NO_DATA=0`. No license-based capacity inference exists or was used.

## Production Safety

- Synthetic/test residue: none observed in current or snapshot data.
- Cross-tenant leakage: none; current and snapshot rows outside tenant 2: 0.
- Partial-report replacement: none; complete live acquisition was required and reported.
- Duplicate snapshot generation: none.
- Schema drift: none; both authoritative tables present.
- Runtime error/retry loop: none; live run had zero retries and PASS status.
- Collection audit/status: endpoint `USAGE-003` PASS/PASS; collection SUCCESS.

## Regression

- Focused tests: `python -m unittest tests.usage_reports.test_usage_reports tests.core.test_usage_reports_runtime tests.integration.test_exchange_production_path` -> `36 tests`, `OK`.
- Runtime parity after collection: PASS.

Protection gaps remain non-blocking as classified in EX-P03: Spam `DATA_SOURCE_PENDING`, Quarantine `PLATFORM_BLOCKED`, and phishing/malware/spoof aggregate sources pending. No UX, protection telemetry, message trace, analytics redesign, or token/credit data was involved.

## Final Status

- **EXCHANGE_LIVE_ACCEPTED:** YES
- **READY_FOR_EX_P09:** YES
- **FINAL_STATUS:** `EX_P08_PASS`
