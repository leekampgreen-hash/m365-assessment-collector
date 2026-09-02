BEGIN;

CREATE TABLE core.entra_auth_method (
    user_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    display_name TEXT,
    is_mfa_registered BOOLEAN NOT NULL DEFAULT FALSE,
    is_mfa_capable BOOLEAN NOT NULL DEFAULT FALSE,
    is_passwordless_capable BOOLEAN NOT NULL DEFAULT FALSE,
    methods_registered TEXT,
    default_mfa_method TEXT,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE INDEX idx_entra_auth_method_tenant ON core.entra_auth_method(tenant_id);
GRANT SELECT, INSERT, UPDATE ON core.entra_auth_method TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.entra_auth_method TO graph_agent_migrator;

COMMIT;
