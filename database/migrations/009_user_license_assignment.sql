-- 009_user_license_assignment.sql
-- Forward-only delta for current per-user SKU entitlements.
-- The assigned SKU identifier remains an immutable Graph identifier. Unknown
-- SKU handling is intentionally left to the application persistence path.

BEGIN;

CREATE TABLE IF NOT EXISTS core.user_license_assignment (
    user_license_assignment_id BIGSERIAL PRIMARY KEY,
    tenant_id                  BIGINT NOT NULL
        REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    user_id                    BIGINT NOT NULL
        REFERENCES core."user"(user_id) ON DELETE RESTRICT,
    sku_id                     TEXT NOT NULL,
    first_observed_at          TIMESTAMPTZ NOT NULL,
    last_observed_at           TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, user_id, sku_id)
);

COMMENT ON TABLE core.user_license_assignment IS
    'Current per-user entitlement set from /users.assignedLicenses. Rows are replaced per tenant on a complete user refresh; only SKUs present in subscribed_sku are persisted.';

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'core'
          AND c.relname = 'user_license_assignment_tenant_sku_idx'
    ) THEN
        EXECUTE 'CREATE INDEX user_license_assignment_tenant_sku_idx ON core.user_license_assignment (tenant_id, sku_id)';
    END IF;
END
$migration$;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE core.user_license_assignment
    TO graph_agent_runtime;

GRANT USAGE, SELECT ON SEQUENCE core.user_license_assignment_user_license_assignment_id_seq
    TO graph_agent_runtime;

COMMIT;
