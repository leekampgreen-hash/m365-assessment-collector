-- 010_endpoint_identity_unavailable.sql: allow the controlled identity limit
-- to be recorded as a terminal endpoint result.
BEGIN;

ALTER TABLE control.endpoint_run
    DROP CONSTRAINT IF EXISTS endpoint_run_error_classification_check;

ALTER TABLE control.endpoint_run
    ADD CONSTRAINT endpoint_run_error_classification_check
    CHECK (error_classification IN (
        'PASS', 'AUTH_FAILURE', 'PERMISSION_REQUIRED', 'THROTTLED',
        'API_ERROR', 'NETWORK_ERROR', 'UNKNOWN', 'ENTITY_IDENTITY_UNAVAILABLE'
    ));

COMMIT;
