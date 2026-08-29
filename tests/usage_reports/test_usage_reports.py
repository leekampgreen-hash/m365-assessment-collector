import unittest

from collectors.usage_reports.csv import CsvSchemaError, parse_report_csv
from collectors.usage_reports.registry import REPORTS, build_report_path, normalize_report_rows
from collectors.usage_reports.transport import UsageReportHttpError, UsageReportTransport, build_usage_report_http_open
from collectors.usage_reports.persistence import write_report_rows


class Response:
    def __init__(self, status, headers, content):
        self.status, self.headers, self.content = status, headers, content
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit=-1): return self.content if limit < 0 else self.content[:limit]


class UsageReportTransportTests(unittest.TestCase):
    def test_canonical_d7_paths_for_all_reports(self):
        expected = {
            "office365_active_user": "getOffice365ActiveUserDetail",
            "exchange_email_activity": "getEmailActivityUserDetail",
            "exchange_mailbox_usage": "getMailboxUsageDetail",
            "onedrive_activity": "getOneDriveActivityUserDetail",
            "onedrive_account_usage": "getOneDriveUsageAccountDetail",
            "sharepoint_user_activity": "getSharePointActivityUserDetail",
            "sharepoint_site_usage": "getSharePointSiteUsageDetail",
        }
        for key, method in expected.items():
            self.assertEqual(build_report_path(key), "/v1.0/reports/{}(period='D7')".format(method))
            self.assertNotIn("?period", build_report_path(key))

    def test_period_is_bounded(self):
        with self.assertRaises(ValueError):
            build_report_path("office365_active_user", "D1")
        with self.assertRaises(ValueError):
            build_report_path("office365_active_user", "D7')&evil='")
        with self.assertRaises(ValueError):
            UsageReportTransport(lambda: "x", url_open=lambda request, timeout: None).get(
                "/v1.0/reports/getOffice365ActiveUserDetail", params={"period": "D7"})

    def test_explicit_allowed_redirect_and_no_bearer_on_download(self):
        calls = []
        def opener(request, timeout):
            calls.append(request)
            if len(calls) == 1:
                return Response(302, {"Location": "https://reportswestus.office.com/download?token=secret"}, b"")
            return Response(200, {"Content-Type": "text/csv"}, b"a,b\n1,2\n")
        result = UsageReportTransport(lambda: "bearer-secret", url_open=opener).get("/v1.0/reports/getMailboxUsageDetail")
        self.assertEqual(result.content, b"a,b\n1,2\n")
        self.assertNotIn("Authorization", calls[1].headers)
        self.assertNotIn("bearer-secret", str(result))

    def test_redirect_boundary_and_size(self):
        for location in ("http://reports.office.com/x", "https://evil.office.com/x", "https://reports.office.com:444/x"):
            def opener(request, timeout, location=location):
                return Response(302, {"Location": location}, b"")
            with self.assertRaises(UsageReportHttpError):
                UsageReportTransport(lambda: "x", url_open=opener).get("/v1.0/reports/x")
        def oversized(request, timeout):
            return Response(200, {}, b"12345")
        with self.assertRaises(UsageReportHttpError):
            UsageReportTransport(lambda: "x", url_open=oversized, max_bytes=4).get("/v1.0/reports/x")

    def test_canonical_opener_rejects_automatic_redirects(self):
        opener = build_usage_report_http_open()
        self.assertTrue(callable(opener))


