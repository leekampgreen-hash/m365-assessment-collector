-- 004_core_security_governance_rbac.sql
-- G06-002: Security / governance / RBAC tables.
--
-- Authoritative source: docs/database-schema-design.md Sections 7.3, 7.4,
-- 7.5, 7.6, 21.
--
-- Tables in this migration (8 physical tables):
--   core.audit_event                              — G01-005/006 EVENT_LOG
--   core.risk_detection                           — G01-014 EVENT_LOG
--   core.risky_user                               — G01-013 current
--   core.risky_user_snapshot                      — G01-013 snapshot
--   core.conditional_access_policy                — G01-011 current
--   core.conditional_access_policy_snapshot       — G01-011 snapshot
--   core.directory_role_definition                — G01-018 REFERENCE
--   core.directory_role_assignment                — G01-019 current
--   core.directory_role_assignment_snapshot       — G01-019 snapshot
--
-- ON DELETE behaviour:
--   All tenant_id FKs use ON DELETE RESTRICT. Tenant deletion must not
--   cascade-delete operational or forensic history.

BEGIN;

-- ---------------------------------------------------------------------------
-- core.audit_event  (G01-005 DIRECTORY_AUDIT + G01-006 SIGN_IN)
-- ---------------------------------------------------------------------------
CREATE TABLE core.audit_event (
    audit_event_id      BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    event_source        TEXT        NOT NULL
        CHECK (event_source IN ('DIRECTORY_AUDIT','SIGN_IN')),
    source_object_id    TEXT        NOT NULL,
    event_at            TIMESTAMPTZ NOT NULL,
    collected_at        TIMESTAMPTZ NOT NULL,
    collection_run_id   BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id     BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    actor_user_id       TEXT        NULL,
    actor_app_id        TEXT        NULL,
    activity            TEXT        NULL,
    category            TEXT        NULL,
    result              TEXT        NULL,
    is_interactive      BOOLEAN     NULL,
    risk_level          TEXT        NULL,
    extension           JSONB       NULL,
    retention_class     TEXT        NOT NULL DEFAULT 'LONG'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, event_source, source_object_id)
);

COMMENT ON TABLE  core.audit_event IS
    'G01-005 (DIRECTORY_AUDIT) and G01-006 (SIGN_IN) share this append-only fact table. event_source discriminates the two streams.';
COMMENT ON COLUMN core.audit_event.event_at IS
    'activityDateTime for directoryAudits; createdDateTime for signIns. Separate from collected_at.';
COMMENT ON COLUMN core.audit_event.risk_level IS
    'Reserved for future cross-stream correlation; NULL for current G01-005/G01-006 endpoints.';
COMMENT ON COLUMN core.audit_event.extension IS
    'Reserved JSONB extension. Default NULL; populated only when G03 catalog explicitly justifies a future field.';

