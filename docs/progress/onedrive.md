# OneDrive Progress

OneDrive phases and related OneDrive Standard progress.

## OD-P10 OneDrive workload seal / handover

**Task:** `OD-P10-ONEDRIVE-WORKLOAD-SEAL-001`
**Status:** `OD_P10_SEALED`

`ONEDRIVE_WORKLOAD = SEALED / ACCEPTED`. OD-P01 PASS; OD-P02 PASS with documented live-source limitations; OD-P03 LOCKED / PASS_WITH_GAPS where historical wording applies; OD-P04 CLOSED / PASS; OD-P05 CLOSED / PASS; OD-P06 CLOSED / PASS_WITH_NON_BLOCKING_LIMITATIONS; OD-P07 CLOSED / PASS; OD-P08 CLOSED / PASS_WITH_LIMITATIONS; OD-P09 CLOSED / PASS_WITH_LIMITATIONS; OD-R01 PASS_WITH_NON_BLOCKING_FINDINGS.

The durable OneDrive contract is recorded in `docs/evidence/OD-P10-ONEDRIVE-WORKLOAD-SEAL-001.md`: Microsoft Graph Reports remains the separate capacity source; audit uses the Microsoft 365 Management Activity API at `https://manage.office.com`, `ActivityFeed.Read`, and `Audit.SharePoint`. Persistence is append/event history with idempotent `(tenant_id, audit_record_id)` keys, nullable optional source fields, required lineage on new normal production rows, and no raw `AuditData` business retention. Checkpoint, overlap, retry, pagination, failure, replay, semantic-view, and API contracts are sealed.

Historical blockers are preserved chronologically and marked subsequently closed; no open OneDrive blocker remains. F1 control-vocabulary granularity, F2 source-history classification, and F3 `OD_P07_BOOTSTRAP_PASSWORD` test-fixture invocation are non-blocking findings only. Synthetic residue is NONE. After OD-P10, OneDrive is frozen and may be reopened only for a direct production regression, formally approved new scope, or an independent blocking security/correctness finding.

`ONEDRIVE_WORKLOAD_SEALED: YES`; `NEXT_WORKLOAD: SharePoint data workstream`; no next-workload implementation is included.

Evidence: `docs/evidence/OD-P10-ONEDRIVE-WORKLOAD-SEAL-001.md`.

## OD-P09 OneDrive high-value audit analytics/API closure

**Task:** `OD-P09-ONEDRIVE-HIGH-VALUE-AUDIT-ANALYTICS-API-CLOSURE-001`
**Status:** `OD_P09A_PASS_WITH_LIMITATIONS`

Production validation completed against the authoritative Compose PostgreSQL and Operations API containers. Migration inventory expectations now include 019/020; migration 020 was applied idempotently, the semantic view and runtime SELECT grant were verified, source/runtime parity passed after refreshing only operations-api, and DB/API reconciliation passed for tenant 2. Focused migration and analytics/API tests passed. Capacity data and semantic view remained available; the retained snapshot counts were not changed by validation.

Evidence: `docs/evidence/OD-P09A-ONEDRIVE-AUDIT-ANALYTICS-API-PRODUCTION-VALIDATION-001.md`.

ANALYTICS_API_READY: YES
OD_P09_CLOSED: YES
READY_FOR_OD_R01: YES

## OD-P08 OneDrive audit bounded live acceptance

**Task:** `OD-P08-ONEDRIVE-AUDIT-BOUNDED-LIVE-ACCEPTANCE-001`
**Status:** `OD_P08_PASS_WITH_LIMITATIONS`

One normal bounded production invocation completed against the real Management Activity API and PostgreSQL. Runtime/import and parity checks passed; migrations 018/019 and target/checkpoint tables were available. The live window returned zero content, so no new event was created and no candidate classification was naturally encountered. The three legitimate historical OneDrive audit rows remained intact, with zero duplicate business keys and no synthetic residue. The durable first-run checkpoint advanced to the bounded source-window end. Capacity remained healthy at 26 current rows, 79 account-usage snapshots, and 120 activity snapshots. No real production defect was found.

Evidence: `docs/evidence/OD-P08-ONEDRIVE-AUDIT-BOUNDED-LIVE-ACCEPTANCE-001.md`.

LIVE_ACCEPTANCE_READY: YES
OD_P08_CLOSED: YES
READY_FOR_OD_P09: YES

## OD-P07B OneDrive audit integration matrix reseal

**Task:** `OD-P07B-ONEDRIVE-AUDIT-INTEGRATION-MATRIX-RESEAL-001`
**Status:** `OD_P07B_PASS`

Recovered the OD-P07 integration setup and re-sealed the production-path matrix
after OD-P07A. The blocker was that the `OD_P07_BOOTSTRAP_PASSWORD` environment
variable was absent in `graph-agent-collector-dev`, causing the matrix suite to
be skipped via `SkipTest` in OD-P07A (classification: TEST_FIXTURE_CONFIGURATION /
CONTAINER_ENVIRONMENT, not a production defect). The correction was to inject the
host-side bootstrap secret into the container at invocation; no production or test
source change was required.

Re-run results in `graph-agent-collector-dev`:

- Exact safe-drop defect retest (internal Member + ambiguous sharing):
  normalized=0, persisted=0, records_dropped_out_of_scope=2, malformed_records=0,
  checkpoint advanced — PASS.
- Full OD-P07 matrix `tests.integration.test_onedrive_audit_production_path_matrix`
  — 18/18 PASS (positive anonymous/Guest/malware; safe-drop SharePoint/member/
  ambiguous/secure-link/unrelated/generic; malformed locked-candidate; auth/
  subscription/source/persistence failures; replay/tenant-isolation/checkpoint).
- Direct OneDrive regression `test_onedrive_audit_production_path` +
  `test_onedrive_audit_transport_retry` — 10/10 PASS.
