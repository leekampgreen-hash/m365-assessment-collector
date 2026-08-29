-- STD-15G2C: authoritative Exchange mailbox capacity analytical view.
--
-- This view is the single derived-data contract for Exchange mailbox
-- capacity reporting. It is intentionally a VIEW (not a physical table):
-- no derived utilization/status values are duplicated into persisted
-- tables. One row is exposed per authoritative current Exchange mailbox
-- record (the newest observed_at generation per tenant).
--
-- Semantics (kept separate):
--   mailbox_capacity     = prohibit_send_receive_quota
--   utilization_percent  = storage_used * 100.0 / prohibit_send_receive_quota
--                          (NULL when the denominator is missing/zero/invalid)
--   usage_level          = LOW (<50), MEDIUM (>=50 and <80), HIGH (>=80),
--                          NO_DATA (denominator missing/zero/invalid)
--   report_refresh_date  = authoritative report refresh date
--   last_activity_date   = last email activity date
--
-- user_ref is a tenant-safe correlation identity (deterministic hash of the
-- mailbox identity), never the raw identity value.
BEGIN;

CREATE OR REPLACE VIEW analytics.exchange_mailbox_capacity AS
WITH newest AS (
    SELECT tenant_id, MAX(observed_at) AS observed_at
    FROM core.usage_exchange_mailbox_usage
    GROUP BY tenant_id
),
current_mailboxes AS (
    SELECT m.*
    FROM core.usage_exchange_mailbox_usage m
    JOIN newest n
      ON n.tenant_id = m.tenant_id
     AND n.observed_at = m.observed_at
),
computed AS (
    SELECT
        m.tenant_id,
        btrim(m.identity_value) AS identity_value,
        CASE
            WHEN m.identity_is_masked IS TRUE
                 OR m.identity_value IS NULL
                 OR btrim(m.identity_value) = ''
            THEN 'masked'
            ELSE 'user-' || left(encode(digest(lower(btrim(m.identity_value))::bytea, 'sha256'), 'hex'), 16)
        END AS user_ref,
        m.identity_is_masked,
        m.storage_used,
        m.prohibit_send_receive_quota AS mailbox_capacity,
        CASE
            WHEN m.prohibit_send_receive_quota IS NULL
                 OR m.prohibit_send_receive_quota <= 0
            THEN NULL
            ELSE (m.storage_used * 100.0) / m.prohibit_send_receive_quota
        END AS utilization,
        m.report_refresh_date,
        m.last_activity_date
    FROM current_mailboxes m
)
SELECT
    tenant_id,
    user_ref,
    identity_is_masked,
    storage_used,
    mailbox_capacity,
    round(utilization, 2) AS utilization_percent,
    CASE
        WHEN utilization IS NULL THEN 'NO_DATA'
        WHEN utilization < 50 THEN 'LOW'
        WHEN utilization < 80 THEN 'MEDIUM'
        ELSE 'HIGH'
    END AS usage_level,
    report_refresh_date,
    last_activity_date,
    identity_value,
    identity_value AS user_principal_name
FROM computed;

GRANT SELECT ON analytics.exchange_mailbox_capacity TO graph_agent_runtime;
GRANT USAGE ON SCHEMA analytics TO graph_agent_runtime;

COMMIT;
