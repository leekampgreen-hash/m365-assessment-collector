-- Auth schema
BEGIN;

CREATE SCHEMA IF NOT EXISTS auth;

-- Users
CREATE TABLE auth."user" (
    user_id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    totp_secret TEXT,
    totp_enrolled BOOLEAN NOT NULL DEFAULT FALSE,
    role TEXT NOT NULL CHECK (role IN ('SUPER_ADMIN', 'TENANT_ADMIN', 'TENANT_USER')),
    tenant_id BIGINT REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT super_admin_no_tenant CHECK (
        (role = 'SUPER_ADMIN' AND tenant_id IS NULL) OR
        (role != 'SUPER_ADMIN' AND tenant_id IS NOT NULL)
    )
);

-- Sessions
CREATE TABLE auth.session (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES auth."user"(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_active_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address TEXT,
    user_agent TEXT,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE
);

-- Auth events
CREATE TABLE auth.auth_event (
    event_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES auth."user"(user_id) ON DELETE SET NULL,
    tenant_id BIGINT REFERENCES core.tenant(tenant_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'LOGIN_SUCCESS', 'LOGIN_FAILED', 'MFA_SUCCESS', 'MFA_FAILED',
        'LOGOUT', 'SESSION_EXPIRED', 'PASSWORD_CHANGED',
        'TOTP_ENROLLED', 'TOTP_RESET', 'ACCOUNT_LOCKED', 'ACCOUNT_UNLOCKED'
    )),
    ip_address TEXT,
    user_agent TEXT,
    detail JSONB,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Admin audit trail
CREATE TABLE auth.admin_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    actor_user_id BIGINT REFERENCES auth."user"(user_id) ON DELETE SET NULL,
    tenant_id BIGINT REFERENCES core.tenant(tenant_id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN (
        'TENANT_CREATED', 'TENANT_DISABLED', 'TENANT_ENABLED',
        'USER_CREATED', 'USER_DISABLED', 'USER_ROLE_CHANGED',
        'FEATURE_FLAG_CHANGED', 'SKU_PRICING_UPDATED',
        'COLLECTOR_TRIGGERED', 'SYSTEM_SETTING_CHANGED',
        'PASSWORD_RESET', 'TOTP_RESET'
    )),
    target_type TEXT,
    target_id TEXT,
    before_state JSONB,
    after_state JSONB,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- API access log
CREATE TABLE auth.api_access_log (
    log_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES auth."user"(user_id) ON DELETE SET NULL,
    tenant_id BIGINT REFERENCES core.tenant(tenant_id) ON DELETE SET NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER,
    duration_ms INTEGER,
    ip_address TEXT,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

GRANT USAGE ON SCHEMA auth TO graph_agent_migrator, graph_agent_runtime;
GRANT ALL ON ALL TABLES IN SCHEMA auth TO graph_agent_migrator;
GRANT ALL ON ALL SEQUENCES IN SCHEMA auth TO graph_agent_migrator;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA auth TO graph_agent_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA auth TO graph_agent_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON TABLES TO graph_agent_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO graph_agent_runtime;

COMMIT;
