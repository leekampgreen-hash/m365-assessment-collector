-- 013_conditional_access_security_evidence.sql: retain the minimum
-- deterministic Conditional Access security evidence for G01-011.
BEGIN;

ALTER TABLE core.conditional_access_policy
    ADD COLUMN client_app_types TEXT[] NULL,
    ADD COLUMN grant_built_in_controls TEXT[] NULL,
    ADD COLUMN security_evidence_complete BOOLEAN NULL;

ALTER TABLE core.conditional_access_policy_snapshot
    ADD COLUMN client_app_types TEXT[] NULL,
    ADD COLUMN grant_built_in_controls TEXT[] NULL,
    ADD COLUMN security_evidence_complete BOOLEAN NULL;

COMMENT ON COLUMN core.conditional_access_policy.security_evidence_complete IS
    'NULL means collected before G01-011 security evidence extension; TRUE/FALSE distinguishes complete from incomplete new evidence.';
COMMENT ON COLUMN core.conditional_access_policy_snapshot.security_evidence_complete IS
    'NULL means collected before G01-011 security evidence extension; TRUE/FALSE distinguishes complete from incomplete new evidence.';

COMMIT;
