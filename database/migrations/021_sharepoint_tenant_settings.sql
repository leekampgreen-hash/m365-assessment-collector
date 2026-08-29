BEGIN;

CREATE TABLE core.sharepoint_tenant_settings (
    tenant_id INTEGER NOT NULL,
    source_object_id TEXT NOT NULL,
    collection_run_id UUID,
    endpoint_run_id UUID,
    collected_at TIMESTAMPTZ,
    retention_class TEXT,
    last_observed_at TIMESTAMPTZ,
    sharing_capability TEXT,
    default_sharing_link_type TEXT,
    external_user_expiration_required BOOLEAN,
    external_user_expiration_in_days INTEGER,
    file_anonymous_link_type TEXT,
    folder_anonymous_link_type TEXT,
    require_anonymous_links_expire_in_days INTEGER,
    allow_guest_user_sharing BOOLEAN,
    PRIMARY KEY (tenant_id, source_object_id)
);

REVOKE ALL ON core.sharepoint_tenant_settings FROM PUBLIC;
GRANT ALL ON core.sharepoint_tenant_settings TO graph_agent_runtime;

COMMIT;