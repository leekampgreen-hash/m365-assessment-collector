# OD-P07B OneDrive audit integration matrix reseal

TASK_ID: OD-P07B-ONEDRIVE-AUDIT-INTEGRATION-MATRIX-RESEAL-001
RESULT: OD_P07B_PASS
DATE: 2026-08-29

## 1. INTEGRATION SETUP BLOCKER

- **blocker:** the `OD_P07_BOOTSTRAP_PASSWORD` environment variable was not
  present in the `graph-agent-collector-dev` container, so
  `_bootstrap_password()` in
  `tests/integration/test_onedrive_audit_production_path_matrix.py` raised
  `unittest.SkipTest("OD_P07_BOOTSTRAP_PASSWORD unavailable")` during
  `setUpClass`, skipping the entire 18-test suite in OD-P07A.
- **classification:** `TEST_FIXTURE_CONFIGURATION` / `CONTAINER_ENVIRONMENT`
  (test-driver invocation failed to supply the bootstrap secret to the
  container as an environment variable). It is **not** a production defect.
- **correction:** pass the host-side bootstrap secret
  (`secrets/graph-agent-postgres-bootstrap-password`, read via sudo by the
  test driver) into the container as `OD_P07_BOOTSTRAP_PASSWORD` at
  invocation time. The runtime role secret is already mounted at
  `/run/secrets/graph_agent_runtime_password`. No test source, fixture, or
  production source change was required.
- **production_related:** NO
- **status:** resolved

The test is intentionally designed to receive the bootstrap password via an
environment variable because the runtime role has no DELETE on the audit table
and the container should not hold the bootstrap secret on disk. The driver-side
read-and-inject was simply omitted in OD-P07A.

## 2. SAFE-DROP DEFECT RETEST (exact case)

Independent verification using the real production orchestration
`collect_and_persist_onedrive_audit` + `CollectionWriter` lifecycle + real
PostgreSQL, with exactly two safe-drop records:

- internal `Member` sharing (`Workload=OneDrive`, `SharingInvitationCreated`,
  `TargetUserOrGroupType=Member`)
- ambiguous sharing (`Workload=OneDrive`, `SharingSet`,
  `TargetUserOrGroupType=None`)

Observed:

- normalized_events = 0
- persisted_rows = 0
- records_dropped_out_of_scope = 2
- malformed_records = 0
- high_value_candidates = 0
- business rows before/after = 0 / 0
- checkpoint: successful safe-drop processing advanced per locked semantics
  (`checkpoint_advanced = YES`)
- result: **PASS**

This is exactly the locked OD-P07 section-3 contract: Member/internal and
ambiguous sharing are dropped as out-of-scope, never counted as malformed.

## 3. FULL OD-P07 MATRIX

- environment: `graph-agent-collector-dev`
- suite: `tests.integration.test_onedrive_audit_production_path_matrix`
- result: **18/18 PASS** (`Ran 18 tests`, `OK`)

### POSITIVE_MATRIX
- anonymous: PASS (EXTERNAL_SHARING, external=true, anonymous=true)
- guest_external: PASS (EXTERNAL_SHARING, external=true, anonymous=false)
- malware: PASS (MALWARE_DETECTED, external=false, anonymous=false)

### SAFE_DROP_MATRIX
- SharePoint: PASS
- internal_member: PASS
- ambiguous: PASS
- secure_link_only: PASS
- unrelated: PASS
- generic_activity: PASS
(all six: normalized=0, persisted=0, `records_dropped_out_of_scope`=6,
`malformed_records`=0, checkpoint advances)

### MALFORMED_MATRIX
- missing Id: SCHEMA_CONTRACT_FAILURE, PASS
- missing time: SCHEMA_CONTRACT_FAILURE, PASS
- invalid locked candidate: SCHEMA_CONTRACT_FAILURE, PASS
- missing Workload: fail-closed safe drop (not malformed), PASS
- checkpoint unchanged on every malformed failure, PASS
- result: **PASS**

### FAILURE_MATRIX
- auth: PASS (PERMISSION_REQUIRED; no persistence; checkpoint unchanged;
  lifecycle FAILED/ERROR)
- subscription: PASS (SUBSCRIPTION_UNAVAILABLE; checkpoint unchanged;
  lifecycle failure)
- source: PASS (RETRY_EXHAUSTED / SCHEMA_CONTRACT_FAILURE; checkpoint
  unchanged; no false SUCCESS; no over-advance)
- persistence: PASS (PERSISTENCE_ERROR; partial_rows NONE; checkpoint
  unchanged; lifecycle FAILED/ERROR)

### REPLAY / ISOLATION / CHECKPOINT
- same-blob / cross-blob / overlap duplicate skip, distinct-IDs, late-arrival:
  PASS
- tenant isolation (unique `(tenant_id, audit_record_id)`, tenant-scoped
  checkpoint/lineage): PASS
