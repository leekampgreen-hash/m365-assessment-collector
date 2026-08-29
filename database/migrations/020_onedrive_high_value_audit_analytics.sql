BEGIN;

CREATE OR REPLACE VIEW analytics.onedrive_high_value_audit AS
SELECT
    tenant_id,
    audit_record_id,
    event_time,
    event_category,
    operation,
    actor_upn,
    anonymous_flag,
    external_flag,
    COALESCE(source_file_name, source_relative_url) AS object_display_name,
    workload
FROM core.onedrive_high_value_audit_event;

REVOKE ALL ON analytics.onedrive_high_value_audit FROM PUBLIC;
GRANT SELECT ON analytics.onedrive_high_value_audit TO graph_agent_runtime;

COMMIT;
