# OD-P07A OneDrive audit safe-drop metric classification correction

TASK_ID: OD-P07A-ONEDRIVE-AUDIT-SAFE-DROP-METRIC-CLASSIFICATION-FIX-001
RESULT: OD_P07A_BLOCKED
DATE: 2026-08-29

ROOT_CAUSE:
- function: `collect_and_persist_onedrive_audit`
- branch: normalization/metric counting loop in `collectors/onedrive_audit.py`
- exact_issue: a normalizer `None` result for a valid OneDrive record whose operation is in the locked set was routed to `malformed_records`; this incorrectly classified Member/internal and ambiguous sharing as malformed.

CORRECTION:
- exact_change: folded the terminal `else` branch into `records_dropped_out_of_scope += 1`.
- business_semantics_changed: NO
- persistence_changed: NO
- checkpoint_changed: NO
- retry_changed: NO

SAFE_DROP_METRICS:
- internal_member: corrected to dropped_out_of_scope
- ambiguous: corrected to dropped_out_of_scope
- SharePoint: dropped_out_of_scope
- secure_link_only: dropped_out_of_scope
- unrelated: dropped_out_of_scope
- generic_activity: dropped_out_of_scope

MALFORMED_REGRESSION:
- missing_id: normalizer still raises `SCHEMA_CONTRACT_FAILURE`
- missing_time: normalizer still raises `SCHEMA_CONTRACT_FAILURE`
- result: targeted regression passed; malformed candidates do not reach the safe-drop branch

POSITIVE_REGRESSION:
- anonymous: targeted regression passed
- guest_external: targeted regression passed
- malware: targeted regression passed

TESTS:
- environment: `graph-agent-collector-dev`
- OD_P07_matrix: command executed; environment-dependent suite setup skipped, so the required 18/18 real-PostgreSQL matrix could not be re-run in this session
- OneDrive_regression: PASS (focused production-path and transport tests included in command; 10 tests run, 1 environment skip)
- result: targeted code-level regression PASS; full matrix RECHECK BLOCKED by unavailable integration environment

RUNTIME_PARITY:
- PASS; host and `/workspace/collectors/onedrive_audit.py` SHA-256: `5bb2e5dabbf91f8915f6bfed4cec188edda31e659eda208330584997fe0ee49b`
- no rebuild required; bind-mounted source matches runtime

SYNTHETIC_RESIDUE:
- NONE introduced; no live Microsoft 365 call and no database fixture mutation performed by this correction session

REAL_DEFECT_CORRECTED: YES
READY_FOR_OD_P07_RECHECK: NO (required full 18/18 integration matrix is environment-blocked)

FILES_CHANGED:
- `collectors/onedrive_audit.py`
- `docs/evidence/OD-P07A-ONEDRIVE-AUDIT-SAFE-DROP-METRIC-CLASSIFICATION-FIX-001.md`
- `docs/PROJECT_PROGRESS.md`
- `docs/AI_USAGE_LOG.md`

FINAL_STATUS: OD_P07A_BLOCKED
