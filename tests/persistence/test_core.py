"""Offline unit tests for the G09-R4A2a persistence core."""
from __future__ import annotations

import unittest
from copy import deepcopy

from collectors.core.runtime import NormalizedCollection
from collectors.persistence import (
    BoundSqlExecutor,
    CollectionWriter,
    PersistenceError,
    dispatch_persistence,
    write_current_record,
    write_event_record,
    persist_onedrive_high_value_audit_batch,
    write_onedrive_high_value_audit_batch,
    write_reference_record,
    write_snapshot_record,
    write_users_with_assignments,
)
from collectors.persistence.core import _jsonb_parameter
from collectors.workloads.models import NormalizedWorkloadRecord, PersistenceMode


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = connection.rowcount

    def execute(self, sql, parameters):
        self.connection.statements.append((sql, parameters))

class FakeConnection:
    def __init__(self, rowcount=1):
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.rowcount = rowcount

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def collection(records, endpoint_id="G01-001"):
    return NormalizedCollection(
        endpoint_id=endpoint_id,
        workload="Entra ID",
        data_domain="identity",
        collection_timestamp=None,
        tenant_id=7,
        source_metadata={},
        records=records,
    )


class PersistenceCoreTests(unittest.TestCase):
    def test_endpoint_classification_matrix_uses_closed_runtime_vocabulary(self):
        from collectors.core.errors import CLASSIFICATIONS

        for classification in CLASSIFICATIONS:
            connection = FakeConnection()
            result = type("Result", (), {
                "status": "PASS" if classification == "PASS" else "ERROR",
                "pages": 0, "rows": 0, "http_status": None,
                "error_classification": classification, "retry_count": 0,
                "graph_error_code": None,
            })()
            CollectionWriter(connection).complete_endpoint_run(endpoint_run_id=9, result=result)
            self.assertEqual(connection.statements[0][1][5], classification)
            self.assertEqual(connection.statements[0][1][6], None if classification == "PASS" else classification)

        connection = FakeConnection()
        result = type("Result", (), {
            "status": "ERROR", "pages": 0, "rows": 0, "http_status": None,
            "error_classification": "SOMETHING_RANDOM", "retry_count": 0,
            "graph_error_code": None,
        })()
        with self.assertRaises(PersistenceError):
            CollectionWriter(connection).complete_endpoint_run(endpoint_run_id=9, result=result)
        self.assertEqual(connection.statements, [])

    def test_identity_unavailable_endpoint_is_terminal_and_sanitized(self):
        connection = FakeConnection()
        result = type("Result", (), {
            "status": "ERROR", "pages": 1, "rows": 0, "http_status": 200,
            "error_classification": "ENTITY_IDENTITY_UNAVAILABLE", "retry_count": 0,
            "graph_error_code": None,
        })()

        CollectionWriter(connection).complete_endpoint_run(endpoint_run_id=9, result=result)

        sql, parameters = connection.statements[0]
        self.assertIn("status = %s", sql)
        self.assertEqual(parameters[1], "ERROR")
        self.assertEqual(parameters[5], "ENTITY_IDENTITY_UNAVAILABLE")
        self.assertEqual(parameters[6], "ENTITY_IDENTITY_UNAVAILABLE")
        self.assertEqual(connection.commits, 1)

    def test_collection_mixed_results_are_partial_success(self):
        connection = FakeConnection()
        result = lambda endpoint_id, status, classification=None: type("Result", (), {
            "endpoint_id": endpoint_id, "status": status, "rows": 1 if status == "PASS" else 0,
            "error_classification": classification,
        })()

        CollectionWriter(connection).complete_collection_run(
            collection_run_id=5,
            results=[result("USAGE-001", "PASS"), result("USAGE-007", "ERROR", "ENTITY_IDENTITY_UNAVAILABLE")],
        )

        self.assertEqual(connection.statements[0][1][1], "PARTIAL_SUCCESS")
        self.assertEqual(connection.statements[0][1][2:4], (1, 1))
        self.assertEqual(connection.statements[0][1][5].obj, {"failed_endpoints": ["USAGE-007"]})

    def test_collection_failure_metadata_adapts_simple_dict_to_jsonb(self):
        connection = FakeConnection()
        result = type("Result", (), {"endpoint_id": "USAGE-007", "status": "ERROR", "rows": 0})()

        CollectionWriter(connection).complete_collection_run(collection_run_id=5, results=[result])

        parameters = connection.statements[0][1]
        self.assertEqual(parameters[5].obj, {"failed_endpoints": ["USAGE-007"]})
        self.assertNotIn("USAGE-007", connection.statements[0][0])

    def test_collection_failure_metadata_adapts_nested_jsonb_values(self):
        metadata = _jsonb_parameter({
            "failed_endpoints": ["USAGE-007"],
            "details": {"retryable": False, "attempts": [1, None, True]},
        })
        self.assertEqual(metadata.obj, {
            "failed_endpoints": ["USAGE-007"],
            "details": {"retryable": False, "attempts": [1, None, True]},
        })
        self.assertIsInstance(metadata.obj["details"]["attempts"], list)

    def test_empty_jsonb_metadata_is_valid(self):
        self.assertEqual(_jsonb_parameter({}).obj, {})

    def test_collection_success_has_valid_null_jsonb_metadata(self):
        connection = FakeConnection()
        result = type("Result", (), {"endpoint_id": "USAGE-001", "status": "PASS", "rows": 1})()

        CollectionWriter(connection).complete_collection_run(collection_run_id=5, results=[result])

        self.assertIsNone(connection.statements[0][1][5])

    def test_collection_completion_can_be_repeated(self):
        connection = FakeConnection()
        result = type("Result", (), {"endpoint_id": "USAGE-001", "status": "PASS", "rows": 1})()
        writer = CollectionWriter(connection)

        writer.complete_collection_run(collection_run_id=5, results=[result])
        writer.complete_collection_run(collection_run_id=5, results=[result])

        self.assertEqual(len(connection.statements), 2)
        self.assertEqual(connection.commits, 2)

    def test_collection_all_error_results_are_failed(self):
        connection = FakeConnection()
        result = type("Result", (), {"endpoint_id": "USAGE-007", "status": "ERROR", "rows": 0})()

        CollectionWriter(connection).complete_collection_run(collection_run_id=5, results=[result])

        self.assertEqual(connection.statements[0][1][1], "FAILED")

    def test_collection_all_success_results_are_success(self):
        connection = FakeConnection()
        result = type("Result", (), {"endpoint_id": "USAGE-001", "status": "PASS", "rows": 1})()

        CollectionWriter(connection).complete_collection_run(collection_run_id=5, results=[result])

        self.assertEqual(connection.statements[0][1][1], "SUCCESS")
    def test_user_assignment_refresh_is_bounded_and_idempotent(self):
        connection = FakeConnection()
        rows = []
        for user_id, skus in (("u-1", ["sku-1", "sku-2"]), ("u-2", ["sku-1"]), ("u-3", [])):
            row = {
                "tenant_id": 7, "source_object_id": user_id,
                "user_principal_name": None, "display_name": None, "user_type": "Member",
                "account_enabled": user_id != "u-2", "created_date_time": None,
                "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "REFERENCE",
                "_assigned_licenses_available": True, "_assigned_licenses": skus,
            }
            rows.append(NormalizedWorkloadRecord("G01-001", PersistenceMode.CURRENT, current_row=row))
        write_users_with_assignments(BoundSqlExecutor(connection), rows)
        sql = [statement[0] for statement in connection.statements]
        self.assertEqual(sql[0], "DELETE FROM core.user_license_assignment WHERE tenant_id = %s")
        self.assertEqual(sum("INSERT INTO core.user_license_assignment" in item for item in sql), 3)
        self.assertTrue(any("JOIN core.subscribed_sku" in item for item in sql))

    def test_user_assignment_refresh_preserves_existing_set_when_property_missing(self):
        connection = FakeConnection()
        row = {"tenant_id": 7, "source_object_id": "u-1", "last_observed_at": "now",
               "user_principal_name": None, "display_name": None, "user_type": None,
               "account_enabled": False, "created_date_time": None, "retention_class": "REFERENCE",
               "_assigned_licenses_available": False, "_assigned_licenses": None}
        write_users_with_assignments(BoundSqlExecutor(connection), [
            NormalizedWorkloadRecord("G01-001", PersistenceMode.CURRENT, current_row=row)
        ])
        self.assertFalse(any("DELETE FROM core.user_license_assignment" in item[0] for item in connection.statements))

    def test_snapshot_writes_current_and_idempotent_snapshot(self):
        connection = FakeConnection()
        current = {"tenant_id": 7, "source_object_id": "sku-1", "sku_id": "sku", "sku_part_number": "P1", "capability_status": "Enabled", "consumed_units": 1, "prepaid_units": 2, "service_plans": [], "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "STANDARD"}
        snapshot = {"tenant_id": 7, "source_object_id": "sku-1", "collection_run_id": 9, "endpoint_run_id": 10, "snapshot_at": "2026-01-02T00:00:00Z", "consumed_units": 1, "prepaid_units": 2, "capability_status": "Enabled", "service_plans": [], "retention_class": "STANDARD"}
        record = NormalizedWorkloadRecord("G01-004", PersistenceMode.CURRENT_WITH_SNAPSHOT, current_row=current, snapshot_row=snapshot)
        write_snapshot_record(BoundSqlExecutor(connection), record)
        write_snapshot_record(BoundSqlExecutor(connection), record)
        self.assertEqual(len(connection.statements), 4)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id) DO UPDATE", connection.statements[0][0])
        self.assertIn("ON CONFLICT (tenant_id, source_object_id, collection_run_id) DO NOTHING", connection.statements[1][0])
        self.assertEqual(connection.statements[1][0], connection.statements[3][0])
        self.assertEqual(connection.statements[1][1][:-2], connection.statements[3][1][:-2])
        self.assertEqual(connection.statements[1][1][-2].obj, connection.statements[3][1][-2].obj)
        self.assertNotIn("sku-1", connection.statements[1][0])
        self.assertEqual(current["source_object_id"], "sku-1")

    def test_snapshot_requires_lineage(self):
        connection = FakeConnection()
        with self.assertRaises(PersistenceError):
            write_snapshot_record(BoundSqlExecutor(connection), NormalizedWorkloadRecord("G01-004", PersistenceMode.CURRENT_WITH_SNAPSHOT, current_row={}, snapshot_row={}))
        self.assertEqual(connection.statements, [])

    def test_g01_001_current_statement_and_parameters(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 7, "source_object_id": "user-1",
            "user_principal_name": "user@example.test", "display_name": "User",
            "user_type": "Member", "account_enabled": True,
            "created_date_time": "2026-01-01T00:00:00Z",
            "last_observed_at": "2026-01-02T00:00:00Z",
            "retention_class": "REFERENCE", "ignored": "not persisted",
        }

        write_current_record(
            BoundSqlExecutor(connection),
            NormalizedWorkloadRecord("G01-001", PersistenceMode.CURRENT, current_row=row),
        )

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            'INSERT INTO core."user" (tenant_id, source_object_id, user_principal_name, '
            'display_name, user_type, account_enabled, created_date_time, last_observed_at, '
            'retention_class) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) '
            'ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET '
            'user_principal_name = EXCLUDED.user_principal_name, '
            'display_name = EXCLUDED.display_name, user_type = EXCLUDED.user_type, '
            'account_enabled = EXCLUDED.account_enabled, '
            'created_date_time = EXCLUDED.created_date_time, '
            'last_observed_at = EXCLUDED.last_observed_at, '
            'retention_class = EXCLUDED.retention_class',
        )
        self.assertEqual(parameters, (7, "user-1", "user@example.test", "User", "Member", True,
                                      "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "REFERENCE"))
        self.assertEqual(row["ignored"], "not persisted")

    def test_g01_002_current_statement_and_parameters(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 8, "source_object_id": "group-1", "display_name": "Group",
            "mail": "group@example.test", "mail_enabled": True, "security_enabled": False,
            "group_types": ["Unified"], "last_observed_at": "2026-01-02T00:00:00Z",
            "client_app_types": ["browser"], "grant_built_in_controls": [],
            "security_evidence_complete": True, "retention_class": "REFERENCE",
        }

        write_current_record(
            BoundSqlExecutor(connection),
            NormalizedWorkloadRecord("G01-002", PersistenceMode.CURRENT, current_row=row),
        )

        sql, parameters = connection.statements[0]
        self.assertIn('INSERT INTO core."group"', sql)
        self.assertIn('ON CONFLICT (tenant_id, source_object_id) DO UPDATE', sql)
        self.assertEqual(parameters, (8, "group-1", "Group", "group@example.test", True, False,
                                      ["Unified"], "2026-01-02T00:00:00Z", "REFERENCE"))

    def test_g01_003_current_statement_parameters_and_replay_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 9, "source_object_id": "organization-1",
            "display_name": "Example", "country_letter_code": "US",
            "tenant_type": "AAD", "verified_domains": [{"name": "example.test"}],
            "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "REFERENCE",
            "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord("G01-003", PersistenceMode.CURRENT, current_row=row)
        original_row = deepcopy(row)

        write_current_record(BoundSqlExecutor(connection), record)
        write_current_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.organization (tenant_id, source_object_id, display_name, "
            "country_letter_code, tenant_type, verified_domains, last_observed_at, "
            "retention_class) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id) DO UPDATE SET "
            "source_object_id = EXCLUDED.source_object_id, "
            "display_name = EXCLUDED.display_name, "
            "country_letter_code = EXCLUDED.country_letter_code, "
            "tenant_type = EXCLUDED.tenant_type, "
            "verified_domains = EXCLUDED.verified_domains, "
            "last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
        )
        self.assertEqual(
            parameters,
            (9, "organization-1", "Example", "US", "AAD", [{"name": "example.test"}],
             "2026-01-02T00:00:00Z", "REFERENCE"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_g01_007_current_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 10, "source_object_id": "application-1",
            "app_id": "11111111-1111-1111-1111-111111111111", "display_name": "Example App",
            "sign_in_audience": "AzureADMyOrg",
            "created_date_time": "2026-01-01T00:00:00Z",
            "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "REFERENCE",
            "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord(
            "G01-007", PersistenceMode.CURRENT, current_row=row
        )
        original_row = deepcopy(row)

        write_current_record(BoundSqlExecutor(connection), record)
        write_current_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.application (tenant_id, source_object_id, app_id, display_name, "
            "sign_in_audience, created_date_time, last_observed_at, retention_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET "
            "app_id = EXCLUDED.app_id, display_name = EXCLUDED.display_name, "
            "sign_in_audience = EXCLUDED.sign_in_audience, "
            "created_date_time = EXCLUDED.created_date_time, "
            "last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
        )
        self.assertEqual(
            parameters,
            (10, "application-1", "11111111-1111-1111-1111-111111111111", "Example App",
             "AzureADMyOrg", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "REFERENCE"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_g01_008_current_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 11, "source_object_id": "service-principal-1",
            "app_id": "22222222-2222-2222-2222-222222222222", "display_name": "Example SP",
            "account_enabled": True, "service_principal_type": "Application",
            "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "REFERENCE",
            "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord(
            "G01-008", PersistenceMode.CURRENT, current_row=row
        )
        original_row = deepcopy(row)

        write_current_record(BoundSqlExecutor(connection), record)
        write_current_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.service_principal (tenant_id, source_object_id, app_id, "
            "display_name, account_enabled, service_principal_type, last_observed_at, "
            "retention_class) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET "
            "app_id = EXCLUDED.app_id, display_name = EXCLUDED.display_name, "
            "account_enabled = EXCLUDED.account_enabled, "
            "service_principal_type = EXCLUDED.service_principal_type, "
            "last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
        )
        self.assertEqual(
            parameters,
            (11, "service-principal-1", "22222222-2222-2222-2222-222222222222", "Example SP",
             True, "Application", "2026-01-02T00:00:00Z", "REFERENCE"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_g01_009_current_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 12, "source_object_id": "device-1",
            "device_graph_id": "33333333-3333-3333-3333-333333333333",
            "account_enabled": True, "operating_system": "Windows",
            "operating_system_version": "11", "trust_type": "AzureAD",
            "approximate_last_sign_in_date_time": "2026-01-01T00:00:00Z",
            "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "REFERENCE",
            "collection_run_id": 99, "endpoint_run_id": 100, "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord("G01-009", PersistenceMode.CURRENT, current_row=row)
        original_row = deepcopy(row)

        write_current_record(BoundSqlExecutor(connection), record)
        write_current_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.device (tenant_id, source_object_id, device_graph_id, "
            "account_enabled, operating_system, operating_system_version, trust_type, "
            "approximate_last_sign_in_date_time, last_observed_at, retention_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET "
            "device_graph_id = EXCLUDED.device_graph_id, "
            "account_enabled = EXCLUDED.account_enabled, "
            "operating_system = EXCLUDED.operating_system, "
            "operating_system_version = EXCLUDED.operating_system_version, "
            "trust_type = EXCLUDED.trust_type, "
            "approximate_last_sign_in_date_time = EXCLUDED.approximate_last_sign_in_date_time, "
            "last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
        )
        self.assertEqual(
            parameters,
            (12, "device-1", "33333333-3333-3333-3333-333333333333", True, "Windows",
             "11", "AzureAD", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "REFERENCE"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_g01_010_current_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 13, "source_object_id": "administrative-unit-1",
            "display_name": "Headquarters", "description": "HQ staff",
            "visibility": "Hidden", "last_observed_at": "2026-01-02T00:00:00Z",
            "retention_class": "REFERENCE", "collection_run_id": 99,
            "endpoint_run_id": 100, "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord(
            "G01-010", PersistenceMode.CURRENT, current_row=row
        )
        original_row = deepcopy(row)

        write_current_record(BoundSqlExecutor(connection), record)
        write_current_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.administrative_unit (tenant_id, source_object_id, display_name, "
            "description, visibility, last_observed_at, retention_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET "
            "display_name = EXCLUDED.display_name, description = EXCLUDED.description, "
            "visibility = EXCLUDED.visibility, last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
        )
        self.assertEqual(
            parameters,
            (13, "administrative-unit-1", "Headquarters", "HQ staff", "Hidden",
             "2026-01-02T00:00:00Z", "REFERENCE"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_g01_012_current_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 14, "source_object_id": "named-location-1",
            "display_name": "Headquarters", "created_date_time": "2026-01-01T00:00:00Z",
            "modified_date_time": "2026-01-02T00:00:00Z",
            "last_observed_at": "2026-01-03T00:00:00Z", "retention_class": "REFERENCE",
            "collection_run_id": 99, "endpoint_run_id": 100, "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord(
            "G01-012", PersistenceMode.CURRENT, current_row=row
        )
        original_row = deepcopy(row)

        write_current_record(BoundSqlExecutor(connection), record)
        write_current_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.named_location (tenant_id, source_object_id, display_name, "
            "created_date_time, modified_date_time, last_observed_at, retention_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET "
            "display_name = EXCLUDED.display_name, "
            "created_date_time = EXCLUDED.created_date_time, "
            "modified_date_time = EXCLUDED.modified_date_time, "
            "last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
        )
        self.assertEqual(
            parameters,
            (14, "named-location-1", "Headquarters", "2026-01-01T00:00:00Z",
             "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z", "REFERENCE"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_current_writer_rejects_unsupported_endpoint_without_execution(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-999", PersistenceMode.CURRENT, current_row={}
        )

        with self.assertRaisesRegex(PersistenceError, "Unsupported CURRENT endpoint: G01-999"):
            write_current_record(BoundSqlExecutor(connection), record)

        self.assertEqual(connection.statements, [])

    def test_g01_018_reference_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 18, "source_object_id": "role-definition-1",
            "display_name": "Global Administrator", "description": "Full access",
            "is_built_in": True, "last_observed_at": "2026-01-02T00:00:00Z",
            "retention_class": "REFERENCE", "role_permissions": [{"ignored": True}],
            "collection_run_id": 99, "endpoint_run_id": 100,
        }
        record = NormalizedWorkloadRecord(
            "G01-018", PersistenceMode.REFERENCE, current_row=row, reference_row=row
        )
        original_row = deepcopy(row)

        write_reference_record(BoundSqlExecutor(connection), record)
        write_reference_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.directory_role_definition (tenant_id, source_object_id, "
            "display_name, description, is_built_in, last_observed_at, retention_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, source_object_id) DO UPDATE SET "
            "display_name = EXCLUDED.display_name, description = EXCLUDED.description, "
            "is_built_in = EXCLUDED.is_built_in, "
            "last_observed_at = EXCLUDED.last_observed_at, "
            "retention_class = EXCLUDED.retention_class",
        )
        self.assertEqual(
            parameters,
            (18, "role-definition-1", "Global Administrator", "Full access", True,
             "2026-01-02T00:00:00Z", "REFERENCE"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_reference_writer_rejects_unsupported_endpoint_without_execution(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-999", PersistenceMode.REFERENCE, reference_row={}
        )

        with self.assertRaisesRegex(PersistenceError, "Unsupported REFERENCE endpoint: G01-999"):
            write_reference_record(BoundSqlExecutor(connection), record)

        self.assertEqual(connection.statements, [])

    def test_onedrive_high_value_audit_batch_is_idempotent_and_parameter_bound(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 7, "audit_record_id": "audit-1", "event_time": "2026-01-01T00:00:00Z",
            "operation": "SharingSet", "workload": "OneDrive",
            "actor_upn": "actor@example.test", "event_category": "EXTERNAL_SHARING",
            "external_flag": True, "anonymous_flag": False, "collected_at": "2026-01-01T00:01:00Z",
            "target_user_or_group_type": "Guest", "retention_class": "LONG",
        }
        write_onedrive_high_value_audit_batch(BoundSqlExecutor(connection), [row, row], trusted_tenant_id=7)
        self.assertEqual(len(connection.statements), 2)
        self.assertIn("ON CONFLICT (tenant_id, audit_record_id) DO NOTHING", connection.statements[0][0])
        self.assertNotIn("audit-1", connection.statements[0][0])
        self.assertEqual(connection.statements[0], connection.statements[1])

    def test_onedrive_high_value_audit_batch_rejects_unknown_or_internal_classification_before_sql(self):
        connection = FakeConnection()
        row = {"tenant_id": 7, "audit_record_id": "audit-1", "event_time": "now", "operation": "SharingSet",
               "workload": "OneDrive", "record_type": "SharePoint", "actor_upn": "actor",
               "event_category": "EXTERNAL_SHARING", "external_flag": True, "anonymous_flag": False,
               "collected_at": "now", "target_user_or_group_type": "Member"}
        with self.assertRaises(PersistenceError):
            write_onedrive_high_value_audit_batch(BoundSqlExecutor(connection), [row], trusted_tenant_id=7)
        self.assertEqual(connection.statements, [])

    def test_onedrive_high_value_audit_batch_rejects_mixed_tenant_before_sql(self):
        connection = FakeConnection()
        row = {"tenant_id": 8, "audit_record_id": "audit-1", "event_time": "now", "operation": "AnonymousLinkCreated",
               "workload": "OneDrive", "record_type": "SharePoint", "actor_upn": "actor",
               "event_category": "EXTERNAL_SHARING", "external_flag": True, "anonymous_flag": True,
               "collected_at": "now"}
        with self.assertRaises(PersistenceError):
            write_onedrive_high_value_audit_batch(BoundSqlExecutor(connection), [row], trusted_tenant_id=7)
        self.assertEqual(connection.statements, [])

    def test_g01_005_event_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 5, "event_source": "DIRECTORY_AUDIT", "source_object_id": "audit-1",
            "event_at": "2026-01-01T00:00:00Z", "collected_at": "2026-01-01T00:01:00Z",
            "collection_run_id": 50, "endpoint_run_id": 51, "actor_user_id": "Directory",
            "actor_app_id": None, "activity": "Update user", "category": "UserManagement",
            "result": "success", "is_interactive": None, "risk_level": None, "extension": None,
            "retention_class": "LONG", "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord("G01-005", PersistenceMode.EVENT, event_row=row)
        original_row = deepcopy(row)

        write_event_record(BoundSqlExecutor(connection), record)
        write_event_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.audit_event (tenant_id, event_source, source_object_id, event_at, "
            "collected_at, collection_run_id, endpoint_run_id, actor_user_id, actor_app_id, "
            "activity, category, result, is_interactive, risk_level, extension, retention_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, event_source, source_object_id) DO NOTHING",
        )
        self.assertEqual(
            parameters,
            (5, "DIRECTORY_AUDIT", "audit-1", "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z",
             50, 51, "Directory", None, "Update user", "UserManagement", "success", None, None,
             None, "LONG"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_event_writer_rejects_spoofed_registered_source_without_execution(self):
        connection = FakeConnection()
        row = {"tenant_id": 5, "event_source": "SIGN_IN"}
        record = NormalizedWorkloadRecord("G01-005", PersistenceMode.EVENT, event_row=row)

        with self.assertRaisesRegex(PersistenceError, "EVENT source does not match endpoint G01-005"):
            write_event_record(BoundSqlExecutor(connection), record)

        self.assertEqual(connection.statements, [])

    def test_event_writer_rejects_unknown_endpoint_without_execution(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord("G01-999", PersistenceMode.EVENT, event_row={})

        with self.assertRaisesRegex(PersistenceError, "Unsupported EVENT endpoint: G01-999"):
            write_event_record(BoundSqlExecutor(connection), record)

        self.assertEqual(connection.statements, [])

    def test_g01_014_event_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 5, "source_object_id": "risk-1",
            "detected_at": "2026-01-01T00:00:00Z", "activity_at": "2026-01-01T00:01:00Z",
            "collected_at": "2026-01-01T00:02:00Z",
            "collection_run_id": 50, "endpoint_run_id": 51, "risk_event_type": "leakedCredentials",
            "risk_level": "high", "risk_state": "atRisk", "risk_detail": "adminConfirmedHigh",
            "detection_timing_type": "realtime", "activity": "sign-in", "affected_user_id": "user-1",
            "retention_class": "LONG", "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord("G01-014", PersistenceMode.EVENT, event_row=row)
        original_row = deepcopy(row)

        write_event_record(BoundSqlExecutor(connection), record)
        write_event_record(BoundSqlExecutor(connection), record)

        self.assertEqual(len(connection.statements), 2)
        sql, parameters = connection.statements[0]
        self.assertEqual(sql, connection.statements[1][0])
        self.assertEqual(parameters, connection.statements[1][1])
        
        self.assertIn("INSERT INTO core.risk_detection", sql)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id) DO NOTHING", sql)
        
        # Check all params are bound in correct order.
        self.assertEqual(parameters, (
            5, "risk-1", "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z", "2026-01-01T00:02:00Z",
            50, 51, "leakedCredentials", "high", "atRisk", "adminConfirmedHigh", "realtime", "sign-in", "user-1", "LONG"
        ))

        self.assertEqual(row, original_row)

    def test_event_writer_rejects_unsupported_endpoint_without_execution(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord("G01-999", PersistenceMode.EVENT, event_row={})

        with self.assertRaisesRegex(PersistenceError, "Unsupported EVENT endpoint: G01-999"):
            write_event_record(BoundSqlExecutor(connection), record)

        self.assertEqual(connection.statements, [])

    def test_g01_006_event_statement_parameters_replay_and_source_are_deterministic(self):
        connection = FakeConnection()
        row = {
            "tenant_id": 5, "event_source": "SIGN_IN", "source_object_id": "signin-1",
            "event_at": "2026-01-01T00:00:00Z", "collected_at": "2026-01-01T00:01:00Z",
            "collection_run_id": 50, "endpoint_run_id": 51, "actor_user_id": "user-1",
            "actor_app_id": "app-1", "activity": "Office 365", "category": "0",
            "result": "MFA requirement satisfied by claim in the token", "is_interactive": True,
            "risk_level": None, "extension": None,
            "retention_class": "LONG", "ignored": "not persisted",
        }
        record = NormalizedWorkloadRecord("G01-006", PersistenceMode.EVENT, event_row=row)
        original_row = deepcopy(row)

        write_event_record(BoundSqlExecutor(connection), record)
        write_event_record(BoundSqlExecutor(connection), record)

        sql, parameters = connection.statements[0]
        self.assertEqual(
            sql,
            "INSERT INTO core.audit_event (tenant_id, event_source, source_object_id, event_at, "
            "collected_at, collection_run_id, endpoint_run_id, actor_user_id, actor_app_id, "
            "activity, category, result, is_interactive, risk_level, extension, retention_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id, event_source, source_object_id) DO NOTHING",
        )
        self.assertEqual(
            parameters,
            (5, "SIGN_IN", "signin-1", "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z",
             50, 51, "user-1", "app-1", "Office 365", "0",
             "MFA requirement satisfied by claim in the token", True, None, None, "LONG"),
        )
        self.assertEqual(connection.statements[0], connection.statements[1])
        self.assertEqual(row, original_row)

    def test_g01_006_event_row_missing_required_columns_fails_closed(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-006", PersistenceMode.EVENT,
            event_row={"tenant_id": 5, "event_source": "SIGN_IN"},
        )

        with self.assertRaisesRegex(PersistenceError, "EVENT row is missing required columns"):
            write_event_record(BoundSqlExecutor(connection), record)

        self.assertEqual(connection.statements, [])

    def test_collection_writer_accepts_matching_tenant(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-001", PersistenceMode.CURRENT,
            current_row={"tenant_id": 7},
        )
        writes = []

        def write(executor, normalized_record):
            writes.append(normalized_record)

        CollectionWriter(connection, write).write(collection([record]))
        self.assertEqual(writes, [record])
        self.assertEqual(connection.commits, 1)

    def test_collection_writer_rejects_missing_record_tenant_before_writer(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-001", PersistenceMode.CURRENT,
            current_row={},
        )
        writer_called = False

        def write(executor, normalized_record):
            nonlocal writer_called
            writer_called = True

        with self.assertRaisesRegex(PersistenceError, "missing or malformed"):
            CollectionWriter(connection, write).write(collection([record]))
        self.assertFalse(writer_called)
        self.assertEqual(connection.statements, [])
        self.assertEqual(connection.rollbacks, 0)

    def test_collection_writer_rejects_mismatched_record_tenant_before_sql(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-001", PersistenceMode.CURRENT,
            current_row={"tenant_id": 8},
        )
        writer_called = False

        def write(executor, normalized_record):
            nonlocal writer_called
            writer_called = True

        with self.assertRaisesRegex(PersistenceError, "does not match"):
            CollectionWriter(connection, write).write(collection([record]))
        self.assertFalse(writer_called)
        self.assertEqual(connection.statements, [])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 0)

    def test_collection_writer_rejects_missing_trusted_tenant_before_sql(self):
        connection = FakeConnection()
        normalized = collection([])
        normalized.tenant_id = None
        with self.assertRaisesRegex(PersistenceError, "trusted tenant_id"):
            CollectionWriter(connection).write(normalized)
        self.assertEqual(connection.statements, [])

    def test_successful_collection_commits_once_through_injected_connection(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord("G01-001", PersistenceMode.CURRENT)

        def write(executor, normalized_record):
            self.assertIs(normalized_record, record)
            executor.execute("INSERT INTO ignored VALUES (%s)", ("bound",))

        CollectionWriter(connection, write).write(collection([record]))

        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(connection.statements, [
            ("BEGIN", ()),
            ("INSERT INTO ignored VALUES (%s)", ("bound",)),
        ])

    def test_record_writer_exception_rolls_back_once_without_commit(self):
        connection = FakeConnection()

        def fail_writer(executor, normalized_record):
            raise RuntimeError("write failed")

        with self.assertRaisesRegex(RuntimeError, "write failed"):
            CollectionWriter(connection, fail_writer).write(
                collection([NormalizedWorkloadRecord("G01-001", PersistenceMode.CURRENT)])
            )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_zero_record_collection_commits_without_dml(self):
        connection = FakeConnection()
        CollectionWriter(connection).write(collection([]))

        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(connection.statements, [("BEGIN", ())])

    def test_orphaned_collection_run_recovery_is_conditional_and_terminal(self):
        connection = FakeConnection()

        CollectionWriter(connection).recover_orphaned_collection_run(collection_run_id=1)

        sql, parameters = connection.statements[0]
        self.assertIn("status = 'FAILED'", sql)
        self.assertIn("AND status = 'RUNNING'", sql)
        self.assertEqual(parameters[1].obj, {"classification": "LEGACY_STALE_ORPHAN"})
        self.assertEqual(parameters[2], 1)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)

    def test_orphaned_collection_run_recovery_fails_closed_when_not_running(self):
        connection = FakeConnection(rowcount=0)

        with self.assertRaisesRegex(PersistenceError, "exactly one RUNNING row"):
            CollectionWriter(connection).recover_orphaned_collection_run(collection_run_id=1)

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_orphaned_collection_run_recovery_rejects_malformed_id(self):
        connection = FakeConnection()

        with self.assertRaisesRegex(PersistenceError, "missing or malformed"):
            CollectionWriter(connection).recover_orphaned_collection_run(collection_run_id=True)

        self.assertEqual(connection.statements, [])

    def test_collection_writer_persists_current_and_snapshot_as_one_flow(self):
        connection = FakeConnection()
        current = {"tenant_id": 7, "source_object_id": "sku-1", "sku_id": "sku", "sku_part_number": "P1", "capability_status": "Enabled", "consumed_units": 1, "prepaid_units": 2, "service_plans": [], "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "STANDARD"}
        snapshot = {"tenant_id": 7, "source_object_id": "sku-1", "collection_run_id": 9, "endpoint_run_id": 10, "snapshot_at": "2026-01-02T00:00:00Z", "consumed_units": 1, "prepaid_units": 2, "capability_status": "Enabled", "service_plans": [], "retention_class": "STANDARD"}
        record = NormalizedWorkloadRecord("G01-004", PersistenceMode.CURRENT_WITH_SNAPSHOT, current_row=current, snapshot_row=snapshot)

        CollectionWriter(connection, write_snapshot_record).write(collection([record], "G01-004"))

        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(connection.statements[0], ("BEGIN", ()))
        self.assertIn("core.subscribed_sku", connection.statements[1][0])
        self.assertIn("core.subscribed_sku_snapshot", connection.statements[2][0])

    def test_snapshot_endpoints_use_tenant_object_and_run_idempotency_key(self):
        fields = {
            "G01-004": {"sku_id": "sku", "sku_part_number": "P1", "capability_status": "Enabled", "consumed_units": 1, "prepaid_units": 2, "service_plans": []},
            "G01-011": {"display_name": "Policy", "state": "enabled", "created_date_time": None, "modified_date_time": None, "client_app_types": ["browser"], "grant_built_in_controls": [], "security_evidence_complete": True},
            "G01-013": {"risk_level": "high", "risk_state": "atRisk", "risk_detail": None, "is_deleted": False, "is_processing": False, "risk_last_updated_at": None},
            "G01-015": {"service": "Exchange", "status": "good"},
            "G01-019": {"role_definition_id": "role", "principal_id": "principal", "directory_scope_id": "/"},
        }
        for endpoint_id, extra in fields.items():
            connection = FakeConnection()
            current = {"tenant_id": 7, "source_object_id": endpoint_id, **extra, "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "STANDARD"}
            snapshot = {key: value for key, value in current.items() if key != "last_observed_at"}
            snapshot.update({"collection_run_id": 9, "endpoint_run_id": 10, "snapshot_at": "2026-01-02T00:00:00Z"})
            record = NormalizedWorkloadRecord(endpoint_id, PersistenceMode.CURRENT_WITH_SNAPSHOT, current_row=current, snapshot_row=snapshot)
            write_snapshot_record(BoundSqlExecutor(connection), record)
            write_snapshot_record(BoundSqlExecutor(connection), record)
            self.assertEqual(len(connection.statements), 4)
            self.assertIn("ON CONFLICT (tenant_id, source_object_id)", connection.statements[0][0])
            self.assertIn("ON CONFLICT (tenant_id, source_object_id, collection_run_id) DO NOTHING", connection.statements[1][0])
            self.assertEqual(connection.statements[1][0], connection.statements[3][0])
            self.assertEqual(connection.statements[1][1][:-2], connection.statements[3][1][:-2])
            if endpoint_id == "G01-004":
                self.assertEqual(connection.statements[1][1][-2].obj, connection.statements[3][1][-2].obj)
            else:
                self.assertEqual(connection.statements[1][1][-2:], connection.statements[3][1][-2:])

    def test_g01_011_current_and_snapshot_sql_is_closed_and_parameter_bound(self):
        connection = FakeConnection()
        current = {
            "tenant_id": 7, "source_object_id": "cap-1", "display_name": "Policy",
            "state": "enabled", "created_date_time": None,
            "modified_date_time": None, "last_observed_at": "2026-01-02T00:00:00Z",
            "retention_class": "REFERENCE",
        }
        snapshot = {
            "tenant_id": 7, "source_object_id": "cap-1", "collection_run_id": 9,
            "endpoint_run_id": 10, "snapshot_at": "2026-01-02T00:00:00Z",
            "display_name": "Policy", "state": "enabled", "created_date_time": None,
            "modified_date_time": None, "retention_class": "REFERENCE",
        }
        snapshot.update({"client_app_types": ["browser"], "grant_built_in_controls": [], "security_evidence_complete": True})
        current.update({"client_app_types": ["browser"], "grant_built_in_controls": [], "security_evidence_complete": True})
        record = NormalizedWorkloadRecord(
            "G01-011", PersistenceMode.CURRENT_WITH_SNAPSHOT,
            current_row=current, snapshot_row=snapshot,
        )
        write_snapshot_record(BoundSqlExecutor(connection), record)
        current_sql, current_params = connection.statements[0]
        snapshot_sql, snapshot_params = connection.statements[1]
        self.assertIn("core.conditional_access_policy", current_sql)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id) DO UPDATE", current_sql)
        self.assertIn("core.conditional_access_policy_snapshot", snapshot_sql)
        self.assertIn("ON CONFLICT (tenant_id, source_object_id, collection_run_id) DO NOTHING", snapshot_sql)
        self.assertNotIn("Policy", current_sql)
        self.assertNotIn("enabled", snapshot_sql)
        self.assertEqual(current_params[1], "cap-1")
        self.assertEqual(snapshot_params[1], "cap-1")

    def test_snapshot_failure_rolls_back_collection_without_commit(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord("G01-004", PersistenceMode.CURRENT_WITH_SNAPSHOT, current_row={}, snapshot_row={})
        with self.assertRaises(PersistenceError):
            CollectionWriter(connection, write_snapshot_record).write(collection([record], "G01-004"))

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 0)

    def test_dispatch_persistence_rejects_tenant_mismatch_before_sql(self):
        connection = FakeConnection()
        valid = NormalizedWorkloadRecord(
            "G01-001", PersistenceMode.CURRENT,
            current_row={
                "tenant_id": 7, "source_object_id": "user-1",
                "user_principal_name": "user@example.test", "display_name": "User",
                "user_type": "Member", "account_enabled": True,
                "created_date_time": "2026-01-01T00:00:00Z",
                "last_observed_at": "2026-01-02T00:00:00Z", "retention_class": "STANDARD",
            },
        )
        mismatched = NormalizedWorkloadRecord(
            "G01-002", PersistenceMode.CURRENT, current_row={"tenant_id": 7},
        )

        with self.assertRaisesRegex(PersistenceError, "Record endpoint does not match"):
            dispatch_persistence(BoundSqlExecutor(connection), "G01-001", [valid, mismatched])

        self.assertEqual(connection.statements, [])

    def test_direct_writer_rejects_malformed_tenant_before_sql(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-001", PersistenceMode.CURRENT, current_row={"tenant_id": 0},
        )

        with self.assertRaisesRegex(PersistenceError, "tenant_id is missing or malformed"):
            write_current_record(BoundSqlExecutor(connection), record)

        self.assertEqual(connection.statements, [])

    def test_collection_writer_rejects_custom_writer_endpoint_bypass_before_transaction(self):
        connection = FakeConnection()
        record = NormalizedWorkloadRecord(
            "G01-002", PersistenceMode.CURRENT, current_row={"tenant_id": 7},
        )
        writer_called = False

        def write(executor, normalized_record):
            nonlocal writer_called
            writer_called = True

        with self.assertRaisesRegex(PersistenceError, "Record endpoint does not match"):
            CollectionWriter(connection, write).write(collection([record]))

        self.assertFalse(writer_called)
        self.assertEqual(connection.statements, [])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 0)

    def test_executor_rejects_unbound_parameters(self):
        connection = FakeConnection()

        with self.assertRaisesRegex(PersistenceError, "requires bound parameters"):
            BoundSqlExecutor(connection).execute("INSERT INTO ignored VALUES (%s)", None)

        self.assertEqual(connection.statements, [])


if __name__ == "__main__":
    unittest.main()
