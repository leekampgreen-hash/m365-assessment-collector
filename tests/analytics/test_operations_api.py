import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from api.operations import OperationsApiHandler
from capabilities import Capability, CapabilityResolver


class FakeService:
    def cross_workload_user_status(self):
        return [{"display_name": "Test User", "user_principal_name": "test@example.test", "user_ref": "user-test", "licensed": "NO", "assigned_sku_count": 0, "assigned_skus": [], "exchange_status": "UNKNOWN", "exchange_last_activity": None, "onedrive_status": "UNKNOWN", "onedrive_last_activity": None, "sharepoint_status": "UNKNOWN", "sharepoint_last_activity": None}]

    def standard_kpi_summary(self):
        return {"tenant": {"total_users": {"value": 2}}, "license": {}, "exchange": {}, "onedrive": {}, "sharepoint": {}, "cross_workload": {"active_all_3": 0}}

    def tenant_summary(self):
        return {"total_users": {"value": 2, "status": "READY"}}

    def exchange_adoption(self):
        return {"active_users": {"value": 1, "status": "READY"}}

    def onedrive_adoption(self):
        return {
            "active_users": {"value": 1, "status": "READY"},
            "active_accounts": {"value": 1, "status": "READY"},
            "latest_activity": {"value": "2026-08-26", "status": "READY"},
            "total_storage_used": {"value": 100, "status": "READY"},
            "total_file_count": {"value": 4, "status": "READY"},
            "storage_utilization": {"value": 0.25, "status": "READY"},
            "account_details": [{"display_name": "Test User", "user_principal_name": "test@example.test", "user_ref": "user-test", "storage_used": 100, "storage_allocated": 400, "file_count": 4, "report_refresh_date": "2026-08-26"}],
        }

    def sharepoint_user_adoption(self):
        return {"active_users": {"value": 1, "status": "READY"}}

    def orphaned_sites(self):
        return [{"tenant_id": 2, "site_id": "site-old", "last_activity_date": None}]

    def external_sharing_summary(self):
        return [{"tenant_id": 2, "external_share_count": 3, "sites_with_external_shares": 1}]

    def sharepoint_site_adoption(self):
        return {
            "active_sites": {"value": 2, "status": "READY"},
            "latest_activity": {"value": "2026-08-26", "status": "READY"},
            "total_storage_used": {"value": 100, "status": "READY"},
            "total_file_count": {"value": 4, "status": "READY"},
            "storage_utilization": {"value": 0.25, "status": "READY"},
        }

    def license_utilization(self):
        return {"utilization_percentage": {"value": 50, "status": "READY"}}

    def teams_activity_summary(self):
        return [{"tenant_id": 2, "total_users": 1, "inactive_30_days": 1, "inactive_60_days": 1, "inactive_90_days": 1, "users": [{"user_ref": "user-test", "last_activity_date": None}]}]

    def inactivity_candidates(self):
        return [
            {"user_ref": "user-secret", "inactivity_30_60_90": {"30": "inactive", "60": "active", "90": "active"}, "multi_workload_inactive": False},
            {"user_ref": "user-other", "inactivity_30_60_90": {"30": "inactive", "60": "inactive", "90": "inactive"}, "multi_workload_inactive": True},
        ]

    def identity_join_quality(self):
        return {"exchange_email_activity": {"matched": 2, "unmatched_directory": 0, "unmatched_workload": 0}}

    def build(self):
        return {"data_quality": {"source_freshness_exposed": True, "missing_workload_data": [], "missing_entitlement_data": False, "partial_tenant_coverage": False, "identity_joins": self.identity_join_quality()}, "limitations": {"sharepoint_site_analytics_status": "IDENTITY_UNAVAILABLE", "sharepoint_site_stale_conclusion": None, "site_rows_used_for_conclusions": False}}


class FakeHealthCursor:
    def execute(self, query):
        self.query = query

    def fetchone(self):
        return (1,)


class FakeHealthConnection:
    def cursor(self):
        return FakeHealthCursor()

    def close(self):
        pass