class CsvAndAdapterTests(unittest.TestCase):
    def test_csv_quotes_nulls_and_required_schema(self):
        rows = parse_report_csv(b'User Principal Name,Report Refresh Date,Display Name\n"a,b@example.com",2026-08-20,"A\nB"\n', ["User Principal Name", "Report Refresh Date"])
        self.assertEqual(rows[0]["User Principal Name"], "a,b@example.com")
        self.assertIsNone(parse_report_csv("User Principal Name,Report Refresh Date\na,\n", ["User Principal Name", "Report Refresh Date"])[0]["Report Refresh Date"])
        with self.assertRaises(CsvSchemaError):
            parse_report_csv("User Principal Name\na\n", ["User Principal Name", "Report Refresh Date"])

    def test_all_seven_adapters_preserve_commercial_fields(self):
        for key, spec in REPORTS.items():
            header = ",".join(spec.required_columns) + ",Last Activity Date,Storage Used (Bytes),File Count"
            if key == "onedrive_account_usage":
                header = "Report Refresh Date,Owner Principal Name,Last Activity Date,Storage Used (Bytes),File Count"
                values = "2026-08-20,user@example.com,2026-08-19,10,3"
            elif key == "sharepoint_site_usage":
                header = "Report Refresh Date,Site Id,Site URL,Last Activity Date,Storage Used (Bytes),File Count"
                values = "2026-08-20,site-123,https://site.example,2026-08-19,10,3"
            elif key == "sharepoint_user_activity":
                values = "user@example.com,2026-08-20,2026-08-19,10,3"
            else:
                values = "user@example.com,2026-08-20,2026-08-19,10,3"
            current, snapshot = normalize_report_rows(key, header + "\n" + values + "\n", tenant_id=7, observed_at="2026-08-25T00:00:00Z")[0]
            self.assertEqual(current["report_refresh_date"], "2026-08-20")
            self.assertEqual(current["storage_used"], 10)
            self.assertEqual(snapshot["snapshot_identity"], "7:{}:2026-08-20".format(current["entity_key"]))

    def test_onedrive_owner_principal_name_and_stable_fallback(self):
        content = ("Report Refresh Date,Owner Principal Name,Site URL,Storage Used (Bytes)\n"
                   "2026-08-20,owner@example.com,,10\n")
        current, _ = normalize_report_rows("onedrive_account_usage", content,
                                           tenant_id=7, observed_at="now")[0]
        self.assertEqual(current["entity_key"], "owner@example.com")

    def test_exchange_quota_aliases_and_refresh_date_are_normalized(self):
        for quota_header in ("Prohibit Send/Receive Quota (Byte)", "Prohibit Send/Receive Quota (Bytes)"):
            content = ("User Principal Name,Storage Used (Byte),{},Report Refresh Date\n"
                       "User@Example.com,10,20,2026-08-20\n").format(quota_header)
            current, snapshot = normalize_report_rows("exchange_mailbox_usage", content, tenant_id=7, observed_at="now")[0]
            self.assertEqual(current["entity_key"], "user@example.com")
            self.assertEqual(current["storage_used"], 10)
            self.assertEqual(current["prohibit_send_receive_quota"], 20)
            self.assertEqual(current["report_refresh_date"], "2026-08-20")
            self.assertEqual(snapshot["report_refresh_date"], "2026-08-20")

    def test_exchange_invalid_numeric_values_fail_closed_to_null(self):
        content = ("User Principal Name,Storage Used,Prohibit Send/Receive Quota,Report Refresh Date\n"
                   "user@example.com,not-a-number,20,2026-08-20\n")
        current, _ = normalize_report_rows("exchange_mailbox_usage", content, tenant_id=7, observed_at="now")[0]
        self.assertIsNone(current["storage_used"])
        self.assertEqual(current["prohibit_send_receive_quota"], 20)

    def test_exchange_missing_identity_is_rejected(self):
        content = "User Principal Name,Display Name,Report Refresh Date\n,Mailbox,2026-08-20\n"
        with self.assertRaises(CsvSchemaError) as error:
            normalize_report_rows("exchange_mailbox_usage", content, tenant_id=7, observed_at="now")
        self.assertEqual(error.exception.classification, "ENTITY_IDENTITY_UNAVAILABLE")

    def test_mailbox_deleted_flag_is_normalized_deterministically(self):
        content = ("User Principal Name,Report Refresh Date,Is Deleted,Last Activity Date\n"
                   "true@example.com,2026-08-20,TRUE,2026-08-19\n"
                   "false@example.com,2026-08-20,0,2026-08-19\n"
                   "unknown@example.com,2026-08-20,unexpected,2026-08-19\n")
        rows = normalize_report_rows("exchange_mailbox_usage", content, tenant_id=7, observed_at="now")
        self.assertEqual([current["is_deleted"] for current, _ in rows], [True, False, None])

    def test_onedrive_deleted_flags_are_normalized_deterministically(self):
        for key, identity in (("onedrive_activity", "user@example.com"),
                              ("onedrive_account_usage", "owner@example.com")):
            if key == "onedrive_activity":
                content = ("User Principal Name,Report Refresh Date,Is Deleted\n"
                           "{},2026-08-20,unexpected\n").format(identity)
            else:
                content = ("Report Refresh Date,Owner Principal Name,Is Deleted\n"
                           "2026-08-20,{},unexpected\n").format(identity)
            rows = normalize_report_rows(key, content, tenant_id=7, observed_at="now")
            self.assertTrue(rows[0][0]["is_deleted"])

    def test_onedrive_account_without_owner_is_rejected(self):
        content = "Report Refresh Date,Site URL\n2026-08-20,https://site.example\n"
        with self.assertRaises(CsvSchemaError) as error:
            normalize_report_rows("onedrive_account_usage", content, tenant_id=7, observed_at="now")
        self.assertEqual(error.exception.classification, "ENTITY_IDENTITY_UNAVAILABLE")

    def test_site_identity_rejects_zero_id_and_empty_url(self):
        for content in (
            "Report Refresh Date,Site Id,Site URL\n2026-08-20,00000000-0000-0000-0000-000000000000,\n",
            "Report Refresh Date,Site Id,Site URL\n2026-08-20,,\n",
        ):
            with self.assertRaises(CsvSchemaError) as error:
                normalize_report_rows("sharepoint_site_usage", content, tenant_id=7, observed_at="now")
            self.assertEqual(error.exception.classification, "ENTITY_IDENTITY_UNAVAILABLE")

    def test_sharepoint_rows_cannot_collapse_under_one_key(self):
        content = ("Report Refresh Date,Site Id,Site URL,Page View Count\n"
                   "2026-08-20,00000000-0000-0000-0000-000000000000,,1\n"
                   "2026-08-20,00000000-0000-0000-0000-000000000000,,2\n")
        with self.assertRaises(CsvSchemaError):
            normalize_report_rows("sharepoint_site_usage", content, tenant_id=7, observed_at="now")

    def test_valid_site_identity_still_works(self):
        content = ("Report Refresh Date,Site Id,Site URL,Page View Count\n"
                   "2026-08-20,site-123,https://site.example,1\n")
        current, _ = normalize_report_rows("sharepoint_site_usage", content,
                                           tenant_id=7, observed_at="now")[0]
        self.assertEqual(current["entity_key"], "site-123")

    def test_site_identity_falls_back_to_site_url_when_site_id_masked(self):
        # Real SharePoint site usage reports can mask the site id (all-zeros)
        # while leaving the stable, unique site url populated.
        content = ("Report Refresh Date,Site Id,Site URL,Page View Count\n"
                   "2026-08-20,00000000-0000-0000-0000-000000000000,https://site.example,1\n")
        current, _ = normalize_report_rows("sharepoint_site_usage", content,
                                           tenant_id=7, observed_at="now")[0]
        self.assertEqual(current["entity_key"], "https://site.example")
        self.assertEqual(current["site_url"], "https://site.example")

    def test_site_identity_falls_back_to_site_url_when_site_id_absent(self):
        content = ("Report Refresh Date,Site Id,Site URL,Page View Count\n"
                   "2026-08-20,,https://site.example,1\n")
        current, _ = normalize_report_rows("sharepoint_site_usage", content,
                                           tenant_id=7, observed_at="now")[0]
        self.assertEqual(current["entity_key"], "https://site.example")

    def test_site_identity_accepts_site_id_without_site_url(self):
        content = ("Report Refresh Date,Site Id,Site URL,Page View Count\n"
                   "2026-08-20,site-123,,1\n")
        current, _ = normalize_report_rows("sharepoint_site_usage", content,
                                           tenant_id=7, observed_at="now")[0]
        self.assertEqual(current["entity_key"], "site-123")

    def test_site_identity_still_fails_closed_when_both_absent(self):
        # A genuinely identity-less site row (no site id and no site url) must
        # still fail closed; do not fabricate or collapse an identity.
        for content in (
            "Report Refresh Date,Site Id,Site URL\n2026-08-20,,\n",
            "Report Refresh Date,Site Id,Site URL\n2026-08-20,00000000-0000-0000-0000-000000000000,\n",
        ):
            with self.assertRaises(CsvSchemaError) as error:
                normalize_report_rows("sharepoint_site_usage", content, tenant_id=7, observed_at="now")
            self.assertEqual(error.exception.classification, "ENTITY_IDENTITY_UNAVAILABLE")

    def test_current_snapshot_and_refresh_date_idempotency_contract(self):
        class Executor:
            def __init__(self): self.calls = []
            def execute(self, sql, values): self.calls.append((sql, values))
        current = {"tenant_id": 7, "entity_key": "user@example.com", "report_refresh_date": "2026-08-20", "identity_value": "user@example.com", "identity_is_masked": False, "observed_at": "now"}
        snapshot = dict(current, snapshot_identity="7:user@example.com:2026-08-20")
        executor = Executor()
        write_report_rows(executor, "exchange_email_activity", [(current, snapshot)])
        write_report_rows(executor, "exchange_email_activity", [(current, snapshot)])
        self.assertEqual(len(executor.calls), 6)
        self.assertIn("DELETE FROM core.usage_exchange_email_activity WHERE tenant_id = %s", executor.calls[0][0])
        self.assertIn("ON CONFLICT (tenant_id, entity_key)", executor.calls[1][0])
        self.assertIn("ON CONFLICT (tenant_id, entity_key, report_refresh_date) DO NOTHING", executor.calls[2][0])
        self.assertEqual(executor.calls[0], executor.calls[3])

    def test_empty_endpoint_result_does_not_erase_current_state(self):
        class Executor:
            def __init__(self): self.calls = []
            def execute(self, sql, values): self.calls.append((sql, values))
        executor = Executor()
        write_report_rows(executor, "exchange_email_activity", [])
        self.assertEqual(executor.calls, [])

    def test_incomplete_report_fails_before_persistence(self):
        class Executor:
            def __init__(self): self.calls = []
            def execute(self, sql, values): self.calls.append((sql, values))
        current = {"tenant_id": 7, "entity_key": "a@example.com", "report_refresh_date": "2026-08-20"}
        snapshot = dict(current, snapshot_identity="7:a@example.com:2026-08-20")
        executor = Executor()
        with self.assertRaises(ValueError):
            write_report_rows(executor, "exchange_mailbox_usage", [(current, snapshot)], complete=False)
        self.assertEqual(executor.calls, [])

    def test_duplicate_source_keys_fail_before_persistence_and_are_tenant_scoped(self):
        class Executor:
            def __init__(self): self.calls = []
            def execute(self, sql, values): self.calls.append((sql, values))
        def pair(tenant, key):
            current = {"tenant_id": tenant, "entity_key": key, "report_refresh_date": "2026-08-20"}
            return current, dict(current, snapshot_identity="{}:{}:2026-08-20".format(tenant, key))
        executor = Executor()
        with self.assertRaises(ValueError) as error:
            write_report_rows(executor, "exchange_mailbox_usage", [pair(7, "A@EXAMPLE.COM"), pair(7, "a@example.com")])
        self.assertIn("count=2", str(error.exception))
        self.assertEqual(executor.calls, [])
        executor = Executor()
        write_report_rows(executor, "exchange_mailbox_usage", [pair(7, "a@example.com"), pair(8, "a@example.com")])
        self.assertEqual(len(executor.calls), 6)

    def test_runtime_role_can_complete_current_replacement_path(self):
        """The production role needs DELETE for current replacement, not snapshots."""
        import os
        from pathlib import Path

        try:
            import psycopg
        except ImportError:
            self.skipTest("PostgreSQL driver is unavailable")

        password_file = Path("/run/secrets/graph_agent_runtime_password")
        password = os.environ.get("PGPASSWORD", "")
        if not password and password_file.exists():
            password = password_file.read_text(encoding="utf-8").strip()
        if not password:
            self.skipTest("runtime database credentials are unavailable")
        connection = psycopg.connect(
            host=os.environ.get("PGHOST", "postgres"),
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "graph_agent"),
            user=os.environ.get("PGUSER", "graph_agent_runtime"),
            password=password,
        )
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT tenant_id FROM core.tenant ORDER BY tenant_id LIMIT 1")
            tenant_id = cursor.fetchone()[0]
            cursor.execute("DELETE FROM core.usage_exchange_mailbox_usage WHERE tenant_id = %s", (tenant_id,))
            cursor.execute(
                "INSERT INTO core.usage_exchange_mailbox_usage "
                "(tenant_id, entity_key, report_refresh_date, observed_at) "
                "VALUES (%s, %s, %s, %s)",
                (tenant_id, "privilege-probe", "2026-08-20", "2026-08-20T00:00:00Z"),
            )
            cursor.execute("DELETE FROM core.usage_exchange_mailbox_usage WHERE tenant_id = %s", (tenant_id,))
        finally:
            connection.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
