-- 008_usage_reports.sql: curated Microsoft 365 usage report state/history.
-- Raw CSV, bearer tokens, and preauthenticated URLs are never persisted.
BEGIN;

CREATE TABLE IF NOT EXISTS core.usage_office365_active_user (
    usage_id BIGSERIAL PRIMARY KEY, tenant_id BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    entity_key TEXT NOT NULL, report_refresh_date DATE NOT NULL, identity_value TEXT, identity_is_masked BOOLEAN NOT NULL DEFAULT FALSE,
    last_activity_date DATE, site_url TEXT, display_name TEXT, send_count BIGINT, receive_count BIGINT, read_count BIGINT, meeting_count BIGINT,
    mailbox_item_count BIGINT, storage_used BIGINT, storage_allocated BIGINT, file_count BIGINT, active_file_count BIGINT,
    viewed_count BIGINT, edited_count BIGINT, synced_count BIGINT, internal_share_count BIGINT, external_share_count BIGINT,
    page_view_count BIGINT, deleted_date DATE, is_deleted BOOLEAN, has_archive BOOLEAN, assigned_products TEXT, site_template TEXT,
    observed_at TIMESTAMPTZ NOT NULL, retention_class TEXT NOT NULL DEFAULT 'STANDARD',
    CONSTRAINT usage_office365_active_user_tenant_entity_key UNIQUE (tenant_id, entity_key)
);
CREATE TABLE IF NOT EXISTS core.usage_office365_active_user_snapshot (
    LIKE core.usage_office365_active_user INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);

CREATE TABLE IF NOT EXISTS core.usage_exchange_email_activity (
    LIKE core.usage_office365_active_user INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_exchange_email_activity_snapshot (
    LIKE core.usage_exchange_email_activity INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_exchange_mailbox_usage (
    LIKE core.usage_office365_active_user INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_exchange_mailbox_usage_snapshot (
    LIKE core.usage_exchange_mailbox_usage INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_onedrive_activity (
    LIKE core.usage_office365_active_user INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_onedrive_activity_snapshot (
    LIKE core.usage_onedrive_activity INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_onedrive_account_usage (
    LIKE core.usage_office365_active_user INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_onedrive_account_usage_snapshot (
    LIKE core.usage_onedrive_account_usage INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_sharepoint_user_activity (
    LIKE core.usage_office365_active_user INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_sharepoint_user_activity_snapshot (
    LIKE core.usage_sharepoint_user_activity INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_sharepoint_site_usage (
    LIKE core.usage_office365_active_user INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);
CREATE TABLE IF NOT EXISTS core.usage_sharepoint_site_usage_snapshot (
    LIKE core.usage_sharepoint_site_usage INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);

DO $migration$
DECLARE
    current_table TEXT;
    snapshot_table TEXT;
    short_name TEXT;
BEGIN
    FOREACH current_table IN ARRAY ARRAY[
        'usage_office365_active_user', 'usage_exchange_email_activity',
        'usage_exchange_mailbox_usage', 'usage_onedrive_activity',
        'usage_onedrive_account_usage', 'usage_sharepoint_user_activity',
        'usage_sharepoint_site_usage'
    ] LOOP
        short_name := replace(current_table, 'usage_', '');
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = current_table || '_pkey') THEN
            EXECUTE format('ALTER TABLE core.%I ADD CONSTRAINT %I PRIMARY KEY (usage_id)', current_table, current_table || '_pkey');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = current_table || '_tenant_id_fkey') THEN
            EXECUTE format('ALTER TABLE core.%I ADD CONSTRAINT %I FOREIGN KEY (tenant_id) REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT', current_table, current_table || '_tenant_id_fkey');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = current_table || '_tenant_entity_key') THEN
            EXECUTE format('ALTER TABLE core.%I ADD CONSTRAINT %I UNIQUE (tenant_id, entity_key)', current_table, current_table || '_tenant_entity_key');
        END IF;
        snapshot_table := current_table || '_snapshot';
        IF NOT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = ('core.' || snapshot_table)::regclass AND attname = 'snapshot_identity' AND NOT attisdropped) THEN
            EXECUTE format('ALTER TABLE core.%I ADD COLUMN snapshot_identity TEXT NOT NULL', snapshot_table);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = snapshot_table || '_pkey') THEN
            EXECUTE format('ALTER TABLE core.%I ADD CONSTRAINT %I PRIMARY KEY (usage_id)', snapshot_table, snapshot_table || '_pkey');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = snapshot_table || '_tenant_id_fkey') THEN
            EXECUTE format('ALTER TABLE core.%I ADD CONSTRAINT %I FOREIGN KEY (tenant_id) REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT', snapshot_table, snapshot_table || '_tenant_id_fkey');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = snapshot_table || '_refresh_key') THEN
            EXECUTE format('ALTER TABLE core.%I ADD CONSTRAINT %I UNIQUE (tenant_id, entity_key, report_refresh_date)', snapshot_table, snapshot_table || '_refresh_key');
        END IF;
    END LOOP;
END
$migration$;

GRANT SELECT, INSERT, UPDATE ON TABLE
    core.usage_office365_active_user,
    core.usage_office365_active_user_snapshot,
    core.usage_exchange_email_activity,
    core.usage_exchange_email_activity_snapshot,
    core.usage_exchange_mailbox_usage,
    core.usage_exchange_mailbox_usage_snapshot,
    core.usage_onedrive_activity,
    core.usage_onedrive_activity_snapshot,
    core.usage_onedrive_account_usage,
    core.usage_onedrive_account_usage_snapshot,
    core.usage_sharepoint_user_activity,
    core.usage_sharepoint_user_activity_snapshot,
    core.usage_sharepoint_site_usage,
    core.usage_sharepoint_site_usage_snapshot
TO graph_agent_runtime;

GRANT USAGE, SELECT ON SEQUENCE core.usage_office365_active_user_usage_id_seq
TO graph_agent_runtime;

COMMIT;
