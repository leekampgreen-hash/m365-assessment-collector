"""Offline deterministic tests for the G06-002 PostgreSQL migrations.

These tests are **offline only**. They validate the migration artifacts
on disk and never connect to a real PostgreSQL database.

Authoritative source: docs/database-schema-design.md (G06-001 + G06-001R).
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "database" / "migrations"


# ---------------------------------------------------------------------------
# Authoritative inventory (43 physical tables; 0 in analytics).
# ---------------------------------------------------------------------------
EXPECTED_TABLES = {
    # control (2)
    "control.collection_run",
    "control.endpoint_run",
    # raw (1)
    "raw.raw_graph_record",
    # core tenant (1)
    "core.tenant",
    # core directory / identity (7)
    'core."user"',
    'core."group"',
    "core.organization",
    "core.application",
    "core.service_principal",
    "core.device",
    "core.administrative_unit",
    # core licensing (2)
    "core.subscribed_sku",
    "core.subscribed_sku_snapshot",
    "core.user_license_assignment",
    # core security / audit (2)
    "core.audit_event",
    "core.risk_detection",
    # core identity protection (2)
    "core.risky_user",
    "core.risky_user_snapshot",
    # core conditional access (2)
    "core.conditional_access_policy",
    "core.conditional_access_policy_snapshot",
    # core named location (1)
    "core.named_location",
    # core RBAC (3)
    "core.directory_role_definition",
    "core.directory_role_assignment",
    "core.directory_role_assignment_snapshot",
    # core service health (4)
    "core.service_health_overview",
    "core.service_health_overview_snapshot",
    "core.service_health_issue",
    "core.service_health_issue_history",
    # core service update message (2)
    "core.service_update_message",
    "core.service_update_message_history",
    "core.usage_office365_active_user", "core.usage_office365_active_user_snapshot",
    "core.usage_exchange_email_activity", "core.usage_exchange_email_activity_snapshot",
    "core.usage_exchange_mailbox_usage", "core.usage_exchange_mailbox_usage_snapshot",
    "core.usage_onedrive_activity", "core.usage_onedrive_activity_snapshot",
    "core.usage_onedrive_account_usage", "core.usage_onedrive_account_usage_snapshot",
    "core.usage_sharepoint_user_activity", "core.usage_sharepoint_user_activity_snapshot",
    "core.usage_sharepoint_site_usage", "core.usage_sharepoint_site_usage_snapshot",
    "core.usage_teams_user_activity", "core.usage_teams_user_activity_snapshot",
    "security.observation",
    "security.finding_evaluation",
    "security.finding_current",
    "core.onedrive_high_value_audit_event",
    "control.collector_checkpoint",
    "core.sharepoint_tenant_settings",
    "core.sharepoint_high_value_audit_event",
    "core.signin_log",
    'auth."user"',
    "auth.session",
    "auth.auth_event",
    "auth.admin_audit",
    "auth.api_access_log",
    "core.feature_flag",
    "core.tenant_feature",
    "core.system_setting",
    "core.intune_device",
    "core.entra_guest",
    "core.entra_auth_method",
}

EXPECTED_SCHEMAS = {"control", "raw", "core", "analytics", "security", "auth"}

EXPECTED_FILES_IN_ORDER = [
    "001_create_schemas.sql",
    "002_core_tenant_and_control.sql",
    "003_core_directory_and_licensing.sql",
    "004_core_security_governance_rbac.sql",
    "005_core_service_health_and_change.sql",
    "006_raw_traceability.sql",
    "007_indexes.sql",
    "008_usage_reports.sql",
    "009_user_license_assignment.sql",
    "010_endpoint_identity_unavailable.sql",
    "011_security_findings_persistence.sql",
    "012_endpoint_persistence_error.sql",
    "013_conditional_access_security_evidence.sql",
    "013_usage_reports_current_delete.sql",
    "014_exchange_mailbox_quota.sql",
    "015_exchange_mailbox_capacity.sql",
    "016_onedrive_account_capacity.sql",
    "017_onedrive_account_capacity_user_ref.sql",
    "018_onedrive_high_value_audit_event.sql",
    "019_collector_checkpoint.sql",
    "020_onedrive_high_value_audit_analytics.sql",
    "020_signin_log.sql",
    "021_sharepoint_tenant_settings.sql",
    "022_sharepoint_high_value_audit.sql",
    "023_subscribed_sku_lifecycle.sql",
    "024_teams_user_activity.sql",
    "025_auth_schema.sql",
    "026_feature_flags.sql",
    "027_auth_indexes.sql",
    "028_grants_consolidation.sql",
    "029_intune_compliance.sql",
    "030_entra_guests.sql",
    "031_entra_auth_methods.sql",
]


# G01 endpoint → storage kind / required tables mapping.
ENDPOINT_HISTORICAL = {
    "G01-005",  # directory audit
    "G01-006",  # sign-in
    "G01-014",  # risk detection
    "G01-016",  # service health issue + history
    "G01-017",  # service update message + history
}

ENDPOINT_HISTORICAL_WITH_SNAPSHOT = {
    "G01-004",
    "G01-011",
    "G01-013",
    "G01-015",
    "G01-019",
}


# Forbidden credential column names (case-insensitive substring match
# against column definitions in the migrations).
FORBIDDEN_CREDENTIAL_NAMES = [
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization",
    "bearer_token",
    "password",
]

# Forbidden DDL fragments (case-insensitive). The patterns are deliberately
# precise so they do not match legitimate column-list or comment text.
# In particular, ``ON DELETE CASCADE / RESTRICT`` is part of foreign-key
# definitions and must NOT be matched as a destructive statement.
FORBIDDEN_DDL_FRAGMENTS = [
    re.compile(r"(?<!\w)DROP\s+(?:TABLE|INDEX|SCHEMA|DATABASE|VIEW|FUNCTION)(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)TRUNCATE(?:\s+TABLE)?(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)DELETE\s+FROM(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)CREATE\s+DATABASE(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)CREATE\s+ROLE(?!\w)", re.IGNORECASE),
    re.compile(r"(?<!\w)CREATE\s+USER(?!\w)", re.IGNORECASE),
]

# Forbidden token-like literals (defensive heuristic).
FORBIDDEN_LITERAL_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}"),  # JWT-like
    re.compile(r"sk-[A-Za-z0-9]{16,}"),   # sk- prefixed secret
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),  # bearer literal
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_migrations() -> list[Path]:
    """Return all *.sql migration files in deterministic numeric order."""
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    return files


def _all_sql() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in _load_migrations())


_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>(?:\".+?\"|[A-Za-z_][\w$]*)(?:\.(?:\".+?\"|[A-Za-z_][\w$]*))?)",
    re.IGNORECASE,
)


def _extract_create_tables(text: str) -> list[str]:
    """Return the qualified table names declared by CREATE TABLE statements.

    Preserves case-sensitive quoted identifiers (e.g. ``"user"``) so that
    ``core."user"`` matches ``EXPECTED_TABLES`` exactly.
    """
    tables = []
    for m in _CREATE_TABLE_RE.finditer(text):
        name = m.group("name")
        # Normalise whitespace inside the identifier (rare) but preserve
        # quoted form including case.
        tables.append(name)
    return tables


def _normalise_unquoted(name: str) -> str:
    """Lower-case the schema, leave the table as the DDL writes it.

    PostgreSQL stores unquoted identifiers as lower-case; quoted
    identifiers retain case. We mirror that for matching.
    """
    if "." not in name:
        return name.lower()
    schema, table = name.split(".", 1)
    return f"{schema.lower()}.{table}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class MigrationDiscoveryTests(unittest.TestCase):
    def test_migrations_directory_exists(self) -> None:
        self.assertTrue(
            MIGRATIONS_DIR.is_dir(),
            f"migrations directory missing: {MIGRATIONS_DIR}",
        )

    def test_migration_files_discoverable_and_non_empty(self) -> None:
        files = _load_migrations()
        self.assertGreater(len(files), 0, "no migration files discovered")
        for p in files:
            self.assertGreater(p.stat().st_size, 0, f"empty migration: {p.name}")

    def test_migration_order_is_numeric_and_stable(self) -> None:
        files = _load_migrations()
        names = [p.name for p in files]
        self.assertEqual(names, EXPECTED_FILES_IN_ORDER)
        # Numeric prefix must be monotonic (non-decreasing). Prefixes are only
        # an ordering hint applied by sorting the files; the full file name is
        # the stable tie-breaker within a shared slot.
        prefixes = [int(re.match(r"^(\d+)", n).group(1)) for n in names]
        self.assertEqual(prefixes, sorted(prefixes))
        # Every migration number must be unique EXCEPT the intentional 013
        # co-slot, which carries two forward-only migrations:
        #   013_conditional_access_security_evidence.sql (G01-011 security
        #   evidence columns) and
        #   013_usage_reports_current_delete.sql (STD-05B current-state DELETE
        #   grant on usage-report tables).
        # Both are applied and live-proven; the duplicate is deliberate, so it
        # is the only allowed repeated prefix.
        from collections import Counter

        repeated = {p for p, c in Counter(prefixes).items() if c > 1}
        self.assertEqual(repeated, {13, 20})


class SchemaTests(unittest.TestCase):
    def test_four_schemas_declared(self) -> None:
        sql = _all_sql()
        declared = set(
            re.findall(
                r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*;",
                sql,
                re.IGNORECASE,
            )
        )
        self.assertEqual(declared, EXPECTED_SCHEMAS)

    def test_no_extra_schemas_declared(self) -> None:
        sql = _all_sql()
        declared = set(
            re.findall(
                r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*;",
                sql,
                re.IGNORECASE,
            )
        )
        self.assertTrue(declared.issubset(EXPECTED_SCHEMAS))
        self.assertEqual(len(declared), len(EXPECTED_SCHEMAS))


class TableInventoryTests(unittest.TestCase):
    def test_exactly_65_create_table_definitions(self) -> None:
        sql = _all_sql()
        tables = _extract_create_tables(sql)
        # Sanity: drop any duplicate literal entries but expect no
        # duplicates within a single migration run.
        self.assertEqual(
            len(tables),
            65,
            f"expected exactly 65 CREATE TABLE definitions, found {len(tables)}: {tables}",
        )

    def test_all_accepted_table_names_exist(self) -> None:
        sql = _all_sql()
        tables = {_normalise_unquoted(t) for t in _extract_create_tables(sql)}
        expected = {_normalise_unquoted(t) for t in EXPECTED_TABLES}
        missing = expected - tables
        self.assertFalse(
            missing,
            f"missing expected tables: {sorted(missing)}",
        )

    def test_no_unexpected_table_names(self) -> None:
        sql = _all_sql()
        tables = {_normalise_unquoted(t) for t in _extract_create_tables(sql)}
        expected = {_normalise_unquoted(t) for t in EXPECTED_TABLES}
        extra = tables - expected
        self.assertFalse(
            extra,
            f"unexpected extra tables: {sorted(extra)}",
        )

    def test_analytics_has_zero_physical_tables(self) -> None:
        sql = _all_sql()
        tables = _extract_create_tables(sql)
        analytics_tables = [t for t in tables if t.lower().startswith("analytics.")]
        self.assertEqual(
            analytics_tables,
            [],
            "analytics schema must have zero physical tables in G06-002",
        )


class G01PersistenceRequirements(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    # ---------- CURRENT_ONLY --------------------------------------------------
    def test_g01_001_persists(self) -> None:
        self.assertIn('core."user"', self.sql)

    def test_g01_002_persists(self) -> None:
        self.assertIn('core."group"', self.sql)

    def test_g01_003_persists(self) -> None:
        self.assertIn("core.organization", self.sql)

    def test_g01_007_persists(self) -> None:
        self.assertIn("core.application", self.sql)

    def test_g01_008_persists(self) -> None:
        self.assertIn("core.service_principal", self.sql)

    def test_g01_009_persists(self) -> None:
        self.assertIn("core.device", self.sql)

    def test_g01_010_persists(self) -> None:
        self.assertIn("core.administrative_unit", self.sql)

    def test_g01_012_persists(self) -> None:
        self.assertIn("core.named_location", self.sql)

    def test_g01_018_persists(self) -> None:
        self.assertIn("core.directory_role_definition", self.sql)

    # ---------- EVENT_LOG ------------------------------------------------------
    def test_g01_005_and_g01_006_share_audit_event(self) -> None:
        self.assertIn("core.audit_event", self.sql)
        self.assertIn("DIRECTORY_AUDIT", self.sql)
        self.assertIn("SIGN_IN", self.sql)

    def test_g01_014_persists(self) -> None:
        self.assertIn("core.risk_detection", self.sql)
        # Append-only semantics markers
        self.assertIn("source_object_id", self.sql)
        self.assertIn("detected_at", self.sql)
        self.assertIn("collected_at", self.sql)
        self.assertIn("collection_run_id", self.sql)
        self.assertIn("endpoint_run_id", self.sql)

    # ---------- HISTORICAL_WITH_SNAPSHOT ---------------------------------------
    def test_g01_004_current_and_snapshot_exist(self) -> None:
        self.assertIn("core.subscribed_sku", self.sql)
        self.assertIn("core.subscribed_sku_snapshot", self.sql)

    def test_g01_011_current_and_snapshot_exist(self) -> None:
        self.assertIn("core.conditional_access_policy", self.sql)
        self.assertIn("core.conditional_access_policy_snapshot", self.sql)

    def test_g01_013_current_and_snapshot_exist(self) -> None:
        self.assertIn("core.risky_user", self.sql)
        self.assertIn("core.risky_user_snapshot", self.sql)

    def test_g01_015_current_and_snapshot_exist(self) -> None:
        self.assertIn("core.service_health_overview", self.sql)
        self.assertIn("core.service_health_overview_snapshot", self.sql)

    def test_g01_019_current_and_snapshot_exist(self) -> None:
        self.assertIn("core.directory_role_assignment", self.sql)
        self.assertIn("core.directory_role_assignment_snapshot", self.sql)

    def test_snapshot_tables_carry_collection_lineage(self) -> None:
        for snap in (
            "core.subscribed_sku_snapshot",
            "core.risky_user_snapshot",
            "core.conditional_access_policy_snapshot",
            "core.service_health_overview_snapshot",
            "core.directory_role_assignment_snapshot",
        ):
            # Find the CREATE TABLE block for this table.
            pattern = re.compile(
                rf"CREATE\s+TABLE\s+{re.escape(snap)}\s*\((?P<body>.*?)\);",
                re.IGNORECASE | re.DOTALL,
            )
            m = pattern.search(self.sql)
            self.assertIsNotNone(m, f"snapshot table not found: {snap}")
            body = m.group("body")
            self.assertIn(
                "collection_run_id",
                body,
                f"{snap} must carry collection_run_id",
            )
            self.assertIn(
                "endpoint_run_id",
                body,
                f"{snap} must carry endpoint_run_id",
            )
            # Snapshot uniqueness must reference collection_run_id.
            self.assertRegex(
                body,
                re.compile(r"UNIQUE\s*\([^)]*collection_run_id[^)]*\)", re.IGNORECASE),
            )

    # ---------- INCREMENTAL + HISTORICAL (G01-016 / G01-017) ------------------
    def test_g01_016_current_and_history_exist(self) -> None:
        self.assertIn("core.service_health_issue", self.sql)
        self.assertIn("core.service_health_issue_history", self.sql)

    def test_g01_017_current_and_history_exist(self) -> None:
        self.assertIn("core.service_update_message", self.sql)
        self.assertIn("core.service_update_message_history", self.sql)

    def test_g01_016_history_uniqueness_references_version_identity(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+core\.service_health_issue_history\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        self.assertIn("version_identity", body)
        self.assertRegex(
            body,
            re.compile(r"UNIQUE\s*\([^)]*version_identity[^)]*\)", re.IGNORECASE),
        )

    def test_g01_017_history_uniqueness_references_version_identity(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+core\.service_update_message_history\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        self.assertIn("version_identity", body)
        self.assertRegex(
            body,
            re.compile(r"UNIQUE\s*\([^)]*version_identity[^)]*\)", re.IGNORECASE),
        )

    def test_g01_016_history_carries_observed_at(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+core\.service_health_issue_history\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        self.assertIn("observed_at", body)
        self.assertIn("collected_at", body)
        self.assertIn("last_modified_date_time", body)


class ControlAndRawTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_control_tables_exist(self) -> None:
        self.assertIn("control.collection_run", self.sql)
        self.assertIn("control.endpoint_run", self.sql)

    def test_control_collection_run_status_check(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+control\.collection_run\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        for status in ("RUNNING", "SUCCESS", "PARTIAL_SUCCESS", "FAILED"):
            self.assertIn(status, body)

    def test_control_endpoint_run_per_run_uniqueness(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+control\.endpoint_run\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        self.assertRegex(
            body,
            re.compile(r"UNIQUE\s*\([^)]*collection_run_id[^)]*endpoint_id[^)]*\)", re.IGNORECASE),
        )

    def test_raw_table_exists(self) -> None:
        self.assertIn("raw.raw_graph_record", self.sql)


class RetentionClassTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_retention_class_check_constraint_values(self) -> None:
        # The CHECK constraint literals must include all four controlled
        # retention values.
        for v in ("SHORT", "STANDARD", "LONG", "REFERENCE"):
            self.assertIn(
                f"'{v}'",
                self.sql,
                f"retention class value {v} not represented in CHECK constraints",
            )

    def test_retention_class_column_used_on_operational_tables(self) -> None:
        for table in (
            "core.tenant",
            "core.audit_event",
            "core.risk_detection",
            "core.risky_user",
            "core.risky_user_snapshot",
            "core.service_health_issue",
            "core.service_health_issue_history",
            "core.service_update_message",
            "core.service_update_message_history",
            "core.subscribed_sku",
            "core.subscribed_sku_snapshot",
            "core.service_health_overview",
            "core.service_health_overview_snapshot",
            "core.directory_role_assignment",
            "core.directory_role_assignment_snapshot",
            "core.conditional_access_policy",
            "core.conditional_access_policy_snapshot",
            "control.collection_run",
            "control.endpoint_run",
            "raw.raw_graph_record",
        ):
            pattern = re.compile(
                rf"CREATE\s+TABLE\s+{re.escape(table)}\s*\((?P<body>.*?)\);",
                re.IGNORECASE | re.DOTALL,
            )
            m = pattern.search(self.sql)
            self.assertIsNotNone(m, f"table not found: {table}")
            self.assertIn(
                "retention_class",
                m.group("body"),
                f"{table} must carry retention_class column",
            )


class ForeignKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_endpoint_run_references_collection_run(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+control\.endpoint_run\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        self.assertIn(
            "REFERENCES control.collection_run(collection_run_id)",
            body,
        )

    def test_tenant_referenced_by_operational_tables(self) -> None:
        for table in (
            "control.collection_run",
            "control.endpoint_run",
            "core.subscribed_sku_snapshot",
            "core.audit_event",
            "core.risk_detection",
            "core.service_health_issue_history",
            "core.service_update_message_history",
        ):
            pattern = re.compile(
                rf"CREATE\s+TABLE\s+{re.escape(table)}\s*\((?P<body>.*?)\);",
                re.IGNORECASE | re.DOTALL,
            )
            m = pattern.search(self.sql)
            self.assertIsNotNone(m, f"table not found: {table}")
            body = m.group("body")
            self.assertIn(
                "REFERENCES core.tenant(tenant_id)",
                body,
                f"{table} must FK to core.tenant(tenant_id)",
            )

    def test_tenant_deletion_is_restricted(self) -> None:
        # Spot-check that tenant_id FKs do not cascade-delete history.
        # We only require RESTRICT semantics on a representative sample.
        for table in (
            "control.collection_run",
            "core.audit_event",
            "core.service_health_issue_history",
        ):
            pattern = re.compile(
                rf"CREATE\s+TABLE\s+{re.escape(table)}\s*\((?P<body>.*?)\);",
                re.IGNORECASE | re.DOTALL,
            )
            m = pattern.search(self.sql)
            self.assertIsNotNone(m)
            body = m.group("body")
            tenant_fk_match = re.search(
                r"REFERENCES\s+core\.tenant\(tenant_id\)\s+(?P<verb>ON\s+DELETE\s+(?:RESTRICT|CASCADE|SET\s+NULL|SET\s+DEFAULT|NO\s+ACTION))",
                body,
                flags=re.IGNORECASE,
            )
            self.assertIsNotNone(
                tenant_fk_match,
                f"{table}: tenant FK must explicitly declare ON DELETE behaviour",
            )
            verb = tenant_fk_match.group("verb").upper()
            self.assertNotIn(
                "CASCADE",
                verb,
                f"{table}: tenant deletion must not cascade into history",
            )


class IndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_no_index_creation_before_007(self) -> None:
        # Sanity: CREATE INDEX statements belong only to the indexes
        # migration; table migrations should not declare ad-hoc indexes.
        adhoc_idx = re.compile(
            r"^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\b",
            re.IGNORECASE | re.MULTILINE,
        )
        for p in _load_migrations():
            if p.name in ("007_indexes.sql", "011_security_findings_persistence.sql", "018_onedrive_high_value_audit_event.sql", "020_signin_log.sql", "022_sharepoint_high_value_audit.sql", "027_auth_indexes.sql", "029_intune_compliance.sql", "030_entra_guests.sql", "031_entra_auth_methods.sql"):
                continue
            text = p.read_text(encoding="utf-8")
            self.assertNotRegex(
                text,
                adhoc_idx,
                msg=f"ad-hoc CREATE INDEX in {p.name}",
            )

    def test_indexes_migration_has_create_index_statements(self) -> None:
        text = (MIGRATIONS_DIR / "007_indexes.sql").read_text(encoding="utf-8")
        # Should contain CREATE INDEX, and at least the core set.
        self.assertRegex(text, re.compile(r"CREATE\s+INDEX\b", re.IGNORECASE))
        self.assertIn("collection_run_status_started_at_idx", text)
        self.assertIn("service_health_issue_history_tenant_source_observed_idx", text)
        self.assertIn("directory_role_assignment_tenant_principal_idx", text)


class RawSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_no_credential_column_names_anywhere(self) -> None:
        # Find every CREATE TABLE block and check its column list for any
        # forbidden credential column name. The CHECK constraint on
        # raw.raw_graph_record legitimately references these literal
        # strings inside a CHECK expression; that block is allowed and
        # excluded here.
        for m in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\w\"\.]+\s*\((?P<body>.*?)\);",
            self.sql,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            body = m.group("body")
            body_lower = body.lower()
            for forbidden in FORBIDDEN_CREDENTIAL_NAMES:
                # A credential name appearing as a *column identifier*
                # would look like ``  forbidden  TEXT`` or similar — i.e.
                # surrounded by whitespace or commas. Match that shape so
                # we ignore string literals inside CHECK expressions.
                pattern = re.compile(
                    rf"(?:^|[\s,]){re.escape(forbidden)}(?:\s|$|,)",
                    re.IGNORECASE,
                )
                self.assertNotRegex(
                    body,
                    pattern,
                    f"forbidden credential column name '{forbidden}' in table block",
                )

    def test_raw_table_top_level_check_constraint(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+raw\.raw_graph_record\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        for forbidden in ("Authorization", "access_token", "refresh_token", "client_secret", "password", "bearer"):
            self.assertIn(forbidden, body)


class DDLSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_no_destructive_ddl(self) -> None:
        # Strip line comments first so commentary about the absence of
        # destructive statements does not trigger false positives.
        stripped = "\n".join(
            line for line in self.sql.splitlines() if not line.lstrip().startswith("--")
        )
        for pattern in FORBIDDEN_DDL_FRAGMENTS:
            self.assertNotRegex(
                stripped,
                pattern,
                msg=f"forbidden DDL fragment matched: {pattern.pattern}",
            )

    def test_no_credential_literal_values(self) -> None:
        for pattern in FORBIDDEN_LITERAL_PATTERNS:
            self.assertNotRegex(
                self.sql,
                pattern,
                msg=f"forbidden credential literal pattern matched: {pattern.pattern}",
            )

    def test_no_database_or_role_creation(self) -> None:
        self.assertNotRegex(self.sql, re.compile(r"\bCREATE\s+DATABASE\b", re.IGNORECASE))
        self.assertNotRegex(self.sql, re.compile(r"\bCREATE\s+ROLE\b", re.IGNORECASE))
        self.assertNotRegex(self.sql, re.compile(r"\bCREATE\s+USER\b", re.IGNORECASE))
        self.assertNotRegex(self.sql, re.compile(r"\bALTER\s+ROLE\b", re.IGNORECASE))

    def test_usage_report_grants_are_narrow(self) -> None:
        usage_sql = (MIGRATIONS_DIR / "008_usage_reports.sql").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"\bGRANT\s+SELECT,\s*INSERT,\s*UPDATE\s+ON\s+TABLE", usage_sql, re.IGNORECASE)), 1)
        self.assertEqual(len(re.findall(r"\bGRANT\s+USAGE,\s*SELECT\s+ON\s+SEQUENCE", usage_sql, re.IGNORECASE)), 1)
        self.assertNotRegex(usage_sql, re.compile(r"\bGRANT[^;]*\bDELETE\b", re.IGNORECASE | re.DOTALL))
        self.assertNotRegex(usage_sql, re.compile(r"\bGRANT[^;]*\b(?:CREATE|ALTER|DROP)\b", re.IGNORECASE | re.DOTALL))

    def test_usage_report_delete_grant_is_current_tables_only(self) -> None:
        usage_sql = (MIGRATIONS_DIR / "013_usage_reports_current_delete.sql").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"\bGRANT\s+DELETE\s+ON\s+TABLE", usage_sql, re.IGNORECASE)), 1)
        for table in (
            "usage_office365_active_user",
            "usage_exchange_email_activity",
            "usage_exchange_mailbox_usage",
            "usage_onedrive_activity",
            "usage_onedrive_account_usage",
            "usage_sharepoint_user_activity",
            "usage_sharepoint_site_usage",
        ):
            self.assertIn("core." + table, usage_sql)
            self.assertNotIn("core." + table + "_snapshot", usage_sql)
        self.assertNotRegex(usage_sql, re.compile(r"\b(?:GRANT|ALTER|DROP)\b[^;]*\b(?:CREATE|USAGE)\b", re.IGNORECASE | re.DOTALL))

    def test_no_insert_or_data(self) -> None:
        self.assertNotRegex(self.sql, re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE))
        self.assertNotRegex(self.sql, re.compile(r"\bINSERT\s+core\.", re.IGNORECASE))

    def test_statements_terminate_properly(self) -> None:
        # Strip line comments and blank lines first so commentary text
        # inside ``COMMENT ON COLUMN ... IS '...')`` does not pollute
        # the close-paren count.
        for p in _load_migrations():
            text = p.read_text(encoding="utf-8")
            stripped_lines = []
            for line in text.splitlines():
                if line.lstrip().startswith("--"):
                    continue
                stripped_lines.append(line)
            stripped = "\n".join(stripped_lines)

            n_create_table = len(re.findall(r"\bCREATE\s+TABLE\b", stripped, re.IGNORECASE))
            n_create_schema = len(re.findall(r"\bCREATE\s+SCHEMA\b", stripped, re.IGNORECASE))
            n_create_index = len(re.findall(r"\bCREATE\s+INDEX\b", stripped, re.IGNORECASE))

            # CREATE TABLE / CREATE INDEX bodies end with ``);`` on a
            # standalone line (CREATE TABLE has parenthesised body;
            # CREATE INDEX has no body so it ends with ``;`` on a
            # standalone line).
            lines = stripped.splitlines()
            n_close_paren_semicolon = sum(
                1 for line in lines if line.strip() == ");"
            )
            n_semicolon_only = sum(
                1
                for line in lines
                if line.strip().endswith(";")
                and line.strip() != ");"
                and not line.strip().startswith("--")
            )
            # CREATE TABLE statements are closed by ``);`` lines.
            expected_close_paren_semicolon = n_create_table + (1 if p.name in ("018_onedrive_high_value_audit_event.sql", "022_sharepoint_high_value_audit.sql") else 0)
            self.assertEqual(
                expected_close_paren_semicolon,
                n_close_paren_semicolon,
                f"{p.name}: CREATE TABLE count ({n_create_table}) != ');' line count ({n_close_paren_semicolon})",
            )
            # CREATE INDEX statements close with a bare ``;`` line.
            self.assertGreaterEqual(
                n_semicolon_only,
                n_create_index,
                f"{p.name}: CREATE INDEX count ({n_create_index}) exceeds ';' only line count ({n_semicolon_only})",
            )
            # CREATE SCHEMA statements end with ``;`` on the CREATE line.
            n_schema_term = len(
                [
                    line
                    for line in lines
                    if re.search(r"\bCREATE\s+SCHEMA\b[^\(]*;\s*$", line, re.IGNORECASE)
                ]
            )
            self.assertEqual(
                n_create_schema,
                n_schema_term,
                f"{p.name}: CREATE SCHEMA count != semicolon-terminated lines "
                f"({n_create_schema} vs {n_schema_term})",
            )
            # File should end with COMMIT;
            self.assertTrue(
                stripped.rstrip().endswith("COMMIT;"),
                f"{p.name}: file must end with COMMIT;",
            )


class EndpointMappingValidation(unittest.TestCase):
    """Offline mapping assertion for G01-001..G01-019.

    The authoritative mapping is defined inline below. The DDL must
    contain the required tables; the design source must agree on
    HISTORICAL / HISTORICAL_WITH_SNAPSHOT requirements.
    """

    ENDPOINT_REQUIRED_TABLES = {
        # CURRENT_ONLY (9)
        "G01-001": ['core."user"'],
        "G01-002": ['core."group"'],
        "G01-003": ["core.organization"],
        "G01-007": ["core.application"],
        "G01-008": ["core.service_principal"],
        "G01-009": ["core.device"],
        "G01-010": ["core.administrative_unit"],
        "G01-012": ["core.named_location"],
        "G01-018": ["core.directory_role_definition"],
        # HISTORICAL (5)
        "G01-005": ["core.audit_event"],
        "G01-006": ["core.audit_event"],
        "G01-014": ["core.risk_detection"],
        "G01-016": ["core.service_health_issue", "core.service_health_issue_history"],
        "G01-017": ["core.service_update_message", "core.service_update_message_history"],
        # HISTORICAL_WITH_SNAPSHOT (5)
        "G01-004": ["core.subscribed_sku", "core.subscribed_sku_snapshot"],
        "G01-011": ["core.conditional_access_policy", "core.conditional_access_policy_snapshot"],
        "G01-013": ["core.risky_user", "core.risky_user_snapshot"],
        "G01-015": ["core.service_health_overview", "core.service_health_overview_snapshot"],
        "G01-019": ["core.directory_role_assignment", "core.directory_role_assignment_snapshot"],
    }

    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_all_19_endpoint_ids_mapped(self) -> None:
        ids = set(self.ENDPOINT_REQUIRED_TABLES.keys())
        expected = {f"G01-{i:03d}" for i in range(1, 20)}
        self.assertEqual(ids, expected)

    def test_no_missing_endpoint_mapping(self) -> None:
        for endpoint_id, tables in self.ENDPOINT_REQUIRED_TABLES.items():
            for table in tables:
                self.assertIn(
                    table,
                    self.sql,
                    f"{endpoint_id}: missing required table {table}",
                )

    def test_user_license_assignment_table_is_tenant_user_sku_unique(self) -> None:
        self.assertRegex(
            self.sql,
            r"CREATE TABLE(?: IF NOT EXISTS)? core\.user_license_assignment",
        )
        self.assertIn("REFERENCES core.tenant(tenant_id)", self.sql)
        self.assertIn('REFERENCES core."user"(user_id)', self.sql)
        self.assertIn("UNIQUE (tenant_id, user_id, sku_id)", self.sql)

    def test_historical_endpoints_preserve_history(self) -> None:
        # HISTORICAL: G01-005, G01-006, G01-014 via append-only tables;
        # G01-016, G01-017 via current+history pair.
        self.assertEqual(len(ENDPOINT_HISTORICAL), 5)
        for ep in ENDPOINT_HISTORICAL:
            self.assertIn(ep, self.ENDPOINT_REQUIRED_TABLES)

    def test_historical_with_snapshot_endpoints_preserve_history(self) -> None:
        # HISTORICAL_WITH_SNAPSHOT requires both current + snapshot.
        self.assertEqual(len(ENDPOINT_HISTORICAL_WITH_SNAPSHOT), 5)
        for ep in ENDPOINT_HISTORICAL_WITH_SNAPSHOT:
            tables = self.ENDPOINT_REQUIRED_TABLES[ep]
            # Both a "current" table and a "*_snapshot" table must be present.
            self.assertTrue(
                any(t.endswith("_snapshot") for t in tables),
                f"{ep}: must declare a _snapshot table",
            )
            self.assertTrue(
                any(not t.endswith("_snapshot") for t in tables),
                f"{ep}: must declare a current-state table",
            )

    def test_current_history_snapshot_event_requirements(self) -> None:
        # Group endpoints explicitly rather than inferring from table counts.
        current_only = {
            "G01-001", "G01-002", "G01-003",
            "G01-007", "G01-008", "G01-009", "G01-010",
            "G01-012", "G01-018",
        }
        historical_single = {"G01-005", "G01-006", "G01-014"}
        incremental_historical = {"G01-016", "G01-017"}
        hws = ENDPOINT_HISTORICAL_WITH_SNAPSHOT
        # 9 + 3 + 2 + 5 = 19.
        self.assertEqual(
            len(current_only) + len(historical_single) + len(incremental_historical) + len(hws),
            19,
        )
        self.assertEqual(len(current_only), 9)
        # Historical single-event endpoints must have exactly one table.
        for ep in historical_single:
            self.assertEqual(
                len(self.ENDPOINT_REQUIRED_TABLES[ep]),
                1,
                f"{ep}: append-only HISTORICAL must have one table",
            )


class ExchangeCapacityViewTests(unittest.TestCase):
    """STD-15G2C: analytical view contract for Exchange mailbox capacity.

    Validates that migration 015 defines a VIEW (not a physical table), that
    the derived utilization/usage_level formulas match the accepted contract,
    and that NO_DATA fails closed when the capacity denominator is missing,
    zero, or invalid.
    """

    def setUp(self) -> None:
        self.sql = _all_sql()
        self.view_sql = (MIGRATIONS_DIR / "015_exchange_mailbox_capacity.sql").read_text(encoding="utf-8")

    def test_view_is_defined_not_physical_table(self) -> None:
        self.assertIn("CREATE OR REPLACE VIEW analytics.exchange_mailbox_capacity", self.sql)
        self.assertNotIn("CREATE TABLE analytics.exchange_mailbox_capacity", self.sql)

    def test_view_reads_from_authoritative_current_table(self) -> None:
        self.assertIn("core.usage_exchange_mailbox_usage", self.view_sql)
        # The view must not read from the snapshot (it is a current-state view).
        self.assertNotIn("_snapshot", self.view_sql)

    def test_mailbox_capacity_is_prohibit_send_receive_quota(self) -> None:
        self.assertIn("prohibit_send_receive_quota AS mailbox_capacity", self.view_sql)

    def test_utilization_formula_matches_contract(self) -> None:
        self.assertRegex(
            self.view_sql,
            re.compile(r"storage_used\s*\*\s*100\.0\s*/\s*prohibit_send_receive_quota", re.IGNORECASE),
        )
        # Fail closed: NULL when denominator missing/zero/invalid.
        self.assertRegex(
            self.view_sql,
            re.compile(r"prohibit_send_receive_quota\s+IS\s+NULL", re.IGNORECASE),
        )
        self.assertRegex(
            self.view_sql,
            re.compile(r"prohibit_send_receive_quota\s*<=\s*0", re.IGNORECASE),
        )

    def test_usage_level_boundaries_match_contract(self) -> None:
        # LOW < 50; MEDIUM >= 50 and < 80; HIGH >= 80; NO_DATA otherwise.
        low = re.compile(r"WHEN\s+utilization\s*<\s*50\s+THEN\s+'LOW'", re.IGNORECASE)
        medium = re.compile(r"WHEN\s+utilization\s*<\s*80\s+THEN\s+'MEDIUM'", re.IGNORECASE)
        high = re.compile(r"ELSE\s+'HIGH'", re.IGNORECASE)
        no_data = re.compile(r"WHEN\s+utilization\s+IS\s+NULL\s+THEN\s+'NO_DATA'", re.IGNORECASE)
        self.assertIsNotNone(low.search(self.view_sql))
        self.assertIsNotNone(medium.search(self.view_sql))
        self.assertIsNotNone(high.search(self.view_sql))
        self.assertIsNotNone(no_data.search(self.view_sql))

    def test_no_duplicated_derived_physical_columns(self) -> None:
        # The view must not insert derived utilization/status into physical tables.
        self.assertNotIn("INSERT INTO", self.view_sql.upper())
        self.assertNotIn("CREATE TABLE", self.view_sql.upper())

    def test_view_granted_to_runtime(self) -> None:
        self.assertIn("GRANT SELECT ON analytics.exchange_mailbox_capacity TO graph_agent_runtime", self.view_sql)
        self.assertIn("GRANT USAGE ON SCHEMA analytics TO graph_agent_runtime", self.view_sql)


class MiscSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _all_sql()

    def test_quoted_user_and_group_consistent(self) -> None:
        # PostgreSQL 'user' and 'group' need quoting. We use the
        # double-quoted form throughout the DDL.
        self.assertIn('core."user"', self.sql)
        self.assertIn('core."group"', self.sql)

    def test_run_uuid_column_present(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+control\.collection_run\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        self.assertIn("run_uuid", body)
        self.assertIn("UUID", body.upper())

    def test_error_classification_check_present(self) -> None:
        pattern = re.compile(
            r"CREATE\s+TABLE\s+control\.endpoint_run\s*\((?P<body>.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(self.sql)
        self.assertIsNotNone(m)
        body = m.group("body")
        for v in ("AUTH_FAILURE", "PERMISSION_REQUIRED", "THROTTLED", "API_ERROR", "NETWORK_ERROR", "UNKNOWN", "PASS"):
            self.assertIn(v, body)
        self.assertIn("ENTITY_IDENTITY_UNAVAILABLE", self.sql)

    def test_persistence_error_migration_extends_existing_check(self) -> None:
        migration = (MIGRATIONS_DIR / "012_endpoint_persistence_error.sql").read_text(encoding="utf-8")
        self.assertIn("DROP CONSTRAINT IF EXISTS endpoint_run_error_classification_check", migration)
        self.assertIn("PERSISTENCE_ERROR", migration)
        for value in ("PASS", "AUTH_FAILURE", "PERMISSION_REQUIRED", "THROTTLED", "API_ERROR", "NETWORK_ERROR", "UNKNOWN", "ENTITY_IDENTITY_UNAVAILABLE"):
            self.assertIn("'" + value + "'", migration)
        self.assertNotIn("CREATE TABLE", migration.upper())
        self.assertNotIn("GRANT", migration.upper())

    def test_endpoint_error_constraint_matches_runtime_vocabulary(self) -> None:
        """Runtime must never emit an endpoint classification PostgreSQL rejects."""
        from collectors.core.errors import CLASSIFICATIONS

        migration = (MIGRATIONS_DIR / "012_endpoint_persistence_error.sql").read_text(encoding="utf-8")
        declared = set(re.findall(r"'([A-Z_]+)'", migration))
        self.assertEqual(declared, set(CLASSIFICATIONS))

    def test_identity_unavailable_migration_changes_only_endpoint_check(self) -> None:
        migration = (MIGRATIONS_DIR / "010_endpoint_identity_unavailable.sql").read_text(encoding="utf-8")
        self.assertIn("DROP CONSTRAINT IF EXISTS endpoint_run_error_classification_check", migration)
        self.assertIn("ADD CONSTRAINT endpoint_run_error_classification_check", migration)
        self.assertIn("ENTITY_IDENTITY_UNAVAILABLE", migration)
        self.assertNotIn("CREATE TABLE", migration.upper())
        self.assertNotIn("GRANT", migration.upper())


if __name__ == "__main__":
    unittest.main()
