TASK_ID: OD-P05B-ONEDRIVE-AUDIT-COLLECTOR-PRODUCTION-VALIDATION-SEAL-001
RESULT: OD_P05B_BLOCKED

BASELINE:
- service: graph-agent-collector-dev (running)
- entrypoint: collectors.run_collector --onedrive-audit exists; dry-run resolves PASS
- database: graph_agent (authoritative postgres service)
- runtime_role: graph_agent_runtime (Compose configuration)
- migration: 018 table exists; migration-history relation was not available for the queried name
- subscription: not independently verified in this run
- ActivityFeed.Read tenant consent: not independently verified in this run

RUNTIME_PARITY:
- deployment_model: bind-mounted source for collectors, tests, config, scripts, and application paths
- validation_method: docker inspect mount verification plus SHA-256 source/deployed comparison
- artifacts: collectors/onedrive_audit.py, collectors/run_collector.py, collectors/core/auth.py, collectors/persistence/__init__.py, collectors/persistence/core.py
- result: PASS for all five requested artifacts; source and /workspace hashes matched exactly
- note: existing parity helper is operations-api scoped and reports an unrelated persistence mismatch; it does not validate the requested collector artifact set

AUTH_RUNTIME:
- resource: https://manage.office.com configured in collector transport
- ActivityFeed.Read: declared by collector contract; fresh-token audience/scope could not be independently verified
- tenant_match: NOT PROVEN
- app_match: NOT PROVEN
- negative_gate: NOT PROVEN

COLLECTOR_TESTS:
- environment: graph-agent-collector-dev
- runner: python -m unittest
- test_count: 53 persistence tests passed; no focused collector test suite exists
- auth: NOT SEALED
- subscription: NOT SEALED
- transport: NOT SEALED
- parser: NOT SEALED
- workload_filter: direct smoke checks only
- event_filter: direct smoke checks passed for anonymous, guest, member exclusion, malware, secure-link exclusion, unrelated exclusion
- normalization: direct smoke checks only; no required focused suite
- result: INCOMPLETE

PRODUCTION_PATH_INTEGRATION:
- invocation: docker exec graph-agent-collector-dev python -m collectors.run_collector --onedrive-audit --json
- fake_source: NOT IMPLEMENTED/RUN
- source_records: NOT RUN
- expected_persisted: anonymous, Guest external, malware
- actual_persisted: NOT PROVEN
- excluded: direct normalization smoke only; production fixture not run
- duplicate_result: persistence contract previously sealed by OD-P04B; production path not exercised
- PostgreSQL: table exists; live collector invocation failed with PersistenceError before metrics output
- residue: no new rows observed in the queried audit table before/after attempted live run

LIVE_PROOF:
- mode: READ_ONLY_DRY_RUN intended
- invocation: collectors.run_collector --onedrive-audit --json
- auth: NOT PROVEN
- subscription: NOT PROVEN
- content_entries: N/A
- blobs: N/A
- records: N/A
- OneDrive_records: N/A
- SharePoint_records_excluded: N/A
- high_value_records: N/A
- normalized: N/A
- status: BLOCKED; non-dry live invocation failed with PersistenceError and no bounded read-only proof was established

CAPACITY_REGRESSION:
- current_rows: NOT VERIFIED in this run; prior sealed baseline 26
- snapshot_rows: NOT VERIFIED in this run; prior sealed baseline 79
- semantic_rows: analytics.onedrive_account_capacity exists

SYNTHETIC_RESIDUE: NONE OBSERVED; no fake integration fixture was created.

PRODUCTION_CODE_CHANGED: NO

BLOCKERS:
- Required focused collector tests and fake-source PostgreSQL production-path fixture are absent.
- Fresh manage.office.com token gate and bounded live read-only chain were not proven.
- Production invocation currently fails with PersistenceError.
- Existing parity helper is not suitable for this collector scope and reports an unrelated operations-api persistence mismatch.

NON_BLOCKING_LIMITATIONS:
- Collector runtime is bind-mounted; requested collector artifact hashes matched source exactly.
- Secure-link correlation and malware live observation remain deferred by the locked OD-P03 contract.

COLLECTOR_WIRING_READY: NO
OD_P05_CLOSED: NO
READY_FOR_OD_P06: NO

FILES_CHANGED:
- docs/evidence/OD-P05B-ONEDRIVE-AUDIT-COLLECTOR-PRODUCTION-VALIDATION-SEAL-001.md

FINAL_STATUS: OD_P05B_BLOCKED
