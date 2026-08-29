-- 007_indexes.sql
-- G06-002: Non-UNIQUE performance indexes justified by G06-001 §16.
--
-- UNIQUE constraints are already inline in the table CREATE statements.
-- This migration adds only NON-UNIQUE indexes that are not redundant
-- with those UNIQUE constraints.
--
-- Authoritative source: docs/database-schema-design.md Section 16.
--
-- Cardinality-conscious, intentional set. No speculative indexes on
-- every endpoint_id+status pair; no JSONB extension secondary indexes;
-- no full-text indexes.

BEGIN;

-- ---------------------------------------------------------------------------
-- control
-- ---------------------------------------------------------------------------
CREATE INDEX collection_run_status_started_at_idx
    ON control.collection_run (status, started_at DESC);

CREATE INDEX collection_run_tenant_started_at_idx
    ON control.collection_run (tenant_id, started_at DESC);

CREATE INDEX endpoint_run_tenant_endpoint_started_at_idx
    ON control.endpoint_run (tenant_id, endpoint_id, started_at DESC);

CREATE INDEX endpoint_run_status_started_at_idx
    ON control.endpoint_run (status, started_at DESC);

-- ---------------------------------------------------------------------------
-- raw
-- ---------------------------------------------------------------------------
CREATE INDEX raw_graph_record_endpoint_run_idx
    ON raw.raw_graph_record (endpoint_run_id);

CREATE INDEX raw_graph_record_tenant_endpoint_collected_at_idx
    ON raw.raw_graph_record (tenant_id, endpoint_id, collected_at DESC);

CREATE INDEX raw_graph_record_payload_sha256_idx
    ON raw.raw_graph_record (payload_sha256);

-- ---------------------------------------------------------------------------
-- core directory
-- ---------------------------------------------------------------------------
CREATE INDEX application_tenant_app_id_idx
    ON core.application (tenant_id, app_id);

CREATE INDEX service_principal_tenant_app_id_idx
    ON core.service_principal (tenant_id, app_id);

-- ---------------------------------------------------------------------------
-- core events
-- ---------------------------------------------------------------------------
CREATE INDEX audit_event_tenant_source_event_at_idx
    ON core.audit_event (tenant_id, event_source, event_at DESC);

CREATE INDEX audit_event_tenant_actor_event_at_idx
    ON core.audit_event (tenant_id, actor_user_id, event_at DESC);

CREATE INDEX risk_detection_tenant_detected_at_idx
    ON core.risk_detection (tenant_id, detected_at DESC);

-- ---------------------------------------------------------------------------
-- core RBAC
-- ---------------------------------------------------------------------------
CREATE INDEX directory_role_assignment_tenant_role_definition_idx
    ON core.directory_role_assignment (tenant_id, role_definition_id);

CREATE INDEX directory_role_assignment_tenant_principal_idx
    ON core.directory_role_assignment (tenant_id, principal_id);

-- ---------------------------------------------------------------------------
-- core service health / update message (INCREMENTAL + HISTORICAL)
-- ---------------------------------------------------------------------------
-- G01-016 current-state watermark reads
CREATE INDEX service_health_issue_tenant_last_modified_idx
    ON core.service_health_issue (tenant_id, last_modified_date_time DESC);

-- G01-017 current-state watermark reads
CREATE INDEX service_update_message_tenant_last_modified_idx
    ON core.service_update_message (tenant_id, last_modified_date_time DESC);

-- G01-016 history chronology (per issue)
CREATE INDEX service_health_issue_history_tenant_source_lmd_idx
    ON core.service_health_issue_history
        (tenant_id, source_object_id, last_modified_date_time DESC);

CREATE INDEX service_health_issue_history_tenant_source_observed_idx
    ON core.service_health_issue_history
        (tenant_id, source_object_id, observed_at DESC);

CREATE INDEX service_health_issue_history_collection_run_idx
    ON core.service_health_issue_history (collection_run_id);

CREATE INDEX service_health_issue_history_endpoint_run_idx
    ON core.service_health_issue_history (endpoint_run_id);

-- G01-017 history chronology (per message)
CREATE INDEX service_update_message_history_tenant_source_lmd_idx
    ON core.service_update_message_history
        (tenant_id, source_object_id, last_modified_date_time DESC);

CREATE INDEX service_update_message_history_tenant_source_observed_idx
    ON core.service_update_message_history
        (tenant_id, source_object_id, observed_at DESC);

CREATE INDEX service_update_message_history_collection_run_idx
    ON core.service_update_message_history (collection_run_id);

CREATE INDEX service_update_message_history_endpoint_run_idx
    ON core.service_update_message_history (endpoint_run_id);

COMMIT;