- Real PostgreSQL verification PASS; synthetic residue NONE; live tenant (id=2)
  3 legitimate OneDrive audit rows preserved.
- Runtime parity PASS (carried forward; `collectors/onedrive_audit.py` SHA
  `5bb2e5dabbf91f8915f6bfed4cec188edda31e659eda208330584997fe0ee49b` unchanged).

OD-P07 is closed, PRODUCTION_PATH_INTEGRATION_READY = YES, READY_FOR_OD_P08 = YES.

Evidence: `docs/evidence/OD-P07B-ONEDRIVE-AUDIT-INTEGRATION-MATRIX-RESEAL-001.md`.

## OD-P07A OneDrive audit safe-drop metric classification correction

**Task:** `OD-P07A-ONEDRIVE-AUDIT-SAFE-DROP-METRIC-CLASSIFICATION-FIX-001`
**Status:** `OD_P07A_BLOCKED`

Corrected only the production observability branch in `collectors/onedrive_audit.py`: valid normalizer exclusions now increment `records_dropped_out_of_scope`, while malformed locked candidates continue to raise `SCHEMA_CONTRACT_FAILURE`. No business semantics, persistence, checkpoint, retry, auth, subscription, or source behavior changed. The defect is corrected and runtime SHA-256 parity passes (`5bb2e5dabbf91f8915f6bfed4cec188edda31e659eda208330584997fe0ee49b`).

Targeted OneDrive regression command passed 10 tests with 1 environment-dependent skip. The required real-PostgreSQL OD-P07 18/18 recheck is blocked by unavailable integration setup, so OD-P07 re-seal and OD-P08 remain pending. No live Microsoft 365 call or synthetic database mutation was performed; synthetic residue remains NONE.

Evidence: `docs/evidence/OD-P07A-ONEDRIVE-AUDIT-SAFE-DROP-METRIC-CLASSIFICATION-FIX-001.md`.

## OD-P07 OneDrive audit production-path negative matrix

**Task:** `OD-P07-ONEDRIVE-AUDIT-PRODUCTION-PATH-NEGATIVE-MATRIX-001`
**Status:** `OD_P07_BLOCKED`

Validated the complete OneDrive high-value audit production path against a bounded
positive/negative matrix using a FAKE Management Activity source with the REAL
production orchestration (`collect_and_persist_onedrive_audit` + `CollectionWriter`
lifecycle), REAL normalizer/filter, REAL `control.collector_checkpoint`, REAL
`core.onedrive_high_value_audit_event` persistence, and REAL PostgreSQL. Added the
dedicated data-driven suite `tests/integration/test_onedrive_audit_production_path_matrix.py`
(18 tests) run in `graph-agent-collector-dev`.

Positive matrix (anonymous/Guest external/malware), safe-drop business outcome,
malformed locked-candidate (SCHEMA_CONTRACT_FAILURE), auth failure
(PERMISSION_REQUIRED), subscription failure (SUBSCRIPTION_UNAVAILABLE), source/
transport failures (RETRY_EXHAUSTED/SCHEMA_CONTRACT_FAILURE), persistence failure
(PERSISTENCE_ERROR), duplicate/replay, tenant isolation, run lifecycle, and
checkpoint matrix all PASS (17/18). Real PostgreSQL verification passed and
synthetic residue is NONE (live tenant rows preserved).

**REAL DEFECT FOUND (NOT auto-fixed per task instruction):** in
`collectors/onedrive_audit.py` the normalization/metric counting loop counts
valid-but-out-of-scope OneDrive internal/ambiguous sharing records
(`SharingInvitationCreated`/`SharingSet` with non-Guest target) as
`malformed_records` instead of `records_dropped_out_of_scope`. Business persistence,
no-false-success, and checkpoint behavior are correct; the mis-classification
violates the locked OD-P03 contract and OD-P07 sections 3/13 (safe-drop records must
not be classified as malformed merely because out of scope). The defect is the sole
failing gate. Because correcting it requires a production change, OD-P07 is NOT
closed and OD-P08 must not start until corrected and re-sealed.

Evidence: `docs/evidence/OD-P07-ONEDRIVE-AUDIT-PRODUCTION-PATH-NEGATIVE-MATRIX-001.md`.

## OD-P06F OneDrive audit hardening acceptance resume & seal

**Task:** `OD-P06F-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-RESUME-SEAL-001`
**Status:** `OD_P06F_PASS_WITH_LIMITATIONS`

Resumed OD-P06 acceptance from the gates blocked by the OD-P06D `UnboundLocalError` transport defect and corrected in OD-P06E. All previously blocked RETRY and BLOB gates pass against the corrected transport path. The full real-PostgreSQL production-path run sequence (RUN 1 initial success, RUN 2 overlap/late-arrival, RUN 3 partial failure, RUN 4 recovery, RUN 5 stale-writer) passes with checkpoint advance/no-advance and lineage verified relationally. Restart durability (checkpoint_before == checkpoint_after through the authoritative production read path after collector restart) and runtime SHA-256 parity pass. One bounded live read-only dry-run through the production orchestration with `dry_run=True` proves the full read-only pipeline (auth -> subscription -> bounded window -> pagination -> blob -> parsing -> OneDrive/high-value filtering -> normalization) with business persistence delta = 0 and checkpoint delta = 0. Failure classification matrix (PERMISSION_REQUIRED, SUBSCRIPTION_UNAVAILABLE, RETRY_EXHAUSTED, SOURCE_FAILURE, SCHEMA_CONTRACT_FAILURE, PERSISTENCE_ERROR) passes; `UnboundLocalError` appears nowhere. P05/capacity regression confirmed (actor_upn/record_type nullable, idempotency intact, capacity current 26 / snapshots / semantic view). Synthetic residue is NONE; the 3 legitimate production OneDrive audit rows are preserved.

`DATA_HANDLING_READY: YES`; `OD_P06_CLOSED: YES`; `READY_FOR_OD_P07: YES`.

