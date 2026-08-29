# STD-13C Standard KPI Live Acceptance Evidence

- **Task ID:** `STD-13C-STANDARD-KPI-LIVE-ACCEPTANCE-001`
- **Category:** `TEST/VALIDATION`
- **Role:** `LIVE_ACCEPTANCE`
- **Date:** 2026-08-28
- **Result:** `STD_13C_PASS`
- **KPI engine status:** `ACCEPTED`
- **Next task:** `STD-14-STANDARD-API-CONTRACT-001`

## Runtime

- `python3 scripts/check_runtime_parity.py` ran first and passed: all five required runtime modules were `MATCH`.
- API health from `graph-agent-operations-api-dev`: `{"status":"READY","database":"READY"}`.
- Host port was not published; the bounded API readback was executed inside the API container. No source, collector, Graph, schema, or permission changes were made.

## API readback and independent DB cross-check

Tenant 2 API `GET /api/operations/kpi` returned `status=READY`, `as_of=2026-08-27`, and coherent metric envelopes.

- **Tenant:** 39 total users; 25 licensed; 14 unlicensed. Independent DB counts matched exactly; 28 assignment rows and 3 subscribed SKUs were present.
- **License:** `SPB` 25/25/0, 100%, 25 assigned; `AAD_PREMIUM_P2` 1/1/0, 100%, 1 assigned; `POWER_BI_STANDARD` 1,000,000/2/999,998, 0%, 2 assigned. Each SKU was independently keyed and no misleading cross-SKU purchased-license aggregate was present.
- **Exchange:** 23 active, 7 inactive, 9 unknown; latest activity `2026-07-25`; storage `149438006`; mailbox items `56340`.
- **OneDrive:** 23 active, 7 inactive, 9 unknown; latest activity `2026-06-26`; storage `113932223`; files `156`; utilization `3.985413583835068e-06`.
- **SharePoint:** 24 active, 6 inactive, 9 unknown; 3 active sites; latest activity `2026-06-26`; storage `36964667`; files `43`; utilization `1.1206389596433534e-07`.
- **Cross-workload:** active all 3 `22`; exactly 2 `2`; exactly 1 `0`; inactive all complete evidence `6`; users with unknown evidence `9`.

## Validation

- **Unknown handling:** PASS. Unknown counts are exposed separately and are never silently counted as inactive; cross-workload unknown evidence is explicit.
- **Denominator semantics:** PASS. User status counts use the canonical-user directory denominator; capacity utilization uses allocated-capacity semantics. No adoption percentage was inferred.
- **License per SKU:** PASS. Arithmetic and distinct assigned-user counts were independently checked per SKU; no aggregate across unrelated SKUs exists.
- **Tenant isolation:** PASS. API service is configured for tenant 2; independent DB checks were tenant-scoped and matched accepted correlation totals.
- **DB/API consistency:** PASS. Tenant totals, SKU inventory/assignment metrics, workload counts, dates, capacity totals, and cross-workload buckets match the live DB/correlation evidence and accepted prior results.
- **Source metadata:** PASS. Metric envelopes expose `status`, source refresh date where available, source period, and missing dependency; all live metrics are `READY`, with no missing workload or entitlement dependency and no partial tenant coverage.

## Scope and blockers

Read-only bounded acceptance only. No broad fixes were attempted. `psql` was unavailable in the API container, so the independent SQL cross-check used the PostgreSQL runtime container; this is not a blocker. `PROJECT_FILE_MAP` is unchanged because no durable path/component changed.

- **Final status:** `STD_13C_PASS`
