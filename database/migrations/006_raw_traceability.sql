-- 006_raw_traceability.sql
-- G06-002: Optional raw Graph response evidence storage.
--
-- Authoritative source: docs/database-schema-design.md Sections 6, 13.
--
-- Tables in this migration (1 physical table):
--   raw.raw_graph_record — optional Graph evidence (off by default)
--
-- Security posture (from G06-001 Section 6 and ADR-G06-06):
--   - The insert path is responsible for recursively scrubbing the JSONB
--     payload before insert. This DDL does NOT claim to fully sanitise
--     arbitrary nested JSON.
--   - Raw retention is OFF. Operators enable it per-endpoint through a
--     runtime flag (future G-task; not implemented in G06-002).
--   - Storing unlimited sensitive payloads is NOT permitted.
--   - This DDL does NOT introduce any credential-column names. No
--     columns for Authorization, access_token, refresh_token,
--     client_secret, password, or bearer token exist in this table.
--
-- Defensive top-level CHECK (per G06-002 §12): where practical, a
-- top-level CHECK on payload is added to reject rows whose TOP-LEVEL JSON
-- keys contain any of the forbidden credential names. This is NOT a
-- complete recursive secret-scrubbing solution; it only filters the
-- outermost JSON object. Application-layer recursive scrubbing remains
-- mandatory.

BEGIN;

CREATE TABLE raw.raw_graph_record (
    raw_record_id      BIGSERIAL PRIMARY KEY,
    collection_run_id  BIGINT      NOT NULL
        REFERENCES control.collection_run(collection_run_id) ON DELETE CASCADE,
    endpoint_run_id    BIGINT      NOT NULL
        REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE CASCADE,
    endpoint_id        TEXT        NOT NULL,
    tenant_id          BIGINT      NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    source_object_id   TEXT        NULL,
    collected_at       TIMESTAMPTZ NOT NULL,
    payload            JSONB       NOT NULL,
    payload_sha256     BYTEA       NOT NULL,
    payload_byte_size  INTEGER     NOT NULL CHECK (payload_byte_size >= 0),
    retention_class    TEXT        NOT NULL DEFAULT 'SHORT'
        CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE')),
    CONSTRAINT raw_graph_record_no_top_level_creds CHECK (
        NOT (payload ? 'Authorization')
        AND NOT (payload ? 'authorization')
        AND NOT (payload ? 'access_token')
        AND NOT (payload ? 'refresh_token')
        AND NOT (payload ? 'client_secret')
        AND NOT (payload ? 'password')
        AND NOT (payload ? 'bearer')
    )
);

COMMENT ON TABLE  raw.raw_graph_record IS
    'Optional Graph response evidence. Off by default. Insert path MUST recursively scrub the JSONB payload before insert.';
COMMENT ON COLUMN raw.raw_graph_record.payload IS
    'Sanitised JSONB payload. Insert path is responsible for recursively scrubbing nested credential fields; this column has no DB-side recursive scrubber.';
COMMENT ON COLUMN raw.raw_graph_record.payload_sha256 IS
    'SHA-256 hash for dedup detection and tamper-evidence.';
COMMENT ON COLUMN raw.raw_graph_record.payload_byte_size IS
    'Pre-insert payload byte size for capacity planning.';
COMMENT ON CONSTRAINT raw_graph_record_no_top_level_creds ON raw.raw_graph_record IS
    'Defensive top-level CHECK. Rejects rows whose top-level JSONB keys include any credential name. NOT a recursive scrub. Application-layer scrubbing remains mandatory.';

COMMIT;