Non-blocking limitation: the production `complete_endpoint_run` records only the closed `CLASSIFICATIONS` vocabulary, so a partial-failure control-state was recorded with `API_ERROR` while the actual transport classification (`RETRY_EXHAUSTED`) was proven at the transport/orchestration boundary. No effect on checkpoint, business rows, no-false-success, or collectibility.

Evidence: `docs/evidence/OD-P06F-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-RESUME-SEAL-001.md`.

## OD-P06E OneDrive audit direct transport retry correction

**Task:** `OD-P06E-ONEDRIVE-AUDIT-DIRECT-TRANSPORT-RETRY-CORRECTION-001`
**Status:** `OD_P06E_PASS`

Corrected `ManagementActivityTransport._get` so directly raised `AuditTransportError` instances are assigned before shared retry/classification logic. This removes the proven `UnboundLocalError` while preserving bounded 429/5xx retry, Retry-After handling, permission classification, source-failure behavior, urllib HTTPError handling, timeout handling, checkpoint semantics, and business-event filtering. Focused direct transport regression coverage and the existing OneDrive integration suite pass. OD-P06 acceptance remains separate and is not resumed here.

`REAL_OD_P06_DEFECT_CORRECTED: YES`; `READY_FOR_OD_P06_ACCEPTANCE_RESUME: YES`.

Evidence: `docs/evidence/OD-P06E-ONEDRIVE-AUDIT-DIRECT-TRANSPORT-RETRY-CORRECTION-001.md`.

## OD-P06D OneDrive audit hardening acceptance execution

**Task:** `OD-P06D-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-EXECUTION-001`
**Status:** `OD_P06D_BLOCKED`

Execution of the remaining OD-P06 gates started by exercising the focused hardening matrix against the current production Management Activity transport. A **REAL production defect** was found in the retry path of `collectors/onedrive_audit.py` (`ManagementActivityTransport._get`, lines 120-124): an `except AuditTransportError as error: pass` clause causes CPython to delete `error`, so the subsequent `error.classification` raises `UnboundLocalError`. This breaks the required RETRY scenarios (429 then success, Retry-After honored, transient 5xx then success, bounded retry exhaustion) and the BLOB partial-failure/recovery scenarios, which also route through `_get`. The urllib `HTTPError` retry path binds `error` by assignment and still works, which is why prior focused suites passed. Per task instructions the defect was reported and **not** auto-fixed.

Unaffected items verified pass: window/overlap bounds and 4-hour first-run lookback; checkpoint advance/no-advance semantics and dry-run non-mutation; late-arrival normalization without watermark filtering; pagination multi-page/cyclic/bound; non-failure blob multi/duplicate-contentId/malformed; subscription enabled/absent; schema malformed/out-of-scope; timeout bounded-retry path.

`DATA_HANDLING_READY: NO`; `OD_P06_CLOSED: NO`; `READY_FOR_OD_P07: NO`.

Evidence: `docs/evidence/OD-P06D-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-EXECUTION-001.md`.

Next: correct the `_get` retry defect, then re-run the OD-P06D gates.

## OD-P06C OneDrive audit data-handling production validation seal

**Task:** `OD-P06C-ONEDRIVE-AUDIT-DATA-HANDLING-PRODUCTION-VALIDATION-SEAL-001`
**Status:** `OD_P06C_BLOCKED`

Migration 019 was applied idempotently to the authoritative `graph_agent` PostgreSQL database through `graph_agent_migrator`. Real PostgreSQL checkpoint create/read/monotonic/stale-update/source-scope checks passed, focused collector/persistence/auth regression passed 125/125, SHA-256 source/runtime parity passed for all affected collector artifacts, and OneDrive capacity remained current 26, snapshot 79, semantic view available. Closure remains blocked because the full A-AA matrix, real PostgreSQL production-path runs, restart durability capture, and bounded live dry-run were not executed.

`DATA_HANDLING_READY: NO`; `OD_P06_CLOSED: NO`; `READY_FOR_OD_P07: NO`.

## OD-P06B OneDrive audit durable checkpoint and overlap

**Task:** `OD-P06B-ONEDRIVE-AUDIT-DURABLE-CHECKPOINT-OVERLAP-001`
**Status:** `OD_P06B_PASS_WITH_LIMITATIONS`

Added the tenant/source-scoped PostgreSQL-backed `control.collector_checkpoint` migration and persistence primitives. OneDrive collection now applies a bounded four-hour first-run lookback, two-hour configurable UTC overlap, exposes checkpoint/window observability, advances only after successful business persistence, leaves failures unchanged, and uses a monotonic update predicate to prevent stale-run regression. Dry-run reads but never mutates checkpoint or business state.

Focused fake-source orchestration regression passes 3/3. Full focused OD-P06B failure, restart, and production PostgreSQL integration matrix remains limited by the current host/container database-driver/test-environment availability; no live acceptance was run.

`CHECKPOINT_READY: YES`; `READY_FOR_OD_P06C: YES`.

## OD-P06A OneDrive audit runtime parity correction

**Task:** `OD-P06A-ONEDRIVE-AUDIT-RUNTIME-PARITY-CORRECTION-001`
**Status:** `OD_P06A_PASS`

Confirmed the authoritative `collector` Compose service uses `/opt/docker/graph-agent/collectors` bind-mounted at `/workspace/collectors`; no wiring defect existed. The stale collector container was recreated only with `docker compose up -d --force-recreate --no-deps collector`; no Compose or image changes were made. SHA-256 parity passed for `onedrive_audit.py`, `run_collector.py`, `persistence/core.py`, and directly imported `core/errors.py`. Import/compile smoke passed, the service is running without restarts, and no live collection was invoked.

`RUNTIME_PARITY: PASS`; `READY_FOR_OD_P06B: YES`.

## OD-P06 OneDrive audit data-handling hardening

