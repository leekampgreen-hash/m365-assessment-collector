BEGIN;

CREATE TABLE IF NOT EXISTS core.usage_teams_user_activity (
    usage_id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    entity_key TEXT NOT NULL,
    report_refresh_date DATE NOT NULL,
    identity_value TEXT,
    identity_is_masked BOOLEAN NOT NULL DEFAULT FALSE,
    last_activity_date DATE,
    team_chat_message_count BIGINT,
    private_chat_message_count BIGINT,
    call_count BIGINT,
    meeting_count BIGINT,
    is_deleted BOOLEAN,
    observed_at TIMESTAMPTZ NOT NULL,
    retention_class TEXT NOT NULL DEFAULT 'STANDARD',
    CONSTRAINT usage_teams_user_activity_tenant_entity_key UNIQUE (tenant_id, entity_key)
);

CREATE TABLE IF NOT EXISTS core.usage_teams_user_activity_snapshot (
    LIKE core.usage_teams_user_activity INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
ALTER TABLE core.usage_teams_user_activity_snapshot
    ADD COLUMN IF NOT EXISTS snapshot_identity TEXT NOT NULL;
ALTER TABLE core.usage_teams_user_activity_snapshot
    ADD CONSTRAINT usage_teams_user_activity_snapshot_refresh_key
    UNIQUE (tenant_id, entity_key, report_refresh_date);

GRANT SELECT, INSERT, UPDATE ON TABLE
    core.usage_teams_user_activity,
    core.usage_teams_user_activity_snapshot
TO graph_agent_runtime;
GRANT DELETE ON TABLE core.usage_teams_user_activity TO graph_agent_runtime;
GRANT USAGE, SELECT ON SEQUENCE core.usage_teams_user_activity_usage_id_seq TO graph_agent_runtime;

COMMIT;
