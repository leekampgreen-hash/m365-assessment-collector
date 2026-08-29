-- 003_core_directory_and_licensing.sql
-- G06-002: Directory / identity / licensing tables.
--
-- Authoritative source: docs/database-schema-design.md Sections 7.1, 7.2, 21.
--
-- Tables in this migration (10 physical tables):
--   core."user"                       — G01-001 SNAPSHOT CURRENT_ONLY
--   core."group"                      — G01-002 SNAPSHOT CURRENT_ONLY
--   core.organization                 — G01-003 SNAPSHOT CURRENT_ONLY
--   core.application                  — G01-007 SNAPSHOT CURRENT_ONLY
--   core.service_principal            — G01-008 SNAPSHOT CURRENT_ONLY
--   core.device                       — G01-009 SNAPSHOT CURRENT_ONLY
--   core.administrative_unit          — G01-010 SNAPSHOT CURRENT_ONLY
--   core.subscribed_sku               — G01-004 current state
--   core.subscribed_sku_snapshot      — G01-004 snapshot
--   core.named_location               — G01-012 SNAPSHOT CURRENT_ONLY
--
-- Identifier quoting:
--   PostgreSQL reserves both `user` and `group`. The accepted design
--   uses these exact table names (docs/database-schema-design.md §21),
--   so we double-quote them throughout the DDL. All references in later
--   migrations use the same form.
--
-- ON DELETE behaviour:
--   All tenant_id FKs use ON DELETE RESTRICT. Tenant deletion must not
--   cascade-delete operational history.

BEGIN;

