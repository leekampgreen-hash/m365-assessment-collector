BEGIN;

CREATE TABLE IF NOT EXISTS control.collector_checkpoint (
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    collector_id TEXT NOT NULL,
    checkpoint_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, collector_id)
);

REVOKE ALL ON control.collector_checkpoint FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON control.collector_checkpoint TO graph_agent_runtime;

COMMIT;
