BEGIN;

-- Auth schema grants
GRANT USAGE ON SCHEMA auth TO graph_agent_migrator, graph_agent_runtime;
GRANT ALL ON ALL TABLES IN SCHEMA auth TO graph_agent_migrator;
GRANT ALL ON ALL SEQUENCES IN SCHEMA auth TO graph_agent_migrator;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA auth TO graph_agent_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA auth TO graph_agent_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON TABLES TO graph_agent_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO graph_agent_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT USAGE ON SEQUENCES TO graph_agent_runtime;

-- Core feature flags and settings grants
GRANT SELECT, INSERT, UPDATE ON core.feature_flag TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON core.tenant_feature TO graph_agent_runtime;
GRANT SELECT, UPDATE ON core.system_setting TO graph_agent_runtime;

-- Auth user table grants
GRANT SELECT, UPDATE ON auth."user" TO graph_agent_runtime;
GRANT SELECT, INSERT ON auth.auth_event TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON auth.session TO graph_agent_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA auth TO graph_agent_runtime;
COMMIT;
