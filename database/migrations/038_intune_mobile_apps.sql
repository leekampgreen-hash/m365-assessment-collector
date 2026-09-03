BEGIN;

CREATE TABLE core.intune_mobile_app (
    app_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    display_name TEXT,
    publisher TEXT,
    app_type TEXT,
    platform TEXT,
    description TEXT,
    is_featured BOOLEAN,
    publishing_state TEXT,
    created_datetime TIMESTAMP WITH TIME ZONE,
    last_modified_datetime TIMESTAMP WITH TIME ZONE,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, app_id)
);

GRANT SELECT, INSERT, UPDATE ON core.intune_mobile_app TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.intune_mobile_app TO graph_agent_migrator;

COMMIT;
