BEGIN;

CREATE TABLE core.defender_threat (
    device_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    device_name TEXT,
    threat_state TEXT,
    threat_category TEXT,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, device_id)
);

GRANT SELECT, INSERT, UPDATE ON core.defender_threat TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.defender_threat TO graph_agent_migrator;

COMMIT;
