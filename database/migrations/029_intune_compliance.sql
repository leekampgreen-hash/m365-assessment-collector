CREATE TABLE core.intune_device (
    device_id TEXT NOT NULL,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id),
    device_name TEXT,
    compliance_state TEXT,
    operating_system TEXT,
    os_version TEXT,
    user_display_name TEXT,
    last_sync_datetime TIMESTAMP WITH TIME ZONE,
    owner_type TEXT,
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, device_id)
);

CREATE INDEX idx_intune_device_tenant ON core.intune_device(tenant_id);
CREATE INDEX idx_intune_device_compliance ON core.intune_device(tenant_id, compliance_state);

GRANT SELECT, INSERT, UPDATE ON core.intune_device TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.intune_device TO graph_agent_migrator;

COMMIT;