-- ---------------------------------------------------------------------------
-- core."user"  (G01-001)
-- ---------------------------------------------------------------------------
CREATE TABLE core."user" (
    user_id              BIGSERIAL PRIMARY KEY,
    tenant_id            BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id     TEXT        NOT NULL,
    user_principal_name  TEXT        NULL,
    display_name         TEXT        NULL,
    user_type            TEXT        NULL,
    account_enabled      BOOLEAN     NULL,
    created_date_time    TIMESTAMPTZ NULL,
    last_observed_at     TIMESTAMPTZ NOT NULL,
    retention_class      TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    extension            JSONB       NULL,
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE  core."user" IS
    'G01-001 SNAPSHOT CURRENT_ONLY. Upsert by (tenant_id, source_object_id). extension JSONB reserved for future catalog-justified fields; default NULL.';
COMMENT ON COLUMN core."user".extension IS
    'Reserved JSONB extension. Default NULL; populated only when G03 catalog explicitly justifies a future field.';

-- ---------------------------------------------------------------------------
-- core."group"  (G01-002)
-- ---------------------------------------------------------------------------
CREATE TABLE core."group" (
    group_id            BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id    TEXT        NOT NULL,
    display_name        TEXT        NULL,
    mail                TEXT        NULL,
    mail_enabled        BOOLEAN     NULL,
    security_enabled    BOOLEAN     NULL,
    group_types         TEXT[]      NULL,
    last_observed_at    TIMESTAMPTZ NOT NULL,
    retention_class     TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core."group" IS
    'G01-002 SNAPSHOT CURRENT_ONLY. Upsert by (tenant_id, source_object_id).';

-- ---------------------------------------------------------------------------
-- core.organization  (G01-003)
-- ---------------------------------------------------------------------------
CREATE TABLE core.organization (
    organization_id       BIGSERIAL PRIMARY KEY,
    tenant_id             BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id      TEXT        NOT NULL,
    display_name          TEXT        NULL,
    country_letter_code   TEXT        NULL,
    tenant_type           TEXT        NULL,
    verified_domains      JSONB       NULL,
    last_observed_at      TIMESTAMPTZ NOT NULL,
    retention_class       TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id),
    UNIQUE (tenant_id)
);

COMMENT ON TABLE core.organization IS
    'G01-003 SNAPSHOT CURRENT_ONLY. Expected single row per tenant; UNIQUE(tenant_id) reinforces that invariant.';

-- ---------------------------------------------------------------------------
-- core.application  (G01-007)
-- ---------------------------------------------------------------------------
CREATE TABLE core.application (
    application_id        BIGSERIAL PRIMARY KEY,
    tenant_id             BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id      TEXT        NOT NULL,
    app_id                TEXT        NULL,
    display_name          TEXT        NULL,
    sign_in_audience      TEXT        NULL,
    created_date_time     TIMESTAMPTZ NULL,
    last_observed_at      TIMESTAMPTZ NOT NULL,
    retention_class       TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON COLUMN core.application.app_id IS
    'Public-ish application identifier from Graph (not a credential). Used for app<->service_principal correlation.';

-- ---------------------------------------------------------------------------
-- core.service_principal  (G01-008)
-- ---------------------------------------------------------------------------
CREATE TABLE core.service_principal (
    service_principal_id    BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id        TEXT        NOT NULL,
    app_id                  TEXT        NULL,
    display_name            TEXT        NULL,
    account_enabled         BOOLEAN     NULL,
    service_principal_type  TEXT        NULL,
    last_observed_at        TIMESTAMPTZ NOT NULL,
    retention_class         TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON COLUMN core.service_principal.app_id IS
    'Joins to application.app_id for app<->service_principal correlation. Not enforced as FK because both sides are owned by Graph.';

-- ---------------------------------------------------------------------------
-- core.device  (G01-009)
-- ---------------------------------------------------------------------------
CREATE TABLE core.device (
    device_id                          BIGSERIAL PRIMARY KEY,
    tenant_id                          BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id                   TEXT        NOT NULL,
    device_graph_id                    TEXT        NULL,
    account_enabled                    BOOLEAN     NULL,
    operating_system                   TEXT        NULL,
    operating_system_version           TEXT        NULL,
    trust_type                         TEXT        NULL,
    approximate_last_sign_in_date_time TIMESTAMPTZ NULL,
    last_observed_at                   TIMESTAMPTZ NOT NULL,
    retention_class                    TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON COLUMN core.device.approximate_last_sign_in_date_time IS
    'Operational only; not a watermark and not used for incremental filtering.';

-- ---------------------------------------------------------------------------
-- core.administrative_unit  (G01-010)
-- ---------------------------------------------------------------------------
CREATE TABLE core.administrative_unit (
    administrative_unit_id  BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id        TEXT        NOT NULL,
    display_name            TEXT        NULL,
    description             TEXT        NULL,
    visibility              TEXT        NULL,
    last_observed_at        TIMESTAMPTZ NOT NULL,
    retention_class         TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

-- ---------------------------------------------------------------------------
-- core.subscribed_sku  (G01-004 current state)
-- ---------------------------------------------------------------------------
CREATE TABLE core.subscribed_sku (
    subscribed_sku_id   BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id    TEXT        NOT NULL,
    sku_id              TEXT        NULL,
    sku_part_number     TEXT        NULL,
    capability_status   TEXT        NULL,
    consumed_units      INTEGER     NULL,
    prepaid_units       INTEGER     NULL,
    service_plans       JSONB       NULL,
    last_observed_at    TIMESTAMPTZ NOT NULL,
    retention_class     TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.subscribed_sku IS
    'G01-004 current-state row. Upsert by (tenant_id, source_object_id). Per-run history preserved in core.subscribed_sku_snapshot.';

-- ---------------------------------------------------------------------------
-- core.subscribed_sku_snapshot  (G01-004 snapshot)
-- ---------------------------------------------------------------------------
CREATE TABLE core.subscribed_sku_snapshot (
    snapshot_id           BIGSERIAL PRIMARY KEY,
    tenant_id             BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id      TEXT        NOT NULL,
    collection_run_id     BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id       BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    snapshot_at           TIMESTAMPTZ NOT NULL,
    consumed_units        INTEGER     NULL,
    prepaid_units         INTEGER     NULL,
    capability_status     TEXT        NULL,
    service_plans         JSONB       NULL,
    retention_class       TEXT        NOT NULL DEFAULT 'STANDARD'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id, collection_run_id)
);

COMMENT ON TABLE core.subscribed_sku_snapshot IS
    'G01-004 per-run snapshot. UNIQUE(tenant_id, source_object_id, collection_run_id) prevents duplicate snapshots on re-runs.';

-- ---------------------------------------------------------------------------
-- core.named_location  (G01-012)
-- ---------------------------------------------------------------------------
CREATE TABLE core.named_location (
    named_location_id   BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id    TEXT        NOT NULL,
    display_name        TEXT        NULL,
    created_date_time   TIMESTAMPTZ NULL,
    modified_date_time  TIMESTAMPTZ NULL,
    last_observed_at    TIMESTAMPTZ NOT NULL,
    retention_class     TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.named_location IS
    'G01-012 SNAPSHOT CURRENT_ONLY. Per G03, raw ipRanges / country lists are excluded by default.';

COMMIT;
