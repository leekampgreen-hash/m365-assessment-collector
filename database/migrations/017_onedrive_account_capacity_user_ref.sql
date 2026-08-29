BEGIN;

CREATE OR REPLACE VIEW analytics.onedrive_account_capacity AS
WITH computed AS (
    SELECT
        o.usage_id,
        o.tenant_id,
        o.entity_key,
        o.identity_value,
        CASE
            WHEN o.identity_is_masked IS TRUE
                 OR o.identity_value IS NULL
                 OR btrim(o.identity_value) = ''
            THEN 'masked'
            ELSE 'user-' || left(encode(digest(lower(btrim(o.identity_value))::bytea, 'sha256'), 'hex'), 16)
        END AS user_ref,
        o.identity_is_masked,
        o.storage_used,
        o.storage_allocated,
        o.file_count,
        o.report_refresh_date,
        CASE
            WHEN o.storage_allocated IS NULL
                 OR o.storage_allocated <= 0
                 OR o.storage_used IS NULL
            THEN NULL
            ELSE o.storage_used * 100.0 / o.storage_allocated
        END AS utilization_percent
    FROM core.usage_onedrive_account_usage o
)
SELECT
    usage_id,
    tenant_id,
    entity_key,
    identity_value,
    user_ref,
    identity_is_masked,
    storage_used,
    storage_allocated,
    file_count,
    report_refresh_date,
    utilization_percent,
    CASE
        WHEN utilization_percent IS NULL THEN 'NO_DATA'
        WHEN utilization_percent < 50 THEN 'LOW'
        WHEN utilization_percent < 80 THEN 'MEDIUM'
        ELSE 'HIGH'
    END AS usage_level
FROM computed;

GRANT SELECT ON analytics.onedrive_account_capacity TO graph_agent_runtime;
GRANT USAGE ON SCHEMA analytics TO graph_agent_runtime;

COMMIT;
