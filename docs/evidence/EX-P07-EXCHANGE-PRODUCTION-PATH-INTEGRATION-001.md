# EX-P07B Exchange Production-Path Negative Integration Matrix

- **Task ID:** `EX-P07B-NEGATIVE-PATH-INTEGRATION-MATRIX-001`
- **Date:** 2026-08-29
- **Result:** `EX_P07B_PASS`

## Validation

The real `CollectorRuntime` USAGE-003 path was exercised with bounded fake transport and an isolated writer harness. Incomplete, normalized duplicate, stale generation, repeated generation, missing identity, missing/malformed refresh, 429-then-success, and retry exhaustion cases passed. Retry exhaustion is classified `THROTTLED/RETRY_EXHAUSTED`; no writer calls occurred for failure cases.

Two isolated tenants using the same normalized identity passed without collision; generated SQL values remained tenant-scoped for current and snapshot writes.

- Integration and focused usage-report tests: `29 tests`, `OK`, `2 skipped` for unavailable live PostgreSQL credentials.
- Compile validation: PASS (`python3 -m compileall`).
- Production code changed: NO (test harness only).
- Tenant 2 live protection baseline was not re-run because credentials/database service were unavailable in this environment; no production tenant was used by synthetic tests.

- **EX_P07_CLOSED:** YES
- **READY_FOR_EX_P08:** YES
- **FINAL_STATUS:** `EX_P07B_PASS`

No token or credit data is recorded.
