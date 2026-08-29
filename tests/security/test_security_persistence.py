"""Offline tests for the bounded Security persistence transaction."""
import unittest
from types import SimpleNamespace

from security import (DeterministicSecurityFindingService, SecurityObservation,
                      SecurityPersistenceWriter, FindingStatus)
from security.rules.sp_ext_001 import RULE_ID


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, sql, params):
        self.connection.sql.append((sql, params))
        if "observation" in sql and "RETURNING" in sql:
            self.result = None if self.connection.observation_exists else (11,)
            self.connection.observation_exists = True
        elif "finding_evaluation" in sql and "RETURNING" in sql:
            self.result = None if self.connection.evaluation_exists else (21,)
            self.connection.evaluation_exists = True
        elif sql.startswith("SELECT observation_id"):
            self.result = (11,)
        elif sql.startswith("SELECT evaluation_id"):
            self.result = (21,)
        else:
            self.result = None

    def fetchone(self):
        result, self.result = self.result, None
        return result


class Connection:
    def __init__(self, fail_on=None):
        self.sql = []
        self.commits = 0
        self.rollbacks = 0
        self.observation_exists = False
        self.evaluation_exists = False
        self.fail_on = fail_on

    def cursor(self):
        cursor = Cursor(self)
        original = cursor.execute
        def execute(sql, params):
            if self.fail_on and self.fail_on in sql:
                raise RuntimeError(self.fail_on)
            return original(sql, params)
        cursor.execute = execute
        return cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def observation(value="anyone", observed_at="2026-08-27T00:00:00Z"):
    return SecurityObservation(
        rule_id=RULE_ID, value=value, source_available=value is not None,
        observed_at=observed_at, source_type="sharepoint_tenant_settings",
        graph_endpoint="/admin/sharepoint/settings", normalized_field="sharing_capability",
    )


class SecurityPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.service = DeterministicSecurityFindingService()

    def persist(self, connection, value="anyone", observed_at="2026-08-27T00:00:00Z"):
        obs = observation(value, observed_at)
        finding = self.service.evaluate(obs)
        return SecurityPersistenceWriter(connection).persist(
            tenant_id=7, observation=obs, finding=finding), finding

    def test_open_retry_is_idempotent_and_atomic(self):
        connection = Connection()
        first, finding = self.persist(connection)
        second, _ = self.persist(connection)
        self.assertEqual(finding.status, FindingStatus.OPEN)
        self.assertEqual(connection.commits, 2)
        self.assertFalse(second["observation_inserted"])
        self.assertFalse(second["evaluation_inserted"])
        self.assertEqual(first["evaluation_digest"], second["evaluation_digest"])

    def test_pass_and_not_evaluated_are_supported(self):
        for value in ("existing_guests", None):
            connection = Connection()
            _, finding = self.persist(connection, value)
            self.assertIn(finding.status, (FindingStatus.PASS, FindingStatus.NOT_EVALUATED))

    def test_newer_evaluation_updates_projection_and_history_is_not_deleted(self):
        connection = Connection()
        _, old = self.persist(connection, "anyone", "2026-08-27T00:00:00Z")
        _, new = self.persist(connection, "existing_guests", "2026-08-28T00:00:00Z")
        self.assertEqual(old.status, FindingStatus.OPEN)
        self.assertEqual(new.status, FindingStatus.PASS)
        self.assertEqual(sum("INSERT INTO security.finding_evaluation" in s[0] for s in connection.sql), 2)
        self.assertFalse(any("DELETE" in s[0] for s in connection.sql))

    def test_each_failure_rolls_back(self):
        for failure in ("security.observation", "security.finding_evaluation", "security.finding_current"):
            connection = Connection(failure)
            with self.assertRaises(RuntimeError):
                self.persist(connection)
            self.assertEqual(connection.commits, 0)
            self.assertEqual(connection.rollbacks, 1)

    def test_only_sanitized_fields_are_bound(self):
        connection = Connection()
        self.persist(connection)
        text = repr(connection.sql)
        self.assertNotIn("Authorization", text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("password", text.lower())
        self.assertNotIn("raw", text.lower())

    def test_authenticated_persistence_uses_canonical_tenant_resolver(self):
        connection = Connection()
        config = SimpleNamespace(tenant_id="entra-tenant")
        cursor = connection.cursor()
        original_execute = cursor.execute

        def execute(sql, params):
            if sql.startswith("SELECT tenant_id FROM core.tenant"):
                cursor.result = (42,)
                connection.sql.append((sql, params))
                return
            return original_execute(sql, params)

        def fetchall():
            return [(42,)]

        cursor.execute = execute
        cursor.fetchall = fetchall
        original_cursor = connection.cursor
        connection.cursor = lambda: cursor
        obs = observation({"global_admin_assignment_count": 7, "distinct_global_admin_principals": 7})
        obs = SecurityObservation(
            rule_id="M365-ENTRA-GA-001", value=obs.value, source_available=True,
            observed_at=obs.observed_at, source_type="entra_directory_role_assignments",
            graph_endpoint="/roleManagement/directory/roleAssignments",
            normalized_field="global_admin_assignment_count",
        )
        finding = DeterministicSecurityFindingService().evaluate(obs)
        result = SecurityPersistenceWriter(connection).persist_authenticated(
            config=config, observation=obs, finding=finding,
        )
        self.assertEqual(result["observation_id"], 11)
        self.assertEqual(connection.sql[0][1], ("entra-tenant",))
        self.assertIn("enabled = TRUE", connection.sql[0][0])
        self.assertIn((42, "M365-ENTRA-GA-001"), [params[:2] for sql, params in connection.sql if "INSERT INTO security.observation" in sql])
        connection.cursor = original_cursor


if __name__ == "__main__":
    unittest.main()
