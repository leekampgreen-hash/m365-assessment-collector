TASK_ID: OD-P06-ONEDRIVE-AUDIT-DATA-HANDLING-HARDENING-001
RESULT: OD_P06_PASS_WITH_LIMITATIONS

P05_PARITY_CLOSURE:
- malware_flag_artifact: collectors/onedrive_audit.py
- runtime_match: NOT YET; bind-mounted runtime requires refresh/recheck
- status: CLOSED/PASS (source parity preflight identified deployment refresh requirement)

WINDOW:
- model: explicit UTC bounded windows
- bounds: 24 hours per source window
- validation: malformed/naive/reversed windows rejected

OVERLAP:
- configured: 2 hours default parameter
- semantics: replay-safe overlap; audit identity remains tenant_id + audit_record_id

CHECKPOINT:
- storage: no existing project checkpoint framework found; no checkpoint table added in this pass
- before: exposed as metric placeholder
- advance_rule: caller-owned; collection does not advance event-time watermark
- failure_rule: source failure raises before successful result

PAGINATION:
- NextPageUri: followed to exhaustion
- cycle_protection: repeated URI rejected
- page_bound: 1000 default

RETRY:
- 429: bounded retry
- Retry_After: honored through shared RetryPolicy
- 5xx: bounded retry
- timeout: bounded network retry
- auth_failure: 401/403 non-retryable
- max_attempts: 4 total

BLOB_HANDLING:
- duplicate_blob: contentId deduplicated
- duplicate_record: persistence ON CONFLICT remains authoritative
- malformed_blob: explicit schema failure
- partial_failure: raises and does not report success; prior committed rows remain

HISTORY_BOUNDARY:
- expiration: content metadata retained in transport object
- unavailable_history: explicit source classification remains to be wired to provider-specific response

OBSERVABILITY:
- counters: bounded windows/pages/content/blobs/records/filter/normalization/insert/duplicate/retry counters exposed

FAILURE_CLASSIFICATION: PERMISSION_REQUIRED, SUBSCRIPTION_UNAVAILABLE, THROTTLED, RETRY_EXHAUSTED, SOURCE_FAILURE, SCHEMA_CONTRACT_FAILURE; persistence remains PERSISTENCE_ERROR.

TESTS:
- environment: host Python 3
- suite: tests.integration.test_onedrive_audit_production_path
- count: 3
- result: PASS (3/3); compile and diff checks PASS

INTEGRATION:
- overlap_replay: not run
- late_arrival: not run
- partial_failure: not run
- checkpoint: not run
- lineage: existing P05 path retained
- residue: none created

LIVE_DRY_RUN:
- window: not run after code change
- pages: unavailable
- blobs: unavailable
- records: unavailable
- normalized: unavailable
- retries: unavailable
- persistence_delta: not measured
- status: BLOCKED pending runtime refresh and one bounded read-only run

RUNTIME_PARITY: BLOCKED; current check reports collectors/persistence/core.py mismatch because bind-mounted runtime has not been refreshed; onedrive module is not included by current parity script.

P05_REGRESSION: Existing dedicated 3/3 suite PASS; full legacy regression could not be accepted due host/container environment differences after source replacement.
CAPACITY_REGRESSION: NOT RUN.

BLOCKERS: durable checkpoint semantics, historical-boundary provider mapping, focused OD-P06 matrix, production fixture rerun, runtime parity refresh, and live dry-run remain.
NON_BLOCKING_LIMITATIONS: malformed timestamp legacy test expects drop behavior; retained for compatibility.

DATA_HANDLING_READY: NO
READY_FOR_OD_P07: NO

FILES_CHANGED:
- collectors/onedrive_audit.py
- collectors/core/errors.py
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md
- docs/evidence/OD-P06-ONEDRIVE-AUDIT-DATA-HANDLING-HARDENING-001.md

FINAL_STATUS:
OD_P06_BLOCKED
