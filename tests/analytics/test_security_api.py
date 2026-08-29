import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from api.operations import OperationsApiHandler
from api.security import SecurityFindingQueryService


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, parameters=()):
        self.connection.queries.append((query, parameters))
        if "count(*) FILTER" in query and "severity" not in query:
            self.rows = [(1, 1, 0, 0, "2026-08-27T12:00:00+00:00")]
        elif "GROUP BY severity" in query:
            self.rows = [("MEDIUM", 1)]
        elif "EXISTS" in query:
            self.rows = [(True,)]
        elif "DISTINCT baseline_id" in query:
            self.rows = [("M365-BASELINE", "1.0")]
        elif "FROM security.finding_current c" in query and "JOIN security.observation" in query:
            self.rows = [] if parameters[-1] == "missing" or parameters[-1] == "f-1/delete" else [("f-1", "M365-SP-EXT-001", "External Sharing", "External Sharing", "OPEN", "MEDIUM", "M365-BASELINE", "1.0", "existing_guests", "anyone", "Risk", "Recommendation", "Validate", "AVAILABLE", "2026-08-27T12:00:00+00:00", "sharepoint_tenant_settings", "/admin/sharepoint/tenantSettings", "sharing_level", "anyone", "2026-08-27T11:00:00+00:00", 12, 34)]
        elif "FROM security.finding_current c" in query:
            self.rows = [("f-1", "M365-SP-EXT-001", "External Sharing", "External Sharing", "OPEN", "MEDIUM", "M365-BASELINE", "1.0", "existing_guests", "anyone", "Risk", "Recommendation", "Validate", "AVAILABLE", "2026-08-27T12:00:00+00:00")]
        else:
            self.rows = []

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class Connection:
    def __init__(self):
        self.queries = []
        self.closed = False

    def cursor(self):
        return Cursor(self)

    def close(self):
        self.closed = True


class SecurityApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = Connection()
        handler = type("TestHandler", (OperationsApiHandler,), {
            "tenant_id": 2,
            "connection_factory": staticmethod(lambda: self.connection),
        })
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", path)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    def test_summary(self):
        status, payload = self.get("/api/security/summary")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status_counts"]["OPEN"], 1)
        self.assertEqual(payload["data"]["open_severity_distribution"], {"MEDIUM": 1})

    def test_list_filters_and_invalid_filter(self):
        for query in ("?status=OPEN", "?severity=MEDIUM"):
            status, payload = self.get("/api/security/findings" + query)
            self.assertEqual(status, 200)
            self.assertEqual(payload["data"]["findings"][0]["rule_id"], "M365-SP-EXT-001")
        status, payload = self.get("/api/security/findings?status=INVALID")
        self.assertEqual(status, 400)
        self.assertEqual(payload["status"], "INVALID_STATUS_FILTER")

    def test_detail_and_unknown(self):
        status, payload = self.get("/api/security/findings/f-1")
        self.assertEqual(status, 200)
        finding = payload["data"]
        self.assertEqual(finding["baseline_expectation"], "existing_guests")
        self.assertEqual(finding["evidence"]["normalized_value"], "anyone")
        self.assertNotIn("user", json.dumps(payload).lower())
        self.assertNotIn("authorization", json.dumps(payload).lower())
        status, _ = self.get("/api/security/findings/missing")
        self.assertEqual(status, 404)

    def test_data_quality_and_read_only_routes(self):
        status, payload = self.get("/api/security/data-quality")
        self.assertEqual(status, 200)
        self.assertTrue(payload["data"]["persisted_observation_available"])
        for method in ("/api/security/remediate", "/api/security/findings/f-1/delete"):
            status, _ = self.get(method)
            self.assertEqual(status, 404)
        self.assertFalse(any(query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "ALTER", "DROP")) for query, _ in self.connection.queries))

    def test_service_has_no_graph_dependency(self):
        self.assertEqual(SecurityFindingQueryService.__module__, "api.security")
        with open(SecurityFindingQueryService.__module__.replace(".", "/") + ".py", encoding="utf-8") as source_file:
            source = source_file.read().lower()
        self.assertNotIn("requests", source)
        self.assertNotIn("httpx", source)
        self.assertNotIn("psycopg.connect", source)

    def test_database_failure_is_sanitized(self):
        handler = type("FailingHandler", (OperationsApiHandler,), {
            "tenant_id": 2,
            "connection_factory": staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("password=DO_NOT_LEAK"))),
        })
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/api/security/summary")
        response = connection.getresponse()
        body = response.read().decode()
        thread.join()
        server.server_close()
        self.assertEqual(response.status, 503)
        self.assertEqual(json.loads(body)["status"], "DATA_DEPENDENCY_UNAVAILABLE")
        self.assertNotIn("DO_NOT_LEAK", body)


if __name__ == "__main__":
    unittest.main()