**Task:** `OD-P06-ONEDRIVE-AUDIT-DATA-HANDLING-HARDENING-001`
**Status:** `OD_P06_BLOCKED`

Added bounded UTC window validation/splitting, configurable two-hour overlap parameter, bounded Management Activity retries with Retry-After, defensive pagination, duplicate content suppression, explicit blob/schema failures, subscription verification, and operational counters. The existing 3-test OneDrive production-path suite and Python compilation pass. Durable checkpoint storage/advance semantics, provider-specific history-boundary mapping, OD-P06 focused matrix, production integration rerun, runtime parity refresh, capacity regression, and the required post-change live dry-run remain outstanding.

`DATA_HANDLING_READY: NO`; `READY_FOR_OD_P07: NO`.

## OD-P05G OneDrive audit final integration closure

**Task:** `OD-P05G-ONEDRIVE-AUDIT-FINAL-INTEGRATION-CLOSURE-001`
**Status:** `OD_P05G_PASS_WITH_LIMITATIONS`

Added `tests/integration/test_onedrive_audit_production_path.py`, a focused fake Management Activity suite using the real OneDrive transport, normalization, and persistence handoff. The authoritative focused command passed 125/125 in `graph-agent-collector-dev`; the dedicated suite passed 3/3. The suite proves source retrieval, filtering, normalization, auth resource and negative gate, lineage propagation, persistence, and duplicate idempotency. A production mismatch was corrected so malware rows use the required `external_flag=False`.

The current fake-source production-equivalent path no longer reproduces the historical `PersistenceError`, classified `RESOLVED_BY_CURRENT_WIRING`. Fresh runtime claims for `https://manage.office.com` verified the expected audience, tenant, app, and `ActivityFeed.Read`. OD-P05F live read-only evidence remains valid: 3 content entries, 3 blobs, 197 records, 3 normalized duplicate candidates, and zero persistence delta. No live failure injection was performed; it is `NOT_REQUIRED_FOR_CLOSURE`. Synthetic residue is none. Existing database lineage/capacity evidence remains valid; the collector image could not independently load its PostgreSQL driver for a fresh relational query.

`COLLECTOR_WIRING_READY: YES`; `OD_P05_CLOSED: YES`; `READY_FOR_OD_P06: YES`.

## OD-P05F OneDrive audit production closure recheck

**Task:** `OD-P05F-ONEDRIVE-AUDIT-PRODUCTION-CLOSURE-RECHECK-001`
**Status:** `OD_P05F_BLOCKED`

Authoritative `graph-agent-collector-dev` execution passed 122 unittest checks, including persistence, rollback, nullable-field, fail-closed, and CLI dry-run coverage. Production source/runtime SHA-256 parity passed for all three OD-P05E files. A bounded real Management Activity read completed with 3 content entries, 3 blobs, 197 records, 3 normalized duplicate candidates, and zero business-row delta; the three legacy pre-lineage rows were not modified. Capacity current rows remained 26 and the semantic view remained available; snapshot baseline remains 79 from the prior seal.

Closure remains blocked because an isolated synthetic production-path PostgreSQL lineage event, controlled live failure lifecycle proof, and fresh token tenant/app/audience/`ActivityFeed.Read` claim verification were not completed. No synthetic residue was introduced. `COLLECTOR_WIRING_READY: NO`; `OD_P05_CLOSED: NO`; `READY_FOR_OD_P06: NO`.

## OD-P05E OneDrive audit lineage contract correction

**Task:** `OD-P05E-ONEDRIVE-AUDIT-LINEAGE-CONTRACT-CORRECTION-001`
**Status:** `OD_P05E_PASS_WITH_LIMITATIONS`

Corrected OD-P03 documentation to classify `UserId`/`actor_upn` and `RecordType`/`record_type` as optional nullable source fields. The `--onedrive-audit` production path now creates canonical collection and endpoint runs, threads both IDs through normalization, and supplies them to persistence. Dry-run remains read-only and does not persist business events. Focused offline verification passed; live synthetic PostgreSQL production-path proof and deployed parity were not available in this session.

`DOCUMENTATION_DRIFT_CLOSED`; `LINEAGE_READY: YES`; `READY_FOR_OD_P05_CLOSURE_RECHECK: NO` pending runtime integration proof.

## OD-P05B OneDrive audit collector production validation seal

**Task:** `OD-P05B-ONEDRIVE-AUDIT-COLLECTOR-PRODUCTION-VALIDATION-SEAL-001`  
**Status:** `OD_P05B_BLOCKED`

The collector service is running with bind-mounted source, and SHA-256 comparison passed for the requested collector, auth, and persistence artifacts. The dry-run entrypoint resolves, but no focused collector suite or fake-source PostgreSQL production-path fixture exists. Fresh Management Activity auth-gate proof and bounded live read-only proof were not completed; the non-dry invocation failed with `PersistenceError`. No synthetic fixture or residue was introduced. `COLLECTOR_WIRING_READY: NO`; `OD_P05_CLOSED: NO`; `READY_FOR_OD_P06: NO`.

## OD-P05A OneDrive audit collector wiring validation closure

**Task:** `OD-P05A-ONEDRIVE-AUDIT-COLLECTOR-WIRING-VALIDATION-CLOSURE-001`  
**Status:** `OD_P05A_PASS_WITH_GAPS`

Added the bounded `collectors.run_collector --onedrive-audit` production invocation, Management Activity auth/transport selection, normalization, and OD-P04 persistence handoff. Collector-container compile and 53-test persistence suite pass. Runtime parity and bounded live read-only proof remain blocked because the parity helper requires a host Docker executable and no live proof was run. `COLLECTOR_WIRING_READY: NO`; `READY_FOR_OD_P06: NO`.

## OD-P05 OneDrive audit collector normalization wiring

**Task:** `OD-P05-ONEDRIVE-AUDIT-COLLECTOR-NORMALIZATION-WIRING-001`
**Status:** `OD_P05_PASS_WITH_GAPS`

