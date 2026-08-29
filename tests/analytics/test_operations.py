import unittest
from datetime import date

from analytics import OperationsAnalyticsQueryService


def row(user, last=None, **values):
    return {"entity_key": user, "identity_value": user, "last_activity_date": last, **values}


class OperationsAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "users": [
                {"user_principal_name": "alice@example.test", "account_enabled": True},
                {"user_principal_name": "bob@example.test", "account_enabled": False},
                {"user_principal_name": "carol@example.test", "account_enabled": True},
            ],
            "office365_active_user": [row("alice@example.test", "2026-08-25", report_refresh_date="2026-08-26")],
            "exchange_email_activity": [
                row("alice@example.test", "2026-08-25", report_refresh_date="2026-08-26", send_count=2, receive_count=3, read_count=4),
                row("bob@example.test", "2026-06-20", report_refresh_date="2026-08-26", send_count=0, receive_count=0, read_count=0),
            ],
            "exchange_mailbox_usage": [row("alice@example.test", "2026-08-25", report_refresh_date="2026-08-26", mailbox_item_count=12, storage_used=100, is_deleted="false")],
            "onedrive_activity": [row("alice@example.test", "2026-08-25", report_refresh_date="2026-08-26", active_file_count=1), row("bob@example.test", "2026-05-01", report_refresh_date="2026-08-26", active_file_count=0)],
            "onedrive_account_usage": [row("alice@example.test", report_refresh_date="2026-08-26", storage_used=100, file_count=4)],
            "onedrive_account_capacity": [{"entity_key": "alice@example.test", "identity_value": "alice@example.test", "user_ref": "user-69b1145a03334875", "storage_used": 100, "storage_allocated": 400, "file_count": 4, "report_refresh_date": "2026-08-26", "last_activity_date": "2026-08-26", "utilization_percent": 25, "usage_level": "LOW"}],
            "sharepoint_user_activity": [row("alice@example.test", "2026-08-25", report_refresh_date="2026-08-26", viewed_count=1)],
            # The tenant's site report intentionally has no safe identity.
            "sharepoint_site_usage": [row("masked", "2026-08-20", report_refresh_date="2026-08-26")],
            "license_assignments": [row("alice@example.test"), row("bob@example.test")],
            "subscribed_sku": [{"sku_part_number": "E5", "prepaid_units": 3, "consumed_units": 2, "last_observed_at": "2026-08-26"}],
        }
        self.service = OperationsAnalyticsQueryService(self.data, as_of="2026-08-26")

    def test_cross_workload_correlation_fail_safe_and_license_shape(self):
        service = OperationsAnalyticsQueryService({
            "users": [
                {"tenant_id": 1, "user_id": 1, "user_principal_name": "Alice@Example.test"},
                {"tenant_id": 2, "user_id": 2, "user_principal_name": "alice@example.test"},
                {"tenant_id": 1, "user_id": 3, "user_principal_name": "masked@example.test"},
            ],
            "license_assignments": [
                {"tenant_id": 1, "user_id": 1, "sku_id": "sku-a"},
                {"tenant_id": 1, "user_id": 1, "sku_id": "sku-b"},
            ],
            "subscribed_sku": [{"sku_id": "sku-a", "sku_part_number": "A"}, {"sku_id": "sku-b", "sku_part_number": "B"}],
            "exchange_mailbox_usage": [
                row("alice@example.test", "2026-08-25", tenant_id=1, observed_at="2026-08-26", is_deleted=False),
                row("masked", None, tenant_id=1, observed_at="2026-08-26", is_deleted=True, identity_is_masked=True),
            ],
            "onedrive_activity": [row("alice@example.test", None, tenant_id=1, observed_at="2026-08-26", is_deleted=False)],
            "sharepoint_user_activity": [row("alice@example.test", "2026-08-25", tenant_id=1, observed_at="2026-08-26", is_deleted=True)],
        })
        result = service.cross_workload_user_status()
        self.assertEqual(result[0]["assigned_sku_count"], 2)
        self.assertEqual(result[0]["exchange_status"], "ACTIVE")
        self.assertEqual(result[0]["onedrive_status"], "INACTIVE")
        self.assertEqual(result[0]["sharepoint_status"], "INACTIVE")
        self.assertEqual(result[1]["licensed"], "NO")
        self.assertEqual(result[1]["exchange_status"], "UNKNOWN")
        self.assertEqual(result[2]["exchange_status"], "UNKNOWN")

    def test_cross_workload_correlation_exposes_readable_identity_without_changing_joins(self):
        service = OperationsAnalyticsQueryService({
            "users": [
                {"tenant_id": 1, "user_id": 1, "user_principal_name": "alice@example.test", "display_name": "Alice Example"},
            ],
            "license_assignments": [{"tenant_id": 1, "user_id": 1, "sku_id": "sku-a"}],
            "subscribed_sku": [{"sku_id": "sku-a", "sku_part_number": "A"}],
            "exchange_mailbox_usage": [
                row("alice@example.test", "2026-08-25", tenant_id=1, observed_at="2026-08-26", is_deleted=False),
            ],
            "onedrive_activity": [],
            "sharepoint_user_activity": [],
        })
        result = service.cross_workload_user_status()
        self.assertEqual(len(result), 1)
        item = result[0]
        # Human-readable identity is exposed alongside the opaque user_ref.
        self.assertEqual(item["display_name"], "Alice Example")
        self.assertEqual(item["user_principal_name"], "alice@example.test")
        self.assertEqual(item["user_ref"], "user-" + __import__("hashlib").sha256("alice@example.test".encode()).hexdigest()[:16])
        # Joins remain grounded on the canonical directory identity.
        self.assertEqual(item["exchange_status"], "ACTIVE")


    def test_license_attention_counts_current_unique_skus_by_status(self):
        data = dict(self.data)
        data["subscribed_sku"] = [
            {"sku_id": "enabled", "capability_status": "Enabled"},
            {"sku_id": "warning", "capability_status": "WARNING"},
            {"sku_id": "suspended", "capability_status": "Suspended"},
            {"sku_id": "locked", "capability_status": "LockedOut"},
            {"sku_id": "unknown", "capability_status": "FutureState"},
            {"sku_id": "null", "capability_status": None},
            {"sku_id": "warning", "capability_status": "Warning"},
        ]
        service = OperationsAnalyticsQueryService(data)
        result = service.standard_kpi_summary()
        self.assertEqual(result["license_attention_count"], 3)

    def test_license_attention_enabled_only_is_zero(self):
        data = dict(self.data)
        data["subscribed_sku"] = [{"sku_id": "enabled", "capability_status": "Enabled"}]
        service = OperationsAnalyticsQueryService(data)
        self.assertEqual(service.standard_kpi_summary()["license_attention_count"], 0)

    def test_tenant_summary_and_disabled_accounts(self):
        summary = self.service.tenant_summary()
        self.assertEqual(summary["total_users"]["value"], 3)
        self.assertEqual(summary["enabled_users"]["value"], 2)
        self.assertEqual(summary["disabled_users"]["value"], 1)
        self.assertEqual(summary["active_m365_users"]["value"], 1)

    def test_exchange_adoption_and_source_metrics(self):
        result = self.service.exchange_adoption()
        self.assertEqual(result["active_users"]["value"], 1)
        self.assertEqual(result["inactive_users"]["value"], 0)
        self.assertEqual(result["adoption_rate"]["value"], 100.0)
        self.assertEqual(result["send_count"]["value"], 2)
        self.assertEqual(result["mailbox_usage"]["value"]["mailbox_item_count"], 12)
        self.assertEqual(result["mailbox_usage"]["value"]["total_storage_used"], 100)
        self.assertEqual(result["last_activity"]["value"], "2026-08-25")

    def test_onedrive_and_sharepoint_user_adoption(self):
        self.assertEqual(self.service.onedrive_adoption()["active_users"]["value"], 2)
        self.assertEqual(self.service.onedrive_adoption()["account_usage"]["value"]["storage_used"], 100)
        self.assertEqual(self.service.sharepoint_user_adoption()["active_users"]["value"], 1)

    def test_onedrive_account_details_preserve_raw_capacity_and_identity(self):
        service = OperationsAnalyticsQueryService({**self.data, "users": [{"user_principal_name": "alice@example.test", "display_name": "Alice Example"}], "onedrive_account_usage": [row("ALICE@example.test", report_refresh_date="2026-08-26", storage_used="100", storage_allocated="400", file_count="4")], "onedrive_account_capacity": [{"entity_key": "ALICE@example.test", "identity_value": "ALICE@example.test", "user_ref": "user-69b1145a03334875", "storage_used": "100", "storage_allocated": "400", "file_count": "4", "report_refresh_date": "2026-08-26", "utilization_percent": "25", "usage_level": "LOW"}]}, as_of="2026-08-26")
        details = service.onedrive_adoption()["account_details"]
        self.assertEqual(details, [{"display_name": "Alice Example", "user_principal_name": "alice@example.test", "user_ref": "user-" + __import__("hashlib").sha256("alice@example.test".encode()).hexdigest()[:16], "storage_used": 100, "storage_allocated": 400, "utilization_percent": 25, "usage_level": "low", "file_count": 4, "report_refresh_date": "2026-08-26"}])

    def test_sharepoint_basic_kpis_filter_deleted_missing_activity_and_ignore_thresholds(self):
        service = OperationsAnalyticsQueryService({
            "sharepoint_user_activity": [
                row("active@example.test", "2026-08-25", is_deleted=False, viewed_count=0),
                row("missing@example.test", None, is_deleted=False, viewed_count=99),
                row("deleted@example.test", "2026-08-26", is_deleted=True),
                row("malformed@example.test", "2026-08-26", is_deleted="maybe", viewed_count=99),
            ],
            "sharepoint_site_usage": [
                row("site-a", "2026-08-24", is_deleted=False, storage_used="10", file_count="2", storage_allocated="100"),
                row("site-b", None, is_deleted=False, storage_used="20", file_count="3", storage_allocated="200"),
                row("site-deleted", "2026-08-26", is_deleted=True, storage_used="99", file_count="99", storage_allocated="100"),
                row("site-bad", "2026-08-26", is_deleted="maybe", storage_used="bad", file_count="1", storage_allocated="0"),
            ],
        }, as_of="2026-08-27")
        self.assertEqual(service.sharepoint_user_adoption()["active_users"]["value"], 1)
        result = service.sharepoint_site_adoption()
        self.assertEqual(result["active_sites"]["value"], 1)
        self.assertEqual(result["latest_activity"]["value"], "2026-08-24")
        self.assertEqual(result["total_storage_used"]["value"], 30)
        self.assertEqual(result["total_file_count"]["value"], 5)
        self.assertEqual(result["storage_utilization"]["value"], 0.1)

    def test_external_sharing_summary_aggregates_non_deleted_sites_per_tenant(self):
        service = OperationsAnalyticsQueryService({
            "sharepoint_site_usage": [
                {"tenant_id": 2, "site_id": "a", "external_share_count": "3", "is_deleted": False},
                {"tenant_id": 2, "site_id": "b", "external_share_count": 0, "is_deleted": False},
                {"tenant_id": 2, "site_id": "deleted", "external_share_count": 99, "is_deleted": True},
                {"tenant_id": 1, "site_id": "c", "external_share_count": 2, "is_deleted": False},
            ],
        })
        self.assertEqual(service.external_sharing_summary(), [
            {"tenant_id": 1, "external_share_count": 2, "sites_with_external_shares": 1},
            {"tenant_id": 2, "external_share_count": 3, "sites_with_external_shares": 1},
        ])

    def test_orphaned_sites_include_null_and_over_90_days_per_tenant(self):
        service = OperationsAnalyticsQueryService({
            "sharepoint_site_usage": [
                {"tenant_id": 2, "site_id": "recent", "last_activity_date": "2026-08-01"},
                {"tenant_id": 2, "site_id": "old", "last_activity_date": "2026-05-28"},
                {"tenant_id": 1, "site_id": "never", "last_activity_date": None},
            ],
        }, as_of="2026-08-27")
        self.assertEqual(service.orphaned_sites(), [
            {"tenant_id": 1, "site_id": "never", "site_url": None, "display_name": None, "last_activity_date": None},
            {"tenant_id": 2, "site_id": "old", "site_url": None, "display_name": None, "last_activity_date": "2026-05-28"},
        ])

    def test_sharepoint_utilization_fails_closed_for_missing_allocation(self):
        result = OperationsAnalyticsQueryService({
            "sharepoint_site_usage": [row("site", "2026-08-27", storage_used=10, file_count=1)]
        }).sharepoint_site_adoption()
        self.assertIsNone(result["storage_utilization"]["value"])

    def test_exchange_basic_ignores_deleted_and_missing_activity_mailboxes(self):
        data = {
            "exchange_mailbox_usage": [
                row("active@example.test", "2026-08-26", storage_used="10", mailbox_item_count="2", is_deleted=False),
                row("no-activity@example.test", None, storage_used="20", mailbox_item_count="3", is_deleted="0"),
                row("deleted@example.test", "2026-08-26", storage_used="30", mailbox_item_count="4", is_deleted="yes"),
                row("unknown-delete@example.test", "2026-08-25", storage_used="bad", mailbox_item_count=None, is_deleted="maybe"),
            ],
            # Email activity must not affect Exchange basic active users.
            "exchange_email_activity": [row("email-only@example.test", "2026-08-26")],
        }
        result = OperationsAnalyticsQueryService(data, as_of="2026-08-26").exchange_adoption()
        self.assertEqual(result["active_users"]["value"], 1)
        self.assertEqual(result["inactive_users"]["value"], 1)
        self.assertEqual(result["applicable_users"]["value"], 2)
        self.assertEqual(result["last_activity"]["value"], "2026-08-26")
        self.assertEqual(result["mailbox_usage"]["value"], {"total_storage_used": 60, "mailbox_item_count": 9})

    def test_exchange_basic_missing_mailbox_dependency_is_not_zero(self):
        result = OperationsAnalyticsQueryService({"exchange_email_activity": [row("a", "2026-08-26")]}).exchange_adoption()
        self.assertIsNone(result["active_users"]["value"])
        self.assertEqual(result["active_users"]["missing_dependency"], "exchange_mailbox_usage")

    def test_30_60_90_and_multi_workload_inactivity(self):
        candidates = {item["user_ref"]: item for item in self.service.inactivity_candidates()}
        bob = candidates["user-" + __import__("hashlib").sha256(b"bob@example.test").hexdigest()[:16]]
        self.assertEqual(bob["inactivity_30_60_90"], {"30": "inactive", "60": "inactive", "90": "active"})
        self.assertTrue(bob["multi_workload_inactive"])

    def test_license_join_and_missing_dependency(self):
        result = self.service.license_utilization()
        self.assertEqual(result["entitled_users"]["value"], 2)
        self.assertEqual(result["utilized_users"]["value"], 1)
        missing = OperationsAnalyticsQueryService({"users": []}).license_utilization()
        self.assertEqual(missing["utilization_percentage"]["status"], "DATA_DEPENDENCY_UNAVAILABLE")

    def test_missing_workload_is_not_zero(self):
        result = OperationsAnalyticsQueryService({"users": [{"user_principal_name": "a", "account_enabled": True}]}).onedrive_adoption()
        self.assertIsNone(result["active_users"]["value"])
        self.assertEqual(result["active_users"]["status"], "DATA_DEPENDENCY_UNAVAILABLE")

    def test_masked_identity_and_sharepoint_site_limitation(self):
        output = self.service.build()
        self.assertNotIn("alice@example.test", str(output["inactive_user_candidates"]))
        self.assertEqual(output["limitations"]["sharepoint_site_analytics_status"], "IDENTITY_UNAVAILABLE")
        self.assertIsNone(output["limitations"]["sharepoint_site_stale_conclusion"])
        self.assertFalse(output["limitations"]["site_rows_used_for_conclusions"])

    def test_sanitized_contract_contains_required_sections_and_metadata(self):
        output = self.service.build()
        for key in ("tenant_summary", "adoption_summary", "inactive_user_candidates", "exchange_adoption", "onedrive_adoption", "sharepoint_user_adoption", "license_utilization", "data_quality", "limitations"):
            self.assertIn(key, output)
        self.assertEqual(output["exchange_adoption"]["active_users"]["source_refresh_date"], "2026-08-26")
        self.assertTrue(output["data_quality"]["identity_masking_exposed"])

    def test_directory_is_authoritative_and_unmatched_usage_is_quality_evidence(self):
        data = {
            "users": [{"source_object_id": "graph-a", "user_principal_name": "Alice@EXAMPLE.TEST", "account_enabled": True}],
            "exchange_email_activity": [row(" alice@example.test ", "2026-08-25"), row("ghost@example.test", "2026-08-25")],
            "exchange_mailbox_usage": [row("alice@example.test", "2026-08-25")],
            "onedrive_activity": [row("ALICE@example.test", "2026-08-25")],
            "sharepoint_user_activity": [row("ghost@example.test", "2026-08-25")],
        }
        service = OperationsAnalyticsQueryService(data, as_of="2026-08-26")
        self.assertEqual(len(service.inactivity_candidates()), 1)
        quality = service.identity_join_quality()["exchange_email_activity"]
        self.assertEqual(quality, {"matched": 1, "unmatched_directory": 0, "unmatched_workload": 1})
        self.assertEqual(service.exchange_adoption()["active_users"]["value"], 0)
        self.assertEqual(service.onedrive_adoption()["active_users"]["value"], 1)
        self.assertEqual(service.sharepoint_user_adoption()["active_users"]["value"], 1)
        self.assertEqual(service.sharepoint_user_adoption()["active_users"]["status"], "READY")
        self.assertIsNone(service.sharepoint_user_adoption()["adoption_rate"]["value"])

    def test_masked_and_cross_tenant_rows_fail_closed(self):
        service = OperationsAnalyticsQueryService({
            "users": [{"tenant_id": 1, "user_principal_name": "a@example.test", "account_enabled": True}],
            "exchange_email_activity": [row("masked", "2026-08-25"), row("other@example.test", "2026-08-25")],
        }, as_of="2026-08-26")
        self.assertEqual(service.identity_join_quality()["exchange_email_activity"]["matched"], 0)
        self.assertEqual(len(service.inactivity_candidates()), 1)

    def test_broken_join_is_not_false_utilization_or_review(self):
        service = OperationsAnalyticsQueryService({
            "users": [{"user_principal_name": "a@example.test", "account_enabled": True}],
            "license_assignments": [row("a@example.test"), row("a@example.test")],
            "exchange_email_activity": [row("unmatched@example.test", "2026-08-25")],
        }, as_of="2026-08-26")
        result = service.license_utilization()
        self.assertEqual(result["entitled_users"]["value"], 1)
        self.assertEqual(result["utilized_users"]["value"], 0)
        self.assertEqual(result["apparently_unused_entitlement_candidates"]["value"], 0)
        self.assertEqual(result["insufficient_evidence_users"]["value"], 1)

    def test_current_analytics_selects_only_global_newest_generation(self):
        data = {"users": [{"user_principal_name": "new@example.test", "account_enabled": True}],
                "exchange_email_activity": [
                    row("opaque-1", "2026-08-25", observed_at="2026-08-26T00:00:00Z"),
                    row("new@example.test", "2026-08-25", observed_at="2026-08-27T00:00:00Z"),
                ]}
        service = OperationsAnalyticsQueryService(data, as_of="2026-08-27")
        self.assertEqual(len(service.tables["exchange_email_activity"]), 1)
        self.assertEqual(service.identity_join_quality()["exchange_email_activity"]["matched"], 1)
        self.assertEqual(service.identity_join_quality()["exchange_email_activity"]["unmatched_workload"], 0)

    def test_onedrive_account_file_count_is_not_user_activity_evidence(self):
        data = {"users": [{"user_principal_name": "a@example.test", "account_enabled": True}],
                "onedrive_activity": [row("a@example.test", observed_at="2026-08-27T00:00:00Z")],
                "onedrive_account_usage": [row("a@example.test", file_count=99, observed_at="2026-08-27T00:00:00Z")]}
        result = OperationsAnalyticsQueryService(data, as_of="2026-08-27").onedrive_adoption()
        self.assertEqual(result["active_users"]["status"], "READY")
        self.assertEqual(result["active_users"]["value"], 0)

    def test_onedrive_locked_basic_kpis_filter_deleted_and_missing_activity(self):
        data = {
            "onedrive_activity": [
                row("active@example.test", "2026-08-25", is_deleted=False),
                row("active@example.test", "2026-08-20", is_deleted=False),
                row("missing@example.test", None, is_deleted=False),
                row("deleted@example.test", "2026-08-26", is_deleted=True),
            ],
            "onedrive_account_usage": [
                row("a", "2026-08-24", is_deleted=False, storage_used="10", file_count="2", storage_allocated="100"),
                row("b", None, is_deleted=False, storage_used="20", file_count="3", storage_allocated="200"),
                row("deleted", "2026-08-26", is_deleted=True, storage_used="99", file_count="99", storage_allocated="100"),
            ],
            "onedrive_account_capacity": [
                {"entity_key": "a", "identity_value": "a", "user_ref": "user-a", "storage_used": "10", "file_count": "2", "storage_allocated": "100", "report_refresh_date": "2026-08-24", "last_activity_date": "2026-08-24", "utilization_percent": "10", "usage_level": "LOW"},
                {"entity_key": "b", "identity_value": "b", "user_ref": "user-b", "storage_used": "20", "file_count": "3", "storage_allocated": "200", "report_refresh_date": "2026-08-24", "utilization_percent": "10", "usage_level": "LOW"},
            ],
        }
        result = OperationsAnalyticsQueryService(data, as_of="2026-08-27").onedrive_adoption()
        self.assertEqual(result["active_users"]["value"], 1)
        self.assertEqual(result["active_accounts"]["value"], 1)
        self.assertEqual(result["latest_activity"]["value"], "2026-08-25")
        self.assertEqual(result["total_storage_used"]["value"], 30)
        self.assertEqual(result["total_file_count"]["value"], 5)
        self.assertEqual(result["storage_utilization"]["value"], 10.0)

    def test_onedrive_utilization_fails_closed_for_zero_or_missing_allocation(self):
        for allocation in (0, None):
            result = OperationsAnalyticsQueryService({
                "onedrive_account_usage": [row("a", "2026-08-27", storage_used=10, file_count=1, storage_allocated=allocation)]
            }).onedrive_adoption()
            self.assertIsNone(result["storage_utilization"]["value"])

    def test_license_no_evidence_is_insufficient_not_review(self):
        data = {"users": [{"user_principal_name": "a@example.test", "account_enabled": True}],
                "license_assignments": [row("a@example.test")],
                "exchange_email_activity": [row("a@example.test", observed_at="2026-08-27T00:00:00Z")]}
        result = OperationsAnalyticsQueryService(data, as_of="2026-08-27").license_utilization()
        self.assertEqual(result["apparently_unused_entitlement_candidates"]["value"], 0)
        self.assertEqual(result["insufficient_evidence_users"]["value"], 1)

    def test_exchange_capacity_reads_analytical_view_contract(self):
        # The authoritative view is the single derived-data contract: Python
        # must consume utilization_percent/usage_level from the view rather than
        # recompute the capacity formula. Provide view rows directly.
        data = {
            "exchange_mailbox_usage": [
                row("a@example.test", "2026-08-25", report_refresh_date="2026-08-25", mailbox_item_count=5, storage_used=100, is_deleted=False),
                row("b@example.test", "2026-08-25", report_refresh_date="2026-08-25", mailbox_item_count=7, storage_used=200, is_deleted=False),
            ],
            "exchange_mailbox_capacity": [
                {"tenant_id": 1, "identity_value": "a@example.test", "user_ref": "user-aaaa", "identity_is_masked": False, "storage_used": 40, "mailbox_capacity": 100, "utilization_percent": 40.0, "usage_level": "LOW", "report_refresh_date": "2026-08-25", "last_activity_date": "2026-08-25"},
                {"tenant_id": 1, "identity_value": "b@example.test", "user_ref": "user-bbbb", "identity_is_masked": False, "storage_used": None, "mailbox_capacity": None, "utilization_percent": None, "usage_level": "NO_DATA", "report_refresh_date": "2026-08-25", "last_activity_date": None},
            ],
        }
        service = OperationsAnalyticsQueryService(data, as_of="2026-08-26")
        result = service.exchange_capacity()
        self.assertEqual(result["capacity_usage"], {"low": 1, "medium": 0, "high": 0, "no_data": 1})
        self.assertEqual(result["data_last_refreshed"], "2026-08-25")
        self.assertEqual(result["total_storage_used"], 40)
        self.assertEqual(result["total_mailbox_items"], 12)
        by_ref = {d["user_ref"]: d for d in result["mailboxes"]}
        # utilization/usage_level come from the view, not recomputed in Python.
        self.assertEqual(by_ref["user-aaaa"]["utilization_percent"], 40.0)
        self.assertEqual(by_ref["user-aaaa"]["usage_level"], "low")
        self.assertEqual(by_ref["user-aaaa"]["user_principal_name"], "a@example.test")
        self.assertEqual(by_ref["user-aaaa"]["report_refresh_date"], "2026-08-25")
        self.assertEqual(by_ref["user-bbbb"]["utilization_percent"], None)
        self.assertEqual(by_ref["user-bbbb"]["usage_level"], "no_data")
        self.assertEqual(result["mailbox_capacity_risk"]["value"], 0)

    def test_exchange_capacity_falls_back_to_empty_without_view(self):
        # Offline/service construction without the view yields fail-closed empty
        # capacity while adoption/raw metrics still work from the base table.
        service = OperationsAnalyticsQueryService({
            "exchange_mailbox_usage": [row("a@example.test", "2026-08-25", report_refresh_date="2026-08-25", mailbox_item_count=5, storage_used=100, is_deleted=False)],
        }, as_of="2026-08-26")
        result = service.exchange_capacity()
        self.assertEqual(result["capacity_usage"], {"low": 0, "medium": 0, "high": 0, "no_data": 0})
        self.assertEqual(result["mailboxes"], [])
        self.assertEqual(result["total_mailbox_items"], 5)

    def test_exchange_capacity_summary_preserves_all_view_levels(self):
        levels = ["LOW", "MEDIUM", "HIGH", "NO_DATA"]
        service = OperationsAnalyticsQueryService({
            "exchange_mailbox_capacity": [
                {"tenant_id": 1, "identity_value": "u{}@example.test".format(i),
                 "storage_used": None, "mailbox_capacity": None,
                 "utilization_percent": None, "usage_level": level,
                 "report_refresh_date": "2026-08-29"}
                for i, level in enumerate(levels)
            ]
        })
        result = service.exchange_capacity()
        self.assertEqual(result["capacity_usage"], {"low": 1, "medium": 1, "high": 1, "no_data": 1})
        self.assertEqual(result["mailbox_capacity_risk"]["value"], 1)

    def test_sharepoint_audit_summary_counts_operations_per_tenant(self):
        service = OperationsAnalyticsQueryService({
            "sharepoint_high_value_audit_event": [
                {"tenant_id": 2, "audit_record_id": "a1", "event_time": "2026-08-29T10:00:00Z", "event_category": "EXTERNAL_SHARING", "operation": "SharingInvitationCreated", "actor_upn": "alice@example.test", "anonymous_flag": False, "external_flag": True, "site_url": "https://x", "source_file_name": "f", "workload": "SharePoint"},
                {"tenant_id": 2, "audit_record_id": "a2", "event_time": "2026-08-29T10:01:00Z", "event_category": "EXTERNAL_SHARING", "operation": "AnonymousLinkCreated", "actor_upn": "alice@example.test", "anonymous_flag": True, "external_flag": True, "site_url": "https://x", "source_file_name": "g", "workload": "SharePoint"},
                {"tenant_id": 2, "audit_record_id": "a3", "event_time": "2026-08-29T10:02:00Z", "event_category": "EXTERNAL_SHARING", "operation": "SharingInvitationCreated", "actor_upn": "bob@example.test", "anonymous_flag": False, "external_flag": False, "site_url": "https://x", "source_file_name": "h", "workload": "SharePoint"},
                {"tenant_id": 1, "audit_record_id": "a4", "event_time": "2026-08-29T10:03:00Z", "event_category": "EXTERNAL_SHARING", "operation": "SharingRevoked", "actor_upn": "carol@example.test", "anonymous_flag": False, "external_flag": True, "site_url": "https://y", "source_file_name": "i", "workload": "SharePoint"},
            ],
        })
        result = service.sharepoint_audit_summary()
        self.assertEqual(result["summary"]["total_events"], 4)
        self.assertEqual(result["summary"]["operations"], {"SharingInvitationCreated": 2, "AnonymousLinkCreated": 1, "SharingRevoked": 1})
        self.assertEqual(result["summary"]["latest_event_time"], "2026-08-29T10:03:00Z")
        self.assertEqual(result["tenants"], [
            {"tenant_id": 1, "total_events": 1, "operations": {"SharingRevoked": 1}},
            {"tenant_id": 2, "total_events": 3, "operations": {"SharingInvitationCreated": 2, "AnonymousLinkCreated": 1}},
        ])
        self.assertEqual(len(result["recent_events"]), 4)
        self.assertEqual(result["status"], "READY")

    def test_sharepoint_audit_summary_missing_dependency_fails_closed(self):
        result = OperationsAnalyticsQueryService({}).sharepoint_audit_summary()
        self.assertEqual(result["status"], "DATA_DEPENDENCY_UNAVAILABLE")
        self.assertEqual(result["summary"]["total_events"], 0)
        self.assertEqual(result["tenants"], [])

    def test_sharepoint_audit_summary_bounds_limit(self):
        rows = [
            {"tenant_id": 2, "audit_record_id": "a{}".format(i), "event_time": "2026-08-29T10:0{}:00Z".format(i), "event_category": "EXTERNAL_SHARING", "operation": "SharingInvitationCreated", "actor_upn": "a@example.test", "anonymous_flag": False, "external_flag": True, "site_url": "https://x", "source_file_name": "f", "workload": "SharePoint"}
            for i in range(5)
        ]
        result = OperationsAnalyticsQueryService({"sharepoint_high_value_audit_event": rows}).sharepoint_audit_summary(limit=3)
        self.assertEqual(result["limit"], 3)
        self.assertEqual(len(result["recent_events"]), 3)
        self.assertEqual(result["summary"]["total_events"], 5)

    def test_from_connection_loads_assignments_and_skus(self):
        class Cursor:
            def __init__(self, sql):
                self.sql = sql
                self.description = [("user_principal_name",), ("account_enabled",)]
            def execute(self, sql, params):
                self.sql = sql
                if "user_license_assignment" in sql:
                    self.description = [("tenant_id",), ("user_id",), ("sku_id",), ("user_principal_name",)]
                elif "subscribed_sku" in sql:
                    self.description = [("sku_id",), ("sku_part_number",), ("consumed_units",), ("prepaid_units",), ("last_observed_at",)]
                elif 'core."user"' in sql:
                    self.description = [("tenant_id",), ("user_id",), ("source_object_id",), ("user_principal_name",), ("display_name",), ("account_enabled",)]
            def fetchall(self):
                if 'core."user"' in self.sql:
                    return [(7, 11, "source-11", "user@example.test", "Example User", True)]
                return []
        class Connection:
            def cursor(self): return Cursor("")
        service = OperationsAnalyticsQueryService.from_connection(Connection(), 7)
        self.assertIn("tenant_id", service.rows["users"][0])
        self.assertEqual(service.rows["users"][0]["tenant_id"], 7)
        self.assertIn("license_assignments", service.rows)
        self.assertIn("subscribed_sku", service.rows)
        # Canonical user rows carry the human-readable identity fields.
        self.assertEqual(service.rows["users"][0]["display_name"], "Example User")
        self.assertEqual(service.rows["users"][0]["user_principal_name"], "user@example.test")


if __name__ == "__main__":
    unittest.main()