-- ---------------------------------------------------------------------------
-- core.risk_detection  (G01-014)
-- ---------------------------------------------------------------------------
CREATE TABLE core.risk_detection (
    risk_detection_id        BIGSERIAL PRIMARY KEY,
    tenant_id                BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id         TEXT        NOT NULL,
    detected_at              TIMESTAMPTZ NOT NULL,
    activity_at              TIMESTAMPTZ NULL,
    collected_at             TIMESTAMPTZ NOT NULL,
    collection_run_id        BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id          BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    risk_event_type          TEXT        NULL,
    risk_level               TEXT        NULL,
    risk_state               TEXT        NULL,
    risk_detail              TEXT        NULL,
    detection_timing_type    TEXT        NULL,
    activity                 TEXT        NULL,
    affected_user_id         TEXT        NULL,
    retention_class          TEXT        NOT NULL DEFAULT 'LONG'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.risk_detection IS
    'G01-014 append-only fact. Source event id is the dedup key. Excluded: user location, IP, user agent, correlation IDs.';

-- ---------------------------------------------------------------------------
-- core.risky_user  (G01-013 current state)
-- ---------------------------------------------------------------------------
CREATE TABLE core.risky_user (
    risky_user_id            BIGSERIAL PRIMARY KEY,
    tenant_id                BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id         TEXT        NOT NULL,
    risk_level               TEXT        NULL,
    risk_state               TEXT        NULL,
    risk_detail              TEXT        NULL,
    is_deleted               BOOLEAN     NULL,
    is_processing            BOOLEAN     NULL,
    risk_last_updated_at     TIMESTAMPTZ NULL,
    last_observed_at         TIMESTAMPTZ NOT NULL,
    retention_class          TEXT        NOT NULL DEFAULT 'LONG'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

-- ---------------------------------------------------------------------------
-- core.risky_user_snapshot  (G01-013 snapshot)
-- ---------------------------------------------------------------------------
CREATE TABLE core.risky_user_snapshot (
    risky_user_snapshot_id   BIGSERIAL PRIMARY KEY,
    tenant_id                BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id         TEXT        NOT NULL,
    collection_run_id        BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id          BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    snapshot_at              TIMESTAMPTZ NOT NULL,
    risk_level               TEXT        NULL,
    risk_state               TEXT        NULL,
    risk_detail              TEXT        NULL,
    is_deleted               BOOLEAN     NULL,
    is_processing            BOOLEAN     NULL,
    risk_last_updated_at     TIMESTAMPTZ NULL,
    retention_class          TEXT        NOT NULL DEFAULT 'LONG'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id, collection_run_id)
);

COMMENT ON TABLE core.risky_user_snapshot IS
    'G01-013 per-run snapshot. Same shape as subscribed_sku_snapshot. UNIQUE(tenant_id, source_object_id, collection_run_id) prevents duplicate snapshots on re-runs.';

-- ---------------------------------------------------------------------------
-- core.conditional_access_policy  (G01-011 current state)
-- ---------------------------------------------------------------------------
CREATE TABLE core.conditional_access_policy (
    conditional_access_policy_id   BIGSERIAL PRIMARY KEY,
    tenant_id                      BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id               TEXT        NOT NULL,
    display_name                   TEXT        NULL,
    state                          TEXT        NULL,
    created_date_time              TIMESTAMPTZ NULL,
    modified_date_time             TIMESTAMPTZ NULL,
    last_observed_at               TIMESTAMPTZ NOT NULL,
    retention_class                TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.conditional_access_policy IS
    'G01-011 current-state. Per G03: metadata + state only; no conditions/grants policy bodies.';

-- ---------------------------------------------------------------------------
-- core.conditional_access_policy_snapshot  (G01-011 snapshot)
-- ---------------------------------------------------------------------------
CREATE TABLE core.conditional_access_policy_snapshot (
    conditional_access_policy_snapshot_id BIGSERIAL PRIMARY KEY,
    tenant_id                             BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id                      TEXT        NOT NULL,
    collection_run_id                     BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id                       BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    snapshot_at                           TIMESTAMPTZ NOT NULL,
    display_name                          TEXT        NULL,
    state                                 TEXT        NULL,
    created_date_time                     TIMESTAMPTZ NULL,
    modified_date_time                    TIMESTAMPTZ NULL,
    retention_class                       TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id, collection_run_id)
);

-- ---------------------------------------------------------------------------
-- core.directory_role_definition  (G01-018 REFERENCE)
-- ---------------------------------------------------------------------------
CREATE TABLE core.directory_role_definition (
    directory_role_definition_id   BIGSERIAL PRIMARY KEY,
    tenant_id                      BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id               TEXT        NOT NULL,
    display_name                   TEXT        NULL,
    description                    TEXT        NULL,
    is_built_in                    BOOLEAN     NULL,
    last_observed_at               TIMESTAMPTZ NOT NULL,
    retention_class                TEXT        NOT NULL DEFAULT 'REFERENCE'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.directory_role_definition IS
    'G01-018 REFERENCE. Per G03, rolePermissions payloads are excluded.';

-- ---------------------------------------------------------------------------
-- core.directory_role_assignment  (G01-019 current state)
-- ---------------------------------------------------------------------------
CREATE TABLE core.directory_role_assignment (
    directory_role_assignment_id   BIGSERIAL PRIMARY KEY,
    tenant_id                      BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id               TEXT        NOT NULL,
    role_definition_id             TEXT        NULL,
    principal_id                   TEXT        NULL,
    directory_scope_id             TEXT        NULL,
    last_observed_at               TIMESTAMPTZ NOT NULL,
    retention_class                TEXT        NOT NULL DEFAULT 'LONG'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id)
);

COMMENT ON TABLE core.directory_role_assignment IS
    'G01-019 current-state. role_definition_id / principal_id / directory_scope_id are soft Graph references; no DB-level FK is enforced.';

-- ---------------------------------------------------------------------------
-- core.directory_role_assignment_snapshot  (G01-019 snapshot)
-- ---------------------------------------------------------------------------
CREATE TABLE core.directory_role_assignment_snapshot (
    directory_role_assignment_snapshot_id BIGSERIAL PRIMARY KEY,
    tenant_id                             BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id                      TEXT        NOT NULL,
    collection_run_id                     BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id                       BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    snapshot_at                           TIMESTAMPTZ NOT NULL,
    role_definition_id                    TEXT        NULL,
    principal_id                          TEXT        NULL,
    directory_scope_id                    TEXT        NULL,
    retention_class                       TEXT        NOT NULL DEFAULT 'LONG'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    UNIQUE (tenant_id, source_object_id, collection_run_id)
);

COMMIT;