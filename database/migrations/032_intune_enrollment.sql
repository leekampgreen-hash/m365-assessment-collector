BEGIN;

CREATE TABLE core.intune_enrollment (
    device_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    device_name TEXT,
    operating_system TEXT,
    os_version TEXT,
    enrolled_datetime TIMESTAMP WITH TIME ZONE,
    owner_type TEXT,
    enrollment_type TEXT,
    user_display_name TEXT,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, device_id)
);

GRANT SELECT, INSERT, UPDATE ON core.intune_enrollment TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.intune_enrollment TO graph_agent_migrator;

COMMIT;
