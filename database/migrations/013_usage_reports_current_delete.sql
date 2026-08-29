-- 013_usage_reports_current_delete.sql: complete the usage report current-state
-- replacement contract without granting delete access to snapshots.
BEGIN;

GRANT DELETE ON TABLE
    core.usage_office365_active_user,
    core.usage_exchange_email_activity,
    core.usage_exchange_mailbox_usage,
    core.usage_onedrive_activity,
    core.usage_onedrive_account_usage,
    core.usage_sharepoint_user_activity,
    core.usage_sharepoint_site_usage
TO graph_agent_runtime;

COMMIT;