class OperationsApiTests(unittest.TestCase):
    def setUp(self):
        handler = type("TestHandler", (OperationsApiHandler,), {"service_factory": staticmethod(FakeService)})
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

    def test_teams_activity_summary_endpoint(self):
        status, payload = self.get("/api/operations/teams/activity-summary")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["tenants"][0]["inactive_90_days"], 1)

    def test_kpi_endpoint_serializes_read_model(self):
        status, payload = self.get("/api/operations/kpi")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["tenant"]["total_users"]["value"], 2)

    def test_correlation_endpoint_serializes_read_model(self):
        status, payload = self.get("/api/operations/correlation/users")
        self.assertEqual(status, 200)
        user = payload["data"]["users"][0]
        self.assertEqual(user["licensed"], "NO")
        self.assertEqual(user["exchange_status"], "UNKNOWN")
        # The read-only endpoint exposes human-readable identity per row.
        self.assertEqual(user["display_name"], "Test User")
        self.assertEqual(user["user_principal_name"], "test@example.test")
        self.assertEqual(user["user_ref"], "user-test")

    def test_summary_and_product_endpoints(self):
        for path in ("/summary", "/adoption/exchange", "/adoption/onedrive", "/adoption/sharepoint", "/license-utilization", "/data-quality"):
            status, payload = self.get("/api/operations" + path)
            self.assertEqual(status, 200)
            self.assertIn("status", payload)
        status, payload = self.get("/api/operations/data-quality")
        self.assertEqual(status, 200)
        self.assertEqual(payload["limitations"]["sharepoint_site_analytics_status"], "IDENTITY_UNAVAILABLE")

    def test_external_sharing_api_exposes_tenant_summary(self):
        status, payload = self.get("/api/operations/sharepoint/external-sharing")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["tenants"], [{"tenant_id": 2, "external_share_count": 3, "sites_with_external_shares": 1}])

    def test_orphaned_sites_api_exposes_inactive_sites(self):
        status, payload = self.get("/api/operations/sharepoint/orphaned-sites")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["sites"][0]["site_id"], "site-old")

    def test_sharepoint_site_api_exposes_basic_kpis(self):
        status, payload = self.get("/api/operations/adoption/sharepoint/sites")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["active_sites"]["value"], 2)
        self.assertEqual(payload["data"]["storage_utilization"]["value"], 0.25)

    def test_onedrive_api_exposes_basic_kpis(self):
        status, payload = self.get("/api/operations/adoption/onedrive")
        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertEqual(data["active_accounts"]["value"], 1)
        self.assertEqual(data["latest_activity"]["value"], "2026-08-26")
        self.assertEqual(data["total_storage_used"]["value"], 100)
        self.assertEqual(data["total_file_count"]["value"], 4)
        self.assertEqual(data["storage_utilization"]["value"], 0.25)

    def test_onedrive_high_value_audit_endpoint(self):
        class AuditService(FakeService):
            def onedrive_high_value_audit(self, limit):
                return {"status": "READY", "summary": {"total_high_value_events": 3, "external_sharing_events": 2, "anonymous_sharing_events": 1, "malware_detected_events": 1, "latest_event_time": "2026-08-26T00:00:00+00:00"}, "recent_events": [], "limit": min(limit, 100)}
        handler = type("AuditHandler", (OperationsApiHandler,), {"service_factory": staticmethod(AuditService)})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/api/operations/onedrive/high-value-audit?limit=200")
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        thread.join()
        server.server_close()
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["data"]["summary"]["malware_detected_events"], 1)
        self.assertEqual(payload["data"]["limit"], 100)

    def test_sharepoint_audit_summary_endpoint(self):
        class AuditService(FakeService):
            def sharepoint_audit_summary(self, limit):
                return {"status": "READY", "summary": {"total_events": 4, "operations": {"SharingInvitationCreated": 2, "AnonymousLinkCreated": 1, "SharingRevoked": 1}, "latest_event_time": "2026-08-29T10:03:00Z"}, "tenants": [{"tenant_id": 2, "total_events": 4, "operations": {"SharingInvitationCreated": 2, "AnonymousLinkCreated": 1, "SharingRevoked": 1}}], "recent_events": [], "limit": min(limit, 100)}
        handler = type("SharepointAuditHandler", (OperationsApiHandler,), {"service_factory": staticmethod(AuditService)})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/api/operations/sharepoint/audit-summary?limit=200")
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        thread.join()
        server.server_close()
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["data"]["summary"]["total_events"], 4)
        self.assertEqual(payload["data"]["tenants"][0]["tenant_id"], 2)
        self.assertEqual(payload["data"]["limit"], 100)

    def test_inactivity_windows_and_invalid_window(self):
        for days in (30, 60, 90):
            status, payload = self.get("/api/operations/inactivity?days={}".format(days))
            self.assertEqual(status, 200)
            self.assertEqual(payload["data"]["window_days"], days)
        status, payload = self.get("/api/operations/inactivity?days=45")
        self.assertEqual(status, 400)
        self.assertEqual(payload["status"], "INVALID_INACTIVITY_WINDOW")

    def test_no_individual_identity_is_returned(self):
        status, payload = self.get("/api/operations/inactivity")
        self.assertEqual(status, 200)
        self.assertNotIn("user_ref", json.dumps(payload))
        self.assertNotIn("user-secret", json.dumps(payload))

    def test_database_failure_is_sanitized(self):
        handler = type("FailingHandler", (OperationsApiHandler,), {"connection_factory": staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("password=DO_NOT_LEAK")))})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/api/operations/summary")
        response = connection.getresponse()
        body = response.read().decode()
        thread.join()
        server.server_close()
        self.assertEqual(response.status, 503)
        self.assertEqual(json.loads(body)["status"], "DATA_DEPENDENCY_UNAVAILABLE")
        self.assertNotIn("DO_NOT_LEAK", body)

    def test_capabilities_are_read_only_and_identity_free(self):
        class CapabilityService:
            def capabilities(self):
                return [item.to_dict() for item in CapabilityResolver([{
                    "service_plans": [{"servicePlanName": "AAD_PREMIUM", "provisioningStatus": "Success"}],
                }]).all()]
        handler = type("CapabilityHandler", (OperationsApiHandler,), {"capability_service_factory": staticmethod(CapabilityService)})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/api/capabilities")
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        thread.join()
        server.server_close()
        self.assertEqual(response.status, 200)
        self.assertIn("capabilities", payload["data"])
        self.assertNotIn("user", json.dumps(payload).lower())

    def test_health_checks_database_without_exposing_details(self):
        handler = type("HealthHandler", (OperationsApiHandler,), {"connection_factory": staticmethod(FakeHealthConnection)})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/health")
        response = connection.getresponse()
        body = response.read().decode()
        thread.join()
        server.server_close()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(body), {"status": "READY", "database": "READY"})


if __name__ == "__main__":
    unittest.main()
