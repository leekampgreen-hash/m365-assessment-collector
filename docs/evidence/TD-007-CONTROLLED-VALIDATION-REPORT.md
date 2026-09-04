# TD-007 Controlled Validation Environment Certification Report

- **Usage mark:** `TD-007-CONTROLLED-VALIDATION-REPORT-001`
- **Date:** 2026-09-04
- **Environment:** Controlled Validation (`graph-agent-collector-dev`, `graph-agent-postgres-dev`)
- **Status:** **PASS - CERTIFIED**
- **Plan Reference:** `docs/evidence/CH-2.3-CONTROLLED-VALIDATION-ENVIRONMENT-PLAN.md`

## 1. Executive Summary

This report establishes and certifies the controlled validation environment separation between Development, Controlled Validation, and Production per the architectural requirements of CH-2.3 and TD-007.

By isolating live Microsoft Graph tenant execution (TD-003) and live PostgreSQL instance persistence validation (TD-004) within containerized boundaries with dedicated credentials, the project successfully prevents direct production risk while proving full end-to-end integration readiness.

## 2. Environment Separation Boundaries

| Dimension | Local Development | Controlled Validation Environment | Production Target |
|---|---|---|---|
| **Host / Container** | Host machine / Local IDE | Isolated Docker Compose stack (`graph-agent-collector-dev`, `graph-agent-postgres-dev`) | Production Container Cluster / VM |
| **Microsoft Graph** | Mock transports (`mock_graph_transport`) | Dedicated Live Validation Tenant (`2ac16e52-2259-4c0f-b02b-c6a04e5246d6`) | Target Production Enterprise Tenant |
| **Credentials** | Mock strings / test fixtures | Mounted secrets `/workspace/secrets/collector.env` (file-based, uncommitted) | Managed Identity / Vault-injected secrets |
| **Database** | Offline test SQLite / in-memory | Dedicated PostgreSQL 16 container (`graph-agent-postgres-dev`) | Production Managed PostgreSQL Cluster |
| **Database User** | N/A | `graph_agent_runtime` (least-privilege, no DELETE on core tables) | Production App Role (least-privilege) |
| **Evidence Output** | Test runner output | Structured JSON reports (`TD-003`, `TD-004`) with sanitized metadata | Audit & SIEM logs |

## 3. Promotion Gate Verification

1. **Automated Offline Gate:** All 1,400+ unit and invariant tests pass (100%).
2. **Live Graph Gate:** Live tenant query returns HTTP 200 with schema-conforming attributes across all 4 representative endpoint families (TD-003 PASS).
3. **Live PostgreSQL Gate:** Connection, schemas, 10 physical tables, domain constraints, transactional atomicity, upsert, and replay idempotency verified (TD-004 PASS).
4. **Credential Boundary Protection:** Zero credentials or access tokens committed to repository or exposed in evidence artifacts.

## 4. Conclusion & Technical Debt Resolution

The Controlled Validation Environment separation is certified. Promotion procedures and gates are formally established.

**Technical Debt Item TD-007 is RESOLVED.**