Added a production Management Activity API transport and fail-closed OneDrive normalization path. Management tokens use the separate `https://manage.office.com` resource; Audit.SharePoint subscription validation, bounded content listing, pagination, blob retrieval, OneDrive filtering, locked event filtering, and normalized persistence-row generation are implemented. Live read-only proof and deployed runtime parity were not available in this session.

## OD-P04B OneDrive audit persistence validation seal

**Task:** `OD-P04B-ONEDRIVE-AUDIT-PERSISTENCE-VALIDATION-SEAL-001`
**Status:** `OD_P04B_PASS_WITH_LIMITATIONS`

Migration 018, table existence, runtime CONNECT/SELECT/INSERT, generated sequence USAGE/SELECT, and zero prior audit residue passed against `postgres:5432` / `graph_agent` / `graph_agent_runtime`. Collector persistence source is bind-mounted; SHA-256 hashes for `collectors/persistence/__init__.py` and `core.py` matched the deployed collector exactly. The migration is not image-baked and remains host/migrator-owned.

The collector-container focused suite ran 53 tests successfully. Live synthetic Guest external, FileMalwareDetected nullable-field, duplicate idempotency, late-arrival, and fail-closed proofs passed; bootstrap cleanup left zero synthetic audit rows. Atomic rollback is covered by the focused transaction tests. Cross-tenant live fixture creation was unavailable because the authoritative database has one tenant; tenant-scoped uniqueness/query semantics are covered by focused contract tests and this is non-blocking.

`OD-P04` is IMPLEMENTED; initial runtime gaps are closed through P04A/P04B. `PERSISTENCE_PRODUCTION_VALIDATED: YES`. `OD_P04_CLOSED: YES`. `READY_FOR_OD_P05: YES`.

## OD-P04A OneDrive audit persistence runtime validation closure

**Task:** `OD-P04A-ONEDRIVE-AUDIT-PERSISTENCE-RUNTIME-VALIDATION-CLOSURE-001`
**Status:** `OD_P04A_PASS_WITH_GAPS`

Authoritative Compose wiring was reconciled to `postgres:5432`, database `graph_agent`, and runtime role `graph_agent_runtime`; the earlier unavailable-role finding was WRONG_ENVIRONMENT/WRONG_DB_TARGET. The role exists and connects. Migration 018 was applied through the migrator role. Validation exposed and corrected a migration defect in the generated serial-sequence grant; the migration now resolves the installation-generated sequence with `pg_get_serial_sequence`.

Runtime INSERT/SELECT access, anonymous and duplicate idempotency behavior, and fail-closed rejection were proven through the collector container entrypoint. Synthetic cleanup was performed by bootstrap because runtime is correctly not granted DELETE. The collector image has no pytest and does not bake migrations; direct bounded runtime validation and compile checks were used. Full two-tenant and controlled rollback matrix remain gaps; no production tenant rows were used.

## OD-P04 OneDrive high-value audit persistence

**Task:** `OD-P04-ONEDRIVE-HIGH-VALUE-AUDIT-PERSISTENCE-001`
**Status:** `OD_P04_PASS_OFFLINE_PENDING_DB`

Added migration 018 and a narrow normalized batch persistence API for the locked OneDrive high-value audit contract. Validation is fail-closed for tenant, workload, operation, target classification, and derived flags; inserts are parameter-bound, append-only, tenant-scoped, immutable, and idempotent on `(tenant_id, audit_record_id)`. Batch validation completes before any SQL, preserving atomic transaction behavior through the existing `CollectionWriter` boundary. No collector, API, UX, analytics, permissions, or tenant mutation changed.

Focused offline tests pass. Production-equivalent PostgreSQL validation was not available in this session.

## OD-P03C-R2 operator cleanup attestation closure

**Task:** `OD-P03C-R2-OPERATOR-CLEANUP-ATTESTATION-CLOSURE-001`
**Status:** `OD_P03C_R2_PASS`

Operator/UI confirmation records that all four controlled sharing fixtures were manually cleaned: the OneDrive Guest share on `notes.txt`, the OneDrive Anyone link on `Laporan bulanan.docx`, the SharePoint controlled external share on `SP-AUDIT-EXTERNAL.txt`, and the SharePoint Anyone link on `SP-AUDIT-ANONYMOUS.txt`. The OneDrive files and `SP-Audit-Test` site/files remain preserved as reusable test fixtures.

`SYNTHETIC_SHARING_RESIDUE: NONE` and `CLEANUP_STATUS: OPERATOR_VERIFIED`. `AUTOMATED_PERMISSION_VERIFICATION: UNAVAILABLE_NON_BLOCKING`. OD-P03C-R1's automated verification was blocked by a verification-capability limitation; its historical evidence is not treated as current residue and the blocker is closed through operator/UI verification. No automation or technical-debt work is required.

`DATA_CONTRACT_LOCKED: YES`. `READY_FOR_OD_P04: YES`. Cleanup verification tooling does not block OD-P04, and OD-P03 is not reopened.

## OD-P03C-R1 historical reconciliation

OD-P03C-R1 remains recorded as `AUTOMATED VERIFICATION BLOCKED`; later operator/UI evidence closes the cleanup verification without changing the historical result.

## OD-P03C controlled sharing fixture cleanup

**Task:** `OD-P03C-CONTROLLED-SHARING-FIXTURE-CLEANUP-001`
**Status:** `OD_P03C_BLOCKED`

No mutation was performed. The required evidence safely identifies the four fixture files and sharing classifications, but does not provide exact Graph permission IDs or the controlled external recipient identity for all fixtures. The repository has no supported sharing-permission revoke action or live cleanup harness; its only relevant write action is controlled file deletion, which is explicitly prohibited here. All four controlled shares therefore remain active and require a bounded operator cleanup using exact permission IDs before OD-P04.

