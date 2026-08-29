"""Bounded fake Graph Exchange report through production runtime and writer."""
from __future__ import annotations

import csv
import io
import os
import unittest
from pathlib import Path

from collectors.core import CollectorRuntime, RuntimeOptions, dict_source


class _Response:
    status = 200
    headers = {"Content-Type": "text/csv"}

    def __init__(self, content, status=200, headers=None):
        self.content = content
        self.status = status
        self.headers = headers or {"Content-Type": "text/csv"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.content


class _RollbackOnlyConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return self._connection.cursor()

    def commit(self):
        pass

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


class ExchangeProductionPathIntegrationTests(unittest.TestCase):
    def _runtime(self, content, tenant_id=9001, statuses=None, retry_policy=None, incomplete=False):
        statuses = list(statuses or [])
        calls = []
        class Writer:
            def __init__(self):
                self.rows = []
            def write_usage_report(self, key, rows, *, tenant_id, complete=True):
                if incomplete or not complete:
                    raise ValueError("incomplete")
                from collectors.usage_reports.persistence import write_report_rows
                write_report_rows(self, key, rows, complete=complete)
            def execute(self, sql, values):
                self.rows.append((sql, values))
        writer = Writer()
        def begin_collection_run(**kwargs): return 1
        def begin_endpoint_run(**kwargs): return 1
        def complete_endpoint_run(**kwargs): pass
        def complete_collection_run(**kwargs): pass
        Writer.begin_collection_run = staticmethod(begin_collection_run)
        Writer.begin_endpoint_run = staticmethod(begin_endpoint_run)
        Writer.complete_endpoint_run = staticmethod(complete_endpoint_run)
        Writer.complete_collection_run = staticmethod(complete_collection_run)
        def opener(request, timeout=None):
            calls.append(request.full_url)
            if request.full_url.endswith("/token"):
                return _Response(b'{"access_token":"token","expires_in":3600}')
            if statuses:
                status, headers = statuses.pop(0)
                if status != 200:
                    return _Response(b"", status=status, headers=headers)
            return _Response(content.encode() if isinstance(content, str) else content)
        runtime = CollectorRuntime(
            Path("config/api_inventory.json"),
            dict_source({"GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret"}),
            options=RuntimeOptions(http_open=opener, tenant_resolver=lambda config: tenant_id,
                                   collection_writer=writer, retry_policy=retry_policy),
        )
        return runtime, writer, calls

    def _csv(self, rows, header=("User Principal Name", "Storage Used (Byte)", "Prohibit Send/Receive Quota (Byte)", "Report Refresh Date")):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(header)
        writer.writerows(rows)
        return output.getvalue()

    def test_negative_matrix_uses_production_runtime_path(self):
        from collectors.core import RetryPolicy
        valid = self._csv([("a@example.invalid", "10", "100", "2026-08-29")])
        cases = {
            "incomplete": self._csv([]),
            "duplicate": self._csv([("A@EXAMPLE.INVALID", "10", "100", "2026-08-29"), ("a@example.invalid", "20", "100", "2026-08-29")]),
            "missing_identity": self._csv([("", "10", "100", "2026-08-29")]),
            "missing_refresh": self._csv([("a@example.invalid", "10", "100", "")]),
            "malformed_refresh": self._csv([("a@example.invalid", "10", "100", "not-a-date")]),
        }
        for name, content in cases.items():
            runtime, writer, _ = self._runtime(content, incomplete=name == "incomplete")
            result = runtime.run(endpoint_id="USAGE-003").runs[0]
            self.assertEqual(result.status, "ERROR", name)
            self.assertEqual(writer.rows, [], name)
        runtime, writer, _ = self._runtime(valid)
        first = runtime.run(endpoint_id="USAGE-003").runs[0]
        second = runtime.run(endpoint_id="USAGE-003").runs[0]
        self.assertEqual((first.status, second.status), ("PASS", "PASS"))
        self.assertEqual(len(writer.rows), 6)
        self.assertIn("DO NOTHING", writer.rows[2][0])
        stale = self._csv([("a@example.invalid", "99", "100", "2026-08-28")])
        runtime, writer, _ = self._runtime(stale)
        result = runtime.run(endpoint_id="USAGE-003").runs[0]
        self.assertEqual(result.status, "PASS")
        self.assertEqual(len(writer.rows), 3)
        retry_policy = RetryPolicy(max_retries=1, base_delay_seconds=0, sleep=lambda _: None)
        runtime, writer, calls = self._runtime(valid, statuses=[(429, {"Retry-After": "0"}), (200, {})], retry_policy=retry_policy)
        result = runtime.run(endpoint_id="USAGE-003").runs[0]
        self.assertEqual((result.status, result.retry_count), ("PASS", 1))
        self.assertEqual(len(calls), 3)
        runtime, writer, _ = self._runtime(valid, statuses=[(429, {"Retry-After": "0"}), (429, {"Retry-After": "0"})], retry_policy=retry_policy)
        result = runtime.run(endpoint_id="USAGE-003").runs[0]
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.error_classification, "THROTTLED/RETRY_EXHAUSTED")
        self.assertEqual(writer.rows, [])

    def test_tenant_isolation_same_identity_is_scoped(self):
        content = self._csv([("same@example.invalid", "10", "100", "2026-08-29")])
        runtime_a, writer_a, _ = self._runtime(content, tenant_id=9001)
        runtime_b, writer_b, _ = self._runtime(content, tenant_id=9002)
        self.assertEqual(runtime_a.run(endpoint_id="USAGE-003").runs[0].status, "PASS")
        self.assertEqual(runtime_b.run(endpoint_id="USAGE-003").runs[0].status, "PASS")
        values_a = [values for _, values in writer_a.rows]
        values_b = [values for _, values in writer_b.rows]
        self.assertTrue(all(9001 in values for values in values_a))
        self.assertTrue(all(9002 in values for values in values_b))
        self.assertFalse(set(values_a) & set(values_b))

    def test_fake_graph_reaches_current_snapshot_and_capacity_view(self):
        try:
            import psycopg
        except ImportError:
            self.skipTest("PostgreSQL driver is unavailable")
        password_file = Path("/run/secrets/graph_agent_runtime_password")
        if not password_file.exists():
            self.skipTest("production database credentials are unavailable")
        connection = psycopg.connect(
            host=os.environ.get("PGHOST", "postgres"),
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "graph_agent"),
            user=os.environ.get("PGUSER", "graph_agent_runtime"),
            password=password_file.read_text(encoding="utf-8").strip(),
        )
        try:
            cur = connection.cursor()
            cur.execute("SELECT tenant_id FROM core.tenant ORDER BY tenant_id LIMIT 1")
            tenant_id = cur.fetchone()[0]
            rows = [
                ("low@example.invalid", "10", "100", "2026-08-29"),
                ("medium@example.invalid", "50", "100", "2026-08-29"),
                ("high@example.invalid", "80", "100", "2026-08-29"),
                ("nodata@example.invalid", "bad", "0", "2026-08-29"),
            ]
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["User Principal Name", "Storage Used (Byte)", "Prohibit Send/Receive Quota (Byte)", "Report Refresh Date"])
            writer.writerows(rows)
            calls = []

            def opener(request, timeout=None):
                calls.append(request.full_url)
                if request.full_url.endswith("/token"):
                    return _Response(b'{"access_token":"token","expires_in":3600}')
                return _Response(output.getvalue().encode())

            runtime = CollectorRuntime(
                Path("config/api_inventory.json"),
                dict_source({"GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret"}),
                options=RuntimeOptions(http_open=opener, tenant_resolver=lambda config: tenant_id),
                database_connection=_RollbackOnlyConnection(connection),
            )
            summary = runtime.run(endpoint_id="USAGE-003")
            result = summary.runs[0]
            self.assertEqual(result.status, "PASS")
            self.assertEqual(result.source_rows, 4)
            self.assertEqual(result.persisted_rows, 4)
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0].endswith("/token"))
            cur.execute("SELECT count(*) FROM core.usage_exchange_mailbox_usage WHERE tenant_id = %s AND report_refresh_date = '2026-08-29'", (tenant_id,))
            self.assertEqual(cur.fetchone()[0], 4)
            cur.execute("SELECT usage_level, count(*) FROM analytics.exchange_mailbox_capacity WHERE tenant_id = %s GROUP BY usage_level", (tenant_id,))
            self.assertEqual(dict(cur.fetchall()), {"LOW": 1, "MEDIUM": 1, "HIGH": 1, "NO_DATA": 1})
        finally:
            connection.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
