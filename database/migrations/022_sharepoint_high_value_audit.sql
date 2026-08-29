BEGIN;

CREATE TABLE IF NOT EXISTS core.sharepoint_high_value_audit_event (
    sharepoint_high_value_audit_event_id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    audit_record_id TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('SharingInvitationCreated', 'SharingRevoked', 'AnonymousLinkCreated', 'AnonymousLinkRemoved')),
    workload TEXT NOT NULL CHECK (workload = 'SharePoint'),
    record_type TEXT NULL,
    actor_upn TEXT NULL,
    event_category TEXT NOT NULL CHECK (event_category = 'EXTERNAL_SHARING'),
    external_flag BOOLEAN NOT NULL,
    anonymous_flag BOOLEAN NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    client_ip INET NULL,
    object_id TEXT NULL,
    site_url TEXT NULL,
    source_relative_url TEXT NULL,
    source_file_name TEXT NULL,
    unique_sharing_id TEXT NULL,
    target_user_or_group_name TEXT NULL,
    target_user_or_group_type TEXT NULL,
    collection_run_id BIGINT NULL REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id BIGINT NULL REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    retention_class TEXT NOT NULL DEFAULT 'LONG' CHECK (retention_class IN ('SHORT', 'STANDARD', 'LONG', 'REFERENCE')),
    UNIQUE (tenant_id, audit_record_id)
);

CREATE INDEX IF NOT EXISTS sharepoint_high_value_audit_event_tenant_event_time_idx
    ON core.sharepoint_high_value_audit_event (tenant_id, event_time);
CREATE INDEX IF NOT EXISTS sharepoint_high_value_audit_event_tenant_category_event_time_idx
    ON core.sharepoint_high_value_audit_event (tenant_id, event_category, event_time);

REVOKE ALL ON core.sharepoint_high_value_audit_event FROM PUBLIC;
GRANT SELECT, INSERT ON core.sharepoint_high_value_audit_event TO graph_agent_runtime;
DO $$
BEGIN
    EXECUTE format(
        'GRANT USAGE, SELECT ON SEQUENCE %s TO graph_agent_runtime',
        pg_get_serial_sequence('core.sharepoint_high_value_audit_event', 'sharepoint_high_value_audit_event_id')
    );
END;
$$;

COMMIT;
