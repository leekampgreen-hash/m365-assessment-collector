-- 005_core_service_health_and_change.sql
-- G06-002: Service Health / Service Update tables.
--
-- Authoritative source: docs/database-schema-design.md Sections 7.7, 7.7.a,
-- 7.7.b, 10.1, 21.
--
-- Tables in this migration (6 physical tables):
--   core.service_health_overview              — G01-015 current
--   core.service_health_overview_snapshot     — G01-015 snapshot
--   core.service_health_issue                 — G01-016 current (INCREMENTAL)
--   core.service_health_issue_history         — G01-016 history (INCREMENTAL + HISTORICAL)
--   core.service_update_message               — G01-017 current (INCREMENTAL)
--   core.service_update_message_history       — G01-017 history (INCREMENTAL + HISTORICAL)
--
-- G06-001R correction is implemented: G01-016 and G01-017 each have a
-- current-state upsert table AND a versioned history table keyed by
-- (tenant_id, source_object_id, version_identity).
--
-- version_identity ownership:
--   The history table STORES the version_identity column; the algorithm
--   for computing its hash belongs to the Collector / application layer
--   per the accepted G06-001R design (Sections 7.7.a, 7.7.b, 10.3).
--   No speculative SQL-side hash function is added here.
--
-- ON DELETE behaviour:
--   All tenant_id FKs use ON DELETE RESTRICT. Tenant deletion must not
--   cascade-delete operational or forensic history.

BEGIN;

-- ---------------------------------------------------------------------------
-- core.service_health_overview  (G01-015 current state)
-- ---------------------------------------------------------------------------
CREATE TABLE core.service_health_overview (
    service_health_overview_id   BIGSERIAL PRIMARY KEY,
    tenant_id                    BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id             TEXT        NOT NULL,
    service                      TEXT        NULL,
    status                       TEXT        NULL,
    last_observed_at             TIMESTAMPTZ NOT NULL,
    retention_class              TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.service_health_overview IS
    'G01-015 current-state. service + status only; per-run history preserved in core.service_health_overview_snapshot.';

-- ---------------------------------------------------------------------------
-- core.service_health_overview_snapshot  (G01-015 snapshot)
-- ---------------------------------------------------------------------------
CREATE TABLE core.service_health_overview_snapshot (
    service_health_overview_snapshot_id BIGSERIAL PRIMARY KEY,
    tenant_id                           BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id                    TEXT        NOT NULL,
    collection_run_id                   BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id                     BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    snapshot_at                         TIMESTAMPTZ NOT NULL,
    service                             TEXT        NULL,
    status                              TEXT        NULL,
    retention_class                     TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id, collection_run_id)
);

-- ---------------------------------------------------------------------------
-- core.service_health_issue  (G01-016 current state — INCREMENTAL)
-- ---------------------------------------------------------------------------
CREATE TABLE core.service_health_issue (
    service_health_issue_id   BIGSERIAL PRIMARY KEY,
    tenant_id                 BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id          TEXT        NOT NULL,
    service                   TEXT        NULL,
    status                    TEXT        NULL,
    classification            TEXT        NULL,
    start_date_time           TIMESTAMPTZ NULL,
    end_date_time             TIMESTAMPTZ NULL,
    last_modified_date_time   TIMESTAMPTZ NULL,
    is_resolved               BOOLEAN     NULL,
    last_observed_at          TIMESTAMPTZ NOT NULL,
    retention_class           TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.service_health_issue IS
    'G01-016 current-state. INCREMENTAL watermark-based upsert by Graph id. Lifecycle evolution preserved in core.service_health_issue_history.';

-- ---------------------------------------------------------------------------
-- core.service_health_issue_history  (G01-016 history — INCREMENTAL + HISTORICAL)
-- ---------------------------------------------------------------------------
CREATE TABLE core.service_health_issue_history (
    service_health_issue_history_id   BIGSERIAL PRIMARY KEY,
    tenant_id                         BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id                  TEXT        NOT NULL,
    version_identity                  BYTEA       NOT NULL,
    service                           TEXT        NULL,
    status                            TEXT        NULL,
    classification                    TEXT        NULL,
    start_date_time                   TIMESTAMPTZ NULL,
    end_date_time                     TIMESTAMPTZ NULL,
    last_modified_date_time           TIMESTAMPTZ NULL,
    is_resolved                       BOOLEAN     NULL,
    observed_at                       TIMESTAMPTZ NOT NULL,
    collected_at                      TIMESTAMPTZ NOT NULL,
    collection_run_id                 BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id                   BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    extension                         JSONB       NULL,
    retention_class                   TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id, version_identity)
);

