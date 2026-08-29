"""Focused offline tests for the trusted tenant boundary."""
import unittest
from types import SimpleNamespace

from collectors.core.tenant import TrustedTenantResolutionError, resolve_trusted_tenant


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql, self.params = sql, params

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.cursor_instance = Cursor(rows)

    def cursor(self):
        return self.cursor_instance


class TrustedTenantResolutionTests(unittest.TestCase):
    config = SimpleNamespace(tenant_id="entra-tenant")

    def test_unique_enabled_tenant_resolves(self):
        connection = Connection([(42,)])
        self.assertEqual(resolve_trusted_tenant(self.config, connection), 42)
        self.assertIn("entra_tenant_id = %s", connection.cursor_instance.sql)
        self.assertIn("enabled = TRUE", connection.cursor_instance.sql)
        self.assertEqual(connection.cursor_instance.params, ("entra-tenant",))

    def test_missing_disabled_and_duplicate_tenants_fail_closed(self):
        # Disabled rows are excluded by the enabled predicate and therefore
        # have the same fail-closed result as a missing mapping here.
        for rows in ([], [(42,), (43,)]):
            with self.subTest(rows=rows):
                with self.assertRaises(TrustedTenantResolutionError):
                    resolve_trusted_tenant(self.config, Connection(rows))

    def test_no_hardcoded_numeric_tenant_id_or_environment_fallback(self):
        from collectors.core import tenant
        with open(tenant.__file__, encoding="utf-8") as source_file:
            source = source_file.read()
        self.assertNotIn("GRAPH_TENANT_DB_ID", source)
        self.assertNotIn("return 2", source)
        self.assertNotIn("LIMIT 1", source)


if __name__ == "__main__":
    unittest.main()
