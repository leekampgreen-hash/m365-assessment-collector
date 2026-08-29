-- 002_core_tenant_and_control.sql
-- G06-002: Tenant registry + control / lineage tables.
--
-- Authoritative source: docs/database-schema-design.md Sections 5, 12, 21.
--
-- Tables in this migration (3 physical tables):
--   core.tenant         — tenant registry
--   control.collection_run   — per-runtime execution
--   control.endpoint_run    — per-endpoint execution
--
-- Identifier quoting:
--   core.user / core.group collide conceptually with SQL reserved
--   identifiers. We adopt a consistent double-quoting strategy (PostgreSQL
--   "double quote" form). All references to core.user and core.group in
--   downstream migrations use the same form.
--
-- ON DELETE behaviour:
--   control.endpoint_run.collection_run_id  → ON DELETE CASCADE
--     (an endpoint_run cannot exist without its parent run; the design
--      treats the parent/child as one operational unit).
--   control.collection_run.tenant_id        → ON DELETE RESTRICT
--   control.endpoint_run.tenant_id          → ON DELETE RESTRICT
--   Tenant deletion must never cascade-delete operational history.

BEGIN;

-- ---------------------------------------------------------------------------
-- core.tenant
-- ---------------------------------------------------------------------------
CREATE TABLE core.tenant (
    tenant_id        BIGSERIAL PRIMARY KEY,
    entra_tenant_id  TEXT        NOT NULL UNIQUE,
    display_label    TEXT        NOT NULL,
    enabled          BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    retention_class  TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE'))
);

COMMENT ON TABLE  core.tenant IS
    'Tenant registry. Holds Graph directory id + operator label only. Never stores credentials, secrets, tokens, or certificates.';
COMMENT ON COLUMN core.tenant.entra_tenant_id IS
    'Microsoft Entra directory id (not a credential).';
COMMENT ON COLUMN core.tenant.retention_class IS
    'Controlled retention value per G03 / G06-001 Section 15. Duration is set elsewhere.';

-- ---------------------------------------------------------------------------
-- control.collection_run
-- ---------------------------------------------------------------------------
CREATE TABLE control.collection_run (
    collection_run_id          BIGSERIAL PRIMARY KEY,
    run_uuid                   UUID        NOT NULL UNIQUE,
    tenant_id                  BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    started_at                 TIMESTAMPTZ NOT NULL,
    completed_at               TIMESTAMPTZ NULL,
    status                     TEXT        NOT NULL
        CHECK (status IN ('RUNNING','SUCCESS','PARTIAL_SUCCESS','FAILED')),
    trigger_source             TEXT        NOT NULL,
    collector_version          TEXT        NOT NULL,
    config_version             TEXT        NULL,
    selected_endpoint_ids      TEXT[]      NOT NULL,
    endpoints_total            INTEGER     NOT NULL,
    endpoints_passed           INTEGER     NOT NULL DEFAULT 0,
    endpoints_failed           INTEGER     NOT NULL DEFAULT 0,
    rows_total                 BIGINT      NOT NULL DEFAULT 0,
    auth_error_classification  TEXT        NULL,
    error_summary              JSONB       NULL,
    retention_class            TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE'))
);

COMMENT ON TABLE  control.collection_run IS
    'One row per CollectorRuntime.run(...) call. System of record for collection lineage.';
COMMENT ON COLUMN control.collection_run.error_summary IS
    'Sanitised aggregate failure summary JSON. Insert path must never include tokens, secrets, or Authorization values.';
COMMENT ON COLUMN control.collection_run.selected_endpoint_ids IS
    'Endpoint ids selected for this run, in stable order. Used for idempotency / forensic reconstruction.';

-- ---------------------------------------------------------------------------
-- control.endpoint_run
-- ---------------------------------------------------------------------------
CREATE TABLE control.endpoint_run (
    endpoint_run_id        BIGSERIAL PRIMARY KEY,
    collection_run_id      BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE CASCADE,
    endpoint_id            TEXT        NOT NULL,
    endpoint_name          TEXT        NOT NULL,
    tenant_id              BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    started_at             TIMESTAMPTZ NOT NULL,
    completed_at           TIMESTAMPTZ NULL,
    status                 TEXT        NOT NULL
        CHECK (status IN ('PASS','ERROR')),
    pages                  INTEGER     NOT NULL DEFAULT 0,
    rows                   BIGINT      NOT NULL DEFAULT 0,
    http_status            INTEGER     NULL,
    error_classification   TEXT        NULL
        CHECK (error_classification IN ('PASS','AUTH_FAILURE','PERMISSION_REQUIRED','THROTTLED','API_ERROR','NETWORK_ERROR','UNKNOWN')),
    error_message_safe     TEXT        NULL,
    retry_count            INTEGER     NOT NULL DEFAULT 0,
    graph_error_code       TEXT        NULL,
    retention_class        TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (collection_run_id, endpoint_id)
);

COMMENT ON TABLE  control.endpoint_run IS
    'One row per endpoint attempted inside a collection_run. Mirrors CollectionResult; never stores raw authentication exceptions.';
COMMENT ON COLUMN control.endpoint_run.error_message_safe IS
    'Sanitised classification label only. Insert path must scrub tokens, secrets, Authorization headers, and bearer values.';

COMMIT;