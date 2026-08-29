-- 011_security_findings_persistence.sql
-- Bounded deterministic Security observation and finding persistence.
BEGIN;

CREATE SCHEMA IF NOT EXISTS security;

CREATE TABLE IF NOT EXISTS security.observation (
    observation_id       BIGSERIAL PRIMARY KEY,
    tenant_id            BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    rule_id              TEXT NOT NULL,
    source_type          TEXT NOT NULL,
    source_endpoint      TEXT NOT NULL,
    normalized_field     TEXT NOT NULL,
    normalized_value     TEXT,
    dependency_status    TEXT NOT NULL CHECK (dependency_status IN ('AVAILABLE','UNAVAILABLE','NOT_APPLICABLE')),
    observed_at          TIMESTAMPTZ NOT NULL,
    collection_run_id    BIGINT NULL REFERENCES control.collection_run(collection_run_id) ON DELETE RESTRICT,
    endpoint_run_id      BIGINT NULL REFERENCES control.endpoint_run(endpoint_run_id) ON DELETE RESTRICT,
    observation_digest   TEXT NOT NULL UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS security.finding_evaluation (
    evaluation_id        BIGSERIAL PRIMARY KEY,
    tenant_id            BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    finding_id           TEXT NOT NULL,
    observation_id       BIGINT NOT NULL REFERENCES security.observation(observation_id) ON DELETE RESTRICT,
    rule_id              TEXT NOT NULL,
    baseline_id          TEXT NOT NULL,
    baseline_version     TEXT NOT NULL,
    category             TEXT NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('PASS','OPEN','NOT_EVALUATED')),
    severity             TEXT NOT NULL CHECK (severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
    baseline_expectation TEXT NOT NULL,
    observed_state       TEXT NOT NULL,
    risk                 TEXT NOT NULL,
    recommendation       TEXT NOT NULL,
    validation_guidance  TEXT NOT NULL,
    dependency_status    TEXT NOT NULL CHECK (dependency_status IN ('AVAILABLE','UNAVAILABLE','NOT_APPLICABLE')),
    evaluated_at         TIMESTAMPTZ NOT NULL,
    evaluation_digest    TEXT NOT NULL UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, observation_id, evaluation_digest)
);

CREATE TABLE IF NOT EXISTS security.finding_current (
    tenant_id            BIGINT NOT NULL REFERENCES core.tenant(tenant_id) ON DELETE RESTRICT,
    finding_id           TEXT NOT NULL,
    rule_id              TEXT NOT NULL,
    baseline_id          TEXT NOT NULL,
    baseline_version     TEXT NOT NULL,
    latest_evaluation_id BIGINT NOT NULL REFERENCES security.finding_evaluation(evaluation_id) ON DELETE RESTRICT,
    status               TEXT NOT NULL CHECK (status IN ('PASS','OPEN','NOT_EVALUATED')),
    severity             TEXT NOT NULL CHECK (severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
    observed_state       TEXT NOT NULL,
    evaluated_at         TIMESTAMPTZ NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, rule_id, baseline_id, baseline_version)
);

CREATE INDEX IF NOT EXISTS security_observation_tenant_rule_observed_idx
    ON security.observation (tenant_id, rule_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS security_finding_evaluation_tenant_finding_evaluated_idx
    ON security.finding_evaluation (tenant_id, finding_id, evaluated_at DESC);

REVOKE ALL ON SCHEMA security FROM PUBLIC;
REVOKE ALL ON security.observation, security.finding_evaluation, security.finding_current FROM graph_agent_runtime;
GRANT USAGE ON SCHEMA security TO graph_agent_runtime;
GRANT SELECT, INSERT ON security.observation, security.finding_evaluation TO graph_agent_runtime;
GRANT SELECT, INSERT, UPDATE ON security.finding_current TO graph_agent_runtime;
GRANT USAGE, SELECT ON SEQUENCE security.observation_observation_id_seq,
    security.finding_evaluation_evaluation_id_seq TO graph_agent_runtime;

COMMIT;
