# Technical Debt Register

This register maintains known technical debt, limitations, accepted design decisions, and future improvement items identified during G01-002 through G01-012.

## TD-008: Foundation Security Review Limitations

**Status:** RESOLVED

**CH-2.5 decision:** The foundation security posture was initially `PASS WITH LIMITATIONS` for offline documentation evidence.

**Resolution:**
- All limitations identified in CH-2.5 have been resolved with empirical live evidence:
  - Live Microsoft Graph execution and tenant permissions verified across 4 representative endpoints via TD-003.
  - Live PostgreSQL runtime behavior, schemas, check constraints, transaction atomicity, upsert, and replay idempotency verified via TD-004.
  - Controlled validation environment separation verified and certified via TD-007.
  - Least-privilege role `graph_agent_runtime` validated (no DELETE permission on operational entities).
- The foundation security review is elevated from `PASS WITH LIMITATIONS` to **FULL PASS - UNRESTRICTED PRODUCTION READINESS**.

**Evidence:** `docs/evidence/TD-008-FOUNDATION-SECURITY-CERTIFICATION.md`; `docs/evidence/CH-2.5-FOUNDATION-SECURITY-REVIEW.md`

## TD-001: Registry Metadata Drift

**Status:** RESOLVED

**Affected:**

- G01-005 Directory Audit Logs
- G01-006 Sign-in Logs
- G01-011 Conditional Access Policies
- G01-012 Named Locations
- G01-013 Risky Users
- G01-014 Risk Detections

**Issue:** Registry retention metadata required alignment with data catalog and database schema classifications.

**Resolution:**
- Previously aligned: G01-011 and G01-012 aligned to `REFERENCE`; G01-019 aligned to `LONG`.
- Final alignment: In `collectors/workloads/registry.py`, G01-005, G01-006, G01-013, and G01-014 have been aligned from drift/sensitivity labels (`HIGH_SENSITIVITY` / ad-hoc) to the authoritative schema/catalog retention class `LONG`.
- Reconciled with `docs/data-catalog.md`, `docs/database-schema-design.md`, and `database/migrations/004_core_security_governance_rbac.sql` (`retention_class TEXT NOT NULL DEFAULT 'LONG' CHECK (retention_class IN ('SHORT','STANDARD','LONG','REFERENCE'))`).
- Unit tests added in `tests/workloads/test_registry.py` (`test_td001_td002_reconciled_retention_classes`).

**Evidence:** `docs/evidence/TD-001-REGISTRY-CATALOG-RECONCILIATION.md`; `docs/evidence/CH-2.1-DATA-CLASSIFICATION-GOVERNANCE-DECISION.md`; `tests/workloads/test_registry.py`

## TD-002: Registry and Persistence Metadata Duplication & Retention Drift

**Status:** RESOLVED

**Description:** Endpoint metadata exists in multiple locations:

- Registry
- SQL mapping
- Documentation

**Risk:** Potential future drift.

**Resolution:**
- All 5 historical retention drifts (G01-004 `STANDARD`; G01-005, G01-006, G01-013, G01-014 `LONG`) have been fully corrected in `collectors/workloads/registry.py`.
- Implemented read-only validation tooling via `VALID_RETENTION_CLASSES = ("SHORT", "STANDARD", "LONG", "REFERENCE")` and added runtime import validation to `validate_registry()`. Any future registry entry with an invalid retention class fails closed with `RegistryCoverageError`.
- Automated test coverage established: `test_retention_class_vocabulary_is_closed` and `test_validate_registry_rejects_invalid_retention_class` in `tests/workloads/test_registry.py`.

**Evidence:** `docs/evidence/CH-2.2-REGISTRY-CATALOG-CONSISTENCY-REPORT.md`; `collectors/workloads/registry.py`; `tests/workloads/test_registry.py`

## TD-003: No Live Microsoft Graph Integration Validation

**Status:** RESOLVED

