"""Focused offline tests for G01-016 / G01-017 HISTORY persistence with physical idempotency."""
import unittest
from copy import deepcopy
from collectors.persistence import BoundSqlExecutor, PersistenceError, write_current_record, write_event_record, write_history_record, write_reference_record
from collectors.workloads.models import NormalizedWorkloadRecord, PersistenceMode
from collectors.workloads import normalize_record, LineageContext, REGISTRY, PersistenceMode as PM


class FakeCursor:
    def __init__(self, c):
        self.c = c

    def execute(self, s, p):
        self.c.statements.append((s, p))


class FakeConnection:
    def __init__(self):
        self.statements = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass


def _g01_016_record():
    lc = LineageContext(tenant_id=42, collection_run_id=1001, endpoint_run_id=9001, observed_at="2026-08-20T12:00:00Z", retention_class="STANDARD")
    return normalize_record("G01-016", {"id": "issue-1", "service": "Exchange", "status": "investigating", "classification": "advisory", "startDateTime": "2026-08-19T00:00:00Z", "endDateTime": None, "lastModifiedDateTime": "2026-08-20T01:00:00Z", "isResolved": False}, lc)


def _g01_017_record():
    lc = LineageContext(tenant_id=42, collection_run_id=1001, endpoint_run_id=9001, observed_at="2026-08-20T12:00:00Z", retention_class="STANDARD")
    return normalize_record("G01-017", {"id": "message-1", "category": "PlanForChange", "severity": "Normal", "startDateTime": "2026-08-19T00:00:00Z", "endDateTime": "2026-08-25T00:00:00Z", "lastModifiedDateTime": "2026-08-20T01:00:00Z", "isMajorChange": False, "actionRequiredByDateTime": None, "services": ["Exchange"]}, lc)


