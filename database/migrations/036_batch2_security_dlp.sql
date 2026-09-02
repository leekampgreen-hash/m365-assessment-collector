BEGIN;
CREATE TABLE core.defender_o365_alert (
    source_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    name TEXT,
    status TEXT,
    severity TEXT,
    category TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, source_id)
);
CREATE TABLE core.defender_cloud_app_alert (
    source_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    name TEXT,
    status TEXT,
    severity TEXT,
    category TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, source_id)
);
CREATE TABLE core.dlp_alert (
    source_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    name TEXT,
    status TEXT,
    severity TEXT,
    category TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, source_id)
);
CREATE TABLE core.dlp_label (
    source_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    name TEXT,
    status TEXT,
    severity TEXT,
    category TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, source_id)
);
GRANT SELECT, INSERT, UPDATE ON core.defender_o365_alert, core.defender_cloud_app_alert, core.dlp_alert, core.dlp_label TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.defender_o365_alert, core.defender_cloud_app_alert, core.dlp_alert, core.dlp_label TO graph_agent_migrator;
COMMIT;
