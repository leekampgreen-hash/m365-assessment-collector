"""Offline G09-R2 tests for the collector-to-workload-normalizer handoff."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from collectors.core import (
    CollectorRuntime,
    NormalizationError,
    RuntimeOptions,
    RuntimeError_,
    dict_source,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")
        self.headers = {}

    def read(self):
        return self.payload

    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class CollectorNormalizationHandoffTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.inventory = Path(self.directory.name) / "inventory.json"
        self.inventory.write_text(json.dumps([{
            "id": "G01-001",
            "name": "Users",
            "workload": "Entra ID",
            "path": "/v1.0/users",
            "pagination": True,
            "enabled": True,
        }]))

    def _runtime(self, pages):
        graph_pages = iter(pages)

        def opener(request, timeout=None):
            if "login.microsoftonline.com" in request.full_url:
                return FakeResponse({"access_token": "offline-token", "expires_in": 3600})
            return FakeResponse(next(graph_pages))

        return CollectorRuntime(
            self.inventory,
            dict_source({
                "GRAPH_TENANT_ID": "tenant-guid",
                "GRAPH_CLIENT_ID": "client-guid",
                "GRAPH_CLIENT_SECRET": "offline-secret",
            }),
            options=RuntimeOptions(
                http_open=opener,
                lineage_context={
                    "tenant_id": 42,
                    "collection_run_id": 100,
                    "endpoint_run_id": 200,
                    "observed_at": "2026-08-22T12:00:00+00:00",
                },
                tenant_resolver=lambda config: 42,
            ),
        )

    @staticmethod
    def _record(identifier):
        return {"id": identifier, "displayName": "User " + identifier}

    def test_missing_tenant_is_rejected_before_writer(self):
        writer = mock.Mock()
        runtime = CollectorRuntime(
            self.inventory,
            dict_source({
                "GRAPH_TENANT_ID": "tenant-guid",
                "GRAPH_CLIENT_ID": "client-guid",
                "GRAPH_CLIENT_SECRET": "offline-secret",
            }),
            options=RuntimeOptions(http_open=lambda *args, **kwargs: None, collection_writer=writer),
        )
        with self.assertRaisesRegex(RuntimeError_, "trusted tenant resolver is required"):
            runtime.run(endpoint_id="G01-001")
        writer.write.assert_not_called()

    def test_mismatched_tenant_is_rejected_before_writer(self):
        writer = mock.Mock()
        runtime = self._runtime([{"value": [self._record("one")]}])
        runtime.options.collection_writer = writer
        runtime.options.tenant_resolver = lambda config: 7
        with self.assertRaisesRegex(RuntimeError_, "does not match trusted tenant"):
            runtime.run(endpoint_id="G01-001")
        writer.write.assert_not_called()

    def test_one_record_reaches_correct_normalizer_with_metadata(self):
        summary = self._runtime([{"value": [self._record("one")]}]).run(endpoint_id="G01-001")

        self.assertEqual(len(summary.normalized_runs), 1)
        handoff = summary.normalized_runs[0]
        self.assertEqual(handoff.endpoint_id, "G01-001")
        self.assertEqual(handoff.workload, "Entra ID")
        self.assertEqual(handoff.tenant_id, 42)
        self.assertEqual(handoff.collection_timestamp, "2026-08-22T12:00:00+00:00")
        self.assertEqual(handoff.source_metadata["path"], "/v1.0/users")
        self.assertEqual(len(handoff.records), 1)
        self.assertEqual(handoff.records[0].current_row["source_object_id"], "one")
        self.assertEqual(handoff.records[0].current_row["tenant_id"], 42)

    def test_multiple_paginated_records_normalize_exactly_once(self):
        summary = self._runtime([
            {
                "value": [self._record("one"), self._record("two")],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=next",
            },
            {"value": [self._record("three")]},
        ]).run(endpoint_id="G01-001")

        handoff = summary.normalized_runs[0]
        self.assertEqual(summary.runs[0].rows, 3)
        self.assertEqual(
            [record.current_row["source_object_id"] for record in handoff.records],
            ["one", "two", "three"],
        )

    def test_zero_records_is_a_valid_empty_normalization(self):
        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-001")

        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.runs[0].rows, 0)
        self.assertEqual(len(summary.normalized_runs), 1)
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_normalization_failure_is_explicit_and_deterministic(self):
        runtime = self._runtime([{"value": ["not-a-record"]}])

        with self.assertRaisesRegex(NormalizationError, "Normalization failed for G01-001: TypeError"):
            runtime.run(endpoint_id="G01-001")

    def test_organization_single_object_reaches_current_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-003",
            "name": "Organization",
            "workload": "Entra ID",
            "path": "/v1.0/organization",
            "pagination": False,
            "enabled": True,
        }]))
        runtime = self._runtime([{
            "value": [{
                "id": "org-1",
                "displayName": "Example Tenant",
                "verifiedDomains": [],
                "countryLetterCode": "US",
                "tenantType": "AAD",
            }],
        }])

        summary = runtime.run(endpoint_id="G01-003")

        self.assertEqual(summary.runs[0].rows, 1)
        self.assertEqual(len(summary.normalized_runs[0].records), 1)
        record = summary.normalized_runs[0].records[0]
        self.assertEqual(record.endpoint_id, "G01-003")
        self.assertEqual(record.current_row["source_object_id"], "org-1")
        self.assertEqual(record.current_row["tenant_id"], 42)

    def test_applications_pagination_reaches_current_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-007",
            "name": "Applications",
            "workload": "Microsoft Entra ID",
            "path": "/v1.0/applications",
            "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([
            {
                "value": [{"id": "app-1", "appId": "app-id-1", "displayName": "One"}],
                "@odata.nextLink": "https://graph.example/v1.0/applications?$skiptoken=next",
            },
            {"value": [{"id": "app-2", "createdDateTime": "2026-08-20T00:00:00Z"}]},
        ])

        summary = runtime.run(endpoint_id="G01-007")

        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual(summary.runs[0].rows, 2)
        records = summary.normalized_runs[0].records
        self.assertEqual([r.current_row["source_object_id"] for r in records], ["app-1", "app-2"])
        self.assertTrue(all(r.persistence_mode.value == "CURRENT" for r in records))

    def test_applications_empty_result_is_successful_empty_normalization(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-007", "name": "Applications",
            "path": "/v1.0/applications", "pagination": True, "enabled": True,
        }]))
        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-007")
        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_applications_malformed_later_page_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-007", "name": "Applications",
            "path": "/v1.0/applications", "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "app-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/applications?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0
        summary = runtime.run(endpoint_id="G01-007")
        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].rows, 1)
        writer.write.assert_not_called()

    def test_service_principals_pagination_reaches_current_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-008",
            "name": "Service Principals",
            "workload": "Microsoft Entra ID",
            "path": "/v1.0/servicePrincipals",
            "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([
            {
                "value": [{"id": "sp-1", "displayName": "One"}],
                "@odata.nextLink": "https://graph.example/v1.0/servicePrincipals?$skiptoken=next",
            },
            {"value": [{"id": "sp-2", "accountEnabled": False}]},
        ])

        summary = runtime.run(endpoint_id="G01-008")

        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual(summary.runs[0].rows, 2)
        records = summary.normalized_runs[0].records
        self.assertEqual([r.current_row["source_object_id"] for r in records], ["sp-1", "sp-2"])
        self.assertTrue(all(r.persistence_mode.value == "CURRENT" for r in records))

    def test_service_principals_empty_result_is_successful_empty_normalization(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-008", "name": "Service Principals",
            "path": "/v1.0/servicePrincipals", "pagination": True, "enabled": True,
        }]))
        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-008")
        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_service_principals_malformed_later_page_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-008", "name": "Service Principals",
            "path": "/v1.0/servicePrincipals", "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "sp-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/servicePrincipals?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0
        summary = runtime.run(endpoint_id="G01-008")
        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].rows, 1)
        writer.write.assert_not_called()

    def test_devices_pagination_reaches_current_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-009",
            "name": "Devices",
            "workload": "Microsoft Entra ID",
            "path": "/v1.0/devices",
            "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([
            {
                "value": [{"id": "device-1", "deviceId": "graph-device-1"}],
                "@odata.nextLink": "https://graph.example/v1.0/devices?$skiptoken=next",
            },
            {"value": [{"id": "device-2", "operatingSystem": "Linux"}]},
        ])

        summary = runtime.run(endpoint_id="G01-009")

        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual(summary.runs[0].rows, 2)
        records = summary.normalized_runs[0].records
        self.assertEqual(
            [record.current_row["source_object_id"] for record in records],
            ["device-1", "device-2"],
        )
        self.assertTrue(all(record.persistence_mode.value == "CURRENT" for record in records))

    def test_devices_empty_result_is_successful_empty_normalization(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-009", "name": "Devices", "path": "/v1.0/devices",
            "pagination": True, "enabled": True,
        }]))

        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-009")

        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_devices_malformed_later_page_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-009", "name": "Devices", "path": "/v1.0/devices",
            "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "device-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/devices?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0

        summary = runtime.run(endpoint_id="G01-009")

        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].rows, 1)
        writer.write.assert_not_called()

    def test_administrative_units_pagination_reaches_current_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-010", "name": "Administrative Units",
            "path": "/v1.0/directory/administrativeUnits", "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([
            {
                "value": [{"id": "au-1", "displayName": "HQ"}],
                "@odata.nextLink": "https://graph.example/v1.0/directory/administrativeUnits?$skiptoken=next",
            },
            {"value": [{"id": "au-2", "visibility": "Hidden"}]},
        ])

        summary = runtime.run(endpoint_id="G01-010")

        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual(summary.runs[0].rows, 2)
        self.assertEqual(
            [record.current_row["source_object_id"] for record in summary.normalized_runs[0].records],
            ["au-1", "au-2"],
        )

    def test_administrative_units_empty_result_is_successful(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-010", "name": "Administrative Units",
            "path": "/v1.0/directory/administrativeUnits", "pagination": True,
            "enabled": True,
        }]))

        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-010")

        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_administrative_units_malformed_later_page_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-010", "name": "Administrative Units",
            "path": "/v1.0/directory/administrativeUnits", "pagination": True,
            "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "au-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/directory/administrativeUnits?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0

        summary = runtime.run(endpoint_id="G01-010")

        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].rows, 1)
        writer.write.assert_not_called()

    def test_administrative_units_malformed_next_link_fails_without_write(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-010", "name": "Administrative Units",
            "path": "/v1.0/directory/administrativeUnits", "pagination": True,
            "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([{
            "value": [{"id": "au-1"}], "@odata.nextLink": 17,
        }])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0

        summary = runtime.run(endpoint_id="G01-010")

        self.assertEqual(summary.runs[0].status, "ERROR")
        writer.write.assert_not_called()

    def test_conditional_access_policies_pagination_reaches_current_and_snapshot(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-011", "name": "Conditional Access Policies",
            "path": "/v1.0/identity/conditionalAccess/policies", "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([
            {"value": [{"id": "cap-1", "displayName": "One"}],
             "@odata.nextLink": "https://graph.example/v1.0/identity/conditionalAccess/policies?$skiptoken=next"},
            {"value": [{"id": "cap-2", "state": "disabled"}]},
        ])
        summary = runtime.run(endpoint_id="G01-011")
        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual(summary.runs[0].rows, 2)
        records = summary.normalized_runs[0].records
        self.assertEqual([record.current_row["source_object_id"] for record in records], ["cap-1", "cap-2"])
        self.assertTrue(all(record.snapshot_row is not None for record in records))

    def test_conditional_access_security_evidence_survives_real_handoff(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-011", "name": "Conditional Access Policies",
            "path": "/v1.0/identity/conditionalAccess/policies", "pagination": True,
            "enabled": True,
        }]))
        summary = self._runtime([{"value": [{
            "id": "cap-1", "displayName": "Legacy clients", "state": "enabled",
            "conditions": {"clientAppTypes": ["exchangeActiveSync", "other"]},
            "grantControls": {"builtInControls": ["block"]},
        }]}]).run(endpoint_id="G01-011")
        record = summary.normalized_runs[0].records[0]
        self.assertEqual(record.current_row["client_app_types"], ["exchangeActiveSync", "other"])
        self.assertEqual(record.current_row["grant_built_in_controls"], ["block"])
        self.assertTrue(record.current_row["security_evidence_complete"])
        self.assertEqual(record.snapshot_row["client_app_types"], record.current_row["client_app_types"])
        self.assertEqual(record.snapshot_row["grant_built_in_controls"], record.current_row["grant_built_in_controls"])

    def test_conditional_access_policies_empty_result_is_successful(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-011", "name": "Conditional Access Policies",
            "path": "/v1.0/identity/conditionalAccess/policies", "pagination": True,
            "enabled": True,
        }]))
        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-011")
        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_conditional_access_policies_malformed_later_page_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-011", "name": "Conditional Access Policies",
            "path": "/v1.0/identity/conditionalAccess/policies", "pagination": True,
            "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "cap-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/identity/conditionalAccess/policies?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0
        summary = runtime.run(endpoint_id="G01-011")
        self.assertEqual(summary.runs[0].status, "ERROR")
        writer.write.assert_not_called()

    def test_conditional_access_policies_malformed_next_link_fails_without_write(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-011", "name": "Conditional Access Policies",
            "path": "/v1.0/identity/conditionalAccess/policies", "pagination": True,
            "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([{"value": [{"id": "cap-1"}], "@odata.nextLink": 17}])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0
        summary = runtime.run(endpoint_id="G01-011")
        self.assertEqual(summary.runs[0].status, "ERROR")
        writer.write.assert_not_called()

    def test_named_locations_pagination_reaches_current_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-012", "name": "Conditional Access Named Locations",
            "path": "/v1.0/identity/conditionalAccess/namedLocations",
            "pagination": True, "enabled": True,
        }]))
        runtime = self._runtime([
            {"value": [{"id": "loc-1", "displayName": "One"}],
             "@odata.nextLink": "https://graph.example/v1.0/identity/conditionalAccess/namedLocations?$skiptoken=next"},
            {"value": [{"id": "loc-2", "displayName": "Two"}]},
        ])
        summary = runtime.run(endpoint_id="G01-012")
        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual(summary.runs[0].rows, 2)
        self.assertEqual(
            [record.current_row["source_object_id"] for record in summary.normalized_runs[0].records],
            ["loc-1", "loc-2"],
        )
        self.assertTrue(all(record.snapshot_row is None for record in summary.normalized_runs[0].records))

    def test_named_locations_empty_result_is_successful(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-012", "name": "Conditional Access Named Locations",
            "path": "/v1.0/identity/conditionalAccess/namedLocations",
            "pagination": True, "enabled": True,
        }]))
        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-012")
        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_named_locations_malformed_later_page_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-012", "name": "Conditional Access Named Locations",
            "path": "/v1.0/identity/conditionalAccess/namedLocations",
            "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "loc-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/identity/conditionalAccess/namedLocations?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0
        summary = runtime.run(endpoint_id="G01-012")
        self.assertEqual(summary.runs[0].status, "ERROR")
        writer.write.assert_not_called()

    def test_named_locations_malformed_next_link_fails_without_write(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-012", "name": "Conditional Access Named Locations",
            "path": "/v1.0/identity/conditionalAccess/namedLocations",
            "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([{"value": [{"id": "loc-1"}], "@odata.nextLink": 17}])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0
        summary = runtime.run(endpoint_id="G01-012")
        self.assertEqual(summary.runs[0].status, "ERROR")
        writer.write.assert_not_called()

    def test_subscribed_skus_pagination_reaches_current_and_snapshot_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-004",
            "name": "Subscribed SKUs",
            "workload": "Microsoft 365 Licensing",
            "path": "/v1.0/subscribedSkus",
            "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([
            {
                "value": [{
                    "id": "sku-1",
                    "skuId": "sku-id-1",
                    "skuPartNumber": "ENTERPRISE_E5",
                    "prepaidUnits": {"enabled": 10, "suspended": 1, "warning": 2},
                }],
                "@odata.nextLink": "https://graph.example/v1.0/subscribedSkus?$skiptoken=next",
            },
            {"value": [{"id": "sku-2", "consumedUnits": 4}]},
        ])

        summary = runtime.run(endpoint_id="G01-004")

        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual(summary.runs[0].rows, 2)
        records = summary.normalized_runs[0].records
        self.assertEqual([r.current_row["source_object_id"] for r in records], ["sku-1", "sku-2"])
        self.assertEqual(records[0].current_row["prepaid_units"], 13)
        self.assertIsNotNone(records[0].snapshot_row)

    def test_subscribed_skus_propagates_collection_run_to_current_and_snapshot(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-004", "name": "Subscribed SKUs",
            "workload": "Microsoft 365 Licensing", "path": "/v1.0/subscribedSkus",
            "pagination": True, "enabled": True,
        }]))
        summary = self._runtime([{"value": [{"id": "sku-1"}]}]).run(endpoint_id="G01-004")
        record = summary.normalized_runs[0].records[0]
        self.assertEqual(record.current_row["collection_run_id"], 100)
        self.assertEqual(record.snapshot_row["collection_run_id"], 100)

    def test_persisted_runtime_creates_run_when_lineage_is_missing(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-004", "name": "Subscribed SKUs",
            "workload": "Microsoft 365 Licensing", "path": "/v1.0/subscribedSkus",
            "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        writer.begin_collection_run.return_value = 321
        runtime = CollectorRuntime(
            self.inventory,
            dict_source({"GRAPH_TENANT_ID": "tenant-guid", "GRAPH_CLIENT_ID": "client-guid", "GRAPH_CLIENT_SECRET": "offline-secret"}),
            options=RuntimeOptions(
                http_open=lambda request, timeout=None: FakeResponse(
                    {"access_token": "offline-token", "expires_in": 3600}
                    if "login.microsoftonline.com" in request.full_url
                    else {"value": [{"id": "sku-1"}]}
                ),
                tenant_resolver=lambda config: 42,
                collection_writer=writer,
            ),
        )
        summary = runtime.run(endpoint_id="G01-004")
        record = summary.normalized_runs[0].records[0]
        writer.begin_collection_run.assert_called_once_with(tenant_id=42, endpoint_ids=["G01-004"])
        self.assertEqual(record.current_row["collection_run_id"], 321)
        self.assertEqual(record.snapshot_row["collection_run_id"], 321)

    def test_persisted_runtime_creates_endpoint_lineage_and_completes(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-004", "name": "Subscribed SKUs",
            "workload": "Microsoft 365 Licensing", "path": "/v1.0/subscribedSkus",
            "pagination": True, "enabled": True,
        }]))

        class Writer:
            def __init__(self):
                self.endpoint = []
                self.completed = []
                self.collections = []
            def begin_collection_run(self, **kwargs):
                return 41
            def begin_endpoint_run(self, **kwargs):
                self.endpoint.append(kwargs)
                return 77
            def write(self, normalized):
                self.completed.append(normalized.records[0].snapshot_row)
            def complete_endpoint_run(self, **kwargs):
                self.completed.append(kwargs["result"])
            def complete_collection_run(self, **kwargs):
                self.collections.append(kwargs)

        writer = Writer()
        runtime = CollectorRuntime(
            self.inventory,
            dict_source({
                "GRAPH_TENANT_ID": "tenant-guid", "GRAPH_CLIENT_ID": "client-guid",
                "GRAPH_CLIENT_SECRET": "offline-secret",
            }),
            options=RuntimeOptions(
                http_open=lambda request, timeout=None: FakeResponse(
                    {"access_token": "offline-token", "expires_in": 3600}
                    if "login.microsoftonline.com" in request.full_url
                    else {"value": [{"id": "sku-1"}]}
                ), tenant_resolver=lambda config: 42, collection_writer=writer,
            ),
        )
        runtime.options.collection_writer = writer
        summary = runtime.run(endpoint_id="G01-004")
        self.assertEqual(writer.endpoint[0]["collection_run_id"], 41)
        self.assertEqual(writer.endpoint[0]["spec"].endpoint_id, "G01-004")
        self.assertEqual(writer.completed[0]["collection_run_id"], 41)
        self.assertEqual(writer.completed[0]["endpoint_run_id"], 77)
        self.assertEqual(writer.completed[1].status, "PASS")
        self.assertEqual(writer.collections[0]["collection_run_id"], 41)
        self.assertEqual(summary.runs[0].status, "PASS")

    def test_persisted_runtime_without_run_lifecycle_fails_closed(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-004", "name": "Subscribed SKUs",
            "workload": "Microsoft 365 Licensing", "path": "/v1.0/subscribedSkus",
            "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock(spec=[])
        runtime = CollectorRuntime(
            self.inventory,
            dict_source({"GRAPH_TENANT_ID": "tenant-guid", "GRAPH_CLIENT_ID": "client-guid", "GRAPH_CLIENT_SECRET": "offline-secret"}),
            options=RuntimeOptions(
                http_open=lambda request, timeout=None: FakeResponse(
                    {"access_token": "offline-token", "expires_in": 3600}
                    if "login.microsoftonline.com" in request.full_url
                    else {"value": [{"id": "sku-1"}]}
                ),
                tenant_resolver=lambda config: 42,
                collection_writer=writer,
            ),
        )
        with self.assertRaisesRegex(RuntimeError_, "collection run context is required"):
            runtime.run(endpoint_id="G01-004")

    def test_subscribed_skus_malformed_record_fails_explicitly(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-004",
            "name": "Subscribed SKUs",
            "workload": "Microsoft 365 Licensing",
            "path": "/v1.0/subscribedSkus",
            "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([{"value": [{"skuId": "missing-id"}]}])

        with self.assertRaisesRegex(NormalizationError, "Normalization failed for G01-004: ValueError"):
            runtime.run(endpoint_id="G01-004")

    def test_directory_audit_pagination_reaches_event_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-005",
            "name": "Directory Audit Logs",
            "workload": "Microsoft Entra ID",
            "path": "/v1.0/auditLogs/directoryAudits",
            "pagination": True,
            "enabled": True,
        }]))
        runtime = self._runtime([
            {"value": [{"id": "audit-1", "activityDateTime": "2026-08-19T12:00:00Z"}],
             "@odata.nextLink": "https://graph.example/v1.0/auditLogs/directoryAudits?$skiptoken=next"},
            {"value": [{"id": "audit-2", "result": "success"}]},
        ])

        summary = runtime.run(endpoint_id="G01-005")
        self.assertEqual(summary.runs[0].pages, 2)
        records = summary.normalized_runs[0].records
        self.assertEqual([r.event_row["source_object_id"] for r in records], ["audit-1", "audit-2"])
        self.assertTrue(all(r.event_row["event_source"] == "DIRECTORY_AUDIT" for r in records))

    def test_directory_audit_malformed_record_fails_explicitly(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-005", "name": "Directory Audit Logs",
            "path": "/v1.0/auditLogs/directoryAudits", "pagination": True, "enabled": True,
        }]))
        runtime = self._runtime([{"value": [{"activityDateTime": "missing-id"}]}])
        with self.assertRaisesRegex(NormalizationError, "Normalization failed for G01-005: ValueError"):
            runtime.run(endpoint_id="G01-005")

    def test_directory_audit_later_page_failure_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-005", "name": "Directory Audit Logs",
            "path": "/v1.0/auditLogs/directoryAudits", "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "audit-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/auditLogs/directoryAudits?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0

        summary = runtime.run(endpoint_id="G01-005")
        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].rows, 1)
        writer.write.assert_not_called()

    def test_sign_in_pagination_reaches_event_normalizer(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-006", "name": "Sign-in Logs", "path": "/v1.0/auditLogs/signIns",
            "pagination": True, "enabled": True,
        }]))
        runtime = self._runtime([
            {"value": [{"id": "sign-1", "createdDateTime": "2026-08-19T12:00:00Z"}],
             "@odata.nextLink": "https://graph.example/v1.0/auditLogs/signIns?$skiptoken=next"},
            {"value": [{"id": "sign-2", "status": {"errorCode": 0}}]},
        ])
        summary = runtime.run(endpoint_id="G01-006")
        self.assertEqual(summary.runs[0].pages, 2)
        self.assertEqual([r.event_row["source_object_id"] for r in summary.normalized_runs[0].records], ["sign-1", "sign-2"])
        self.assertTrue(all(r.event_row["event_source"] == "SIGN_IN" for r in summary.normalized_runs[0].records))

    def test_sign_in_empty_result_is_successful_empty_normalization(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-006", "name": "Sign-in Logs", "path": "/v1.0/auditLogs/signIns",
            "pagination": True, "enabled": True,
        }]))
        summary = self._runtime([{"value": []}]).run(endpoint_id="G01-006")
        self.assertEqual(summary.runs[0].status, "PASS")
        self.assertEqual(summary.normalized_runs[0].records, [])

    def test_sign_in_malformed_later_page_does_not_write_partial_batch(self):
        self.inventory.write_text(json.dumps([{
            "id": "G01-006", "name": "Sign-in Logs", "path": "/v1.0/auditLogs/signIns",
            "pagination": True, "enabled": True,
        }]))
        writer = mock.Mock()
        runtime = self._runtime([
            {"value": [{"id": "sign-1"}],
             "@odata.nextLink": "https://graph.example/v1.0/auditLogs/signIns?$skiptoken=next"},
            {},
        ])
        runtime.options.collection_writer = writer
        runtime.options.max_retries = 0
        summary = runtime.run(endpoint_id="G01-006")
        self.assertEqual(summary.runs[0].status, "ERROR")
        self.assertEqual(summary.runs[0].rows, 1)
        writer.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
