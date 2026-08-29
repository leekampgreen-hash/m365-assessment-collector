-- 001_create_schemas.sql
-- G06-002: Logical schema creation.
--
-- Four schemas per G06-001 design:
--   control   — collection execution / endpoint execution / lineage
--   raw       — optional Graph evidence (off by default)
--   core      — normalised operational entities
--   analytics — serving layer (intentionally empty in G06-002)
--
-- Authoritative source: docs/database-schema-design.md (Sections 3, 20, 21).
--
-- This migration is forward-only schema creation. No data, no DML, no
-- destructive statements. Re-runnable on a clean database; on a populated
-- database CREATE SCHEMA IF NOT EXISTS is a no-op so the migration remains
-- idempotent.

BEGIN;

CREATE SCHEMA IF NOT EXISTS control;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMIT;