-- 023_subscribed_sku_lifecycle.sql
-- Add next_lifecycle_datetime and capability_status_expiry to core.subscribed_sku
--
-- Authoritative source: docs/database-schema-design.md Section 7.2
--
-- This migration adds two new fields to track SKU lifecycle and capability status expiry:
--   - next_lifecycle_datetime: When the SKU enters its next lifecycle phase
--   - capability_status_expiry: When the current capability status expires
--
-- Both fields are nullable to maintain backward compatibility.

BEGIN;

-- Add next_lifecycle_datetime column
ALTER TABLE core.subscribed_sku
ADD COLUMN next_lifecycle_datetime TIMESTAMPTZ NULL;

-- Add capability_status_expiry column
ALTER TABLE core.subscribed_sku
ADD COLUMN capability_status_expiry TIMESTAMPTZ NULL;

-- Update comments to reflect the new fields
COMMENT ON COLUMN core.subscribed_sku.next_lifecycle_datetime IS
    'When the SKU enters its next lifecycle phase (e.g., trial->paid, paid->expired). Null if unknown or not applicable.';

COMMENT ON COLUMN core.subscribed_sku.capability_status_expiry IS
    'When the current capability_status expires. Null if unknown, not applicable, or for perpetual licenses.';

COMMIT;
