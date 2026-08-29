#!/bin/sh
set -eu

migration_password=$(cat /run/secrets/graph_agent_migration_password)
runtime_password=$(cat /run/secrets/graph_agent_runtime_password)

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set=migration_password="$migration_password" \
  --set=runtime_password="$runtime_password" <<'SQL'
CREATE ROLE graph_agent_migrator
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    PASSWORD :'migration_password';

CREATE ROLE graph_agent_runtime
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    PASSWORD :'runtime_password';

CREATE DATABASE graph_agent OWNER graph_agent_migrator;
REVOKE ALL ON DATABASE graph_agent FROM PUBLIC;
GRANT CONNECT ON DATABASE graph_agent TO graph_agent_runtime;
\connect graph_agent
REVOKE ALL ON SCHEMA public FROM PUBLIC;
-- Provide sha256 for the authoritative analytics exchange capacity view
-- (analytics.exchange_mailbox_capacity) so its tenant-safe user_ref matches
-- the existing sha256[:16] correlation identity used by the analytics layer.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SQL
