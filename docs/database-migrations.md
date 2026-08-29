# G06-002 — Database Migrations

> **G06-002 — PostgreSQL DDL & Migration Implementation**
> **Authoritative design:** `docs/database-schema-design.md` (G06-001 + G06-001R)
> **Status:** Forward-only DDL artifacts. **Migrations are NOT applied** in G06-002.

## 1. Scope

G06-002 produces the PostgreSQL migration files that materialise the
physical schema described in `docs/database-schema-design.md`. The task
creates migration artifacts and **does not** connect to any PostgreSQL
server, does not install PostgreSQL, does not start a container, and does
not modify any collector, configuration, secret, or discovery state.

## 2. Target

PostgreSQL (open-source engine) — selected in `docs/database-schema-design.md`
§2. Logical schema design is engine-agnostic; the migrations here are
PostgreSQL-specific DDL.

## 3. Migration layout

```
database/migrations/
  001_create_schemas.sql
  002_core_tenant_and_control.sql
  003_core_directory_and_licensing.sql
  004_core_security_governance_rbac.sql
  005_core_service_health_and_change.sql
  006_raw_traceability.sql
  007_indexes.sql
  008_usage_reports.sql
  009_user_license_assignment.sql
  010_endpoint_identity_unavailable.sql
  012_endpoint_persistence_error.sql
```

Files are applied in numeric order. Each file is idempotent where
practical (`CREATE SCHEMA IF NOT EXISTS`, `IF NOT EXISTS` table forms via
plain `CREATE TABLE` — re-running the whole set against an empty database
is deterministic). All files wrap their DDL in `BEGIN; ... COMMIT;` so
they are transaction-safe.

## 4. Schemas

| Schema | Tables in G06-002 | Purpose |
|---|---|---|
| `control` | 2 | Collection execution / endpoint execution / lineage |
| `raw` | 1 | Optional Graph evidence (off by default) |
| `core` | 26 | Normalised operational entities (incl. tenant) |
| `analytics` | 0 | Serving layer — intentionally empty in G06-002 |

**Total physical tables: 29** (control 2 + raw 1 + core 26 + analytics 0).
The `analytics` schema is reserved for materialised views / serving
queries in a later G-task; no physical tables exist in it during G06-002.

## 5. Table inventory

### control (2)

- `control.collection_run` — per-runtime execution lineage.
- `control.endpoint_run` — per-endpoint execution lineage.

### raw (1)

- `raw.raw_graph_record` — optional Graph evidence.

### core (26)

- `core.tenant`
- Directory / identity: `core."user"`, `core."group"`, `core.organization`,
  `core.application`, `core.service_principal`, `core.device`,
  `core.administrative_unit`
- Licensing: `core.subscribed_sku`, `core.subscribed_sku_snapshot`
- Security / Audit: `core.audit_event`, `core.risk_detection`
- Identity Protection: `core.risky_user`, `core.risky_user_snapshot`
- Conditional Access: `core.conditional_access_policy`,
  `core.conditional_access_policy_snapshot`, `core.named_location`
- RBAC: `core.directory_role_definition`, `core.directory_role_assignment`,
  `core.directory_role_assignment_snapshot`
- Service Health / Change: `core.service_health_overview`,
  `core.service_health_overview_snapshot`, `core.service_health_issue`,
  `core.service_health_issue_history`, `core.service_update_message`,
  `core.service_update_message_history`

`core."user"` and `core."group"` are double-quoted to avoid PostgreSQL
identifier collision with reserved words. This strategy is consistent
across all migration files.

## 6. Key and FK principles

- Internal surrogate `BIGSERIAL` primary keys throughout.
- Graph `source_object_id` carried as a separate `TEXT` column, never
  trusted as a primary key on its own.
- All operational, audit, and raw rows carry `tenant_id` and reference
  `core.tenant(tenant_id)`.
- UNIQUE constraints are tenant-scoped where applicable:
  - Current-state: `UNIQUE (tenant_id, source_object_id)`
  - Snapshot: `UNIQUE (tenant_id, source_object_id, collection_run_id)`
  - Endpoint: `UNIQUE (collection_run_id, endpoint_id)`
  - INCREMENTAL history: `UNIQUE (tenant_id, source_object_id, version_identity)`
- `ON DELETE` behaviour is deliberate:
  - `control.endpoint_run.collection_run_id` → `ON DELETE CASCADE`
  - All `tenant_id` foreign keys → `ON DELETE RESTRICT`
  - `raw.raw_graph_record` lineage FKs → `ON DELETE CASCADE`
- Tenant deletion must not cascade-delete operational or forensic
  history.

## 7. version_identity ownership

The two `*_history` tables (`core.service_health_issue_history`,
`core.service_update_message_history`) `STORE` a `version_identity`
column (`BYTEA`). The algorithm that calculates its hash belongs to the
collector / application layer per `docs/database-schema-design.md`
§7.7.a, §7.7.b, §10.3. No speculative SQL-side hash function is added.
The DDL preserves the column; the application supplies the value.

Primary rule (per design):

