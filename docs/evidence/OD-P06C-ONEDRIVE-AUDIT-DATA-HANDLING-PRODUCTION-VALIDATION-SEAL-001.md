# OD-P06C OneDrive audit data-handling production validation seal

TASK_ID: OD-P06C-ONEDRIVE-AUDIT-DATA-HANDLING-PRODUCTION-VALIDATION-SEAL-001
RESULT: OD_P06C_BLOCKED
DATE: 2026-08-29

MIGRATION_019:
- applied: YES, via graph_agent_migrator using psql -f
- table: control.collector_checkpoint exists
- key: PRIMARY KEY (tenant_id, collector_id); tenant FK to core.tenant
- grants: graph_agent_runtime SELECT/INSERT/UPDATE; PUBLIC revoked
- idempotent: YES; second application completed with relation-exists notice
- status: PASS

CHECKPOINT_DB:
- create: PASS (real PostgreSQL/runtime role)
- read: PASS
- advance: PASS
- monotonic: PASS; stale update affected 0 rows
- tenant_scope: PASS by tenant FK and composite key
- source_scope: PASS by collector_id component of composite key

FOCUSED_TESTS:
- environment: graph-agent-collector-dev
- suite: tests.integration.test_onedrive_audit_production_path, tests.persistence.test_core, tests.core.test_auth_runtime_cli
- count: 125
- result: PASS (125/125)
- gaps: Full A-AA matrix, real PostgreSQL orchestration fixtures, restart proof, and live dry-run were not available in the executed suite.

INTEGRATION:
- run1_initial: NOT RUN as real PostgreSQL fake-source orchestration
- run2_overlap: NOT RUN
- duplicate_replay: PASS in focused fake-source orchestration
- late_arrival: NOT RUN against real PostgreSQL
- run3_partial_failure: NOT RUN as production fixture
- checkpoint_unchanged: PASS at SQL contract level; not production orchestration
- run4_recovery: NOT RUN
- run5_stale_writer: PASS at SQL contract level
- lineage: focused normalization carries collection_run_id and endpoint_run_id; relational production verification not run
- result: BLOCKED

RESTART_DURABILITY:
- before: NOT CAPTURED
- after: NOT CAPTURED
- result: NOT RUN

OBSERVABILITY:
- counters: source inspection confirms checkpoint/window and collection counters; live result not captured
- result: PARTIAL

FAILURE_CLASSIFICATION:
- result: Focused regression covers auth and runtime error mapping; production classification matrix not independently executed. Existing vocabulary includes PERMISSION_REQUIRED, SUBSCRIPTION_UNAVAILABLE, THROTTLED/RETRY_EXHAUSTED, SOURCE_FAILURE, SCHEMA_CONTRACT_FAILURE, and PERSISTENCE_ERROR.

RUNTIME_PARITY:
- files: collectors/onedrive_audit.py, collectors/run_collector.py, collectors/persistence/core.py, collectors/persistence/__init__.py, collectors/core/errors.py
- result: PASS; SHA-256 source/runtime pairs matched. Host compileall passed with isolated cache prefix; collector bind-mounted compileall encountered non-mutating cache permission errors.

LIVE_DRY_RUN:
- window: NOT RUN
- pages: unavailable
- content_entries: unavailable
- blobs: unavailable
- records: unavailable
- OneDrive_records: unavailable
- high_value: unavailable
- normalized: unavailable
- retries: unavailable
- business_rows_before: not applicable
- business_rows_after: not applicable
- persistence_delta: not measured
- checkpoint_before: not captured
- checkpoint_after: not captured
- checkpoint_delta: not measured
- result: BLOCKED pending bounded live validation

CAPACITY_REGRESSION:
- current: 26
- snapshot: 79
- semantic_view: available, 26 rows

P05_REGRESSION: Focused P05-compatible suite passes; business audit baseline remains 3 rows and no historical rows were modified. Full P05 closure semantics were not reopened.

SYNTHETIC_RESIDUE: NONE; SQL contract fixtures were rolled back; checkpoint row count 0 after validation.

BLOCKERS: Real PostgreSQL production-path runs 1-5, full focused A-AA matrix, restart durability capture, and one bounded live read-only dry-run remain unexecuted.
NON_BLOCKING_LIMITATIONS: Migration test suite is offline and reports five pre-existing expectations that do not include migration 019 / count all migrations; this is not a migration application failure. Collector image does not bind-mount database/ for that suite.

DATA_HANDLING_READY: NO
OD_P06_CLOSED: NO
READY_FOR_OD_P07: NO

FILES_CHANGED:
- database/migrations/019_collector_checkpoint.sql (pre-existing OD-P06B implementation applied)
- docs/evidence/OD-P06C-ONEDRIVE-AUDIT-DATA-HANDLING-PRODUCTION-VALIDATION-SEAL-001.md
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md

FINAL_STATUS: OD_P06C_BLOCKED