COMMENT ON TABLE  core.service_health_issue_history IS
    'G01-016 append-only versioned history. A history row is appended only when the deterministic version_identity advances.';
COMMENT ON COLUMN core.service_health_issue_history.version_identity IS
    'Deterministic version-identity hash. Computed by the collector/application layer (primary rule: hash(tenant_id, source_object_id, last_modified_date_time); fallback: hash(tenant_id, source_object_id, status, is_resolved, start_date_time, end_date_time)). Stored here verbatim; not calculated in SQL.';

-- ---------------------------------------------------------------------------
-- core.service_update_message  (G01-017 current state — INCREMENTAL)
-- ---------------------------------------------------------------------------
CREATE TABLE core.service_update_message (
    service_update_message_id        BIGSERIAL PRIMARY KEY,
    tenant_id                        BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id                 TEXT        NOT NULL,
    category                         TEXT        NULL,
    severity                         TEXT        NULL,
    start_date_time                  TIMESTAMPTZ NULL,
    end_date_time                    TIMESTAMPTZ NULL,
    last_modified_date_time          TIMESTAMPTZ NULL,
    is_major_change                  BOOLEAN     NULL,
    action_required_by_date_time     TIMESTAMPTZ NULL,
    services                         TEXT[]      NULL,
    last_observed_at                 TIMESTAMPTZ NOT NULL,
    retention_class                  TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.service_update_message IS
    'G01-017 current-state. INCREMENTAL watermark-based upsert. Publication-lifecycle evolution preserved in core.service_update_message_history.';

-- ---------------------------------------------------------------------------
-- core.service_update_message_history  (G01-017 history — INCREMENTAL + HISTORICAL)
-- ---------------------------------------------------------------------------
CREATE TABLE core.service_update_message_history (
    service_update_message_history_id BIGSERIAL PRIMARY KEY,
    tenant_id                          BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id                   TEXT        NOT NULL,
    version_identity                   BYTEA       NOT NULL,
    category                           TEXT        NULL,
    severity                           TEXT        NULL,
    start_date_time                    TIMESTAMPTZ NULL,
    end_date_time                      TIMESTAMPTZ NULL,
    last_modified_date_time            TIMESTAMPTZ NULL,
    is_major_change                    BOOLEAN     NULL,
    action_required_by_date_time       TIMESTAMPTZ NULL,
    services                           TEXT[]      NULL,
    observed_at                        TIMESTAMPTZ NOT NULL,
    collected_at                       TIMESTAMPTZ NOT NULL,
    collection_run_id                  BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id                    BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    extension                          JSONB       NULL,
    retention_class                    TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id, version_identity)
);

COMMENT ON TABLE  core.service_update_message_history IS
    'G01-017 append-only versioned history. A history row is appended only when the deterministic version_identity advances.';
COMMENT ON COLUMN core.service_update_message_history.version_identity IS
    'Deterministic version-identity hash. Computed by the collector/application layer (primary rule: hash(tenant_id, source_object_id, last_modified_date_time); fallback: hash(tenant_id, source_object_id, category, severity, is_major_change, start_date_time, end_date_time, action_required_by_date_time)). Stored here verbatim; not calculated in SQL.';

COMMIT;