class G01_016_HistoryTests(unittest.TestCase):
    def test_sql_mapping_current_and_history(self):
        c = FakeConnection()
        write_history_record(BoundSqlExecutor(c), _g01_016_record())
        self.assertEqual(len(c.statements), 2)
        sql_cur, _ = c.statements[0]
        sql_hist, _ = c.statements[1]
        self.assertIn("INSERT INTO core.service_health_issue ", sql_cur)
        self.assertNotIn("core.service_health_issue_history", sql_cur)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET", sql_cur)
        self.assertIn("INSERT INTO core.service_health_issue_history", sql_hist)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id, version_identity) DO NOTHING", sql_hist)
        self.assertIn("%s", sql_cur)
        self.assertIn("%s", sql_hist)
        self.assertNotIn("issue-1", sql_cur)
        self.assertNotIn("issue-1", sql_hist)

    def test_parameters(self):
        c = FakeConnection()
        rec = _g01_016_record()
        write_history_record(BoundSqlExecutor(c), rec)
        _, p_cur = c.statements[0]
        _, p_hist = c.statements[1]
        self.assertEqual(p_cur, (42, "issue-1", "Exchange", "investigating", "advisory", "2026-08-19T00:00:00Z", None, "2026-08-20T01:00:00Z", False, "2026-08-20T12:00:00Z", "STANDARD"))
        self.assertEqual(p_hist[0], 42)
        self.assertEqual(p_hist[1], "issue-1")
        self.assertIsInstance(p_hist[2], (bytes, bytearray))
        self.assertEqual(len(p_hist[2]), 32)
        self.assertEqual(p_hist[3:11], ("Exchange", "investigating", "advisory", "2026-08-19T00:00:00Z", None, "2026-08-20T01:00:00Z", False, "2026-08-20T12:00:00Z"))
        self.assertEqual(p_hist[11], "2026-08-20T12:00:00Z")
        self.assertEqual(p_hist[12], 1001)
        self.assertEqual(p_hist[13], 9001)
        self.assertEqual(p_hist[14], "STANDARD")

    def test_conflict_targets(self):
        c = FakeConnection()
        write_history_record(BoundSqlExecutor(c), _g01_016_record())
        self.assertIn("(tenant_id, source_object_id)", c.statements[0][0])
        self.assertIn("(tenant_id, source_object_id, version_identity)", c.statements[1][0])

    def test_physical_idempotency_unchanged_replay_has_distinct_guard(self):
        c = FakeConnection()
        rec = _g01_016_record()
        write_history_record(BoundSqlExecutor(c), rec)
        sql_cur = c.statements[0][0]
        self.assertIn("IS DISTINCT FROM", sql_cur)
        self.assertIn("WHERE (", sql_cur)
        self.assertIn("core.service_health_issue.service", sql_cur)
        self.assertIn("EXCLUDED.service", sql_cur)

    def test_replay_deterministic_sql(self):
        c = FakeConnection()
        rec = _g01_016_record()
        write_history_record(BoundSqlExecutor(c), rec)
        first = list(c.statements)
        write_history_record(BoundSqlExecutor(c), rec)
        self.assertEqual(c.statements[0], c.statements[2])
        self.assertEqual(c.statements[1], c.statements[3])
        self.assertEqual(c.statements[0], first[0])
        self.assertEqual(c.statements[1], first[1])

    def test_changed_record_still_upserts_with_same_conflict_target(self):
        lc = LineageContext(tenant_id=42, collection_run_id=1001, endpoint_run_id=9001, observed_at="2026-08-20T12:00:00Z", retention_class="STANDARD")
        r1 = normalize_record("G01-016", {"id": "issue-1", "service": "Exchange", "status": "investigating", "lastModifiedDateTime": "2026-08-20T01:00:00Z"}, lc)
        r2 = normalize_record("G01-016", {"id": "issue-1", "service": "Exchange", "status": "resolved", "lastModifiedDateTime": "2026-08-21T01:00:00Z"}, lc)
        c1 = FakeConnection()
        c2 = FakeConnection()
        write_history_record(BoundSqlExecutor(c1), r1)
        write_history_record(BoundSqlExecutor(c2), r2)
        self.assertEqual(c1.statements[0][0], c2.statements[0][0])
        self.assertNotEqual(c1.statements[0][1], c2.statements[0][1])
        self.assertIn("IS DISTINCT FROM", c1.statements[0][0])
        self.assertIn("IS DISTINCT FROM", c2.statements[0][0])
        self.assertNotEqual(c1.statements[1][1][2], c2.statements[1][1][2])

    def test_source_mutation_none(self):
        c = FakeConnection()
        rec = _g01_016_record()
        orig_cur = deepcopy(rec.current_row)
        orig_hist = deepcopy(rec.history_row)
        write_history_record(BoundSqlExecutor(c), rec)
        self.assertEqual(rec.current_row, orig_cur)
        self.assertEqual(rec.history_row, orig_hist)

    def test_fail_closed_unsupported_endpoint(self):
        c = FakeConnection()
        with self.assertRaisesRegex(PersistenceError, "Unsupported CURRENT_WITH_HISTORY endpoint"):
            write_history_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-999", PersistenceMode.CURRENT_WITH_HISTORY, current_row={}, history_row={}))
        self.assertEqual(c.statements, [])

    def test_fail_closed_wrong_mode(self):
        c = FakeConnection()
        rec = _g01_016_record()
        wrong = NormalizedWorkloadRecord("G01-016", PersistenceMode.CURRENT, current_row=rec.current_row, history_row=rec.history_row)
        with self.assertRaisesRegex(PersistenceError, "Only CURRENT_WITH_HISTORY"):
            write_history_record(BoundSqlExecutor(c), wrong)
        self.assertEqual(c.statements, [])

    def test_missing_columns_fail_closed(self):
        c = FakeConnection()
        rec = _g01_016_record()
        bad = NormalizedWorkloadRecord("G01-016", PersistenceMode.CURRENT_WITH_HISTORY, current_row={"tenant_id": 1}, history_row=rec.history_row)
        with self.assertRaisesRegex(PersistenceError, "Current row is missing required columns"):
            write_history_record(BoundSqlExecutor(c), bad)
        self.assertEqual(c.statements, [])
        bad2 = NormalizedWorkloadRecord("G01-016", PersistenceMode.CURRENT_WITH_HISTORY, current_row=rec.current_row, history_row={"tenant_id": 1})
        with self.assertRaisesRegex(PersistenceError, "History row is missing required columns"):
            write_history_record(BoundSqlExecutor(c), bad2)
        self.assertEqual(c.statements, [])

    def test_requires_both_rows(self):
        c = FakeConnection()
        with self.assertRaisesRegex(PersistenceError, "requires current_row"):
            write_history_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-016", PersistenceMode.CURRENT_WITH_HISTORY, current_row=None, history_row={}))
        with self.assertRaisesRegex(PersistenceError, "requires history_row"):
            write_history_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-016", PersistenceMode.CURRENT_WITH_HISTORY, current_row={}, history_row=None))

    def test_parameterized_sql_no_interpolation(self):
        c = FakeConnection()
        rec = _g01_016_record()
        write_history_record(BoundSqlExecutor(c), rec)
        for sql, params in c.statements:
            for p in params:
                if isinstance(p, str) and p:
                    self.assertNotIn(p, sql)

    def test_deterministic_two_versions_produce_different_history_params(self):
        lc = LineageContext(tenant_id=42, collection_run_id=1001, endpoint_run_id=9001, observed_at="2026-08-20T12:00:00Z", retention_class="STANDARD")
        r1 = normalize_record("G01-016", {"id": "issue-1", "service": "Exchange", "status": "investigating", "lastModifiedDateTime": "2026-08-20T01:00:00Z"}, lc)
        r2 = normalize_record("G01-016", {"id": "issue-1", "service": "Exchange", "status": "investigating", "lastModifiedDateTime": "2026-08-21T01:00:00Z"}, lc)
        c1 = FakeConnection()
        c2 = FakeConnection()
        write_history_record(BoundSqlExecutor(c1), r1)
        write_history_record(BoundSqlExecutor(c2), r2)
        self.assertNotEqual(c1.statements[1][1][2], c2.statements[1][1][2])
        self.assertEqual(c1.statements[0][1][:2], c2.statements[0][1][:2])

    def test_registry_alignment_g01_016(self):
        entry = REGISTRY["G01-016"]
        self.assertEqual(entry.persistence_mode, PM.CURRENT_WITH_HISTORY)
        self.assertEqual(entry.current_table, "core.service_health_issue")
        self.assertEqual(entry.history_table, "core.service_health_issue_history")


class G01_017_HistoryTests(unittest.TestCase):
    def test_sql_mapping_current_and_history(self):
        c = FakeConnection()
        write_history_record(BoundSqlExecutor(c), _g01_017_record())
        self.assertEqual(len(c.statements), 2)
        sql_cur, _ = c.statements[0]
        sql_hist, _ = c.statements[1]
        self.assertIn("INSERT INTO core.service_update_message ", sql_cur)
        self.assertNotIn("core.service_update_message_history", sql_cur)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET", sql_cur)
        self.assertIn("INSERT INTO core.service_update_message_history", sql_hist)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id, version_identity) DO NOTHING", sql_hist)
        self.assertIn("%s", sql_cur)
        self.assertIn("%s", sql_hist)
        self.assertNotIn("message-1", sql_cur)

    def test_parameters(self):
        c = FakeConnection()
        rec = _g01_017_record()
        write_history_record(BoundSqlExecutor(c), rec)
        _, p_cur = c.statements[0]
        _, p_hist = c.statements[1]
        self.assertEqual(p_cur, (42, "message-1", "PlanForChange", "Normal", "2026-08-19T00:00:00Z", "2026-08-25T00:00:00Z", "2026-08-20T01:00:00Z", False, None, ["Exchange"], "2026-08-20T12:00:00Z", "STANDARD"))
        self.assertEqual(p_hist[0], 42)
        self.assertEqual(p_hist[1], "message-1")
        self.assertIsInstance(p_hist[2], (bytes, bytearray))
        self.assertEqual(len(p_hist[2]), 32)
        self.assertEqual(p_hist[10], ["Exchange"])
        self.assertEqual(p_hist[11], "2026-08-20T12:00:00Z")
        self.assertEqual(p_hist[12], "2026-08-20T12:00:00Z")
        self.assertEqual(p_hist[13], 1001)
        self.assertEqual(p_hist[15], "STANDARD")

    def test_conflict_targets(self):
        c = FakeConnection()
        write_history_record(BoundSqlExecutor(c), _g01_017_record())
        self.assertIn("(tenant_id, source_object_id)", c.statements[0][0])
        self.assertIn("(tenant_id, source_object_id, version_identity)", c.statements[1][0])

    def test_physical_idempotency_guard_present(self):
        c = FakeConnection()
        write_history_record(BoundSqlExecutor(c), _g01_017_record())
        sql_cur = c.statements[0][0]
        self.assertIn("IS DISTINCT FROM", sql_cur)
        self.assertIn("WHERE (", sql_cur)
        self.assertIn("core.service_update_message.category", sql_cur)

    def test_changed_record_still_deterministic(self):
        lc = LineageContext(tenant_id=42, collection_run_id=1001, endpoint_run_id=9001, observed_at="2026-08-20T12:00:00Z", retention_class="STANDARD")
        r1 = normalize_record("G01-017", {"id": "m-1", "category": "PlanForChange", "severity": "Normal", "lastModifiedDateTime": "2026-08-20T01:00:00Z"}, lc)
        r2 = normalize_record("G01-017", {"id": "m-1", "category": "PlanForChange", "severity": "High", "lastModifiedDateTime": "2026-08-21T01:00:00Z"}, lc)
        c1 = FakeConnection()
        c2 = FakeConnection()
        write_history_record(BoundSqlExecutor(c1), r1)
        write_history_record(BoundSqlExecutor(c2), r2)
        self.assertEqual(c1.statements[0][0], c2.statements[0][0])
        self.assertNotEqual(c1.statements[0][1], c2.statements[0][1])

    def test_replay_deterministic_sql(self):
        c = FakeConnection()
        rec = _g01_017_record()
        write_history_record(BoundSqlExecutor(c), rec)
        write_history_record(BoundSqlExecutor(c), rec)
        self.assertEqual(c.statements[0], c.statements[2])
        self.assertEqual(c.statements[1], c.statements[3])

    def test_source_mutation_none(self):
        c = FakeConnection()
        rec = _g01_017_record()
        orig_cur = deepcopy(rec.current_row)
        orig_hist = deepcopy(rec.history_row)
        write_history_record(BoundSqlExecutor(c), rec)
        self.assertEqual(rec.current_row, orig_cur)
        self.assertEqual(rec.history_row, orig_hist)

    def test_fail_closed_unsupported(self):
        c = FakeConnection()
        with self.assertRaisesRegex(PersistenceError, "Unsupported CURRENT_WITH_HISTORY endpoint"):
            write_history_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-015", PersistenceMode.CURRENT_WITH_HISTORY, current_row={}, history_row={}))
        self.assertEqual(c.statements, [])

    def test_parameterized_sql(self):
        c = FakeConnection()
        rec = _g01_017_record()
        write_history_record(BoundSqlExecutor(c), rec)
        for sql, params in c.statements:
            for p in params:
                if isinstance(p, str) and p:
                    self.assertNotIn(p, sql)

    def test_fallback_version_identity_path(self):
        lc = LineageContext(tenant_id=42, collection_run_id=1001, endpoint_run_id=9001, observed_at="2026-08-20T12:00:00Z", retention_class="STANDARD")
        r1 = normalize_record("G01-017", {"id": "m-1", "category": "PlanForChange", "severity": "high", "isMajorChange": True, "startDateTime": "2026-08-19T00:00:00Z", "endDateTime": None, "actionRequiredByDateTime": "2026-09-01T00:00:00Z"}, lc)
        r2 = normalize_record("G01-017", {"id": "m-1", "category": "PlanForChange", "severity": "medium", "isMajorChange": True, "startDateTime": "2026-08-19T00:00:00Z", "endDateTime": None, "actionRequiredByDateTime": "2026-09-01T00:00:00Z"}, lc)
        c1 = FakeConnection()
        c2 = FakeConnection()
        write_history_record(BoundSqlExecutor(c1), r1)
        write_history_record(BoundSqlExecutor(c2), r2)
        self.assertNotEqual(c1.statements[1][1][2], c2.statements[1][1][2])

    def test_registry_alignment_g01_017(self):
        entry = REGISTRY["G01-017"]
        self.assertEqual(entry.persistence_mode, PM.CURRENT_WITH_HISTORY)
        self.assertEqual(entry.current_table, "core.service_update_message")
        self.assertEqual(entry.history_table, "core.service_update_message_history")


