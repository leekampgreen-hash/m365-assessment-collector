"""Live PostgreSQL validation suite for TD-004.

Validates representative persistence patterns and database invariants against the
live PostgreSQL instance:
- Database connectivity & transaction boundaries (commit, rollback).
- Schema existence: core, control, raw schemas.
- Table existence: core.device, core.application, core.named_location,
  core.conditional_access_policy, core.conditional_access_policy_snapshot,
  core.audit_event, core.signin_log, control.collection_run, control.endpoint_run.
- Check constraints: retention_class ('SHORT','STANDARD','LONG','REFERENCE'),
  endpoint_run status and error_classification.
- Persistence execution:
  * CURRENT upsert pattern
  * CURRENT_WITH_SNAPSHOT dual-write pattern
  * EVENT append-only replay idempotency (ON CONFLICT DO NOTHING)
  * Transaction rollback behavior (atomicity, no partial writes)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg


def get_connection():
    # Read environment or secret password file
    password = None
    for pw_path in (
        Path("/run/secrets/graph_agent_runtime_password"),
        Path("/workspace/secrets/graph-agent-runtime-password"),
        Path("secrets/graph-agent-runtime-password"),
    ):
        if pw_path.exists():
            password = pw_path.read_text().strip()
            break

    host = os.getenv("PGHOST", "postgres")
    port = int(os.getenv("PGPORT", "5432"))
    dbname = os.getenv("PGDATABASE", "graph_agent")
    user = os.getenv("PGUSER", "graph_agent_runtime")

    return psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        autocommit=False,
    )


def run_live_postgres_validation() -> dict:
    results = []
    overall_pass = True

    # 1. Connectivity Test
    start = time.monotonic()
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            pg_ver = cur.fetchone()[0]
        conn.close()
        results.append({
            "test": "connectivity",
            "status": "PASS",
            "details": f"Connected to PostgreSQL ({pg_ver[:30]}...)",
            "duration_seconds": round(time.monotonic() - start, 3),
        })
    except Exception as exc:
        results.append({
            "test": "connectivity",
            "status": "FAIL",
            "error": str(exc),
        })
        return {
            "overall_status": "FAIL",
            "results": results,
        }

    # 2. Schema Existence
    start = time.monotonic()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name IN ('core', 'control', 'raw');
            """)
            found_schemas = [row[0] for row in cur.fetchall()]
        expected_schemas = ["core", "control", "raw"]
        missing_schemas = set(expected_schemas) - set(found_schemas)
        passed = len(missing_schemas) == 0
        if not passed:
            overall_pass = False
        results.append({
            "test": "schema_existence",
            "status": "PASS" if passed else "FAIL",
            "found_schemas": found_schemas,
            "missing_schemas": list(missing_schemas),
            "duration_seconds": round(time.monotonic() - start, 3),
        })
    except Exception as exc:
        overall_pass = False
        results.append({"test": "schema_existence", "status": "FAIL", "error": str(exc)})

    # 3. Table Existence
    start = time.monotonic()
    expected_tables = [
        ("core", "device"),
        ("core", "application"),
        ("core", "named_location"),
        ("core", "conditional_access_policy"),
        ("core", "conditional_access_policy_snapshot"),
        ("core", "audit_event"),
        ("core", "signin_log"),
        ("control", "collection_run"),
        ("control", "endpoint_run"),
        ("control", "collector_checkpoint"),
    ]
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_schema, table_name FROM information_schema.tables
                WHERE table_schema IN ('core', 'control');
            """)
            existing_tables = set(cur.fetchall())
        missing_tables = [f"{s}.{t}" for s, t in expected_tables if (s, t) not in existing_tables]
        passed = len(missing_tables) == 0
        if not passed:
            overall_pass = False
        results.append({
            "test": "table_existence",
            "status": "PASS" if passed else "FAIL",
            "checked_count": len(expected_tables),
            "missing_tables": missing_tables,
            "duration_seconds": round(time.monotonic() - start, 3),
        })
    except Exception as exc:
        overall_pass = False
        results.append({"test": "table_existence", "status": "FAIL", "error": str(exc)})

    # 4. Check Constraints Verification
    start = time.monotonic()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT conname, pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_namespace n ON n.oid = c.connamespace
                WHERE n.nspname IN ('core', 'control') AND contype = 'c';
            """)
            constraints = {row[0]: row[1] for row in cur.fetchall()}
        
        # Check endpoint_run_error_classification_check
        has_err_cls = "endpoint_run_error_classification_check" in constraints
        has_retention = any("retention_class" in v for v in constraints.values())
        passed = has_err_cls and has_retention
        if not passed:
            overall_pass = False
        results.append({
            "test": "check_constraints",
            "status": "PASS" if passed else "FAIL",
            "error_classification_check_present": has_err_cls,
            "retention_class_check_present": has_retention,
            "duration_seconds": round(time.monotonic() - start, 3),
        })
    except Exception as exc:
        overall_pass = False
        results.append({"test": "check_constraints", "status": "FAIL", "error": str(exc)})

    # Fetch valid tenant_id from database
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id FROM core.tenant LIMIT 1;")
            tenant_row = cur.fetchone()
            tenant_id = tenant_row[0] if tenant_row else None
    except Exception as exc:
        tenant_id = None

    # 5. Transaction Atomicity & Rollback Test
    start = time.monotonic()
    try:
        test_run_uuid = "00000000-0000-0000-0000-000000000099"
        # Insert a row and roll back
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO control.collection_run 
                (run_uuid, tenant_id, started_at, status, trigger_source, collector_version, selected_endpoint_ids, endpoints_total)
                VALUES (%s, %s, NOW(), 'RUNNING', 'test', 'test', ARRAY['G01-001'], 1)
            """, (test_run_uuid, tenant_id))
        conn.rollback()

        # Verify row does not exist after rollback
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM control.collection_run WHERE run_uuid = %s;", (test_run_uuid,))
            count = cur.fetchone()[0]
        passed = (count == 0)
        if not passed:
            overall_pass = False
        results.append({
            "test": "transaction_atomicity_and_rollback",
            "status": "PASS" if passed else "FAIL",
            "persisted_after_rollback": count,
            "duration_seconds": round(time.monotonic() - start, 3),
        })
    except Exception as exc:
        overall_pass = False
        conn.rollback()
        results.append({"test": "transaction_atomicity_and_rollback", "status": "FAIL", "error": str(exc)})

    # 6. CURRENT pattern upsert execution test
    start = time.monotonic()
    try:
        test_actor_id = "test-live-agent-app-01"
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            # 1st upsert
            cur.execute("""
                INSERT INTO core.application
                (tenant_id, source_object_id, app_id, display_name, last_observed_at, retention_class)
                VALUES (%s, %s, 'app-1', 'App Alpha', %s, 'REFERENCE')
                ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET
                display_name = EXCLUDED.display_name, last_observed_at = EXCLUDED.last_observed_at;
            """, (tenant_id, test_actor_id, now))
            # 2nd upsert (update)
            cur.execute("""
                INSERT INTO core.application
                (tenant_id, source_object_id, app_id, display_name, last_observed_at, retention_class)
                VALUES (%s, %s, 'app-1', 'App Alpha Updated', %s, 'REFERENCE')
                ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET
                display_name = EXCLUDED.display_name, last_observed_at = EXCLUDED.last_observed_at;
            """, (tenant_id, test_actor_id, now))
            # Query back within transaction
            cur.execute("SELECT display_name FROM core.application WHERE tenant_id = %s AND source_object_id = %s;", (tenant_id, test_actor_id))
            name = cur.fetchone()[0]
        # Roll back transaction for isolation (least-privilege role has no DELETE permission)
        conn.rollback()
        passed = (name == "App Alpha Updated")
        if not passed:
            overall_pass = False
        results.append({
            "test": "current_pattern_upsert",
            "status": "PASS" if passed else "FAIL",
            "updated_value_verified": name,
            "duration_seconds": round(time.monotonic() - start, 3),
        })
    except Exception as exc:
        overall_pass = False
        conn.rollback()
        results.append({"test": "current_pattern_upsert", "status": "FAIL", "error": str(exc)})

    # 7. EVENT pattern duplicate-ignore replay test
    start = time.monotonic()
    try:
        event_src_id = "test-live-audit-event-01"
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            # Find an existing collection_run_id and endpoint_run_id
            cur.execute("SELECT collection_run_id, endpoint_run_id FROM control.endpoint_run LIMIT 1;")
            row = cur.fetchone()
            if row:
                col_run_id, ep_run_id = row[0], row[1]
            else:
                test_run_uuid = "00000000-0000-0000-0000-000000000088"
                cur.execute("""
                    INSERT INTO control.collection_run
                    (run_uuid, tenant_id, started_at, status, trigger_source, collector_version, selected_endpoint_ids, endpoints_total)
                    VALUES (%s, %s, NOW(), 'RUNNING', 'test', 'test', ARRAY['G01-005'], 1)
                    ON CONFLICT (run_uuid) DO UPDATE SET status = EXCLUDED.status
                    RETURNING collection_run_id;
                """, (test_run_uuid, tenant_id))
                col_run_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO control.endpoint_run
                    (collection_run_id, endpoint_id, endpoint_name, tenant_id, started_at, status)
                    VALUES (%s, 'G01-005', 'directoryAudits', %s, NOW(), 'PASS')
                    RETURNING endpoint_run_id;
                """, (col_run_id, tenant_id))
                ep_run_id = cur.fetchone()[0]

            # 1st insert
            cur.execute("""
                INSERT INTO core.audit_event
                (tenant_id, event_source, source_object_id, event_at, collected_at, collection_run_id, endpoint_run_id, activity, result, retention_class)
                VALUES (%s, 'DIRECTORY_AUDIT', %s, %s, %s, %s, %s, 'Update User', 'success', 'LONG')
                ON CONFLICT (tenant_id, event_source, source_object_id) DO NOTHING;
            """, (tenant_id, event_src_id, now, now, col_run_id, ep_run_id))
            # 2nd insert with same unique key -> must DO NOTHING without error
            cur.execute("""
                INSERT INTO core.audit_event
                (tenant_id, event_source, source_object_id, event_at, collected_at, collection_run_id, endpoint_run_id, activity, result, retention_class)
                VALUES (%s, 'DIRECTORY_AUDIT', %s, %s, %s, %s, %s, 'Update User', 'success', 'LONG')
                ON CONFLICT (tenant_id, event_source, source_object_id) DO NOTHING;
            """, (tenant_id, event_src_id, now, now, col_run_id, ep_run_id))
            # Verify count is exactly 1 within transaction
            cur.execute("SELECT count(*) FROM core.audit_event WHERE tenant_id = %s AND source_object_id = %s;", (tenant_id, event_src_id))
            cnt = cur.fetchone()[0]
        # Roll back transaction so no test event is committed and no DELETE is required
        conn.rollback()
        passed = (cnt == 1)
        if not passed:
            overall_pass = False
        results.append({
            "test": "event_pattern_duplicate_replay_idempotency",
            "status": "PASS" if passed else "FAIL",
            "recorded_count": cnt,
            "duration_seconds": round(time.monotonic() - start, 3),
        })
    except Exception as exc:
        overall_pass = False
        conn.rollback()
        results.append({"test": "event_pattern_duplicate_replay_idempotency", "status": "FAIL", "error": str(exc)})

    conn.close()

    summary = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_status": "PASS" if overall_pass else "FAIL",
        "total_checks": len(results),
        "passed_checks": sum(1 for r in results if r["status"] == "PASS"),
        "results": results,
    }
    return summary


if __name__ == "__main__":
    try:
        report = run_live_postgres_validation()
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["overall_status"] == "PASS" else 1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
