BEGIN;

CREATE TABLE core.entra_named_location (
    location_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    display_name TEXT,
    location_type TEXT,
    is_trusted BOOLEAN,
    ip_ranges JSONB,
    countries_and_regions JSONB,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, location_id)
);

GRANT SELECT, INSERT, UPDATE ON core.entra_named_location TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.entra_named_location TO graph_agent_migrator;

COMMIT;