Fixtures were not deleted or otherwise mutated. No site, file, ownership, membership, permission registration, subscription, database, collector, or UX change was made. No audit ingestion was awaited.

`READY_FOR_OD_P04: NO` pending exact-permission identification and canonical revoke execution.

## OD-P03 OneDrive high-value audit data contract lock

**Task:** `OD-P03-ONEDRIVE-HIGH-VALUE-AUDIT-DATA-CONTRACT-LOCK-001`  
**Status:** `OD_P03_PASS_WITH_GAPS`

The production OneDrive Basic high-value audit contract is locked from the authoritative OD-P02D-R3 live Audit.SharePoint evidence plus explicitly documented Microsoft capability. The source is the Microsoft 365 Management Activity API (`contentType=Audit.SharePoint`, `https://manage.office.com`, application permission `ActivityFeed.Read`), separate from the Microsoft Graph Reports OneDrive capacity contract.

`Workload=OneDrive` is the authoritative workload discriminator; `Workload=SharePoint` records are excluded, and missing/unknown workload fails closed. The event grain is one immutable row per `(tenant_id, audit_record_id)` where `audit_record_id=Id`; `contentId` remains transport metadata. The locked in-scope events are OneDrive `AnonymousLinkCreated`, `SharingInvitationCreated`/`SharingSet` with structured `TargetUserOrGroupType=Guest`, and documented `FileMalwareDetected` when encountered. Anonymous events are `EXTERNAL_SHARING`, external, and anonymous. Member/internal and unknown/ambiguous sharing classifications are excluded or fail closed.

OD-P04 must use append/event-history persistence, tenant scope, idempotent duplicate handling, nullable optional source fields, overlapping windows, and late-arrival safety without destructive tenant-wide replacement. Secure-link operation-pair correlation is `DEFERRED_SCHEMA_ENRICHMENT`; malware is `SUPPORTED_DOCUMENTED` but `LIVE_EVENT_NOT_OBSERVED`. Existing OneDrive capacity fields and Microsoft Graph Reports authority remain unchanged. Controlled fixtures remain pending cleanup and are test evidence only. Evidence: `docs/evidence/OD-P03-ONEDRIVE-HIGH-VALUE-AUDIT-DATA-CONTRACT-LOCK-001.md`.

`DATA_CONTRACT_LOCKED: YES`. `READY_FOR_OD_P04: YES`.

## OD-P02D-R3 audit blob content field proof

**Task:** `OD-P02D-R3-AUDIT-BLOB-CONTENT-FIELD-PROOF-001`
**Status:** `OD_P02D_R3_PASS_WITH_GAPS`

Bounded retrieval passed the fresh management-token and enabled-subscription gates. Two Audit.SharePoint blobs were retrieved directly (171 records total), safely matching all four controlled OneDrive/SharePoint fixtures. The payload proves `Id`, `CreationTime`, object identity, operation, workload, anonymous-link semantics, Guest-based external classification, and unique audit IDs; `Workload` is a deterministic OneDrive/SharePoint discriminator in the sample. Secure-link operation-pair correlation and malware observation remain unproven/non-blocking. No mutation, persistence, cleanup, or subscription change occurred. Evidence: `docs/evidence/OD-P02D-R3-AUDIT-BLOB-CONTENT-FIELD-PROOF-001.md`.

`READY_FOR_OD_P03: YES`. Use tenant plus audit `Id` for deduplication, overlap windows for delayed arrival, and fail-closed classification when workload or structured external target evidence is absent.

## OD-P02D-R2 known sharing schema proof

**Task:** `OD-P02D-R2-KNOWN-SHARING-SCHEMA-PROOF-001`
**Status:** `OD_P02D_R2_EVENT_INGESTION_PENDING`

A bounded read-only live probe surfaced two newer Audit.SharePoint blob metadata entries, newest `2026-08-29T08:19:22.756Z`, but complete record payloads were not safely validated. No event identity, field-presence schema, OneDrive discriminator, anonymous semantics, external-recipient proof, or audit-record dedup identity was asserted. Known shares remain active and require separate cleanup. Evidence: `docs/evidence/OD-P02D-R2-KNOWN-SHARING-SCHEMA-PROOF-001.md`.

Exactly one bounded next action: retry read-only retrieval of the two surfaced blobs within the same limits and capture field presence only.

## OD-P02D-R1 known external-sharing audit proof

**Task:** `OD-P02D-R1-KNOWN-EXTERNAL-SHARING-AUDIT-PROOF-001`
**Status:** `OD_P02D_R1_EVENT_INGESTION_PENDING`

Fresh app-only management-token and enabled `Audit.SharePoint` subscription gates passed. A bounded read-only content listing found one Audit.SharePoint blob (`contentCreated=2026-08-29T07:51:21.886Z`, expiration `2026-09-12T07:48:32.071Z`), but the controlled event record could not be safely retrieved/validated in this run; no event identity, live schema, OneDrive discriminator, or independent external classification was asserted. No mutation, persistence, or cleanup occurred. Evidence: `docs/evidence/OD-P02D-R1-KNOWN-EXTERNAL-SHARING-AUDIT-PROOF-001.md`.

Exactly one bounded next action: retry retrieval of the identified content blob read-only, up to the same limits, then classify only from structured fields.

## OD-P02C Audit.SharePoint content/schema proof

**Task:** `OD-P02C-ONEDRIVE-AUDIT-CONTENT-SCHEMA-PROOF-001`
**Status:** `OD_P02C_CONTENT_PENDING`

Rerun after the subscription activation wait passed the fresh management-token gates: `ActivityFeed.Read` present, tenant/app matched, and audience was `https://manage.office.com`. `Audit.SharePoint` was present exactly once and enabled. Bounded four-hour and 24-hour listings each returned HTTP 200 with one page, zero blobs, and zero records; no content was downloaded, persisted, or mutated. Schema, OneDrive discriminator, locked event semantics, malware fields, pagination, ordering, late arrival, and dedup behavior remain unproven. Evidence: `docs/evidence/OD-P02C-R1-ONEDRIVE-AUDIT-CONTENT-SCHEMA-PROOF-001.md`.