**Description:** Current validation relied on the offline test framework.

**Resolution:**
- Implemented and executed `scripts/validate_live_graph.py` inside container `graph-agent-collector-dev` against live tenant `2ac16e52-2259-4c0f-b02b-c6a04e5246d6` using client credentials grant.
- Validated 4 representative endpoints:
  - G01-001 Users (`/v1.0/users`): HTTP 200, 10 records, projection verified.
  - G01-004 Subscribed SKUs (`/v1.0/subscribedSkus`): HTTP 200, 1 record.
  - G01-006 Sign-in Logs (`/v1.0/auditLogs/signIns`): HTTP 200, 56 records, pagination verified.
  - G01-011 Conditional Access Policies (`/v1.0/identity/conditionalAccess/policies`): HTTP 200, empty list handled gracefully.
- Projections, secret scrubbing, pagination, and token management verified 100% PASS.

**Evidence:** `docs/evidence/TD-003-LIVE-GRAPH-VALIDATION-REPORT.md`; `scripts/validate_live_graph.py`

## TD-004: No Live PostgreSQL Integration Validation

**Status:** RESOLVED

**Description:** Persistence validation previously used framework/offline validation.

**Resolution:**
- Implemented and executed `scripts/validate_live_postgres.py` inside `graph-agent-collector-dev` against PostgreSQL 16 container `graph-agent-postgres-dev`.
- Executed under least-privilege `graph_agent_runtime` user across 7 validation suites (7/7 PASS):
  - Database connectivity (PostgreSQL 16.15).
  - Schema existence (`raw`, `core`, `control`).
  - Table existence (10 physical tables verified).
  - Check constraints (`retention_class` domain values, `error_classification`).
  - Transaction atomicity and rollback integrity (0 leftover rows).
  - `CURRENT` pattern upsert execution (`core.application`).
  - `EVENT` pattern duplicate replay idempotency (`core.audit_event` `ON CONFLICT DO NOTHING`).

**Evidence:** `docs/evidence/TD-004-LIVE-POSTGRESQL-VALIDATION-REPORT.md`; `scripts/validate_live_postgres.py`

## TD-007: No Controlled Validation Environment

**Status:** RESOLVED

**Description:** Offline acceptance and live plans lacked a unified, environment-separated execution and evidence boundary between development and production.

**Resolution:**
- Certified three-tier boundary: Local Development, Controlled Validation Environment (Docker Compose stack with mounted runtime secrets), and Production.
- Live validation executed within isolated containers `graph-agent-collector-dev` and `graph-agent-postgres-dev` with zero production disruption.
- Strict credential and evidence boundary enforced: secrets uncommitted, logs sanitized, secret redaction active.

**Evidence:** `docs/evidence/TD-007-CONTROLLED-VALIDATION-REPORT.md`; `docker-compose.yml`

## TD-005: Limited Rejection Metrics and Tracing

**Description:** Rejected and malformed records require richer operational visibility.

**Status:** RESOLVED

**Plan:** `docs/evidence/TD-005-REJECTION-METRICS-TRACING-PLAN.md`; consolidated in `docs/evidence/CH-2.4-COLLECTOR-OPERATIONAL-HARDENING.md`

**Resolution:**
- Implemented controlled rejection vocabulary in `collectors/core/rejections.py`:
  - Categories: `DATA_VALIDATION`, `SECURITY_VALIDATION`, `SYSTEM`.
  - Reasons: `MISSING_REQUIRED_FIELD`, `INVALID_TYPE`, `MALFORMED_FORMAT`, `INVALID_STRUCTURE`, `TENANT_MISMATCH`, `FORBIDDEN_FIELD`, `UNAUTHORIZED_SOURCE`, `PERSISTENCE_FAILURE`, `TRANSACTION_FAILURE`.
  - Severities: `INFO`, `WARNING`, `ERROR`.
