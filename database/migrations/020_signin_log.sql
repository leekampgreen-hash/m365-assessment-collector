BEGIN;

CREATE TABLE IF NOT EXISTS core.signin_log (
    signin_log_id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES core.tenant(tenant_id),
    source_signin_id TEXT NOT NULL,
    user_principal_name TEXT,
    user_display_name TEXT,
    app_display_name TEXT,
    ip_address TEXT,
    location_city TEXT,
    location_country TEXT,
    signin_datetime TIMESTAMPTZ,
    status_error_code INTEGER,
    status_failure_reason TEXT,
    is_interactive BOOLEAN,
    client_app_used TEXT,
    conditional_access_status TEXT,
    risk_level_during_signin TEXT,
    risk_state TEXT,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    retention_class TEXT DEFAULT 'SHORT',
    UNIQUE (tenant_id, source_signin_id)
);
CREATE INDEX IF NOT EXISTS signin_log_tenant_datetime_idx ON core.signin_log (tenant_id, signin_datetime);
CREATE INDEX IF NOT EXISTS signin_log_tenant_error_idx ON core.signin_log (tenant_id, status_error_code);
REVOKE ALL ON core.signin_log FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON core.signin_log TO graph_agent_runtime;
GRANT USAGE, SELECT ON SEQUENCE core.signin_log_signin_log_id_seq TO graph_agent_runtime;

COMMIT;