Next action: one bounded read-only rerun after content availability, preferably following a controlled safe external-sharing test event if approved.

## OD-P02B Audit.SharePoint subscription activation

**Task:** `OD-P02B-AUDIT-SHAREPOINT-SUBSCRIPTION-ACTIVATION-001`
**Status:** `OD_P02B_PASS_CONTENT_PENDING`

A new app-only token for `https://manage.office.com` matched the tenant and app and contained `ActivityFeed.Read`. The pre-state subscription list was empty. Exactly one pull subscription was started with `contentType=Audit.SharePoint`; the API returned HTTP 200 with status `enabled` and no webhook. Post-state contained only that subscription. A bounded four-hour content listing probe returned HTTP 500, classified as `CONTENT_PENDING`; no content blob was downloaded and no event schema was inspected. Evidence: `docs/evidence/OD-P02B-AUDIT-SHAREPOINT-SUBSCRIPTION-ACTIVATION-001.md`.

Next action: bounded content/schema proof only, after content becomes readable.

## OD-P02A OneDrive audit permission live acceptance

**Task:** `OD-P02A-ONEDRIVE-AUDIT-PERMISSION-LIVE-ACCEPTANCE-001`  
**Status:** `OD_P02A_PASS_WITH_GAPS`

The live app-only token matched the expected tenant, app identity, and `https://manage.office.com` audience, and `ActivityFeed.Read` was present (`roles_count=1`). The Management Activity API accepted authentication and tenant access with HTTP 200, but no `Audit.SharePoint` subscription exists. Per scope, no subscription was started and content/event proof stopped before retrieval. Evidence: `docs/evidence/OD-P02A-ONEDRIVE-AUDIT-PERMISSION-LIVE-ACCEPTANCE-001.md`.

Next action: tenant administrator starts an `Audit.SharePoint` subscription, then the same bounded read-only content and schema proof is rerun.

### STD-05 locked OneDrive Standard usage scope (authoritative)

Approved by STD-05 contract discovery (`STD-05-ONEDRIVE-BASIC-CONTRACT-001`).
This is the single source of truth for what OneDrive Standard "basic usage"
means; do not widen it without a separate contract decision.

**Smallest contract:** the two-report pair `USAGE-004` (`onedrive_activity` /
`getOneDriveActivityUserDetail`) and `USAGE-005` (`onedrive_account_usage` /
`getOneDriveUsageAccountDetail`), period `D7` default. Both declare
`Reports.Read.All`, application auth, and are existing inventory/registry/
adapter/persistence entries. Neither report alone satisfies the locked scope:
per-user active/activity evidence lives in `USAGE-004`, while storage, file
count, and allocated capacity live only in `USAGE-005`.

**In scope:**

- Active users (from `USAGE-004` evidence only: `usage_onedrive_activity` rows
  that are not deleted and have a non-empty `last_activity_date`; no
  viewed/synced threshold semantics are invented).
- Active accounts (from `USAGE-005` evidence only: `usage_onedrive_account_usage`
  rows that are not deleted and have a non-empty `last_activity_date`).
- Last activity (`last_activity_date`, max over the active set).
- Total storage used (`storage_used`, summed across the current
  `usage_onedrive_account_usage` report set).
- File count (`file_count`, summed across the current
  `usage_onedrive_account_usage` report set).
- Basic storage utilization, directly supported by the standard report:
  `storage_used / storage_allocated` per account (and aggregate), because
  `getOneDriveUsageAccountDetail` exposes both `Storage Used (Byte)` and
  `Storage Allocated (Byte)` in the locked report schema. (Contrast with
  Exchange, where no single usable quota column is exposed.)

**Out of scope (explicitly excluded, do not collect or surface):**

- sharing / oversharing (shared-internal/external file counts);
- file-level / per-file detail;
- permission analysis;
- DLP / Purview;
- advanced analytics.

The existing `analytics/operations.py` `onedrive_adoption()` derives OneDrive
"active users" from `onedrive_activity` `viewed_count` / `synced_count`
evidence. That evidence is OUT of the locked STD-05 scope; STD-05 KPI
derivation must be grounded in `last_activity_date` presence on non-deleted
rows (per the semantics above) and must surface storage utilization from
`onedrive_account_usage`. Any later widening that reintroduces activity-count
thresholds or sharing evidence requires an explicit contract update here.

**Scope accounting:** This STD-05 scope record is documentation-only. No
production Python, database migration, inventory/configuration, Scenario Agent,
permission, credential, Entra, or Graph behavior was changed.

### STD-05B OneDrive Basic collector implementation (PASS)

Implemented the OneDrive Basic collector to the locked STD-05 scope above,
closing the STD-04-identified persistence and KPI-source gaps for OneDrive:

- **Persistence privilege fix:** `database/migrations/013_usage_reports_current_delete.sql`
  grants `graph_agent_runtime` `DELETE` on all seven `core.usage_*` current
  tables (snapshots excluded), so the current-state `DELETE + INSERT`
  replacement contract no longer fails with `InsufficientPrivilege`.
- **Fail-closed OneDrive deletion normalization:** `collectors/usage_reports/registry.py`
  treats malformed/ambiguous OneDrive `Is Deleted` flags as deleted (`is_deleted=True`)
  so malformed rows never inflate active counts.
- **STD-05 KPI derivation:** `analytics/operations.py::onedrive_adoption()` now
  emits the six locked KPIs — `active_users` (non-deleted `onedrive_activity`
  rows with a non-empty `last_activity_date`), `active_accounts` (non-deleted
  `onedrive_account_usage` rows with a non-empty `last_activity_date`),
  `latest_activity` (max `last_activity_date` over the active set),
  `total_storage_used`, `total_file_count`, and `storage_utilization`
  (`storage_used / storage_allocated`, aggregating the current
  `onedrive_account_usage` set; fails closed to `None` for zero/missing
  allocation). Viewed/synced count thresholds are no longer used to derive the
  locked OneDrive basic `active_users`.
