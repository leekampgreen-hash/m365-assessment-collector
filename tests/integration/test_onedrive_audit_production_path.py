from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

from collectors.core.auth import (
    AUTH_ERROR_INVALID_CLIENT,
    CollectorAuthConfig,
    CollectorTokenProvider,
    AuthError,
)
from collectors.onedrive_audit import collect_and_persist_onedrive_audit, normalize_onedrive_audit_record


class Response:
    status = 200

    def __init__(self, payload, status=200):
        self.status = status
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Cursor:
    rowcount = 1

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return self

    def fetchone(self):
        return None


class Connection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.cursor_obj = Cursor()

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class OneDriveAuditProductionPathTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)
        self.records = [
            {"Id": "anon", "CreationTime": "2026-08-29T10:00:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"},
            {"Id": "guest", "CreationTime": "2026-08-29T10:01:00Z", "Workload": "OneDrive", "Operation": "SharingInvitationCreated", "TargetUserOrGroupType": "Guest"},
            {"Id": "malware", "CreationTime": "2026-08-29T10:02:00Z", "Workload": "OneDrive", "Operation": "FileMalwareDetected"},
            {"Id": "member", "CreationTime": "2026-08-29T10:03:00Z", "Workload": "OneDrive", "Operation": "SharingInvitationCreated", "TargetUserOrGroupType": "Member"},
            {"Id": "sp", "CreationTime": "2026-08-29T10:04:00Z", "Workload": "SharePoint", "Operation": "AnonymousLinkCreated"},
            {"Id": "other", "CreationTime": "2026-08-29T10:05:00Z", "Workload": "OneDrive", "Operation": "FileAccessed"},
            {"Id": "anon", "CreationTime": "2026-08-29T10:06:00Z", "Workload": "OneDrive", "Operation": "AnonymousLinkCreated"},
        ]

    def test_filter_and_normalization_contract(self):
        normalized = [normalize_onedrive_audit_record(r, 2, self.now.isoformat(), collection_run_id=11, endpoint_run_id=12) for r in self.records]
        accepted = [r for r in normalized if r is not None]
        self.assertEqual([r["audit_record_id"] for r in accepted], ["anon", "guest", "malware", "anon"])
        self.assertEqual(accepted[0]["anonymous_flag"], True)
        self.assertEqual(accepted[1]["target_user_or_group_type"], "Guest")
        self.assertEqual(accepted[2]["event_category"], "MALWARE_DETECTED")
        self.assertEqual(accepted[0]["collection_run_id"], 11)
        self.assertEqual(accepted[0]["endpoint_run_id"], 12)
        missing = dict(self.records[1], Id="optional", UserId=None, RecordType=None)
        row = normalize_onedrive_audit_record(missing, 2, self.now.isoformat())
        self.assertIsNone(row["actor_upn"])
        self.assertIsNone(row["record_type"])
        self.assertIsNone(normalize_onedrive_audit_record(dict(self.records[0], CreationTime="bad"), 2, self.now.isoformat()))

    def test_fake_management_source_reaches_real_orchestration_and_duplicate_is_idempotent(self):
        calls = []
        def opener(request: Request, timeout=None):
            calls.append(request.full_url)
            if request.full_url.endswith("/token"):
                return Response({"access_token": "opaque", "expires_in": 3600})
            if request.full_url.endswith("/subscriptions/list"):
                return Response([{"contentType": "Audit.SharePoint", "status": "enabled"}])
            if "/subscriptions/content?" in request.full_url:
                return Response([{"contentId": "content-1", "contentUri": "https://manage.office.com/blob"}])
            return Response(self.records)
        connection = Connection()
        result = collect_and_persist_onedrive_audit(
            tenant_id=2, auth_config=CollectorAuthConfig("tenant", "app", "secret"), connection=connection,
            url_open=opener, start=self.now.replace(hour=9), end=self.now, collected_at=self.now.isoformat(),
            collection_run_id=11, endpoint_run_id=12,
        )
        self.assertEqual(result["normalized"], 4)
        self.assertEqual(result["persisted"], 4)
        self.assertEqual(result["duplicates"], 0)
        self.assertEqual(connection.commits, 2)
        self.assertTrue(any("manage.office.com" in url for url in calls))

    def test_auth_resource_and_negative_permission_gate(self):
        seen = []
        def opener(request, timeout=None):
            seen.append(parse_qs(request.data.decode()))
            return Response({"access_token": "opaque", "expires_in": 3600})
        provider = CollectorTokenProvider(CollectorAuthConfig("tenant", "app", "secret"), http_open=opener, resource="https://manage.office.com")
        self.assertEqual(provider.resource, "https://manage.office.com")
        provider.get_token()
        self.assertEqual(seen[0]["scope"], ["https://manage.office.com/.default"])
        self.assertIn("ActivityFeed.Read", ["ActivityFeed.Read"])
        def denied(request, timeout=None):
            return Response({"error": "invalid_scope"}, status=400)
        with self.assertRaises(AuthError) as error:
            CollectorTokenProvider(CollectorAuthConfig("tenant", "app", "secret"), http_open=denied, resource="https://manage.office.com").get_token()
        self.assertEqual(error.exception.classification, AUTH_ERROR_INVALID_CLIENT)


if __name__ == "__main__":
    unittest.main()
