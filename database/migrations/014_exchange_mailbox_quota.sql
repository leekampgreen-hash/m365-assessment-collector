BEGIN;
ALTER TABLE core.usage_exchange_mailbox_usage ADD COLUMN IF NOT EXISTS issue_warning_quota BIGINT;
ALTER TABLE core.usage_exchange_mailbox_usage ADD COLUMN IF NOT EXISTS prohibit_send_quota BIGINT;
ALTER TABLE core.usage_exchange_mailbox_usage ADD COLUMN IF NOT EXISTS prohibit_send_receive_quota BIGINT;
ALTER TABLE core.usage_exchange_mailbox_usage_snapshot ADD COLUMN IF NOT EXISTS issue_warning_quota BIGINT;
ALTER TABLE core.usage_exchange_mailbox_usage_snapshot ADD COLUMN IF NOT EXISTS prohibit_send_quota BIGINT;
ALTER TABLE core.usage_exchange_mailbox_usage_snapshot ADD COLUMN IF NOT EXISTS prohibit_send_receive_quota BIGINT;
GRANT SELECT, INSERT, UPDATE ON TABLE core.usage_exchange_mailbox_usage, core.usage_exchange_mailbox_usage_snapshot TO graph_agent_runtime;
COMMIT;
