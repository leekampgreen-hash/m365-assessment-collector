BEGIN;

CREATE TABLE core.entra_device (
    device_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    display_name TEXT,
    operating_system TEXT,
    os_version TEXT,
    last_signin_datetime TIMESTAMP WITH TIME ZONE,
    is_managed BOOLEAN,
    is_compliant BOOLEAN,
    trust_type TEXT,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, device_id)
);

GRANT SELECT, INSERT, UPDATE ON core.entra_device TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.entra_device TO graph_agent_migrator;

COMMIT;
