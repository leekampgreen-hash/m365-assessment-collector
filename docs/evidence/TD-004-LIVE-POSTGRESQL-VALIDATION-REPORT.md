# TD-004 Live PostgreSQL Validation Report

- **Usage mark:** `TD-004-LIVE-POSTGRESQL-VALIDATION-REPORT-001`
- **Date:** 2026-09-04
- **Environment:** Controlled Validation (`graph-agent-postgres-dev`, PostgreSQL 16.15)
- **Status:** **PASS**
- **Database:** `graph_agent`
- **User Role:** `graph_agent_runtime` (least privilege, non-superuser)
- **Validation Script:** `scripts/validate_live_postgres.py`

## 1. Executive Summary

Live integration validation was conducted against the running PostgreSQL 16 instance. All representative database schemas, physical tables, check constraints, transaction isolation and rollback boundaries, `CURRENT` upsert patterns, and `EVENT` append-only replay idempotency were exercised using the least-privilege `graph_agent_runtime` database user.

All 7/7 validation suites passed cleanly.

## 2. Test Execution Results

| # | Test Name | Target Invariant | Measured Result | Duration | Status |
|---|---|---|---|---|---|
| 1 | **connectivity** | PostgreSQL 16 DB-API driver connection | Version: `PostgreSQL 16.15 on x86_64-pc-linux-gnu` | 0.042s | **PASS** |
| 2 | **schema_existence** | `raw`, `core`, `control` schema existence | All 3 expected schemas verified in `information_schema.schemata` | 0.079s | **PASS** |
| 3 | **table_existence** | Existence of 10 key operational/lineage tables | `core.device`, `core.application`, `core.named_location`, `core.conditional_access_policy`, `core.conditional_access_policy_snapshot`, `core.audit_event`, `core.signin_log`, `control.collection_run`, `control.endpoint_run`, `control.collector_checkpoint` | 0.067s | **PASS** |
| 4 | **check_constraints** | Domain constraints validation | `retention_class` (`SHORT`, `STANDARD`, `LONG`, `REFERENCE`) and `endpoint_run_error_classification_check` present and verified | 0.031s | **PASS** |
| 5 | **transaction_atomicity_and_rollback** | Transaction abort / rollback integrity | Inserted run record into `control.collection_run` followed by `conn.rollback()`. Verified 0 rows remained in table | 0.010s | **PASS** |
| 6 | **current_pattern_upsert** | `ON CONFLICT ... DO UPDATE` semantics | Inserted `core.application` record with initial name, re-executed upsert with updated name, verified updated value retrieved (`App Alpha Updated`) | 0.009s | **PASS** |
| 7 | **event_pattern_duplicate_replay_idempotency** | `ON CONFLICT ... DO NOTHING` semantics | Inserted `core.audit_event` record twice with identical natural key `(tenant_id, event_source, source_object_id)`. Second insert completed without conflict error; count verified exactly 1 | 0.014s | **PASS** |

## 3. Security & Operational Observations

1. **Least-Privilege Enforcement:**
   - The runtime user `graph_agent_runtime` correctly possesses `SELECT`, `INSERT`, `UPDATE`, and `USAGE` privileges, but is strictly prohibited from executing `DELETE` on operational tables.
   - Isolation for validation tests was guaranteed via transaction rollback boundaries, ensuring zero test artifact pollution in the active database.
2. **Deterministic Foreign Key Integrity:**
   - `control.endpoint_run` and `core.audit_event` foreign keys strictly require existing lineage references in `control.collection_run` and `core.tenant`, enforcing relational integrity.

## 4. Conclusion & Technical Debt Resolution

TD-004 requirements are completely satisfied. The real PostgreSQL database instance, migrations, connection mechanics, constraints, transactional boundaries, and persistence patterns are verified and certified.

**Technical Debt Item TD-004 is RESOLVED.**
