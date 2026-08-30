import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from collectors.core.runtime import CollectorRuntime, RuntimeOptions
from collectors.core.results import safe_dumps
from collectors.core.config import dict_source


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "config" / "api_inventory.json"


class Response:
    status = 200
    headers = {"Content-Type": "text/csv"}

    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.content


class UsageRuntimeTests(unittest.TestCase):
    def _runtime(self, opener, writer=None):
        return CollectorRuntime(
            INVENTORY,
            dict_source({
                "GRAPH_TENANT_ID": "tenant",
                "GRAPH_CLIENT_ID": "client",
                "GRAPH_CLIENT_SECRET": "secret",
            }),
            options=RuntimeOptions(
                http_open=opener,
                tenant_resolver=lambda config: 7,
                collection_writer=writer,
            ),
        )

    def test_inventory_has_exactly_seven_usage_reports_and_distinct_type(self):
        specs = CollectorRuntime(INVENTORY, {}).specs
        usage = [spec for spec in specs if spec.transport_type == "USAGE_REPORT_CSV"]
        self.assertEqual(len(usage), 8)
        self.assertEqual({spec.period for spec in usage}, {"D7"})
        self.assertEqual(len({spec.report_key for spec in usage}), 8)
        self.assertTrue(all(spec.path.endswith("(period='D7')") for spec in usage))
        self.assertTrue(all(spec.transport_type == "NORMAL_GRAPH_JSON" for spec in specs[:19]))

    def test_usage_routes_to_report_transport_and_reuses_token_provider(self):
        calls = []

        def opener(request, timeout=None):
            calls.append(request.full_url)
            if request.full_url.endswith("/token"):
                return type("TokenResponse", (), {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: False,
                    "read": lambda self: b'{"access_token":"token","expires_in":3600}',
                })()
            return Response(b"User Principal Name,Report Refresh Date\nuser@example.com,2026-08-20\n")

        writer = Mock()
        summary = self._runtime(opener, writer).run(endpoint_id="USAGE-001")
        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.runs[0].rows, 1)
        self.assertEqual(len(calls), 2)
        self.assertIn("period='D7'", calls[1])
        writer.write_usage_report.assert_called_once()
        self.assertNotIn("token", safe_dumps(summary.to_dict()))

    def test_usage_only_run_uses_named_adapter_without_graph_transport(self):
        def opener(request, timeout=None):
            if request.full_url.endswith("/token"):
                return type("TokenResponse", (), {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: False,
                    "read": lambda self: b'{"access_token":"token","expires_in":3600}',
                })()
            return Response(b"User Principal Name,Report Refresh Date\nuser@example.com,2026-08-20\n")

        with patch.object(CollectorRuntime, "build_transport", side_effect=AssertionError("normal transport built")):
            with patch("collectors.usage_reports.registry.get_adapter", wraps=__import__(
                    "collectors.usage_reports.registry", fromlist=["get_adapter"]).get_adapter) as adapter:
                summary = self._runtime(opener).run(endpoint_id="USAGE-001")
        self.assertEqual(summary.runs[0].status, "PASS")
        adapter.assert_called_once_with("office365_active_user")

    def test_mixed_execution_preserves_graph_path_and_isolates_report_failure(self):
        def opener(request, timeout=None):
            if request.full_url.endswith("/token"):
                return type("TokenResponse", (), {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: False,
                    "read": lambda self: b'{"access_token":"token","expires_in":3600}',
                })()
            if "/users" in request.full_url:
                return type("JsonResponse", (), {
                    "status": 200, "headers": {}, "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: False,
                    "read": lambda self, limit=-1: b'{"value":[{"id":"u1"}]}',
                })()
            return Response(b"bad header\nvalue\n")

        summary = self._runtime(opener).run(endpoint_ids=["G01-001", "USAGE-001"])
        self.assertEqual([run.status for run in summary.runs], ["PASS", "ERROR"])
        self.assertEqual(summary.runs[1].error_classification, "REPORT_SCHEMA_INVALID")

    def test_identity_unavailable_is_controlled_and_does_not_write(self):
        def opener(request, timeout=None):
            if request.full_url.endswith("/token"):
                return type("TokenResponse", (), {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: False,
                    "read": lambda self: b'{"access_token":"token","expires_in":3600}',
                })()
            return Response(b"Report Refresh Date,Owner Principal Name\n2026-08-20,\n")

        writer = Mock()
        summary = self._runtime(opener, writer).run(endpoint_id="USAGE-005")
        self.assertEqual(summary.runs[0].error_classification, "ENTITY_IDENTITY_UNAVAILABLE")
        self.assertTrue(summary.runs[0].identity_unavailable)
        writer.write_usage_report.assert_not_called()

    def test_sharepoint_identity_unavailable_completes_endpoint_and_partial_collection(self):
        def opener(request, timeout=None):
            if request.full_url.endswith("/token"):
                return type("TokenResponse", (), {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: False,
                    "read": lambda self: b'{"access_token":"token","expires_in":3600}',
                })()
            if "SharePointSiteUsageDetail" in request.full_url:
                return Response(b"Report Refresh Date,Site Id,Site URL\n2026-08-20,,\n")
            return Response(b"User Principal Name,Report Refresh Date\nuser@example.com,2026-08-20\n")

        class LifecycleWriter:
            def __init__(self):
                self.completed_endpoints = []
                self.completed_collections = []
                self.site_rows = []

            def begin_collection_run(self, **kwargs):
                return 501

            def begin_endpoint_run(self, **kwargs):
                return 900 + len(self.completed_endpoints)

            def write_usage_report(self, key, rows, **kwargs):
                if key == "sharepoint_site_usage":
                    self.site_rows.extend(rows)

            def complete_endpoint_run(self, **kwargs):
                self.completed_endpoints.append(kwargs["result"])

            def complete_collection_run(self, **kwargs):
                self.completed_collections.append(kwargs)

        writer = LifecycleWriter()
        summary = self._runtime(opener, writer).run(
            endpoint_ids=["USAGE-001", "USAGE-002", "USAGE-003", "USAGE-004", "USAGE-005", "USAGE-006", "USAGE-007"]
        )

        self.assertEqual(len(writer.completed_endpoints), 7)
        self.assertEqual(writer.completed_endpoints[-1].status, "ERROR")
        self.assertEqual(writer.completed_endpoints[-1].error_classification, "ENTITY_IDENTITY_UNAVAILABLE")
        self.assertEqual(len(writer.site_rows), 0)
        self.assertEqual(writer.completed_collections[0]["results"], summary.runs)
        self.assertEqual([run.status for run in summary.runs[:-1]], ["PASS"] * 6)
        self.assertEqual(summary.runs[-1].status, "ERROR")

    def test_all_seven_reports_execute_through_canonical_runtime(self):
        def opener(request, timeout=None):
            if request.full_url.endswith("/token"):
                return type("TokenResponse", (), {
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *args: False,
                    "read": lambda self: b'{"access_token":"token","expires_in":3600}',
                })()
            if "OneDriveUsageAccountDetail" in request.full_url:
                content = b"Report Refresh Date,Owner Principal Name\n2026-08-20,owner@example.com\n"
            elif "SharePointSiteUsageDetail" in request.full_url:
                content = b"Report Refresh Date,Site Id,Site URL\n2026-08-20,site-1,https://site.example\n"
            else:
                content = b"User Principal Name,Report Refresh Date\nuser@example.com,2026-08-20\n"
            return Response(content)

        writer = Mock()
        ids = ["USAGE-{:03d}".format(index) for index in range(1, 8)]
        summary = self._runtime(opener, writer).run(endpoint_ids=ids)
        self.assertEqual(len(summary.runs), 7)
        self.assertTrue(all(run.status == "PASS" for run in summary.runs))
        self.assertTrue(all(run.source_rows == 1 and run.persisted_rows == 1 for run in summary.runs))
        self.assertEqual(writer.write_usage_report.call_count, 7)


if __name__ == "__main__":
    unittest.main()
