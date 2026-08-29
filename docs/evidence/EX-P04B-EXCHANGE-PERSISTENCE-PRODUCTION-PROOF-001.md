# EX-P04B Exchange Persistence Production Proof

- **Task ID:** `EX-P04B-EXCHANGE-PERSISTENCE-PRODUCTION-PROOF-001`
- **Date:** 2026-08-29
- **Project:** graph-agent
- **Result:** `EX_P04B_PASS`

## Runtime

- **Service:** `operations-api` (`graph-agent-operations-api-dev`); collector runtime exercised in `graph-agent-collector-dev`.
- **Artifact:** `graph-agent-collector:dev`, rebuilt and `operations-api` recreated only after stale parity was detected.
- **Parity:** PASS for `analytics/operations.py`, `collectors/usage_reports/registry.py`, `api/operations.py`, `collectors/persistence/core.py`, and `collectors/core/runtime.py`.

## Authoritative database and baseline

- **Database/user:** `graph_agent` / `graph_agent_runtime`.
- **Tenant:** 2.
- **Current before:** 30 rows.
- **Snapshot before:** 90 rows.
- **Latest report refresh:** `2026-08-25`.
- **Bounded baseline hashes:** current `9d47b6e263dec34e619fd946f62ec72d`; snapshot `2d1215e2fe8c0c6c51d6564226861bfb`.

## Production-path safety proofs

Controlled inputs used `collectors.usage_reports.persistence.write_report_rows` from the collector container. No Microsoft Graph calls were made. Synthetic successful writes ran inside a transaction and were rolled back.

- **Incomplete report:** explicit rejection before SQL; current and snapshot preserved.
- **Duplicate business key:** `SYN@example.invalid` / `syn@example.invalid` rejected as normalized collision with `count=2`; no SQL executed; current and snapshot preserved.
- **Empty report:** `NO_OP`; existing state preserved.
- **Repeated complete generation:** first synthetic generation produced one temporary current row and one snapshot; second generation produced identical state and snapshot delta `0`; rollback removed all synthetic data.
- **Rollback proof:** after rollback current returned to 30 and snapshot to 90; both baseline hashes matched exactly.

## Live data integrity after validation

- Current rows: 30.
- Unique mailbox keys: 30.
- Duplicate keys: 0.
- Null `storage_used`: 0.
- Null `prohibit_send_receive_quota`: 0.
- Invalid/negative/zero numeric values: 0.
- Snapshot rows: 90; historical generations preserved (previous evidence records `2026-08-23`, `2026-08-24`, `2026-08-25`, 30 each).
- Pre-quota historical NULL artifacts remain preserved by policy; no historical rewrite performed.

## Analytics compatibility

`analytics.exchange_mailbox_capacity` remains read-only and compatible: 30 rows matching current state, distribution `LOW=30`, utilization range `0.00` to `0.02`, and valid utilization semantics. No analytics objects were modified.

## Test fixture issue

The focused usage-report and runtime suite passed: 30 tests. The unrelated fixture/setup failure noted in prior task context was not reproduced and was not repaired; it does not affect this production-path persistence confidence result.

## Final status

- **PERSISTENCE_READY:** YES
- **READY_FOR_EX_P05:** YES
- **FINAL_STATUS:** `EX_P04B_PASS`

No token or credit data is recorded.