- run lifecycle (success/safe-drop/failures) and checkpoint matrix
  (positive/out-of-scope/duplicate advance; failures unchanged): PASS

## 4. DIRECT REGRESSION

- suite: `tests.integration.test_onedrive_audit_production_path` (3) +
  `tests.integration.test_onedrive_audit_transport_retry` (7)
- count: 10
- result: **10/10 PASS** (`Ran 10 tests`, `OK`, no skips)

## 5. REAL POSTGRESQL VERIFICATION

Reused the matrix's real-PostgreSQL path (`graph_agent` DB, runtime role for
production-path persistence, bootstrap role for fixture setup/cleanup). The
18-test suite asserts, against real rows, business row counts, event categories,
lineage non-null, tenant consistency, checkpoint behavior (advance on success,
unchanged on failure), and zero business rows for safe-drop scenarios. All passed.
Independent post-run DB queries confirm: synthetic tenants/business rows/checkpoint
rows/collection runs/endpoint runs = 0; live tenant (id=2) 3 legitimate OneDrive
audit rows preserved.

## 6. SYNTHETIC CLEANUP

- business rows (synthetic): 0
- checkpoint rows (synthetic): 0
- collection runs (synthetic): 0
- endpoint runs (synthetic): 0
- synthetic tenant fixtures (555001/555002): 0
- live production OneDrive audit rows preserved (3)
- SYNTHETIC_RESIDUE = NONE

## 7. RUNTIME PARITY

No production source changed in this task. `collectors/onedrive_audit.py`
SHA-256 remains `5bb2e5dabbf91f8915f6bfed4cec188edda31e659eda208330584997fe0ee49b`
on both host and container (bind-mounted), matching OD-P07A's locked runtime
parity. The OD-P07A runtime-parity PASS is carried forward. All matrix-relevant
production modules (persistence, core, auth, errors, models) also match between
host and container.

## 8. NO LIVE MICROSOFT 365 / NO OD-P06 REPEAT

No live Management Activity call was made. OD-P06 acceptance was not repeated.
No new acceptance gates were introduced. OD-P08 remains the bounded live
acceptance task and is now unblocked.

## RESULTS SUMMARY

- INTEGRATION_SETUP: blocker = missing `OD_P07_BOOTSTRAP_PASSWORD` env var in
  collector container; classification = TEST_FIXTURE_CONFIGURATION /
  CONTAINER_ENVIRONMENT; correction = inject bootstrap secret at invocation;
  production_related = NO; status = resolved
- SAFE_DROP_DEFECT_RETEST: normalized=0, persisted=0, dropped_out_of_scope=2,
  malformed=0, checkpoint advanced (YES), result = PASS
- OD_P07_MATRIX: environment graph-agent-collector-dev; suite
  tests.integration.test_onedrive_audit_production_path_matrix; passed 18/18;
  failed 0; result = PASS
- POSITIVE_MATRIX: anonymous PASS, guest_external PASS, malware PASS
- SAFE_DROP_MATRIX: SharePoint PASS, internal_member PASS, ambiguous PASS,
  secure_link_only PASS, unrelated PASS, generic_activity PASS
- MALFORMED_MATRIX: PASS
- FAILURE_MATRIX: auth PASS, subscription PASS, source PASS, persistence PASS
- REPLAY_TENANT_CHECKPOINT: PASS
- POSTGRES_VERIFICATION: PASS
- REGRESSION: suite production_path + transport_retry; count 10; result PASS
- RUNTIME_PARITY: PASS (carried forward, SHA confirmed)
- SYNTHETIC_RESIDUE: NONE
- NEW_PRODUCTION_DEFECT_FOUND: NO
- BLOCKERS: none
- NON_BLOCKING_LIMITATIONS:
  - The safe-drop retest and matrix are run by injecting the bootstrap secret
    via an environment variable at invocation; the driver must continue to do
    this for future integration runs (no persistent container environment
    change was made).
  - `complete_endpoint_run` records only the closed `CLASSIFICATIONS` vocabulary;
    SUBSCRIPTION_UNAVAILABLE / SCHEMA_CONTRACT_FAILURE / SOURCE_FAILURE /
    RETRY_EXHAUSTED control-state uses the documented `API_ERROR` workaround while
    the true classification is proven at the orchestration boundary (carried from
    OD-P06F; no effect on checkpoint/business/no-false-success).
- PRODUCTION_PATH_INTEGRATION_READY: YES
- OD_P07_CLOSED: YES
- READY_FOR_OD_P08: YES

## CLOSURE

Chronology preserved:

- OD-P07: production-path matrix found the safe-drop metric classification
  defect (valid internal/ambiguous sharing counted as malformed).
- OD-P07A: corrected the production metric classification; full 18/18 recheck
  was blocked by unavailable integration setup.
- OD-P07B: recovered the integration setup (injected the bootstrap secret) and
  re-sealed the matrix at 18/18 PASS.

FINAL_STATUS: OD_P07B_PASS
