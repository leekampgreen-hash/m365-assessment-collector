"""Focused offline tests for G01-015 alignment: CURRENT_WITH_SNAPSHOT vs EVENT conflict."""
import unittest
from pathlib import Path
from copy import deepcopy
from collectors.persistence import BoundSqlExecutor, PersistenceError, write_event_record
from collectors.workloads.models import NormalizedWorkloadRecord, PersistenceMode
from collectors.workloads import REGISTRY, PersistenceMode as PM


class FakeCursor:
    def __init__(self, c): self.c=c
    def execute(self, s, p): self.c.statements.append((s,p))
class FakeConnection:
    def __init__(self): self.statements=[]
    def cursor(self): return FakeCursor(self)
    def commit(self): pass
    def rollback(self): pass

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"

class G01_015RegistryAlignmentTests(unittest.TestCase):
    def test_registry_mode_is_current_with_snapshot(self):
        entry = REGISTRY["G01-015"]
        self.assertEqual(entry.persistence_mode, PM.CURRENT_WITH_SNAPSHOT)
        self.assertEqual(entry.current_table, "core.service_health_overview")
        self.assertEqual(entry.snapshot_table, "core.service_health_overview_snapshot")
        self.assertIsNone(entry.history_table)
        self.assertIsNone(entry.event_table)

    def test_registry_snapshot_table_matches_migration(self):
        sql = "".join(p.read_text() for p in sorted(MIGRATIONS_DIR.glob("*.sql")))
        self.assertIn("core.service_health_overview", sql)
        self.assertIn("core.service_health_overview_snapshot", sql)
        self.assertIn("UNIQUE (tenant_id, source_object_id, collection_run_id)", sql)

    def test_persistence_core_rejects_g01_015_as_event(self):
        c=FakeConnection()
        row={"tenant_id":1,"source_object_id":"svc-1","service":"Exchange","status":"ServiceOperational","last_observed_at":"2026-01-02T00:00:00Z","retention_class":"STANDARD"}
        with self.assertRaisesRegex(PersistenceError, "Unsupported EVENT endpoint"):
            write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-015", PersistenceMode.EVENT, event_row=row))
        self.assertEqual(c.statements, [])

    def test_persistence_event_endpoints_exclude_g01_015(self):
        from collectors.persistence.core import _EVENT_ENDPOINTS
        self.assertEqual(set(_EVENT_ENDPOINTS.keys()), {"G01-005","G01-006","G01-014","SP-A01"})
        self.assertNotIn("G01-015", _EVENT_ENDPOINTS)

    def test_source_mutation_none_on_rejection(self):
        c=FakeConnection()
        row={"tenant_id":1,"source_object_id":"svc-1","service":"Exchange","status":"ServiceOperational","last_observed_at":"2026-01-02T00:00:00Z","retention_class":"STANDARD"}
        orig=deepcopy(row)
        rec=NormalizedWorkloadRecord("G01-015", PersistenceMode.EVENT, event_row=row)
        try:
            write_event_record(BoundSqlExecutor(c), rec)
        except PersistenceError:
            pass
        self.assertEqual(row, orig)
        self.assertEqual(rec.event_row, orig)

    def test_parameterized_sql_for_valid_events(self):
        c=FakeConnection()
        row={"tenant_id":5,"event_source":"DIRECTORY_AUDIT","source_object_id":"a1","event_at":"2026-01-01T00:00:00Z","collected_at":"2026-01-01T00:01:00Z","collection_run_id":1,"endpoint_run_id":1,"actor_user_id":None,"actor_app_id":None,"activity":None,"category":None,"result":None,"is_interactive":None,"risk_level":None,"extension":None,"retention_class":"LONG"}
        write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-005", PersistenceMode.EVENT, event_row=row))
        sql, params = c.statements[0]
        self.assertIn("%s", sql)
        for p in params:
            if isinstance(p, str) and p:
                self.assertNotIn(p, sql)

    def test_regression_g01_005_still_works(self):
        c=FakeConnection(); row={"tenant_id":5,"event_source":"DIRECTORY_AUDIT","source_object_id":"a1","event_at":"2026-01-01T00:00:00Z","collected_at":"2026-01-01T00:01:00Z","collection_run_id":1,"endpoint_run_id":1,"actor_user_id":None,"actor_app_id":None,"activity":None,"category":None,"result":None,"is_interactive":None,"risk_level":None,"extension":None,"retention_class":"LONG"}
        write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-005", PersistenceMode.EVENT, event_row=row))
        self.assertIn("core.audit_event", c.statements[0][0])

    def test_g01_005_duplicate_replay_uses_closed_conflict_and_do_nothing(self):
        c=FakeConnection(); row={"tenant_id":5,"event_source":"DIRECTORY_AUDIT","source_object_id":"a1","event_at":"2026-01-01T00:00:00Z","collected_at":"2026-01-01T00:01:00Z","collection_run_id":1,"endpoint_run_id":1,"actor_user_id":None,"actor_app_id":None,"activity":None,"category":None,"result":None,"is_interactive":None,"risk_level":None,"extension":None,"retention_class":"LONG"}
        record = NormalizedWorkloadRecord("G01-005", PersistenceMode.EVENT, event_row=row)
        write_event_record(BoundSqlExecutor(c), record)
        write_event_record(BoundSqlExecutor(c), record)
        sql, params = c.statements[0]
        self.assertIn("ON CONFLICT (tenant_id, event_source, source_object_id) DO NOTHING", sql)
        self.assertEqual(c.statements[0], c.statements[1])

    def test_g01_006_duplicate_replay_uses_sign_in_conflict_and_do_nothing(self):
        c=FakeConnection(); row={"tenant_id":5,"event_source":"SIGN_IN","source_object_id":"s1","event_at":"2026-01-01T00:00:00Z","collected_at":"2026-01-01T00:01:00Z","collection_run_id":1,"endpoint_run_id":1,"actor_user_id":"u1","actor_app_id":"a1","activity":"Browser","category":"0","result":"ok","is_interactive":True,"risk_level":None,"extension":None,"retention_class":"LONG"}
        record = NormalizedWorkloadRecord("G01-006", PersistenceMode.EVENT, event_row=row)
        write_event_record(BoundSqlExecutor(c), record)
        write_event_record(BoundSqlExecutor(c), record)
        self.assertIn("INSERT INTO core.audit_event", c.statements[0][0])
        self.assertIn("ON CONFLICT (tenant_id, event_source, source_object_id) DO NOTHING", c.statements[0][0])
        self.assertEqual(c.statements[0], c.statements[1])

    def test_g01_006_rejects_spoofed_event_source_without_sql(self):
        c=FakeConnection()
        row={"tenant_id":5,"event_source":"DIRECTORY_AUDIT","source_object_id":"s1"}
        with self.assertRaisesRegex(PersistenceError, "EVENT source does not match endpoint G01-006"):
            write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-006", PersistenceMode.EVENT, event_row=row))
        self.assertEqual(c.statements, [])

    def test_g01_005_tenant_mismatch_is_rejected_before_sql(self):
        c=FakeConnection(); row={"tenant_id":0,"event_source":"DIRECTORY_AUDIT","source_object_id":"a1"}
        with self.assertRaisesRegex(PersistenceError, "tenant_id"):
            write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-005", PersistenceMode.EVENT, event_row=row))
        self.assertEqual(c.statements, [])
    def test_regression_g01_014_still_works(self):
        c=FakeConnection(); row={"tenant_id":5,"source_object_id":"r1","detected_at":"2026-01-01T00:00:00Z","activity_at":None,"collected_at":"2026-01-01T00:01:00Z","collection_run_id":1,"endpoint_run_id":1,"risk_event_type":None,"risk_level":None,"risk_state":None,"risk_detail":None,"detection_timing_type":None,"activity":None,"affected_user_id":None,"retention_class":"LONG"}
        write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-014", PersistenceMode.EVENT, event_row=row))
        self.assertIn("core.risk_detection", c.statements[0][0])

if __name__ == "__main__": unittest.main()
