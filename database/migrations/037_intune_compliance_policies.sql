BEGIN;

CREATE TABLE core.intune_compliance_policy (
    policy_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    display_name TEXT,
    description TEXT,
    platforms TEXT,
    created_datetime TIMESTAMP WITH TIME ZONE,
    last_modified_datetime TIMESTAMP WITH TIME ZONE,
    scheduled_actions JSONB,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, policy_id)
);

GRANT SELECT, INSERT, UPDATE ON core.intune_compliance_policy TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.intune_compliance_policy TO graph_agent_migrator;

COMMIT;
