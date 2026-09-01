-- Feature flags
BEGIN;

CREATE TABLE core.feature_flag (
    flag_name TEXT PRIMARY KEY,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Tenant feature overrides
CREATE TABLE core.tenant_feature (
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE CASCADE,
    flag_name TEXT NOT NULL REFERENCES core.feature_flag(flag_name) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, flag_name)
);

-- System settings
CREATE TABLE core.system_setting (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    setting_type TEXT NOT NULL CHECK (setting_type IN ('STRING', 'INTEGER', 'BOOLEAN', 'JSON')),
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by BIGINT REFERENCES auth."user"(user_id) ON DELETE SET NULL
);

COMMIT;