class RegressionExistingHandlersTests(unittest.TestCase):
    def test_current_still_works(self):
        c = FakeConnection()
        row = {"tenant_id": 7, "source_object_id": "user-1", "user_principal_name": "user@example.test", "display_name": "User", "user_type": "Member", "account_enabled": True, "created_date_time": "2026-01-01T00:00:00Z", "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "REFERENCE"}
        write_current_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-001", PersistenceMode.CURRENT, current_row=row))
        self.assertIn('core."user"', c.statements[0][0])
        self.assertIn("ON CONFLICT (tenant_id, source_object_id) DO UPDATE", c.statements[0][0])

    def test_event_still_works(self):
        c = FakeConnection()
        row = {"tenant_id": 5, "event_source": "DIRECTORY_AUDIT", "source_object_id": "a1", "event_at": "2026-01-01T00:00:00Z", "collected_at": "2026-01-01T00:01:00Z", "collection_run_id": 1, "endpoint_run_id": 1, "actor_user_id": None, "actor_app_id": None, "activity": None, "category": None, "result": None, "is_interactive": None, "risk_level": None, "extension": None, "retention_class": "LONG"}
        write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-005", PersistenceMode.EVENT, event_row=row))
        self.assertIn("core.audit_event", c.statements[0][0])
        self.assertIn("ON CONFLICT (tenant_id, event_source, source_object_id) DO NOTHING", c.statements[0][0])

    def test_reference_still_works(self):
        c = FakeConnection()
        row = {"tenant_id": 18, "source_object_id": "role-definition-1", "display_name": "Global Administrator", "description": "Full access", "is_built_in": True, "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "REFERENCE"}
        write_reference_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-018", PersistenceMode.REFERENCE, reference_row=row))
        self.assertIn("core.directory_role_definition", c.statements[0][0])

    def test_g01_015_not_an_event_endpoint(self):
        c = FakeConnection()
        row = {"tenant_id": 1, "source_object_id": "svc-1", "service": "Exchange", "status": "ServiceOperational", "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "STANDARD"}
        with self.assertRaisesRegex(PersistenceError, "Unsupported EVENT endpoint"):
            write_event_record(BoundSqlExecutor(c), NormalizedWorkloadRecord("G01-015", PersistenceMode.EVENT, event_row=row))
        self.assertEqual(c.statements, [])

    def test_g01_015_registry_is_snapshot_not_event(self):
        entry = REGISTRY["G01-015"]
        self.assertEqual(entry.persistence_mode, PM.CURRENT_WITH_SNAPSHOT)
        self.assertEqual(entry.current_table, "core.service_health_overview")
        self.assertEqual(entry.snapshot_table, "core.service_health_overview_snapshot")


if __name__ == "__main__":
    unittest.main()