- **API surface:** `api/operations.py` already routed `/api/operations/adoption/onedrive`
  to `onedrive_adoption()`; no contract change was required.
- **Offline evidence:** `tests/analytics/test_operations.py` covers deleted/missing
  activity filtering and zero/missing-allocation fail-closed utilization.

**Scope accounting:** This STD-05B implementation is recorded here for the
Standard Version progress log. The running deployment containers were built from
pre-STD-05B source (see STD-06 live acceptance); container runtime parity for the
changed `analytics/operations.py` and `collectors/usage_reports/registry.py`
modules must be restored and re-verified before OneDrive Basic can be ACCEPTED.

### STD-06A OneDrive runtime parity correction (PASS)

Rebuilt the shared `graph-agent-collector:dev` image from the current host source and recreated only `collector` and `operations-api`. The prior stale runtime was caused by `Dockerfile.collector` copying production modules into the image while `operations-api` had no source bind mount; the existing process therefore reused an image created before STD-05B and did not observe later host edits. `scripts/check_runtime_parity.py` now provides a repeatable host-to-runtime hash gate for all changed production modules before live acceptance.

The rebuilt API is healthy and its OneDrive readback against the existing live DB exposes `active_users`, `active_accounts`, `latest_activity`, `total_storage_used`, `total_file_count`, and `storage_utilization` with values 23, 23, 2026-06-26, 113932223, 156, and 3.985413583835068e-06. No Graph collection, writes, permissions, schema, or KPI semantics changed.

### STD-06B Migration regression closure (PASS)

Closed the one remaining migration test expectation failure introduced by migration `013_usage_reports_current_delete.sql` (STD-05B). The failing test `test_migration_order_is_numeric_and_stable` did not account for the two forward-only `013`-prefixed files on disk (`013_conditional_access_security_evidence.sql` and `013_usage_reports_current_delete.sql`). Determination: the test expectation was STALE; the migration is live-applied, proven, forward-only, and contract-compliant. Bounded correction updated only `tests/database/test_migrations.py` — added `013_usage_reports_current_delete.sql` to `EXPECTED_FILES_IN_ORDER` and permitted the single intentional `013` co-slot in the numeric-prefix assertion. Focused migration suite = 63 PASS; usage-report persistence/analytics regression = 43 PASS (1 skipped for missing DB driver). No migration, DB privilege, KPI logic, runtime, or Graph behavior changed. `STD06_RERUN_READY=YES`.

## STD-06 OneDrive Basic live acceptance (ACCEPTED)

**Status:** ACCEPTED — `ONEDRIVE_BASIC_STATUS=ACCEPTED`, `FINAL_STATUS=STD_06_PASS`.
Evidence: `docs/evidence/STD-06-ONEDRIVE-BASIC-LIVE-ACCEPTANCE-001.md`.

**Final rerun (`STD-06-RERUN-ONEDRIVE-BASIC-LIVE-ACCEPTANCE-001`) PASS:**

- **Runtime parity gate PASS (run first):** `scripts/check_runtime_parity.py`
  passed (exit 0) before any API acceptance — `analytics/operations.py`,
  `collectors/usage_reports/registry.py`, `api/operations.py`,
  `collectors/persistence/core.py`, `collectors/core/runtime.py` all MATCH host
  hashes. The STD-06A-rebuilt `graph-agent-operations-api-dev` now serves the
  STD-05B source.
- **Live collection path PASS:** `USAGE-004` (`onedrive_activity`,
  `getOneDriveActivityUserDetail(period='D7')`) and `USAGE-005`
  (`onedrive_account_usage`, `getOneDriveUsageAccountDetail(period='D7')`) each
  ran `COLLECT` through the capability gate, hit the real Graph (30 + 26 rows),
  normalized with no errors, and persisted to current and snapshot tables
  (`persisted_rows` 30 + 26).
- **Permission gate fail-closed PASS:** withholding `Reports.Read.All` returns
  `SKIP_PERMISSION_REQUIRED` with no Graph call or persistence.
- **Deleted/malformed + zero/missing allocation PASS:** malformed OneDrive
  `Is Deleted` flags fail closed to deleted; deleted/missing-activity rows are
  excluded from active counts; `storage_utilization` fails closed to `None` for
  zero/missing allocation (host logic + unit tests).
- **No viewed/synced threshold drives active-user KPI:** API reports
  `viewed_count=0` and `synced_count=0`, while `active_users=23` is derived only
  from `last_activity_date` presence on non-deleted `onedrive_activity` rows.
- **DB ↔ API consistency PASS:** the running API readback matches the live DB
  evidence for all six locked KPIs — active_users 23, active_accounts 23,
  latest_activity 2026-06-26, total_storage_used 113932223, total_file_count 156,
  storage_utilization 3.9854e-06 (SQL cross-check on newest current generation,
  non-deleted).
- **Analytics + API readback PASS:** `GET /api/operations/adoption/onedrive`
  returns `READY` with all six locked KPIs. `tests.analytics.test_operations`
  = 19 PASS; `tests.usage_reports.test_usage_reports` = 17 PASS.
- **Historical blocker resolved:** the original STD-06 run was BLOCKED on
  runtime/container parity (Defect B). That was corrected by STD-06A (rebuild
  `graph-agent-collector:dev` + recreate collector/operations-api) and the
  migration-regression gap by STD-06B. Persistence (STD-04 Defect A) was already
  resolved for OneDrive by migration `013`. This rerun confirms end-to-end
  consistency; OneDrive Basic is ACCEPTED and STD-17 is unblocked.

**Scope accounting:** Acceptance-only. No production Python, migration, inventory,
permission, credential, or runtime source was modified.
