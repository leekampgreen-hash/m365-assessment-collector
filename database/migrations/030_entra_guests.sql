CREATE TABLE core.entra_guest (
    user_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    display_name TEXT,
    created_datetime TIMESTAMP WITH TIME ZONE,
    last_signin_datetime TIMESTAMP WITH TIME ZONE,
    account_enabled BOOLEAN,
    has_license BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE INDEX idx_entra_guest_tenant ON core.entra_guest(tenant_id);
GRANT SELECT, INSERT, UPDATE ON core.entra_guest TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.entra_guest TO graph_agent_migrator;

COMMIT;
