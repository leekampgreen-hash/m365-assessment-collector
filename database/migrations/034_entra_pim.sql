BEGIN;

CREATE TABLE core.entra_pim_assignment (
    assignment_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    principal_display_name TEXT,
    role_display_name TEXT,
    assignment_type TEXT,
    start_datetime TIMESTAMP WITH TIME ZONE,
    end_datetime TIMESTAMP WITH TIME ZONE,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, assignment_id)
);

GRANT SELECT, INSERT, UPDATE ON core.entra_pim_assignment TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.entra_pim_assignment TO graph_agent_migrator;

COMMIT;