```
version_identity = hash(tenant_id, source_object_id, last_modified_date_time)
```

Fallback rule when Graph omits `lastModifiedDateTime`:

- G01-016: `hash(tenant_id, source_object_id, status, is_resolved,
  start_date_time, end_date_time)`
- G01-017: `hash(tenant_id, source_object_id, category, severity,
  is_major_change, start_date_time, end_date_time,
  action_required_by_date_time)`

## 8. Raw payload scrub requirement

`raw.raw_graph_record.payload` is `JSONB NOT NULL`. The DDL adds a
defensive **top-level** CHECK constraint
(`raw_graph_record_no_top_level_creds`) that rejects rows whose
top-level JSONB keys include any of `Authorization`, `authorization`,
`access_token`, `refresh_token`, `client_secret`, `password`, or
`bearer`.

This is **not** a complete recursive secret-scrubbing solution. The
insert path (collector / persistence layer) is responsible for
recursively scrubbing the JSONB payload before insert. Raw retention is
off by default; operators enable it per-endpoint via a runtime flag
(future G-task).

## 9. Transaction strategy

- Each migration is a single PostgreSQL transaction (`BEGIN; ... COMMIT;`).
- The migration files do not perform DML; they only create schemas,
  tables, indexes, and CHECK constraints.
- Migrations are forward-only. No `DROP`, `TRUNCATE`, `DELETE`,
  `CREATE DATABASE`, `CREATE ROLE`, `CREATE USER`, `GRANT`, `INSERT`,
  or `UPDATE` is present.

## 10. Rollback philosophy

G06-002 does **not** include rollback migrations. Migrations are
forward-only schema creation. If a future G-task must roll back a
schema, it does so by introducing a new forward migration that
reverses the change explicitly (e.g. `DROP TABLE` in a new migration
file). This is consistent with the destructive-statement prohibition
in G06-002.

## 11. How migrations are eventually applied

These migrations are **not applied** in G06-002. A future deployment
G-task will:

1. Stand up a PostgreSQL instance.
2. Create a database (out of scope of the migration files; the
   migrations target the current/default database of the connecting
   role).
3. Apply the migration files in numeric order using a migration tool
   (e.g. `psql -f`, Flyway, Liquibase, sqitch, golang-migrate). The
   files use vanilla PostgreSQL DDL and require no tool-specific
   syntax.
4. Provision `core.tenant` rows and application DB roles per
   `docs/database-schema-design.md` §13.

## 12. Validation command

Offline validation lives in `tests/database/test_migrations.py`. Run
with:

```bash
python3 -m unittest tests.database.test_migrations -v
```

The test suite validates (at minimum):

- migration files discoverable in deterministic numeric order
- SQL files non-empty
- exactly 4 schemas declared
- exactly 29 CREATE TABLE definitions
- analytics has zero physical tables
- all 29 accepted table names exist
- no unexpected table names
- all G01-required persistence tables exist
- G01-016 current + history exist
- G01-017 current + history exist
- required history uniqueness references `version_identity`
- snapshot tables contain collection lineage
- event tables contain source identity + timestamps
- control tables exist
- raw table exists
- retention controlled values represented
- no forbidden credential column names
- no destructive DDL
- no credential/token-like literal values
- expected FK/UNIQUE structures present
- SQL statements terminate properly
- offline G01-001..G01-019 endpoint mapping preserves CURRENT_ONLY,
  HISTORICAL, and HISTORICAL_WITH_SNAPSHOT requirements

## 13. Scope remaining for future database deployment / loading

- PostgreSQL provisioning and connection management.
- `core.tenant` provisioning at first deployment.
- Application DB roles per `docs/database-schema-design.md` §13
  (collector role, analytics role, operator role).
- Encryption at rest, TLS, IAM-style credential management.
- Retention policy engine (driven by `retention_class`; durations
  defined elsewhere — G03 retains classification authority).
- Migration application tooling (out of scope of G06-002).
- All INSERT/UPDATE/DQL traffic against the schema (collector
  persistence is a G07 concern; G06-002 ships the schema only).

## 14. Source files changed in G06-002

- `database/migrations/001_create_schemas.sql` (new)
- `database/migrations/002_core_tenant_and_control.sql` (new)
- `database/migrations/003_core_directory_and_licensing.sql` (new)
- `database/migrations/004_core_security_governance_rbac.sql` (new)
- `database/migrations/005_core_service_health_and_change.sql` (new)
- `database/migrations/006_raw_traceability.sql` (new)
- `database/migrations/007_indexes.sql` (new)
- `tests/database/test_migrations.py` (new)
- `docs/database-migrations.md` (this file; new)

## 15. Protected files (unchanged)

- `config/api_inventory.json`
- `secrets/*`
- `agents/discovery/*`
- `data/discovery/*`
- `collectors/core/*`
- `collectors/run_collector.py`
- `docs/api-inventory.md`
- `docs/permission-matrix.md`
- `docs/data-catalog.md`
- `docs/auth-app-registration-design.md`
- `docs/collector-framework.md`
- `docs/database-schema-design.md`