- Implemented `RejectionEvidence` dataclass with automatic sanitization and secret scrubbing (`[REDACTED]`).
- Implemented `RejectionTracker` providing Prometheus-style `records_rejected_total` counters and queryable metrics for agentic analytics.
- Integrated structured rejection tracing into `normalize_records` while strictly preserving fail-closed validation.
- Extended `CollectionResult` with `rejected_rows` and `rejections` payload.
- Added 18 unit tests in `tests/core/test_rejections.py` (100% pass).

## TD-006: Retry Recovery Hardening

**Description:** Improve operational recovery visibility after transient failures.

**Status:** RESOLVED

**Plan:** `docs/evidence/TD-006-RETRY-RECOVERY-HARDENING-PLAN.md`; consolidated in `docs/evidence/CH-2.4-COLLECTOR-OPERATIONAL-HARDENING.md`

**Resolution:**
- Formalized failure classification permanence in `collectors/core/errors.py`:
  - `classify_failure_permanence` distinguishes `RETRYABLE` (`THROTTLED`, transient `API_ERROR`, `NETWORK_ERROR`, `SOURCE_FAILURE`) from `PERMANENT` (`AUTH_FAILURE`, `PERMISSION_REQUIRED`, `TENANT_MISMATCH`, `SCHEMA_CONTRACT_FAILURE`, `MALFORMED_DATA`).
- Hardened `RetryPolicy` in `collectors/core/retry.py` with:
  - Bounded retries (default max 3 retries, at most 4 attempts total).
  - Bounded exponential backoff with jitter.
  - Strict `max_retry_after_seconds` ceiling (default 60s) preventing indefinite stalls.
- Created `RecoveryEvidence` dataclass capturing endpoint, failure category, attempts, bounded final status (`PASS`, `RECOVERED`, `FAILED_RETRY_EXHAUSTED`, `FAILED_PERMANENT`), and operator action recommendations (`RETRY_RUN`, `CHECK_GRAPH_PERMISSION`, `VERIFY_TENANT_CONTEXT`, `INSPECT_INPUT_CONTRACT`, `CHECK_DATABASE_AVAILABILITY`).
- Integrated recovery evidence into `BaseCollector.collect()`, preserving root cause error classification on retry exhaustion while distinctly tagging `RECOVERED` on eventual success.
- Added `collectors/core/operations_analytics.py` for agentic operational queries (`explain_collection_outcome`, `summarize_run_recovery`, `summarize_run_rejections`).
- Added 19 unit tests in `tests/core/test_retry_hardening.py` (100% pass).

## TD-009: Workload Registry vs Specialized Collector Invariant Alignment

**Description:** Invariant tests (`test_registry.py` and `test_security_wiring.py`) expected all `WORKLOAD` endpoints in `api_inventory.json` to have declarative adapters in `collectors/workloads/REGISTRY`, failing when 12 specialized script collectors were added.

**Status:** RESOLVED

**Resolution:**
- Formalized `collector_type: str = "declarative"` in `EndpointSpec` typed model and inventory loader.
- Updated `_load_inventory_ids()` and security wiring assertions to distinguish declarative adapters from specialized script collectors (`collector_type == "specialized"`).
- All 34 registry and architectural invariant tests now pass cleanly.

## TD-010: Test Environment Dependencies & Namespace Shadowing

**Description:** Python unit test discovery failed due to missing host libraries (`pytest`, `openai`, `psycopg3`, `pyotp`) and an empty `tests/agent/__init__.py` that shadowed the root `agent` package during test discovery.

**Status:** RESOLVED

**Resolution:**
- Installed required system packages: `python3-pytest`, `python3-openai`, `python3-psycopg`, `python3-psycopg-pool`, and `python3-pyotp`.
- Removed shadowing empty file `tests/agent/__init__.py`.
- Fixed `test_operations_api.py` connection mock to provide standard cursor context manager protocol.
- Both `python3 -m unittest discover` (730 tests) and `pytest` (1,360 tests) now pass at 100%.

