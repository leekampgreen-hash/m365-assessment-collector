# Project Progress

## TM-P03 Teams analytics + API (PASS)

**Task:** `TM-P03-CLOSE`
**Status:** `TM-P03 PASS`

- `teams_activity_summary()` implemented.
- `GET /api/operations/teams/activity-summary` implemented.
- Inactive detection covers 30/60/90-day windows.
- Full suite PASS; runtime parity PASS.

## DA-P02 Groups and role assignments population (PASS)

**Task:** `DA-P02-CLOSE`
**Status:** `DA-P02 PASS`

Populated targeted directory tables through live targeted collection:

- `core."group"`: 18 rows
- `core.directory_role_assignment`: 11 rows
- Pytest environment fixed permanently; broad collector-container suite passes **1314/1314 tests**.

## DA-P03 License expiry field (PASS)

**Task:** `DA-P03-CLOSE`
**Status:** `DA-P03 PASS`

Added license expiry field through migration 023 and populated through live targeted collection:

- Migration 023 applied: `next_lifecycle_datetime` and `capability_status_expiry` columns added to `core.subscribed_sku`
- Column existence verified: both columns present in `core.subscribed_sku`
- Targeted collection completed: `G01-004` endpoint executed successfully
- Expiry data populated: `next_lifecycle_datetime` and `capability_status_expiry` fields populated in `core.subscribed_sku`

## DA-P01 Persistence defect closure (PASS)

**Task:** `DA-P01-CLOSE`
**Status:** `DA-P01 PASS`

Fixed two persistence defects:

- `G01-003`: jsonb serialization fix in `core.py`.
- `G01-005/006`: missing adapter columns fix.

Authoritative database verification found 1 row in `core.organization` and 3 rows in
`core.audit_event`. Focused validation passed **125/125 tests**, and runtime parity
passed.

## SP-P12 SharePoint workload seal / handover

**Task:** `SP-P12-SHAREPOINT-WORKLOAD-SEAL-001`
**Status:** `SP_P12_SEALED`

`SHAREPOINT_WORKLOAD = SEALED / ACCEPTED`. SP-P03 PASS; SP-P04 PASS; SP-P05
PASS; SP-P06 PASS; SP-P07 PASS; SP-P08 PASS
(`sharing_capability: externalUserAndGuestSharing`); SP-P09 PASS; SP-P10
PASS_WITH_LIMITATIONS (zero-content trial tenant); SP-P11 PASS.

Completed phases: SP-P03 expanded the SharePoint tenant settings collector and
registered `G01-020`; SP-P04 applied migration 021
(`core.sharepoint_tenant_settings`); SP-P05 wired the production pipeline with
integration tests PASS; SP-P06 added orphaned-sites analytics + API; SP-P07 added
external-sharing analytics + API; SP-P08 confirmed live acceptance with
`sharing_capability: externalUserAndGuestSharing`; SP-P09 wired the SharePoint
audit collector and applied migration 022
(`core.sharepoint_high_value_audit_event`); SP-P10 completed audit live acceptance
PASS_WITH_LIMITATIONS (zero-content trial tenant, pipeline proven via a controlled
synthetic real-PostgreSQL proof); SP-P11 closed audit analytics + API with focused
suites 54/54 PASS.

The durable SharePoint contract is recorded in
`docs/evidence/SP-P12-SHAREPOINT-WORKLOAD-SEAL-001.md`: tenant settings persisted to
`core.sharepoint_tenant_settings`, sharing capability locked at
`externalUserAndGuestSharing`, audit persisted to
`core.sharepoint_high_value_audit_event` (append/event-history, tenant-scoped,
idempotent), and the read-only `GET /api/operations/sharepoint/audit-summary` API
with a `[1, 100]` clamped limit and fail-closed dependency behavior.

Historical blockers from SP-P10's zero-content live window are non-blocking and
resolved via the controlled synthetic proof. Synthetic residue is NONE. After
SP-P12, SharePoint is frozen and may be reopened only for a direct production
regression, formally approved new scope, or an independent blocking
security/correctness finding.

`SHAREPOINT_WORKLOAD_SEALED: YES`; `NEXT_WORKLOAD: License data workstream`; no
next-workload implementation is included.

Evidence: `docs/evidence/SP-P12-SHAREPOINT-WORKLOAD-SEAL-001.md`.

## SP-P11 SharePoint audit analytics and API (PASS)

**Task:** `SP-P11-SHAREPOINT-AUDIT-ANALYTICS-API-001`
**Status:** `SP_P11_PASS`

Added the read-only SharePoint high-value audit analytics projection and
Operations API route over the persisted `core.sharepoint_high_value_audit_event`
rows (the `G01-020` / SharePoint audit event-history contract). The work follows
the locked SharePoint high-value audit contract and the accepted OneDrive
high-value audit analytics/API pattern.

- **Analytics (`analytics/operations.py`):** `OperationsAnalyticsQueryService`
  now loads `core.sharepoint_high_value_audit_event` (tenant-scoped, newest-first)
  and exposes `sharepoint_audit_summary(limit=50)`, returning a summary
  (`total_events`, per-operation counts, `latest_event_time`), per-tenant
  aggregates, and a bounded `recent_events` detail list. The `limit` is clamped
  to `[1, 100]`. Fail-closed: with no loaded dependency rows the method reports
  `status="DATA_DEPENDENCY_UNAVAILABLE"` with empty summary/tenants rather than
  fabricating results.
- **API (`api/operations.py`):** new read-only `GET /api/operations/sharepoint/audit-summary?limit=...`.
  Invalid/non-numeric/zero `limit` returns HTTP 400 `INVALID_LIMIT`; otherwise the
  route returns HTTP 200 with the analytics payload and the derived status.
- **Scope:** read-only analytics + API + focused tests. No Graph collection,
  permission, migration, persistence, or runtime-deployment source change; no
  live Microsoft call and no synthetic database mutation.
- **Tests:** focused analytics/API suites pass **54/54** in
  `graph-agent-collector-dev`
  (`python3 -m unittest tests.analytics.test_operations tests.analytics.test_operations_api tests.analytics.test_security_api`).
  Coverage includes per-tenant operation counting, fail-closed missing dependency,
  bounded limit, and the `audit-summary` endpoint serialization/validation.
- **Runtime parity:** `operations-api` rebuilt
  (`docker compose up -d --build --no-deps operations-api`) and
  `scripts/check_runtime_parity.py` passes (exit 0) — all five checked production
  modules MATCH host hashes including the changed `analytics/operations.py` and
  `api/operations.py`. API `/health` → `{"status":"READY","database":"READY"}`.
- **SYNTHETIC_RESIDUE:** NONE.

- **Next:** SharePoint follow-up validation / continued SharePoint data
  workstream as scheduled.

## SP-P10 SharePoint audit live acceptance

**Status:** `SP_P10_PASS_WITH_LIMITATIONS`

SharePoint audit live acceptance completed with a bounded real Management Activity
invocation against the trial tenant. The live window returned zero content, so no
new event was created and no candidate classification was naturally encountered.
The pipeline was proven independently via a controlled synthetic real-Postgres
proof. Operations proven end-to-end: `SharingInvitationCreated`,
`AnonymousLinkCreated`, `AnonymousLinkRemoved`, and `SharingRevoked`.

- **Live window:** zero content (trial tenant).
- **Pipeline proven:** controlled synthetic real-Postgres proof.
- **Operations proven:** SharingInvitationCreated, AnonymousLinkCreated, AnonymousLinkRemoved, SharingRevoked.
- **SYNTHETIC_RESIDUE:** NONE.
- **PARITY:** PASS.

## SP-P03 through SP-P07 SharePoint progress summary

- **SP-P03:** SharePoint tenant settings expanded and the `G01-020` endpoint wired into the workload registry.
- **SP-P04:** Migration 021 applied for SharePoint tenant settings persistence.
- **SP-P05:** SharePoint tenant settings collector and production-path persistence wiring implemented, with focused coverage.
- **SP-P06:** SharePoint orphaned-sites analytics method and read-only Operations API route implemented, with focused coverage.
- **SP-P07:** SharePoint follow-up validation remains the next acceptance step after the implemented collector and analytics/API work.

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

## EX-P10 Exchange Basic seal / handover

**Task:** `EX-P10-EXCHANGE-BASIC-SEAL-001`
**Status:** `EXCHANGE BASIC: SEALED / ACCEPTED`

Final status: EX-P01 PASS; EX-P02 CLOSED/PASS; EX-P03 PASS; EX-P04 PASS;
EX-P05 PASS; EX-P06 PASS AFTER VALIDATION CLOSURE; EX-P07 PASS; EX-P08 PASS;
EX-P09 PASS; EX-R01 `PASS_WITH_NON_BLOCKING_FINDING`. There is no open
production blocker.

Supported Exchange Basic contract: mailbox identity/UPN, storage used, mailbox
capacity from `prohibit_send_receive_quota`, utilization percentage,
`LOW`/`MEDIUM`/`HIGH`/`NO_DATA`, and report refresh date. The authoritative
semantic layer is `analytics.exchange_mailbox_capacity`; Mailbox Capacity Risk
is `count(usage_level = HIGH)`.

Protection boundary: Spam is BASIC/EOP and `DATA_SOURCE_PENDING`; Quarantine is
BASIC/EOP and `ARCHITECTURE_BLOCKED` by the supported platform boundary, not
technical debt; Phishing/Malware/Spoof have Basic EOP capability acknowledged,
with aggregate collector source pending and advanced Defender telemetry
 deferred. These are not Exchange Basic closure blockers.

Exclusions remain raw Message Trace, per-message lifecycle/event/action,
per-user sent/read/received activity, Top Senders, Top Sender Domains,
Top Recipients, Top Source IP, advanced Defender telemetry, and UX redesign.

Accepted evidence: current rows 30, semantic rows 30, duplicate rows 0,
LOW=30, MEDIUM=0, HIGH=0, NO_DATA=0, latest refresh `2026-08-26`, Mailbox
Capacity Risk=0, runtime parity PASS, production API READY, and bounded live
Graph acceptance PASS. These counts and timestamp are acceptance evidence, not
hardcoded future expectations.

EX-P06 chronology is preserved: implemented; initial validation blocked; validation
subsequently CLOSED/PASS through EX-P06A; production behavior later re-proven by
EX-P07B/EX-P08. EX-R01 found no dropped capability, production wiring regression,
persistence regression, runtime drift, or deferred-feature dependency. Its sole
NON_BLOCKING finding was EX-P06 documentation-status drift, closed by EX-P10.

Scope: documentation/handover only; no production source, tests, UX, feature, or
service rebuild changed.

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


## Standard Version Roadmap and Shared Preflight

**Status:** STANDARD VERSION ACTIVE / EXCHANGE BASIC SEALED / EX-P10 ACCEPTED

The Standard Version is the active delivery track. Historical G/CH work remains
preserved. Exchange, OneDrive, SharePoint, and License are the four priority
workloads. Each workload is collector-first: its bounded live acceptance must
complete before its corresponding Basic Scenario Agent work begins. Rule #11 is
closed and its production-live acceptance is preserved; it is not reopened by
this roadmap.

### Current delivery sequence

| Task | Delivery item | State / gate |
|---|---|---|
| STD-00 | Standard Version reprioritization and shared preflight | COMPLETE; this record |
| STD-01 | Shared capability / production wiring preflight | COMPLETE WITH BLOCKERS; this record |
| STD-02 | User Identity Baseline | NEXT |
| EX-P03 | Exchange Basic DATA contract lock | PASS (EX_P03_PASS); canonical fields, capacity semantics, protection gaps, and message-level exclusions locked; next EX-P04 persistence/current/history reconciliation |
| EX-P04A | Exchange persistence safety correction | PASS (EX_P04A_PASS); complete-acquisition gate and duplicate source-key rejection added; live acceptance deferred to EX-P04B |
| EX-P04B | Exchange persistence production proof | PASS (EX_P04B_PASS); deployed runtime parity, authoritative graph_agent DB safety proofs, live integrity, and analytics compatibility validated; ready for EX-P05 |
| EX-P05 | Exchange collector/normalization wiring | PASS (EX_P05_PASS); USAGE-003 production collector, locked normalization, completeness safety, packaging parity, focused runtime tests, and bounded live read-only collection validated; ready for EX-P06 |
| EX-P06 | Exchange data-handling hardening | PASS after validation closure; initially BLOCKED at validation, then CLOSED/PASS through EX-P06A and later EX-P07B/EX-P08 integration/live evidence; bounded retries, Retry-After propagation, schema/date fail-closed validation, and forward-generation persistence gate validated |
| EX-P07 | Exchange production-path integration | PASS (EX_P07B_PASS); bounded production-runtime negative matrix and tenant-scoped isolation tests pass; compile validation pass; live tenant protection remains rollback-only/environment-dependent |
| EX-P08 | Exchange bounded live acceptance | PASS (EX_P08_PASS); one production USAGE-003 Graph execution completed with runtime parity, current/snapshot integrity, analytics agreement, and focused regression PASS |
| EX-P09 | Exchange analytics/API closure | PASS (EX_P09_PASS); authoritative capacity view, tenant-scoped Operations API summary/detail, HIGH risk KPI, fail-closed behavior, live DB/API consistency, focused tests, and runtime parity validated |
| EX-P10 | Exchange Basic seal / handover | SEALED / ACCEPTED; EX-P01–EX-P09 reconciled, supported capability and protection boundary locked, and accepted production evidence recorded |
| STD-03 | Exchange Basic Collector | PLANNED; collector first |
| STD-04 | Exchange Live Acceptance | PLANNED; required before STD-16 |
| STD-05 | OneDrive Basic Collector | IMPLEMENTED (STD-05B) |
| STD-06 | OneDrive Live Acceptance | ACCEPTED (STD-06 rerun PASS); required before STD-17 |
| STD-07 | SharePoint Basic Collector | IMPLEMENTED (STD-07B); live acceptance next |
| STD-08 | SharePoint Live Acceptance | ACCEPTED (rerun PASS after STD-08A identity correction); required before STD-18 |
| STD-09 | License Inventory | COMPLETE WITH BLOCKER; baseline contract closed |
| STD-10 | User-License Mapping | CONTRACT PASS; STD-10B NOT_REQUIRED / SKIPPED (existing production wiring satisfies contract) |
| STD-11 | License Live Acceptance | ACCEPTED; required before license scenarios |
| STD-12 | Cross-workload Correlation | ACCEPTED (STD-12B IMPLEMENTED; STD-12C live acceptance PASS after STD-12D fix) |
| STD-13 | Standard KPI Engine | CONTRACT PASS; STD-13B IMPLEMENTED; focused automated validation PASS; live acceptance next |
| STD-14 | Standard API | CONTRACT PASS; no API implementation gap; STD-14B not required (all Standard functions map to existing routes) |
| STD-15 | Standard Dashboard | ACCEPTED at STD-15C rerun; deployed browser/DOM, API/assets, and parity validation pass |
| STD-15E | Workload usage drilldown UX | IMPLEMENTED; focused tests and runtime parity pass; deployed browser acceptance pending |
| STD-15K1A | Dashboard drilldown usability refinement | IMPLEMENTED; frontend formatting, search, filtering, and pagination added; runtime validation recorded; browser acceptance deferred to STD-15K1B |
| STD-15K1B | SharePoint and SKU UI cleanup | IMPLEMENTED; redundant SharePoint usage mini menu removed, SharePoint storage formatted, and Assigned SKUs normalized for customer-facing rendering; browser acceptance deferred to STD-15K1C |
| STD-15G2C | Exchange DB RCA + analytical view | PASS (STD_15G2C_PASS); authoritative DB reconciled, quota persistence defect corrected, analytics view created and adopted by API | 
| STD-15G2B | Exchange capacity completion | RESOLVED via STD-15G2C; database reconciliation complete | 
| STD-15G3B | Exchange UI contract fix | PASS (STD_15G3B_PASS); capacity buckets, refresh date, storage formatting, mailbox item mapping corrected; runtime parity PASS; browser acceptance deferred to STD-15G3C | 
  | STD-15H2 | OneDrive capacity data wiring | ACCEPTED (STD_15H2A_PASS); runtime parity and authoritative DB/API account-row reconciliation PASS; raw per-account capacity/identity exposed through existing analytics/API |
  | STD-15H3 | OneDrive capacity semantic view | ACCEPTED (STD_15H3_PASS); authoritative 26-row analytical VIEW created and live-validated with fail-closed utilization/usage-level semantics |
  | STD-15H4A | OneDrive capacity API acceptance | BLOCKED (STD_15H4A_BLOCKED); live API dependency issue remains; STD-15H4C forward-only view contract correction PASS; superseded by STD-15H4D live acceptance |
  | STD-15H4D | OneDrive capacity API live acceptance | ACCEPTED (STD_15H4D_PASS); migration 017 applied and recorded, runtime SELECT/parity PASS, API READY with 26 details and LOW 26; view/API consistency and aggregate regression PASS |
 |

 | STD-15I2 | User identity display wiring | PASS (STD_15I2_PASS); readable identity (display_name/user_principal_name) exposed through analytics, correlation API, and workload UI without changing canonical join semantics; runtime parity PASS |
| STD-15I3 | Exchange active-only presentation | PASS (STD_15I3_PASS); customer-facing Exchange capacity views (detail, usage summary, workload card) show ACTIVE Exchange users only; INACTIVE/UNKNOWN excluded from capacity presentation while retained in backend evidence; counts reconcile to active rows |
| STD-15F | Workload usage drilldown live acceptance | BLOCKED; runtime/API preflight passed, isolated Chromium harness startup blocked |
 | STD-15H5A | OneDrive capacity UI live acceptance | BLOCKED (STD_15H5A_BLOCKED); superseded by STD-15H5D browser rerun evidence |
 | STD-15H5D | OneDrive capacity UI browser rerun | BLOCKED (STD_15H5D_BLOCKED); parity/UI/API preflight PASS and isolated Chromium clean, but deployed UI still shows unavailable OneDrive buckets/date and zero usage-summary/drilldown rows despite API READY with 26 details; evidence `docs/evidence/STD-15H5D-ONEDRIVE-CAPACITY-UI-BROWSER-RERUN-001.md` |
| STD-15H5G | OneDrive capacity UI final browser acceptance | ACCEPTED (STD_15H5G_PASS); parity/UI/API preflight PASS; isolated Chromium PASS at desktop and narrow viewports with 26 rows, correct buckets/date/storage/files, filters, utilization, and usable horizontal overflow; evidence `docs/evidence/STD-15H5G-ONEDRIVE-UI-FINAL-BROWSER-ACCEPTANCE-001.md` |
| STD-16 | Exchange Scenario | CONTRACT PREFLIGHT COMPLETE WITH BLOCKERS; STD-16B blocked pending delegated Mail.Send authorization and SEND_MAIL wiring; after STD-04 |
| STD-17 | OneDrive Scenario | PLANNED; after STD-06 |
| STD-18 | SharePoint Scenario | PLANNED; after STD-08 |
| STD-19 | Scenario Correlation | PLANNED |
| STD-20 | Cross-workload Production Test | CLOSURE PREFLIGHT BLOCKED; SharePoint user-usage API dependency unavailable and main-dashboard Usage Overview mount/wiring is not proven |
| STD-21 | Runtime Parity / Hardening | PLANNED |
| STD-22 | Standard Feature Closure | PLANNED |

Execution order is:

`STD-02 -> STD-03 -> STD-04 -> STD-05 -> STD-06 -> STD-07 -> STD-08 -> STD-09 -> STD-10 -> STD-11 -> STD-12 -> STD-13 -> STD-14 -> STD-15 -> STD-16 -> STD-17 -> STD-18 -> STD-19 -> STD-20 -> STD-21 -> STD-22`

The following remain explicitly deferred, not deleted, until STD-22 closes:

- additional Entra security rules and security-posture expansion;
- Identity Protection, PIM, and advanced Conditional Access analysis;
- Purview, DLP, and oversharing analytics;
- advanced license optimization, AI recommendations, cost modelling, and anomaly detection.

### STD-01 bounded preflight findings

**Auth:** The native Collector path is app-only OAuth 2.0 client credentials.
`collectors/core/auth.py` acquires a tenant-specific v2 token for
`https://graph.microsoft.com/.default`; `collectors/run_collector.py` selects
the protected `secrets/collector.env` source and the production entrypoint is
`python -m collectors.run_collector`. Scenario device-code auth is separate.

**Permission declarations:** Endpoint-declared permissions are loaded from
`config/api_inventory.json`. The production capability gate receives the
explicit `--granted-graph-permissions` deployment declaration in
`collectors/run_collector.py`; it does not infer grants from token errors. The
recorded sanitized Collector token roles in
`data/discovery/discovery-state.json` / `docs/permission-matrix.md` include
`User.Read.All` and `LicenseAssignment.Read.All`, but do not include
`Reports.Read.All`. No token values, secrets, credentials, or authorization
headers were recorded here.

**Inventory:** The seven usage-report entries already cover Exchange basic
email/mailbox activity, OneDrive activity/account usage, and SharePoint
user/site usage, all with application auth and `Reports.Read.All`. `G01-004`
covers subscribed SKU inventory with `LicenseAssignment.Read.All`. `G01-001`
includes `assignedLicenses`, and `database/migrations/009_user_license_assignment.sql`
plus the existing persistence path support assignment rows, but no separate
user-license-assignment inventory entry exists. Therefore Exchange, OneDrive,
SharePoint, and License inventory are EXISTING; user-license assignment is
PARTIAL.

**Wiring:** The generic path is CollectorRuntime -> Graph/usage-report
transport -> normalized result -> workload/usage adapter -> persistence
dispatcher or usage-report writer -> PostgreSQL. The usage-report transport,
CSV normalizer, report registry, and usage tables are reusable. The central
`collectors/workloads/registry.py` currently binds only G01-001 through
G01-019, so no workload-specific Exchange, OneDrive, or SharePoint collector
binding is present. The production CLI, capability gate, database writer,
trusted tenant resolution, and Docker image/package path are reusable.

**Database readiness:** Existing current, snapshot, history, user, subscribed
SKU, user-license-assignment, and usage-report contracts support upcoming
Exchange basic usage without architectural redesign. No migration was created
or changed. This is architecture readiness only, not collector or live
acceptance evidence.

**Blockers:**

- `Reports.Read.All` is not present in the recorded deployed/token-role
  baseline; STD-03, STD-05, and STD-07 require a separately verified
  app-only-compatible permission declaration before live acceptance. No grant
  or admin consent was requested.
- Central workload registry bindings and workload-specific collector adapters
  for Exchange, OneDrive, and SharePoint are missing; existing usage-report
  modules are reusable but do not constitute those bounded collector tasks.
- User-license assignment is PARTIAL because its source and persistence logic
  exist but it has no dedicated API inventory entry; STD-10 must close the
  contract before acceptance.

**Rule #11 accounting:** Rule #11 remains CLOSED / production-live accepted in
the existing project history and is not reopened or modified by STD-00/STD-01.

**Scope accounting:** This section is documentation-only preflight evidence.
No production Python, database migration, inventory/configuration, Scenario
Agent, permission, credential, Entra, or Graph behavior was changed.

### STD-03 locked Exchange Standard usage scope (authoritative)

Approved by STD-03 contract discovery (`STD-03-EXCHANGE-BASIC-CONTRACT-001`).
This is the single source of truth for what Exchange Standard "basic usage"
means; do not widen it without a separate contract decision.

**In scope (from `USAGE-003` / `getMailboxUsageDetail`, period `D7` default):**

- Active users (derived from report evidence only: `exchange_mailbox_usage`
  rows that are not deleted and have a non-empty `last_activity_date`; no
  message-count or threshold semantics are invented).
- Last activity (`last_activity_date`).
- Total mailbox storage used (`storage_used`, aggregated across the current
  report set).
- Basic mailbox / storage utilization only where it is already available from
  the same standard report (mailbox `mailbox_item_count`, `storage_used`).
  A quota-based utilization ratio is NOT included because
  `getMailboxUsageDetail` does not expose a single usable quota column in the
  locked report schema.

**Out of scope (explicitly excluded, do not collect or surface):**

- send count, receive count, read count;
- message-level / per-message data;
- spam / phish / malware / spoof reporting;
- advanced Defender features;
- Basic Protection reporting (deferred until Exchange Usage basic is live
  accepted).

The existing `analytics/operations.py` `exchange_adoption()` derives Exchange
"active users" from `exchange_email_activity` send/receive/read evidence. That
evidence is OUT of the locked STD-03 scope; STD-03 KPI derivation must be
grounded in `exchange_mailbox_usage` only. Any later widening that reintroduces
email-activity evidence requires an explicit contract update here.

**Scope accounting:** This STD-03 scope record is documentation-only. No
production Python, database migration, inventory/configuration, Scenario Agent,
permission, credential, Entra, or Graph behavior was changed.

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

### STD-07 locked SharePoint Standard usage scope (authoritative)

Approved by STD-07 contract discovery (`STD-07-SHAREPOINT-BASIC-CONTRACT-001`).
This is the single source of truth for what SharePoint Standard "basic usage"
means; do not widen it without a separate contract decision.

**Smallest contract:** the two-report pair `USAGE-006` (`sharepoint_user_activity`
/ `getSharePointActivityUserDetail`) and `USAGE-007` (`sharepoint_site_usage` /
`getSharePointSiteUsageDetail`), period `D7` default. Both declare
`Reports.Read.All`, application auth, and are existing inventory/registry/
adapter/persistence entries. Neither report alone satisfies the locked scope:
per-user active/activity evidence lives in `USAGE-006`, while site storage, file
count, and allocated capacity live only in `USAGE-007`.

**In scope:**

- Active sites (from `USAGE-007` evidence only: `usage_sharepoint_site_usage`
  rows that are not deleted and have a non-empty `last_activity_date`; no
  file-count or activity-count threshold semantics are invented).
- Active users (from `USAGE-006` evidence only: `usage_sharepoint_user_activity`
  rows that are not deleted and have a non-empty `last_activity_date`; no
  viewed/synced threshold semantics are invented).
- Last activity (`last_activity_date`, max over the active set).
- Total storage used (`storage_used`, summed across the current
  `usage_sharepoint_site_usage` report set).
- Total file count (`file_count`, summed across the current
  `usage_sharepoint_site_usage` report set).
- Basic storage utilization, directly supported by the standard report:
  `storage_used / storage_allocated` (per site and aggregate), because
  `getSharePointSiteUsageDetail` exposes both `Storage Used (Byte)` and
  `Storage Allocated (Byte)` in the locked report schema (same shape as the
  accepted OneDrive `USAGE-005` contract).

**Out of scope (explicitly excluded, do not collect or surface):**

- site permission analysis;
- oversharing / external-sharing investigation;
- shared-internal/shared-external file counts;
- file-level / per-file inventory;
- DLP / Purview;
- Defender / security posture;
- advanced analytics.

The existing `analytics/operations.py` `sharepoint_user_adoption()` derives
SharePoint "active users" via the generic `_adoption()` / `_evidence_status()`
path, which for the `sharepoint_user_activity` workload falls back to
`viewed_count` / `edited_count` / `synced_count` / `page_view_count` counts when
`last_activity_date` is absent. That activity-count fallback is OUT of the locked
STD-07 scope; STD-07 KPI derivation must be grounded in `last_activity_date`
presence on non-deleted rows only, and must surface site storage, file count, and
utilization from `usage_sharepoint_site_usage`. No site-level
(`sharepoint_site_usage`) analytics method or API route exists yet; both are the
primary SharePoint-specific implementation for STD-07B.

**STD-07B implementation result:** `sharepoint_user_adoption()` now derives active
users only from non-deleted rows with valid `last_activity_date`. The new
`sharepoint_site_adoption()` exposes active sites, latest activity, total storage,
file count, and fail-closed storage utilization. Read-only API exposure is
`/api/operations/adoption/sharepoint/sites`; shared USAGE-006/007 inventory,
Reports.Read.All gate, normalization, current/snapshot persistence, and runtime
paths remain unchanged. Focused analytics and API tests pass. No migration,
permission, Graph-write, sharing, DLP, or runtime deployment change was made.

**Scope accounting:** This STD-07B implementation is recorded here for the
Standard Version progress log. The running deployment containers were built from
pre-STD-07B source; container runtime parity for the changed `analytics/operations.py`
and `api/operations.py` modules must be restored and re-verified before SharePoint
Basic can be ACCEPTED (see STD-07C).

### STD-07C SharePoint runtime parity correction (PASS)

Rebuilt the shared `graph-agent-collector:dev` image from the current host source
and recreated only `collector` and `operations-api`. The stale runtime was caused
by `Dockerfile.collector` baking `analytics`/`api` into the image while neither
`operations-api` nor `collector` had a source bind mount for those directories,
so the running containers kept pre-STD-07B `analytics/operations.py` and
`api/operations.py`. `scripts/check_runtime_parity.py` (host-to-runtime hash gate,
run FIRST before any SharePoint API acceptance) now passes with all five checked
production modules MATCH: `analytics/operations.py`, `api/operations.py`,
`collectors/usage_reports/registry.py`, `collectors/persistence/core.py`,
`collectors/core/runtime.py` (exit `0`).

The rebuilt API is healthy (`/health` → `{"status":"READY","database":"READY"}`).
Both deployed routes return HTTP 200 with the accepted STD-07B semantics:
`/api/operations/adoption/sharepoint` → `sharepoint_user_adoption()` reports
`active_users` grounded only in non-deleted `sharepoint_user_activity` rows with
a valid `last_activity_date` (24 active), and `/api/operations/adoption/sharepoint/sites`
→ `sharepoint_site_adoption()` reports active sites, latest activity, total
storage, file count, and fail-closed storage utilization from
`usage_sharepoint_site_usage`. No Graph collection, writes, permissions, schema,
or KPI semantics changed. `STD08_READY=YES`.

### STD-08A SharePoint site identity RCA and correction (PASS)

The STD-08 live acceptance was BLOCKED because native `USAGE-007` /
`getSharePointSiteUsageDetail(D7)` failed closed as `ENTITY_IDENTITY_UNAVAILABLE`
(`rows=0`, `persisted_rows=0`). RCA (`STD-08A-SHAREPOINT-SITE-IDENTITY-RCA-001`):

- **Root cause (identity-policy logic):** `collectors/usage_reports/registry.py::_identity`
  required BOTH a valid (non-zero) `Site Id` AND a non-empty `Site URL` to accept
  a site identity. The live report provides a populated, stable `Site Id`
  (per-site GUID) but masks/omits the `Site URL` value, so every row returned
  `None` and the report failed closed.
- **Correction:** the site branch now prefers `Site Id` whenever present and
  non-zero, falls back to a non-empty `Site URL`, and still fails closed
  (`ENTITY_IDENTITY_UNAVAILABLE`) only when neither a usable `Site Id` nor a
  non-empty `Site URL` exists. No schema, migration, permission, KPI semantics,
  or Graph behavior changed.
- **Wiring:** parity gate exit `0` after rebuild/recreate of `collector` +
  `operations-api`; permission gate still `SKIP_PERMISSION_REQUIRED` without
  `Reports.Read.All`.
- **Live proof:** native `USAGE-007` now `PASS` with 12 rows normalized and
  persisted (distinct valid site `entity_key`s, no collapsing). Site adoption
  readback reflects the new set (`active_sites=3`, `total_storage_used=36964667`,
  `total_file_count=43`, `latest_activity=2026-06-26`).
- **Offline:** 706 tests OK (1 skipped for missing DB driver); focused
  site-identity fail-open/fallback/fail-closed coverage added.
- **Next:** `STD-09-LICENSE-INVENTORY-BASELINE-001`.

### STD-09 License Inventory Baseline (PASS WITH BLOCKER)

- Closed the tenant/SKU inventory contract by reusing accepted G01-004 `GET /v1.0/subscribedSkus` collection, `LicenseAssignment.Read.All` application permission, normalization, and current-plus-snapshot persistence.
- Canonical KPIs use only persisted `prepaid_units` and `consumed_units`: available units are `prepaid_units - consumed_units`; utilization is `consumed_units / prepaid_units * 100` only when purchased units are positive and both operands are present.
- Existing `core.subscribed_sku` and `core.subscribed_sku_snapshot` are sufficient; no migration, live read, permission change, or production source change was required. Existing Graph evidence is HTTP 200, one page, three rows; accepted implementation evidence covers 233 tests.
- Existing analytics/API wiring reads the inventory, but its current license endpoint is user-assignment/evidence oriented; tenant/SKU KPI exposure remains future KPI/API scope and does not block the baseline contract.
- A pre-existing retention metadata drift was open at baseline: registry `REFERENCE` versus authoritative adapter/catalog/schema/migration `STANDARD`. This drift is now closed by `STD-09A-LICENSE-RETENTION-WIRING-CLOSURE-001`.
- **Evidence:** `docs/evidence/STD-09-LICENSE-INVENTORY-BASELINE-001.md`.
- **Status:** `STD_09_PASS_WITH_BLOCKERS`; `STD10_READY=YES`.
- **Next:** `STD-10-USER-LICENSE-MAPPING-CONTRACT-001`.

### STD-09A License Retention Wiring Closure (PASS / FIXED)

**Status:** `STD_09A_FIXED_PASS`

- Closed the G01-004 retention-class drift. Root cause was stale registry metadata: `collectors/workloads/registry.py` set `G01-004` `retention_class="REFERENCE"` while the authoritative adapter (`collectors/workloads/directory/subscribed_skus.py` `RETENTION_CLASS="STANDARD"`), `docs/data-catalog.md`, `docs/database-schema-design.md`, and `database/migrations/003_core_directory_and_licensing.sql` all define `STANDARD`.
- **Proved registry drift, not contract error:** the adapter hard-codes `STANDARD` into both the current and snapshot rows at normalization, so the persisted retention value has always been `STANDARD`; the registry value is metadata-only for G01-004 (G07-A directory adapters do not consume `lineage.retention_class`).
- **Correction:** updated the registry `G01-004` `retention_class` from `REFERENCE` to `STANDARD` (smallest correction). No persistence-mode, snapshot, schema, migration, permission, or Graph change; no change to the durable retention contract (`STANDARD`). Added a focused registry contract test `test_g01_004_contract_and_standard_retention`.
- **Runtime parity:** rebuilt `graph-agent-collector:dev` and recreated `graph-agent-operations-api-dev`; both the collector and operations-api runtime now report `G01-004 retention=STANDARD`. `scripts/check_runtime_parity.py` gate passes (all MATCH) and the operations API is healthy.
- **Validation:** focused registry/normalization/persistence contract suites pass (242 relevant tests: registry, directory adapters, workload integration, persistence core, normalization handoff). Pre-existing, environment-only failures remain in `tests/persistence/test_g01_015_event` (migration dir not mounted in test container) and `tests/discovery/test_discovery_agent` (`agents` module not importable there); both are unrelated to this change.
- **Result:** `G01-004` is usable by `STD-10` user-license mapping; `STD10_READY=YES`.

### STD-10 User ↔ License Mapping Contract (PASS)

**Status:** `STD_10_CONTRACT_PASS`

- Defined the canonical app-only User ↔ License mapping contract (`STD-10-USER-LICENSE-MAPPING-CONTRACT-001`): User → assigned SKU (`user.assignedLicenses[].skuId`, G01-001) → subscribed SKU inventory (`core.subscribed_sku` by `(tenant_id, sku_id)`).
- **Verified the current collection/persistence already satisfies the contract:** Graph source (`GET /v1.0/users` with `assignedLicenses`, `LicenseAssignment.Read.All`), normalization (`collectors/workloads/directory/users.py` `_assigned_licenses`/`_assigned_licenses_available` handoff), persistence (`collectors/persistence/core.py::write_users_with_assignments` → `core.user_license_assignment`).
- **Canonical keys:** user = `core."user".(tenant_id, source_object_id)`; SKU = `core.subscribed_sku.sku_id` (immutable Graph SKU id); tenant isolation via `tenant_id` FKs `ON DELETE RESTRICT`; assignment source is app-only `assignedLicenses`.
- **Semantics confirmed:** stable user and SKU joins, duplicate handling (`UNIQUE(tenant_id, user_id, sku_id)` + `ON CONFLICT ... DO UPDATE last_observed_at`), multiple SKUs per user (one row per `(user, sku)`), users with no license (empty set), stale/removed assignment (tenant delete + rebuild on complete refresh), partial/incomplete evidence (refresh aborted and existing set preserved).
- **DB redesign:** NO — `core.user_license_assignment` (migration `009`) already has the canonical shape; no migration, schema, FK, or index change.
- **Read-only API/query semantics** (licensed users, users by SKU, assigned count by SKU, user↔SKU mapping) defined for later Standard API/KPI scope; not built now.
- **Documentation:** added durable `core.user_license_assignment` canonical mapping entry to `docs/database-schema-design.md` (table existed in migration 009 but was absent from the durable schema design doc); evidence at `docs/evidence/STD-10-USER-LICENSE-MAPPING-CONTRACT-001.md`.
- **No blockers.** No Graph write, permission, `/licenseDetails`, cross-workload, KPI, or assignment/unassignment work performed.
- **Next:** `STD-11-LICENSE-BASIC-LIVE-ACCEPTANCE-001`.

### STD-10B User-License Mapping Implementation

**Status:** `NOT_REQUIRED / SKIPPED`

Existing accepted G01-001/G01-004 production wiring already satisfies the STD-10 mapping contract; no implementation, migration, API, or source change is required.

### STD-11 License Basic Live Acceptance (PASS)

**Status:** `STD_11_PASS`; License Basic `ACCEPTED`.

Native runtime parity passed first. Real app-only Graph reads succeeded for G01-001 users with `assignedLicenses` (HTTP 200, 4 pages, 39 users) and G01-004 subscribed SKUs (HTTP 200, 1 page, 3 SKUs), gated by `User.Read.All` and `LicenseAssignment.Read.All`. Tenant 2 readback shows 3 SKUs, 1,000,026 purchased/enabled units, 28 consumed units, 999,998 available units, and 0.0027999% weighted utilization; 39 users comprise 25 licensed and 14 unlicensed users, with 28 assignment rows and 2 users carrying multiple SKUs. Per-SKU assigned counts are AAD_PREMIUM_P2=1, POWER_BI_STANDARD=2, SPB=25.

Database checks confirm current users, current-plus-snapshot SKU persistence (3 current / 6 snapshots), zero orphan assignments, tenant-scoped joins, complete refresh semantics, and read-only consistency between calculated metrics and persisted rows. Existing accepted implementation tests provide fail-closed partial assignedLicenses preservation evidence; no mutation was performed during acceptance.

- **Evidence:** `docs/evidence/STD-11-LICENSE-BASIC-LIVE-ACCEPTANCE-001.md`.
- **Next:** `STD-12-CROSS-WORKLOAD-CORRELATION-CONTRACT-001`.

### STD-12 Cross-workload Correlation Contract (PASS)

**Status:** `STD_12_CONTRACT_PASS`; `STD12B_READY=YES`.

Defined the minimal tenant-safe User ↔ License ↔ Exchange ↔ OneDrive ↔ SharePoint correlation contract. Canonical user = `core."user".(tenant_id, source_object_id)`; license join via `core.user_license_assignment.user_id` → `core.subscribed_sku.sku_id` (STD-10); per-workload usage join via **casefolded UPN** (`core."user".user_principal_name` ↔ usage `identity_value`/`entity_key`) using the accepted Exchange `exchange_mailbox_usage` / OneDrive `onedrive_activity` / SharePoint `sharepoint_user_activity` reports (D7).

**Fail-safe status semantics (per canonical user, per workload):** `ACTIVE` = non-deleted row with non-empty `last_activity_date`; `INACTIVE` = inactivity provable from complete evidence (non-deleted row with empty `last_activity_date`, or deleted row / `deleted_date`); `UNKNOWN` = default for no workload row (absence of evidence), masked/unresolvable identity, or ambiguous evidence. Masked users are never classified INACTIVE. SharePoint site usage is tenant/site capacity evidence and NOT a user identity source.

**Verified existing wiring supports the contract:** `core."user"`, `core.user_license_assignment`, `core.subscribed_sku`, and the three user-kind usage tables already carry tenant-safe identity columns; `analytics/operations.py::OperationsAnalyticsQueryService.from_connection` already loads all of them and performs the UPN join and newest-`observed_at` filtering. **DB redesign:** NO — no migration, schema, FK, or index change.

**Smallest future read model:** one row per canonical user (user_ref, licensed, assigned_sku_count, assigned_skus, exchange/onedrive/sharepoint status + last activity) as a derived read-only analytics/API surface (future STD-13 KPI / STD-14 API). **STD-12B implementation** is bounded to a read-only analytics method + read-only API route + focused tests; no Graph, permission, KPI, optimization, or persistence change.

- **Evidence:** `docs/evidence/STD-12-CROSS-WORKLOAD-CORRELATION-CONTRACT-001.md`; implementation verified by focused analytics/API tests.
- **Result:** `STD_12B_PASS` for source implementation and offline tests; runtime parity/live readback remain required for acceptance.
- **Next:** `STD-12C-CROSS-WORKLOAD-CORRELATION-LIVE-ACCEPTANCE-001`.

### STD-12C Cross-workload Correlation live acceptance (ACCEPTED after STD-12D correction)

**Status:** `STD_12C_PASS`; correlation `ACCEPTED`.

The independent STD-12C rerun (after STD-12D corrected the bounded wiring
defect) ran the runtime-parity gate first (`scripts/check_runtime_parity.py`
PASS, all five modules MATCH) and the API is healthy (`/health` → `READY`/`READY`).

The STD-12D fix is verified in place: `OperationsAnalyticsQueryService.from_connection`
now selects `tenant_id` onto canonical user rows, while the tenant-scoped
workload guard is preserved. The live `GET /api/operations/correlation/users`
readback now matches the independent DB evidence exactly:

- **Correlation readback:** 39 canonical users; 25 licensed / 14 unlicensed;
  28 assignment rows; 2 multi-SKU users (admin=3 SKUs, william.tan=2 SKUs);
  per-SKU counts AAD_PREMIUM_P2=1 / POWER_BI_STANDARD=2 / SPB=25.
- **Workload status (live API):** Exchange 23/7/9, OneDrive 23/7/9,
  SharePoint 24/6/9 (ACTIVE/INACTIVE/UNKNOWN). An independent read-only SQL
  cross-check reproduced exactly these values from the live DB.

All 11 acceptance points pass: user coverage, license/SKU mapping, same-tenant
join, cross-tenant block (tenant guard preserved; only tenant 2 in live DB),
workload status, unknown fail-safe (9 users with zero rows per workload),
deleted semantics (deleted exchange row → INACTIVE, exercised live), masked
identity (fail-safe, none live), casefolded-UPN determinism (33 mixed-case
users / 24 mixed-case workload rows all match), multiple-SKU representation,
and DB/API consistency.

- **Evidence:** `docs/evidence/STD-12C-CROSS-WORKLOAD-CORRELATION-LIVE-ACCEPTANCE-001.md`.
- **Next:** `STD-13-STANDARD-KPI-ENGINE-CONTRACT-001`.

### STD-13 Standard KPI Engine Contract (PASS)

**Status:** `STD_13_CONTRACT_PASS`; `STD13B_READY=YES`; DB redesign required: `NO`.

The minimal V1 BASIC KPI contract is documented in `docs/evidence/STD-13-STANDARD-KPI-ENGINE-CONTRACT-001.md`. It defines tenant totals, independently keyed per-SKU inventory and assignment metrics, accepted Exchange/OneDrive/SharePoint status and capacity metrics, and simple cross-workload counts. ACTIVE/INACTIVE/UNKNOWN semantics remain fail-safe: absence, masking, ambiguity, or incomplete evidence is UNKNOWN and never silently inactive. No aggregate across unrelated SKUs, optimization, reclaim, savings, cost, AI, or advanced adoption KPI is defined.

Existing tenant-scoped analytics loaders, accepted correlation, metric envelopes, operations API conventions, and current usage/license tables support the contract without migrations or schema redesign. STD-13B is bounded to read-only analytics/API wiring and focused tests; no Graph calls/writes or dashboard work.

- **Evidence:** `docs/evidence/STD-13-STANDARD-KPI-ENGINE-CONTRACT-001.md`.

### STD-13B Standard KPI Engine focused automated validation (PASS)

**Status:** `STD_13B1_PASS`; the prior pytest availability blocker is closed using the supported `python3 -m unittest` runner.

- **Focused validation:** `python3 -m unittest tests.analytics.test_operations tests.analytics.test_operations_api -v` — 32 tests passed.
- **Coverage:** `standard_kpi_summary()`, `/api/operations/kpi`, tenant totals, per-SKU arithmetic and isolation, UNKNOWN handling, exact 1/2/3 workload counts, inactive-all complete-evidence semantics, tenant isolation, API serialization, and the existing cross-workload correlation regression.
- **Syntax validation:** `python3 -m py_compile analytics/operations.py api/operations.py tests/analytics/test_operations.py tests/analytics/test_operations_api.py` — PASS.
- **Scope:** Test validation and documentation only; no KPI semantic changes, Graph calls/writes, dependency installation, or token/credit logging.
- **Next:** `STD-13C-STANDARD-KPI-LIVE-ACCEPTANCE-001`.

### STD-13C Standard KPI Engine live acceptance (PASS)

**Status:** `STD_13C_PASS`; Standard KPI Engine `ACCEPTED`.

Bounded read-only live acceptance ran against tenant 2. Runtime parity ran first and all five required modules matched. API health and `GET /api/operations/kpi` were ready. Independent tenant-scoped database checks matched the API and accepted correlation evidence: 39 users, 25 licensed, 14 unlicensed; per-SKU inventory and assignments; Exchange 23/7/9, OneDrive 23/7/9, SharePoint 24/6/9; and cross-workload counts 22 all-three, 2 exactly-two, 0 exactly-one, 6 inactive-complete, 9 unknown-evidence. UNKNOWN remained distinct from INACTIVE, metadata was coherent, and no aggregate cross-SKU license metric was present.

- **Evidence:** `docs/evidence/STD-13C-STANDARD-KPI-LIVE-ACCEPTANCE-001.md`.
- **Scope:** Read-only acceptance; no source, collector, Graph, schema, permission, or API expansion changes.
- **Next:** `STD-14-STANDARD-API-CONTRACT-001`.

### STD-14 Standard API Contract (PASS)

**Status:** `STD_14_CONTRACT_PASS`; `IMPLEMENTATION_REQUIRED=NO`.

Inventoried the existing read-only Standard-version API (`api/operations.py`) and mapped every required Standard product function to an existing accepted route. No real implementation gap was found, so `STD-14B` is not required; the smallest authoritative Standard API contract is satisfied by existing routes.

- **Primary overview:** `GET /api/operations/kpi` (`standard_kpi_summary()`) — confirmed consumable as the dashboard's primary overview source (STD-13C live-proven). Provides tenant totals, per-SKU license inventory, Exchange/OneDrive/SharePoint status + capacity, and cross-workload counts, with `as_of`, metric envelopes, and `data_quality`.
- **Correlation / user↔SKU mapping:** `GET /api/operations/correlation/users` (`cross_workload_user_status()`).
- **Per-workload detail:** `/api/operations/adoption/exchange`, `/adoption/onedrive`, `/adoption/sharepoint`, `/adoption/sharepoint/sites`.
- **Data quality:** `/api/operations/data-quality`.

**Classification:** overview_kpi, exchange, onedrive, sharepoint_users, sharepoint_sites, correlation, license_inventory, user_license_mapping — all `READY`. `missing` and `duplicate` — none. `partial` — one documentation-only note: the `/kpi` license section is keyed by `sku_part_number` (fallback `sku_id`); the dashboard joins license inventory to correlation `assigned_skus` on `sku_part_number`. Not a redesign requirement.

**Verification:** tenant isolation (single tenant per instance, all reads `WHERE tenant_id = %s`), read-only (GET-only over persisted rows), consistent `_response`/`_metric` envelopes, explicit `UNKNOWN` vs `INACTIVE` semantics, `as_of`/`source_refresh_date`/`source_period` metadata, API/runtime ownership (`api/operations.py` + `analytics/operations.py`), and no sensitive Graph payload exposure (`user_ref` hashed; SKU identifiers only). Dashboard backend `READY=YES`.

- **Evidence:** `docs/evidence/STD-14-STANDARD-API-CONTRACT-001.md`.
- **Next:** `STD-15-STANDARD-DASHBOARD-CONTRACT-001`.

### STD-15B Standard Dashboard Implementation (PASS_WITH_BLOCKERS)

**Status:** `STD_15B_PASS_WITH_BLOCKERS`; `BACKEND_CHANGED=NO`.

Implemented the Standard read-only dashboard in `operations-ui/public/` using `/api/operations/kpi` and `/api/operations/correlation/users`. Added overview, per-SKU license table, workload panels, cross-workload counts, and opaque user correlation table while preserving loading/error handling, explicit UNKNOWN/INACTIVE states, unavailable values, and responsive overflow.

- **Files changed:** `operations-ui/public/index.html`, `operations-ui/public/app.js`, `operations-ui/public/styles.css`, this progress record, activity log, and implementation evidence.
- **Validation:** Static syntax check completed; runtime rebuild/page/API/parity validation remains blocked pending available Docker/runtime access.
- **Next:** `STD-15C-STANDARD-DASHBOARD-LIVE-ACCEPTANCE-001`.

### STD-15C Standard Dashboard Live Acceptance (PASS)

**Status:** `STD_15C_PASS`; dashboard accepted.

The deployed dashboard passed ephemeral Playwright + Chromium validation on the UI Docker network at desktop and narrow viewports. Page status was 200, JavaScript completed with no console/page/request errors, KPI and correlation APIs returned 200, and the required DOM counts and responsive table overflow were observed. The prior timeout was classified as `TEST_HARNESS_DEFECT` and corrected without changing dashboard source.

- **Evidence:** `docs/evidence/STD-15C-STANDARD-DASHBOARD-LIVE-ACCEPTANCE-001.md`.
- **Files changed:** evidence, this progress record, and activity log.
- **Blocker:** none.
- **Next:** `STD-16-EXCHANGE-BASIC-SCENARIO-CONTRACT-001`; STD-16 not started automatically.

### STD-15 Standard Dashboard Contract (PASS)

**Status:** `STD_15_CONTRACT_PASS`; `IMPLEMENTATION_READY=YES`; `BACKEND_CHANGE_REQUIRED=NO`.

Defined the smallest management-facing Standard dashboard using the existing `operations-ui/` shell, cards, panels, status badges, loading/error states, and responsive grids. `/api/operations/kpi` is the sole aggregate source for overview, per-SKU licenses, workload metrics, and cross-workload counts; `/api/operations/correlation/users` supplies the user detail table and SKU mapping. Existing adoption routes are optional detail sources and `/api/operations/data-quality` supplies limitations/dependency detail. No charts, recommendations, optimization, new endpoints, Graph calls, writes, or backend changes are included. UNKNOWN remains visibly distinct from INACTIVE, and cross-SKU license totals are not defined.

- **Evidence:** `docs/evidence/STD-15-STANDARD-DASHBOARD-CONTRACT-001.md`.
- **Files changed:** evidence, progress, activity log, and `docs/PROJECT_FILE_MAP.md` (durable UI path ownership recorded).
- **Blockers:** none.
- **Next:** `STD-15B-STANDARD-DASHBOARD-IMPLEMENTATION-001`.

### STD-08 SharePoint Basic live acceptance rerun (PASS)

The independent bounded native rerun completed after the STD-08A site identity correction. Runtime parity ran first and passed. With `Reports.Read.All`, USAGE-006 returned 30 rows and USAGE-007 returned 12 rows; both normalized and persisted successfully. Without the permission, both endpoints returned `SKIP_PERMISSION_REQUIRED` with zero rows and no Graph or persistence activity.

The canonical Site Id produced 12 distinct site `entity_key` values despite blank Site URLs. Identity-less rows still fail closed as `ENTITY_IDENTITY_UNAVAILABLE`. API and DB agree for tenant 2: active_users 24, active_sites 3, latest_activity 2026-06-26, total_storage_used 36964667, total_file_count 43, storage_utilization 1.1206389596433534e-07. Active status is grounded only in non-deleted rows with non-empty `last_activity_date`; viewed/synced/page-view thresholds are not used.

- **Evidence:** `docs/evidence/STD-08-SHAREPOINT-BASIC-LIVE-ACCEPTANCE-001.md`.
- **Status:** `STD_08_PASS`; SharePoint Basic `ACCEPTED`.
- **Next:** `STD-09-LICENSE-INVENTORY-BASELINE-001`.

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

## Integration-First Engineering Baseline

**Status:** SEALED - OFFLINE PASS

- Canonical baseline: `docs/engineering-baseline.md`. Future production feature
  tasks require its Phase 0 production wiring preflight before implementation
  or live execution.
- Registry-driven architecture invariants now validate each registered Security
  execution against the capability vocabulary, declared Graph permissions,
  canonical inventory, app-only/read-only boundary, collector factory,
  deterministic evaluator, and orchestrator resolution. Inventory endpoint
  types retain their workload-registry obligations.
- Offline Dockerfile parity verifies Collector image package copies, including
  `collectors`, `capabilities`, and `security`. Existing persistence contracts
  validate closed runtime error vocabulary and psycopg JSONB adaptation.
- Representative production-path integration uses a fake Microsoft Graph
  boundary with real capability gate, Security orchestrator, collector,
  normalizer, evaluator, and Security persistence transaction contract.
  No PostgreSQL-backed test fixture exists; database server/API read-path
  confirmation remains a bounded live or controlled-environment concern.

## CH8 Security Findings Foundation

**Status:** PASS

- Built the deterministic Security Findings foundation for the Microsoft 365 Security & Operational Intelligence product (foundation only).
- Added domain contracts in `security/models.py`: `SecurityRule`, `SecurityBaseline`, `SecurityObservation`, `SecurityFinding`, `EvidenceReference`, `Recommendation`, and the `SecurityFindingService` contract, with `PASS`/`OPEN`/`NOT_EVALUATED` status and `INFO`/`LOW`/`MEDIUM`/`HIGH`/`CRITICAL` severity.
- Enforced fail-safe semantics (`NO_EVIDENCE != SECURITY_GAP`); missing/ambiguous/unsupported/malformed evidence is `NOT_EVALUATED`, never `OPEN`.
- Defined the product baseline `m365-security-recommended-v1` (version `1.0.0`) with `formal_compliance_claim = False` (no CIS/NIST/Secure Score/regulatory claim).
- Implemented first rule `M365-SP-EXT-001` (SharePoint / OneDrive External Sharing) with explicit ordered canonical levels and deterministic status/severity/recommendation; the recommendation advises but never executes remediation.
- Added `DeterministicSecurityFindingService` resolving baseline/rule, validating dependency, and performing a deterministic comparison with stable finding ids and no AI/network dependency.
- Added 26 targeted tests in `tests/security/test_security_findings.py` covering the CH8 contract matrix. Full offline regression passed 684 tests; `compileall` succeeded.
- `Graph_reads=0`, `Graph_writes=0`, `DB_writes=0`, `DB_schema_changed=NO`, `Entra_changed=NO`, `Scenario_changed=NO`, `Intune_touched=NO`.

## CH8 License-Aware Security Production Pipeline Seal

**Status:** SEALED - PASS

- Closed the capability-aware Security production contract: customer entitlement
  selects the supported feature subset, and `NOT_ENTITLED` skips without Graph
  reads, evaluation, or a false finding while retaining distinct `UNKNOWN`,
  `PERMISSION_REQUIRED`, and `SOURCE_UNAVAILABLE` states.
- Recorded the app-only Security boundary, generic Security orchestration,
  Scenario Agent authentication separation, Collector lifecycle versus Security
  persistence failure domains, deterministic findings, and absence of Graph
  writes/remediation.
- Recorded live Rule #7 evidence: G01-011 HTTP 200, one page; 3 Conditional Access
  policies (0 enabled, 2 report-only, 1 disabled); `OPEN` / `MEDIUM`, presence-only
  scope. Persisted seven-rule snapshot remains available through the read-only API.
- Evidence: `docs/security-production-orchestration.md` and
  `docs/evidence/CH8-SECURITY-FINDINGS-FOUNDATION-001.md`.
- Read-only validation: API/database health `200`, Security summary/findings `200`,
  seven persisted evaluations. No Graph call, DB write, schema, Entra, Scenario,
  Intune, or runtime change. Accepted baseline remains 684 PASS.

## CH-2.5 Foundation Security Review

**Status:** PASS WITH LIMITATIONS / DOCUMENTED OFFLINE REVIEW

- Created `docs/evidence/CH-2.5-FOUNDATION-SECURITY-REVIEW.md` covering authentication, tenant binding and cross-tenant rejection, the requested Graph permissions, approved projections, sensitive-data exclusion, raw payload exclusion, evidence boundaries, parameter-bound SQL, closed mappings, replay protection, and transaction rollback for G01-002 through G01-012.
- Confirmed the documented tenant identity source is trusted runtime lineage and that missing, malformed, or mismatched tenant values fail closed before SQL/writer execution.
- Preserved the G01-003 observed permission anomaly and the four open registry retention drifts; neither was silently corrected by this review.
- Accepted the security posture as `PASS WITH LIMITATIONS` because validation was offline only. No live Graph execution, live PostgreSQL execution, or production tenant testing occurred.
- Documentation-only change. `collectors/`, adapters, registry runtime, persistence runtime, and database migrations were not modified.

## CH-2.4 Collector Operational Hardening

**Status:** DOCUMENTED / PLANNED

- Created `docs/evidence/CH-2.4-COLLECTOR-OPERATIONAL-HARDENING.md` as the consolidated operational hardening design for G01-002 through G01-012.
- Defined accepted versus rejected records and bounded `DATA_VALIDATION`, `SECURITY_VALIDATION`, and `SYSTEM` rejection categories.
- Defined retryable throttling, temporary Graph failure, network issue, and temporary database issue conditions, plus permanent permission, tenant mismatch, schema, and invalid-data conditions.
- Defined redacted operational evidence fields for execution, endpoint, timestamp, failure classification/reason, attempts, final status, and recommended action.
- Documented future agentic failure explanation, trend analysis, and recovery recommendation capabilities, with possible metrics table, dashboard, alerting, and recovery workflow scope.
- TD-005 Rejection Metrics and Tracing and TD-006 Retry Recovery Hardening are now consolidated under the CH-2.4 design; implementation remains separately approved future work.
- Documentation-only change. Collectors, adapters, registry runtime, persistence runtime, and database migrations were not modified.

## CH-2.3 Controlled Validation Environment

**Status:** DOCUMENTED / PLANNED

- Created `docs/evidence/CH-2.3-CONTROLLED-VALIDATION-ENVIRONMENT-PLAN.md` to define the controlled validation boundary between offline tests and production.
- Separated Development, Controlled Validation, and Production environments with dedicated identity, data, database, access, and evidence boundaries.
- Coordinated representative Microsoft Graph validation for G01-005 Directory Audit, G01-006 Sign-ins, G01-009 Devices, G01-011 Conditional Access, and G01-012 Named Locations, covering authentication, permissions, payload schema, field types, pagination, and adapter mapping.
- Coordinated PostgreSQL validation for `core.audit_event`, `core.application`, `core.device`, `core.named_location`, and `core.conditional_access_policy` plus its approved snapshot behavior, covering schema, constraints, replay, rollback, and transaction behavior.
- Defined bounded evidence containing validation ID, timestamp, endpoint/target, permission, record count, and result while excluding tokens, secrets, credentials, and raw sensitive payloads.
- Defined PASS gating for live API contract match, database persistence validation, and captured evidence; live execution remains planned and requires controlled environments.
- Documented how the plan can become a future Scenario Validation Agent. No production code, collectors, adapters, registry runtime, persistence runtime, or database migrations were modified.

## CH-2.2 Registry Catalog Consistency Validation

**Status:** GOVERNANCE VALIDATION - PASS WITH DOCUMENTED DRIFT

- Reviewed all 19 G01 registry entries against `docs/data-catalog.md`, `docs/database-schema-design.md`, and `database/migrations/`.
- Confirmed endpoint identity, Graph path references, owner/workload classification, adapter mapping, persistence semantics, database targets, and sensitivity classifications across the reviewed sources.
- Confirmed five retention drifts: G01-004 is registry `REFERENCE` versus catalog/schema/migration `STANDARD`; G01-005, G01-006, G01-013, and G01-014 are registry `HIGH_SENSITIVITY` versus catalog/schema/migration `LONG`. `HIGH_SENSITIVITY` remains sensitivity for the latter four.
- Classified collection-pattern versus registry-mode vocabulary, current/history implementation mapping, and shared `core.audit_event` storage as intentional differences.
- Production code, collectors, adapters, registry runtime, persistence runtime, and database migrations were not modified.
- Evidence: `docs/evidence/CH-2.2-REGISTRY-CATALOG-CONSISTENCY-REPORT.md`.

## Foundation Acceptance Review

**Status:** DOCUMENTED

- Created `docs/evidence/FOUNDATION-ACCEPTANCE-REVIEW-G01-002-G01-012.md` covering the completed G01-002 through G01-012 workload range.
- Documented the workload coverage matrix, frozen Graph Collector -> Adapter -> Registry -> Persistence Dispatcher -> Security Boundary -> Writer -> Database architecture, security controls, and EVENT/CURRENT/CURRENT_WITH_SNAPSHOT persistence behavior.
- Recorded focused offline validation, migration regression evidence, and the three unrelated live scenario authentication/network limitations.
- Referenced TD-001 through TD-006 and FB-001 through FB-005 without changing runtime implementation, collectors, adapters, registry behavior, persistence runtime, or database migrations.
- Foundation result: PASS - DOCUMENTED OFFLINE ACCEPTANCE.


## TD-006 Retry Recovery Hardening Plan

**Status:** DOCUMENTED / PLANNED

- Created `docs/evidence/TD-006-RETRY-RECOVERY-HARDENING-PLAN.md` to improve operational resilience and recovery visibility for the G01-002 through G01-012 workloads.
- Classified HTTP throttling, temporary Graph availability issues, transient network failures, and temporary database connection issues as retryable; invalid permission, tenant mismatch, malformed data, and schema violation as permanent.
- Defined a bounded baseline of 3 retries after the initial attempt, exponential backoff with jitter, timeout and total-budget handling, failure escalation, and redacted recovery evidence fields.
- Documented how a future operations agent can answer why collection failed, whether retry was attempted, and whether manual intervention is required.
- Identified possible future retry metrics, failure dashboard, alert integration, and recovery workflow. These were not implemented.
- Production code, collectors, adapters, registry, persistence runtime, and database migrations were not modified.

## TD-005 Rejection Metrics and Tracing Plan

**Status:** DOCUMENTED / PLANNED

- Created `docs/evidence/TD-005-REJECTION-METRICS-TRACING-PLAN.md` to improve visibility into rejected records from G01-002 through G01-012 without exposing sensitive data or weakening fail-closed validation.
- Defined bounded `DATA_VALIDATION`, `SECURITY_VALIDATION`, and `SYSTEM` categories with controlled rejection reasons, required redacted evidence fields, and bounded metric dimensions.
- Documented future agentic analytics for rejection causes, trends, and endpoint quality, while distinguishing record rejection from batch rollback and system failure.
- Possible future implementation scope includes a retention-controlled rejection table, metrics dashboard, and alerting. These were not implemented.
- Production code, collectors, adapters, persistence runtime, and database migrations were not modified.

## TD-004 Live PostgreSQL Validation Plan

**Status:** DOCUMENTED / PLANNED

- Created `docs/evidence/TD-004-LIVE-POSTGRESQL-VALIDATION-PLAN.md` to validate real PostgreSQL behavior against persistence assumptions for representative `CURRENT`, `CURRENT_WITH_SNAPSHOT`, and `EVENT` tables.
- The plan covers connectivity, schema and table existence, closed column mapping, constraints, commit/rollback, replay, tenant boundaries, parameter-bound SQL, and raw-payload exclusion.
- Expected evidence is limited to timestamp, PostgreSQL version, validation outcomes, scenario classifications, redacted metadata, and synthetic identifiers; credentials, connection strings, secrets, and raw payloads are prohibited.
- Production code, collectors, adapters, registry, persistence runtime, and database migrations were not modified.
- Live execution remains planned and requires a controlled PostgreSQL environment; this plan does not replace offline tests.

## TD-003 Live Microsoft Graph Validation Plan

**Status:** DOCUMENTED / PLANNED

- Created `docs/evidence/TD-003-LIVE-GRAPH-VALIDATION-PLAN.md` to validate real tenant behavior for G01-004, G01-005, G01-006, G01-009, G01-011, and G01-012 against the approved offline projections.
- The plan covers application authentication, endpoint execution, response metadata, field types, nullable behavior, pagination, and adapter mapping.
- Evidence requirements prohibit storing credentials, tokens, secrets, or raw sensitive Graph payloads.
- Production code, collectors, adapters, registry, persistence, and database migrations were not modified.

## TD-001 Registry-Catalog Reconciliation

**Status:** GOVERNANCE VALIDATION - PASS WITH DOCUMENTED DRIFT

- Reviewed all 19 G01 registry entries against `docs/data-catalog.md`, `docs/database-schema-design.md`, and `database/migrations/`.
- Endpoint identity, persistence mapping, and target tables reconcile across the sources. G01-011 Conditional Access and G01-012 Named Locations are aligned on owner, adapter, mode, targets, and `REFERENCE` retention.
- Confirmed four registry retention drifts: G01-005, G01-006, G01-013, and G01-014 use `HIGH_SENSITIVITY` in the registry where the catalog/schema retention contract requires `LONG`; G01-019 is aligned to `LONG`.
- Classified the collection-pattern versus registry-mode naming differences and shared audit-event table as intentional differences. No independent owner/adapter documentation inconsistency was found.
- Production code, collectors, adapters, persistence runtime, and migrations were not modified.
- Evidence: `docs/evidence/TD-001-REGISTRY-CATALOG-RECONCILIATION.md`.

## CH-2.1 Data Classification Governance

**Status:** COMPLETED / DECISION DOCUMENTED

- Determined that `HIGH_SENSITIVITY` and `LONG` are different governance dimensions: sensitivity classification and retention duration.
- Confirmed the authoritative interpretation for G01-005, G01-006, G01-013, and G01-014 is `sensitivity=HIGH_SENSITIVITY` with `retention_class=LONG`.
- Recorded the four registry values as metadata drift requiring a separately approved implementation correction; no runtime or metadata value was changed in this review.
- Reviewed the registry, catalog, schema design, and migrations for documentation consistency.
- Production code, collectors, adapters, registry runtime, persistence runtime, and database migrations were not modified.
- Evidence: `docs/evidence/CH-2.1-DATA-CLASSIFICATION-GOVERNANCE-DECISION.md`.

## Technical Debt and Future Validation Foundation

**Status:** DOCUMENTED

- Technical debt register created in `docs/TECHNICAL_DEBT.md`.
- Future validation backlog created in `docs/FUTURE_VALIDATION_BACKLOG.md`.
- No production code changed.

## G01-012 Named Locations CURRENT Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/identity/conditionalAccess/namedLocations` endpoint with application authentication, `Policy.Read.All`, `$top=100`, pagination, and approved fields `id`, `displayName`, `createdDateTime`, and `modifiedDateTime`.
- Reused `collectors/workloads/security_service/adapters.py`; normalization emits current-state rows only and excludes IP ranges, countries and regions, unknown fields, credentials, tokens, authorization material, and raw Graph payload.
- Verified registry `G01-012` uses `CURRENT`, owner `security_service`, adapter `security_service.named_locations`, target `core.named_location`, and retention reconciled from `STANDARD` to `REFERENCE`.
- Reused the existing persistence dispatcher, security boundary, parameter-bound current writer, SQL mapping, and transactional `CollectionWriter`. Conflict is `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE`; tenant validation and rollback remain active.
- Focused validation passed 220 tests, including normalization, field exclusion, missing IDs, malformed records/pages, pagination, empty results, registry mapping, parameter-bound SQL, replay, tenant boundary, and rollback.
- Evidence: `docs/evidence/G01-012-NAMED-LOCATIONS-IMPLEMENT.md`.

## G01-011 Conditional Access Policies CURRENT_WITH_SNAPSHOT Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/identity/conditionalAccess/policies` endpoint with application authentication, `Policy.Read.All`, approved metadata-only projection (`id`, `displayName`, `state`, `createdDateTime`, `modifiedDateTime`), `$top=100`, and `@odata.nextLink` pagination.
- Reused `collectors/workloads/security_service/adapters.py`; it emits current and per-run snapshot rows and excludes conditions, grant controls, session controls, unknown fields, credentials, tokens, and authorization material.
- Verified registry `G01-011` uses `CURRENT_WITH_SNAPSHOT`, owner `security_service`, adapter `security_service.conditional_access_policies`, current target `core.conditional_access_policy`, snapshot target `core.conditional_access_policy_snapshot`, and retention `REFERENCE`.
- Reused the existing paginator, dispatcher, security boundary, parameter-bound `write_snapshot_record`, and transactional `CollectionWriter`. Current conflict is `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE`; snapshot conflict is `(tenant_id, source_object_id, collection_run_id)` with `ON CONFLICT DO NOTHING`.
- Verified trusted runtime tenant lineage cannot be overridden by policy payload data, malformed pages fail before persistence, and transaction rollback remains active.
- Focused validation passed 213 tests, including normalization, field exclusion, malformed records, pagination, empty results, malformed next links, registry mapping, current/snapshot SQL, replay, tenant boundary, and rollback.
- Retention decision recorded: `STANDARD -> REFERENCE`, aligned with the authoritative catalog/schema contract.
- Evidence: `docs/evidence/G01-011-CONDITIONAL-ACCESS-IMPLEMENT.md`.

## G01-010 Administrative Units CURRENT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/directory/administrativeUnits` flow with application authentication, `AdministrativeUnit.Read.All`, the approved four-field `$select`, and `@odata.nextLink` pagination.
- Reused `collectors/workloads/directory/administrative_units.py`; normalization retains only `id`, `displayName`, `description`, and `visibility`, mapped to `source_object_id`, `display_name`, `description`, and `visibility`, plus trusted lineage and retention metadata.
- Verified missing IDs and malformed records fail closed, optional fields remain nullable, unknown properties and credential/token/authorization material are excluded.
- Verified registry `G01-010` uses `CURRENT`, owner `directory`, adapter `directory.administrative_units`, target `core.administrative_unit`, and retention `REFERENCE`.
- Reused the existing persistence dispatcher, security boundary, parameter-bound current writer, and one-transaction `CollectionWriter`. Conflict is `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE`; tenant mismatch and rollback protections remain active.
- Added focused normalization, field-boundary, pagination, empty-result, malformed-page and malformed-nextLink no-partial-write coverage. Existing registry, SQL upsert/replay, tenant-boundary, and rollback coverage was verified.
- Evidence: `docs/evidence/G01-010-ADMINISTRATIVE-UNITS-IMPLEMENT.md`.

## G01-009 Devices CURRENT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/devices` flow with application authentication, `Device.Read.All`, the approved seven-field `$select`, and `@odata.nextLink` pagination.
- Reused `collectors/workloads/directory/devices.py`; normalization retains only `id`, `deviceId`, `accountEnabled`, `operatingSystem`, `operatingSystemVersion`, `trustType`, and `approximateLastSignInDateTime`, mapped to the approved device columns plus trusted lineage and retention metadata.
- Verified missing IDs and malformed records fail closed, optional fields remain nullable, unknown properties and credential, token, and authorization material are excluded.
- Verified registry `G01-009` uses `CURRENT`, owner `directory`, adapter `directory.devices`, target `core.device`, and retention `REFERENCE`.
- Reused the existing persistence dispatcher, security boundary, parameter-bound current writer, and one-transaction `CollectionWriter`. Conflict is `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE`; tenant mismatch and rollback protections remain active.
- Added focused pagination, empty-result, malformed-page no-partial-write, normalization, registry, upsert, replay, tenant-boundary, and rollback coverage. The focused suite passed 260 tests.
- Evidence: `docs/evidence/G01-009-DEVICES-IMPLEMENT.md`.

## G01-008 Service Principals CURRENT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/servicePrincipals` flow with application authentication, `Application.Read.All`, the approved five-field `$select`, and `@odata.nextLink` pagination.
- Reused `collectors/workloads/directory/service_principals.py`; normalization retains only `id`, `appId`, `displayName`, `accountEnabled`, and `servicePrincipalType`, mapped to the approved service-principal columns plus trusted lineage and retention metadata.
- Verified missing IDs and malformed records fail closed, optional fields remain nullable, and key, password, assignment, permission, token, secret, and authorization material is excluded.
- Verified registry `G01-008` uses `CURRENT`, owner `directory`, adapter `directory.service_principals`, and target `core.service_principal`.
- Reused the existing persistence dispatcher, security boundary, parameter-bound current writer, and one-transaction flow. Conflict is `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE`; tenant mismatch and rollback protections remain active.
- Added focused pagination, empty-result, malformed-page no-partial-write, normalization, registry, upsert, replay, tenant-boundary, and rollback coverage. The focused suite passed 256 tests.
- Evidence: `docs/evidence/G01-008-SERVICE-PRINCIPALS-IMPLEMENT.md`.

## G01-007 Applications CURRENT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/applications` flow with application authentication, `Application.Read.All`, the approved five-field `$select`, and `@odata.nextLink` pagination.
- Reused `collectors/workloads/directory/applications.py`; normalization retains only `id`, `appId`, `displayName`, `createdDateTime`, and `signInAudience`, mapped to the approved application columns plus trusted lineage and retention metadata.
- Verified missing IDs and malformed records fail closed, optional fields remain nullable, unknown fields are excluded, and credential/key/authorization material is never copied.
- Verified registry `G01-007` uses `CURRENT`, owner `directory`, adapter `directory.applications`, target `core.application`, and retention `REFERENCE`.
- Reused the existing persistence dispatcher, security boundary, parameter-bound current writer, and one-transaction flow. Conflict is `(tenant_id, source_object_id)` with `ON CONFLICT DO UPDATE`; tenant mismatch and rollback protections remain active.
- Added focused pagination, empty-result, malformed-page no-partial-write, normalization, registry, upsert, replay, tenant-boundary, and rollback coverage. The focused suite passed 250 tests.
- Evidence: `docs/evidence/G01-007-APPLICATIONS-IMPLEMENT.md`.

## G01-006 Sign-In Logs EVENT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/auditLogs/signIns` flow with application authentication, `AuditLog.Read.All`, the approved seven-field `$select`, and `@odata.nextLink` pagination.
- Reused `collectors/workloads/security_service/adapters.py`; normalization retains only the approved sign-in fields, forces `SIGN_IN`, rejects missing IDs and malformed records, maps nested status values, and excludes IP, location, user-agent, correlation, credential, token, and unknown data.
- Verified registry `G01-006` uses `EVENT`, owner `security_service`, event target `core.audit_event`, and event source `SIGN_IN`.
- Reused the existing dispatcher, security boundary, parameter-bound event writer, and one-transaction `CollectionWriter`. Conflict is `(tenant_id, event_source, source_object_id)` with `ON CONFLICT DO NOTHING`; no new writer, migration, or dispatcher redesign was added.
- Verified pagination, empty results, malformed pages, missing IDs, event-source spoofing, duplicate replay, tenant-boundary validation, rollback, and credential exclusion. Failed pages do not reach normalization or persistence, so partial batches are not written.
- Focused validation passed 256 tests.
- Evidence: `docs/evidence/G01-006-SIGN-IN-IMPLEMENT.md`.

## G01-005 Directory Audit EVENT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/auditLogs/directoryAudits` flow with application authentication, `AuditLog.Read.All`, the approved six-field `$select`, and `@odata.nextLink` pagination.
- Reused `collectors/workloads/security_service/adapters.py`; normalization retains only `id`, `activityDateTime`, `activityDisplayName`, `category`, `result`, and `loggedByService`, forces `DIRECTORY_AUDIT`, rejects missing IDs/malformed records, and excludes unknown or credential material.
- Verified registry `G01-005` uses `EVENT`, owner `security_service`, event target `core.audit_event`, and event source `DIRECTORY_AUDIT`.
- Reused the existing dispatcher, security boundary, parameter-bound event writer, and one-transaction `CollectionWriter`. Conflict is `(tenant_id, event_source, source_object_id)` with `ON CONFLICT DO NOTHING`; no new writer, migration, or dispatcher redesign was added.
- Hardened the shared paginator to reject missing/non-list `value` and malformed `@odata.nextLink` responses instead of treating them as successful empty pages. Page failures remain collection failures, so no normalized batch is persisted.
- Focused coverage passed for pagination, empty results, malformed responses, missing IDs, unknown-field and credential exclusion, event-source spoofing, duplicate replay, tenant mismatch, parameter-bound SQL, and rollback.
- Retention metadata remains the existing registry value `HIGH_SENSITIVITY`; no discrepancy was silently changed.
- Evidence: `docs/evidence/G01-005-DIRECTORY-AUDIT-IMPLEMENT.md`.

## G01-004 Subscribed SKUs CURRENT_WITH_SNAPSHOT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/subscribedSkus` flow with application authentication, `LicenseAssignment.Read.All`, approved `$select` fields, and paginator-based collection.
- Verified `collectors/workloads/directory/subscribed_skus.py` retains only `id`, `skuId`, `skuPartNumber`, `capabilityStatus`, `consumedUnits`, `prepaidUnits`, and `servicePlans`, plus trusted lineage and retention metadata. Missing IDs, malformed objects, unknown fields, and credential material fail closed or are excluded.
- Verified `prepaidUnits.enabled + suspended + warning` is transformed into the approved scalar integer representation.
- Verified registry `G01-004` uses `CURRENT_WITH_SNAPSHOT`, current target `core.subscribed_sku`, snapshot target `core.subscribed_sku_snapshot`, and the directory adapter.
- Reused the existing persistence dispatcher, security boundary, snapshot writer, and one-transaction current-plus-snapshot flow. Current conflict is `(tenant_id, source_object_id)`; snapshot conflict is `(tenant_id, source_object_id, collection_run_id)`. No writer, migration, or dispatcher change was required.
- Focused and regression suites passed, including pagination, empty response, malformed response, missing ID, optional fields, prepaid-unit variations, unknown-field and credential exclusion, registry mapping, current/snapshot writes, replay behavior, tenant boundary, and rollback.
- Evidence: `docs/evidence/G01-004-SUBSCRIBED-SKUS-IMPLEMENT.md`.

## G01-003 Organization CURRENT Endpoint Implementation

**Status:** IMPLEMENTED - PASS

- Verified the inventory-driven `GET /v1.0/organization` flow with the documented `Organization.Read.All` permission, non-paginated single-object contract, and existing Graph collector runtime.
- Verified `collectors/workloads/directory/organization.py` normalizes only `id`, `displayName`, `verifiedDomains`, `countryLetterCode`, and `tenantType`, plus trusted lineage; malformed objects and missing `id` fail closed.
- Verified registry `G01-003` uses `CURRENT`, owner `directory`, adapter `directory.organization`, and target `core.organization`.
- Reused the existing current persistence dispatcher/writer. The tenant conflict key is `(tenant_id)` and replay updates the existing tenant row; no writer or migration was added.
- Focused and regression suites passed, including single-object handoff, optional-field handling, unknown-field and credential exclusion, registry validation, tenant boundary, and idempotency.
- Evidence: `docs/evidence/G01-003-ORGANIZATION-IMPLEMENT.md`.

## G01-002-FIX2 Runtime Persistence Wiring

**Status:** IMPLEMENTED - PASS

- Production CLI execution now creates the existing PostgreSQL DB-API connection at the edge and injects both `database_connection` and the canonical `CollectionWriter` into `CollectorRuntime`.
- `CollectionWriter` continues to route through `dispatch_persistence`, the security boundary, existing mode-specific writers, and one transaction; no SQL or persistence design was changed.
- Dry-run remains offline and does not create a database connection.
- Evidence: `docs/evidence/G01-002-FIX2-RUNTIME-PERSISTENCE-WIRING.md`.

## G01-002-FIX1 Runtime Tenant Wiring

**Status:** IMPLEMENTED — PASS

- Fixed the production CLI construction path so `RuntimeOptions` receives a trusted tenant resolver.
- The resolver accepts only the internal positive `core.tenant.tenant_id` surrogate from protected `GRAPH_TENANT_DB_ID` runtime configuration; it does not accept a caller tenant argument or derive identity from Graph data.
- Existing runtime fail-closed behavior, lineage mismatch validation, collection flow, dry-run behavior, dispatcher, and persistence writers remain unchanged.
- Focused evidence: `docs/evidence/G01-002-FIX1-RUNTIME-TENANT-WIRING.md`.

## G01-002 Groups CURRENT Endpoint Implementation

**Status:** IMPLEMENTED — PASS

- Graph collection reuses the inventory-driven `BaseCollector`, existing authentication, retry, and paginator flow for `/v1.0/groups`.
- Groups normalization and `CURRENT` registry dispatch target `core."group"`; the existing current writer and security boundary were unchanged.
- Focused adapter, dispatch, pagination, empty-result, invalid-payload, idempotency, tenant-boundary, and credential-exclusion coverage passed.
- Evidence: `docs/evidence/G01-002-GROUPS-IMPLEMENT.md`

## G01-002 Groups CURRENT Endpoint Design

**Status:** DESIGN COMPLETE — PASS

- Design evidence: `docs/evidence/G01-002-GROUPS-DESIGN.md`
- Scope: Graph `/v1.0/groups` with `Group.Read.All`, paginated collection, directory normalization, registry `CURRENT` dispatch, and idempotent upsert to `core."group"`.
- Production code: Not modified.
- Blockers: None for design; implementation requires focused runtime, adapter, registry, persistence, and failure-path tests.

## G10 Foundation Acceptance

**Status:** ACCEPTED

### Completed Milestones

- G10-001A — User runtime wiring
- G10-001B1 — Tenant binding hardening
- G10-001B2 — Persistence dispatcher
- G10-001B2-FIX1 — Event source enforcement
- G10-001B2-FIX2 — Tenant boundary validation
- G10-001B2-FIX3 — Persistence security boundary

### Accepted Capabilities

- Graph runtime flow
- Trusted tenant handling
- Generic persistence dispatch
- Security validation boundary
- Event validation
- Documentation governance

### Remaining Technical Debt

- Registry and SQL mapping duplication
- No live PostgreSQL integration suite
- Rejection metrics and tracing
- Retry recovery hardening

### Architecture Freeze

Future endpoints should reuse the established flow:

```text
Graph Collector
    |
    v
Adapter
    |
    v
Registry
    |
    v
Persistence Dispatcher
    |
    v
Security Boundary
    |
    v
Writer
    |
    v
Database
```


## G10-001B2-FIX3 Persistence Boundary Hardening

**Status:** Complete

### Security Improvement

All database write APIs now validate populated record tenant IDs before SQL execution. `CollectionWriter` additionally establishes the trusted collection tenant and validates endpoint and registry persistence-mode agreement for every record before `BEGIN`, including when an injected writer is used. Dispatcher batches complete endpoint/mode validation before invoking any SQL handler, preventing partial writes on a later invalid record.

### Write Paths Reviewed

- `CollectionWriter.write` is the transactional trusted-context boundary.
- `dispatch_persistence` is the registry-controlled batch dispatcher.
- `write_current_record`, `write_reference_record`, `write_event_record`, `write_snapshot_record`, and `write_history_record` are low-level SQL handlers protected by row tenant validation, closed endpoint maps, mode checks, required-column checks, and event-source validation where applicable.
- `BoundSqlExecutor.execute` remains the parameter-binding-only execution primitive.

### Test Evidence

Focused persistence tests verify valid `CollectionWriter` flow, dispatcher endpoint/tenant mismatch rejection without SQL, direct low-level malformed-tenant rejection without SQL, preserved event-source checks, and no transaction/commit/rollback activity for pre-transaction validation failures.

### Files Changed

- `collectors/persistence/core.py`
- `tests/persistence/test_core.py`
- `docs/PROJECT_PROGRESS.md`
- `docs/CHANGELOG.md`
- `docs/ARCHITECTURE.md`
- `docs/AI_USAGE_LOG.md`
- `docs/evidence/G10-001B2-FIX3-persistence-boundary.md`

## G10-001B2-FIX2 Tenant Boundary Hardening

**Status:** Complete

### Security Improvement

`CollectionWriter` now validates the trusted runtime `tenant_id` and every populated normalized record row before transaction start or SQL execution. Missing, malformed, and cross-tenant rows are rejected without invoking the writer, issuing `BEGIN`, or creating partial writes.

### Files Changed

- `collectors/persistence/core.py`
- `tests/persistence/test_core.py`
- `docs/PROJECT_PROGRESS.md`
- `docs/CHANGELOG.md`
- `docs/evidence/G10-001B2-FIX2-tenant-boundary.md`

### Test Evidence

Focused persistence unit tests cover matching tenant acceptance, missing record tenant rejection, mismatched tenant rejection, trusted tenant validation, and writer/SQL non-invocation after rejection.

### Remaining Technical Debt

The persistence boundary remains DB-API-like and offline-testable; live PostgreSQL integration coverage and operational rejection metrics remain outstanding.

## G10-001B2 Terra Review Status

**Implementation:** PASS

**Security:** PASS after tenant boundary and event control fixes.

**Architecture review:** Accepted with technical debt.

### Technical Debt

- duplicated endpoint metadata
- persistence mapping duplication
- future registry contract improvement

## G10-001B2 Persistence Dispatcher and Event Control

**Status:** Complete
**Milestone:** G10-001B2 Persistence Dispatcher
**Fix:** G10-001B2-FIX1 Event Control

### Objective

Provide one deterministic persistence dispatch boundary for normalized G01 workload records. The dispatcher selects the writer from the canonical workload registry, validates endpoint and persistence-mode alignment, and routes current, reference, event, snapshot, and history records without allowing records to select arbitrary database identifiers.

G10-001B2-FIX1 specifically prevents non-event workloads from entering the event writer and enforces the registered event-source discriminator for shared audit-event storage.

### Architecture Changes

- `collectors.workloads.models` defines the closed five-value `PersistenceMode` vocabulary and the immutable normalized-record envelope.
- `collectors.workloads.registry` remains the authoritative endpoint-to-mode, table, owner, adapter, retention, and event-source mapping for G01-001 through G01-019.
- `collectors.persistence.core.dispatch_persistence` resolves the registered mode and selects exactly one mode-specific writer per endpoint batch.
- Mode-specific writers use closed, code-owned endpoint/table/column maps; normalized rows provide values only.
- Current and reference records use deterministic upserts; event, snapshot, and history records use conflict-safe append semantics where applicable.
- `CollectionWriter` preserves one-transaction behavior and rolls back on writer or validation failure.
- Event control rejects unsupported event endpoints, requires an event row, validates required columns, and verifies the registered `event_source` before SQL execution.

### Files Changed

Implementation and test evidence for the milestone is present in:

- `collectors/workloads/models.py`
- `collectors/workloads/registry.py`
- `collectors/persistence/core.py`
- `tests/workloads/test_registry.py`
- `tests/workloads/test_integration.py`
- `tests/persistence/test_core.py`
- `tests/persistence/test_g01_015_event.py`

This documentation update changes only project documentation.

### Security Improvements

- SQL values remain driver-bound parameters; values are not interpolated into statements.
- Destination tables and columns are selected from closed endpoint maps, so normalized input cannot choose identifiers.
- Endpoint and persistence-mode mismatches fail before writing.
- Event sources are registry-controlled, preventing cross-source collisions in shared `core.audit_event` storage.
- Unknown endpoints, unsupported event endpoints, incomplete rows, and missing lineage are rejected without issuing SQL.
- Dispatcher inputs and lineage are kept free of credentials, tokens, authorization headers, and unrelated payload fields.

### Test Evidence

Offline unit and integration coverage verifies:

- Complete 19-endpoint registry coverage, closed persistence vocabulary, owner mapping, and migration-aligned target tables.
- Representative dispatch for all persistence modes, source-order preservation, controlled unknown-endpoint errors, and non-mutation of input records and lineage.
- Parameterized SQL, deterministic replay, conflict/idempotency behavior, transaction commit/rollback behavior, and required-column validation.
- Event-control regression coverage confirming G01-005, G01-006, and G01-014 are the only event endpoints, G01-015 remains `CURRENT_WITH_SNAPSHOT`, event-source mismatches are rejected, and rejected input is not mutated.
- No live Microsoft Graph calls or credentials are required by this evidence.

### Remaining Technical Debt

- The persistence boundary is still DB-API-like and offline-testable; a live PostgreSQL integration test exercising the dispatcher against the runtime container remains outstanding.
- Operational metrics, tracing, and durable dead-letter handling for rejected records are not yet part of this milestone.
- Batch failure recovery is transaction rollback at the collection boundary; retry policy and partial-batch observability remain future work.

## EX-P02C Exchange quarantine architecture closure

**Task:** `EX-P02C-QUARANTINE-ARCHITECTURE-CLOSURE-001`  
**Status:** `EX_P02C_PASS`

Quarantine is a **BASIC/EOP service capability**, but unattended app-only collection is **ARCHITECTURE_BLOCKED** under the currently supported Microsoft interfaces. This is a supported-platform boundary, not unfinished implementation and not technical debt.

**Authorization and interface evidence:**

- Exchange Online PowerShell app-only authentication supports `Exchange.ManageAsApp`.
- `Exchange.ManageAsApp` does not itself authorize quarantine access.
- Documented read-only quarantine authorization is available to Security Reader, Global Reader, or Security Operator user/admin access.
- No documented supported service-principal authorization model exists for `Get-QuarantineMessage`.
- Exchange custom RBAC quarantine permissions are obsolete/unsupported.
- No documented GA Exchange Admin API quarantine endpoint is available.
- Undocumented or Preview workarounds are excluded.

**Quarantine lock:**

- Service capability: `BASIC/EOP`
- Collector status: `ARCHITECTURE_BLOCKED`
- Blocker type: `SUPPORTED_PLATFORM_BOUNDARY`
- Technical debt: `NO`
- Future reopen condition: Microsoft provides a supported app-only quarantine authorization/API, or the project explicitly approves delegated-user collection.

No dedicated EXO app, certificate, `Exchange.ManageAsApp` grant, broad Entra role, or PowerShell adapter is to be created for this closure. EX-P02 is closed; EX-P03 through EX-P09 remain not required for Basic. No implementation, UX, tenant mutation, permission, credential, or source behavior changed.

Evidence: `docs/evidence/EX-P02A-BASIC-PROTECTION-SCOPE-CLOSURE-001.md`.

## STD-15G Exchange storage usage correction

**Task:** `STD-15G-EXCHANGE-STORAGE-USAGE-CORRECTION-001`  
**Status:** `STD_15G2_READY`

Bounded live source inspection through `graph-agent-collector-dev` proved `USAGE-003` / `getMailboxUsageDetail(period='D7')` has all required fields: 30 rows; `Report Refresh Date` present and populated on 30/30 rows with value `2026-08-25`; `Storage Used (Byte)`, `Issue Warning Quota (Byte)`, `Prohibit Send Quota (Byte)`, and `Prohibit Send/Receive Quota (Byte)` each present, populated on 30/30 rows, blank on 0 rows, and numerically parseable on 30/30 populated rows. This supersedes the earlier absence statement. No identities or raw CSV rows were printed. STD-15G2 wiring is implementation-ready; no implementation was performed in this task.

Evidence: `docs/evidence/STD-15G-EXCHANGE-STORAGE-USAGE-CORRECTION-001.md`. No OneDrive, SharePoint, SEND_MAIL, license semantics, or unrelated production code was changed.

## STD-15G2A Exchange capacity production validation

**Task:** `STD-15G2A-EXCHANGE-QUOTA-PRODUCTION-WIRING-VALIDATION-001`  
**Status:** `STD_15G2A_BLOCKED`

Migration 014 applied through the production migrator and USAGE-003 completed in the collector runtime with 30 source and 30 persisted rows. Runtime rebuild completed. Focused runtime tests ran (43 total, one numeric-type contract failure); parity remains incomplete for analytics and registry hashes, and database/API bucket evidence remains unverified. Source UI still lacks Exchange storage, capacity, and utilization detail columns. STD-15G3 remains the next task.

Evidence: `docs/evidence/STD-15G2-EXCHANGE-QUOTA-WIRING-IMPLEMENTATION-001.md`.

## STD-15G2C Exchange DB RCA and analytical view

**Task:** `STD-15G2C-EXCHANGE-DB-RCA-AND-ANALYTICAL-VIEW-001`  
**Status:** `STD_15G2C_PASS`

Reconciled the authoritative PostgreSQL target. All three runtimes (migrator,
collector, analytics/API) target `graph_agent` on `postgres:5432`; migration 014
was verified correctly applied (all three quota `BIGINT` columns present on
current + snapshot). The earlier reconciliation mismatch was traced to (a) a
verification run against the wrong (bootstrap) database and (b) a real
persistence defect: the usage-report adapter matched only plural `(Bytes)`
quota headers while the live `getMailboxUsageDetail` CSV uses singular `(Byte)`
headers, so quota fields normalized to `NULL`. The adapter mapping was
corrected, a bounded `USAGE-003` collection repopulated the authoritative
current table (quota 30/30), and the stale current-refresh snapshot generation
was corrected from the authoritative data.

Created forward-only migration `015_exchange_mailbox_capacity.sql` producing the
`analytics.exchange_mailbox_capacity` VIEW as the single derived-data contract
for Exchange capacity (30 rows, reconciles with current). `utilization_percent`
and `usage_level` now come from SQL; `analytics/operations.py` consumes the view
and no longer recomputes the capacity formula. Threshold boundaries (LOW/MEDIUM/
HIGH/NO_DATA) and NO_DATA fail-closed were verified. `pgcrypto` enabled at
bootstrap so the view `user_ref` (sha256[:16]) matches the existing Python
`_user_ref`, preserving cross-workload correlation parity. Deployed runtime
parity PASS; API and view counts reconcile.

Evidence: `docs/evidence/STD-15G2C-EXCHANGE-DB-RCA-AND-ANALYTICAL-VIEW-001.md`.
STD-15G3 remains the next task (Exchange UI capacity detail columns).

## STD-15G3B Exchange UI contract fix

**Task:** `STD-15G3B-EXCHANGE-API-UI-CONTRACT-FIX-001`  
**Status:** `STD_15G3B_PASS`

Bounded UI fix using the STD-15G3A root-cause analysis. Scope limited to `operations-ui/public/app.js`; no backend/API/SQL view changes. Four proven root causes corrected:

1. **capacity_buckets** — `capacity_usage.low/medium/high/no_data` are plain integers but the previous `display()`/`value()` metric-object path returned `null` for non-objects. Added an explicit `primitive` renderer applied only to these known fields. Live values render correctly: LOW=30, MEDIUM=0, HIGH=0, NO DATA=0.
2. **refresh_date** — `data_last_refreshed` is a plain string; rendered via the `primitive` path. Live value renders `2026-08-25`.
3. **mailbox_items** — wrong key `exchange.total_mailbox_items` (non-existent) mapped to `total_mailbox_item_count`; corrected to read `exchange.total_mailbox_item_count`. Live value renders `56434`.
4. **storage_formatting** — `total_storage_used` (metric object with `value` = `150163617`) was shown as raw bytes; applied the existing `storage()` formatter via a `storageValue` helper that extracts the numeric value from either a metric object or a primitive. Renders `143.21 MB`.

`display()`/`value()` global semantics were not weakened; only the known primitive fields are handled explicitly through per-field render kinds (`primitive`, `storage`) in `workloadCard`.

**Validation:**
- JS/source contract check: `node --check` PASS; simulated Exchange card rendered the exact expected strings for all fields (LOW/MEDIUM/HIGH/NO DATA/refresh date/storage/items).
- Rebuild: recreated only the `operations-ui` container (`docker compose up -d --build --no-deps operations-ui`); image rebuilt and container healthy.
- Runtime parity: confirmed against the live `/api/operations/kpi` response — `capacity_usage` `{low:30,medium:0,high:0,no_data:0}`, `data_last_refreshed` `2026-08-25`, `total_storage_used.value` `150163617`, `total_mailbox_item_count.value` `56434`, and no `total_mailbox_items` key. All match task expectations.
- UI health: `/` and `/app.js` both HTTP 200; container healthcheck healthy.
- No backend changes.

Browser/Playwright acceptance deliberately deferred to `STD-15G3C-EXCHANGE-UI-BROWSER-ACCEPTANCE-001`.

Files changed: `operations-ui/public/app.js`.

Evidence: `docs/evidence/STD-15G3B-EXCHANGE-API-UI-CONTRACT-FIX-001.md`.

## STD-15I2 User identity display wiring

**Task:** `STD-15I2-USER-IDENTITY-DISPLAY-WIRING-001`  
**Status:** `STD_15I2_PASS`

Bounded human-readable user identity wiring. Uses prior STD-15I1 evidence that `core."user"` already contains `display_name` and `user_principal_name`. Canonical/internal identity (`source_object_id`/`user_id`, tenant-safe joins, opaque `user_ref`) is unchanged.

1. **Analytics** — `analytics/operations.py`: the canonical `core."user"` SELECT in `from_connection` now includes `display_name` (preserving `user_principal_name`); `cross_workload_user_status()` now emits `display_name`, `user_principal_name`, and `user_ref` per row. No join uses `display_name`/UPN; joins remain grounded on the canonical directory identity.
2. **API** — no new endpoint. Existing `GET /api/operations/correlation/users` returns the correlation rows, which now expose the three fields per row. Existing contracts preserved.
3. **UI** — `operations-ui/public/app.js`: `renderUsers` and `renderDetail` (used by Exchange/OneDrive/SharePoint) now render **Display Name** first, **User / UPN** second, and **User Ref (technical)** last via a muted `.technical-cell` style. The opaque `user_ref` is no longer the primary customer-facing identity column.

**Validation:**
- Focused analytics/API tests: `tests/analytics/test_operations.py` + `tests/analytics/test_operations_api.py` → 35 tests pass, including new assertions for identity exposure.
- JS syntax: `node --check` PASS.
- Rebuild/recreate: only `operations-api` and `operations-ui` services recreated.
- Runtime parity: `scripts/check_runtime_parity.py` → all modules MATCH.
- Live API: first correlation row returned `display_name="Conf Room Adams"`, `user_principal_name="Adams@M365B899688.OnMicrosoft.com"`, `user_ref="user-237457cff1e95e44"`; canonical join behavior unchanged.
- UI health: `/` and `/app.js` HTTP 200; `operations-ui` healthy; deployed app.js matches host.

No usage calculations, Exchange active-user hiding, summary counts, Exchange capacity semantics, OneDrive/SharePoint semantics, or migrations changed. No browser harness.

Evidence: `docs/evidence/STD-15I2-USER-IDENTITY-DISPLAY-WIRING-001.md`.

Next: `STD-15I3-EXCHANGE-ACTIVE-ONLY-PRESENTATION-001`.

## STD-15I3 Exchange active-only presentation

**Task:** `STD-15I3-EXCHANGE-ACTIVE-ONLY-PRESENTATION-001`  
**Status:** `STD_15I3_PASS`

Bounded presentation/summary eligibility change. Customer-facing Exchange capacity views (Exchange detail table, Exchange usage-summary cards, and the Exchange workload card's LOW/MEDIUM/HIGH/NO DATA counts) now show **ACTIVE Exchange users only**. INACTIVE and UNKNOWN users are excluded from capacity presentation but remain in the backend/database evidence unchanged.

**Change (frontend only, `operations-ui/public/app.js`):**
1. Added `exchangeLevel`/`exchangeBucket`/`exchangeActiveUsers` helpers. Eligibility is `exchange_status === "ACTIVE"` (the `email_status`/ACTIVE signal exposed per user by the correlation API). `exchange_usage_level` remains the authoritative view value; no thresholds recomputed.
2. `renderDetail` — Exchange detail rows and the HIGH/MEDIUM/LOW/NO DATA filter-button counts are computed from the ACTIVE exchange pool only; the "Email Status" column is hidden because every visible row is ACTIVE.
3. `usageSummary` — the Exchange usage card counts derive from the ACTIVE exchange pool.
4. `renderWorkloads` — the Exchange card LOW/MEDIUM/HIGH/NO DATA counts now derive from ACTIVE exchange users instead of the all-mailbox `capacity_usage` aggregate (which includes INACTIVE rows).
5. `start()` — correlation rows populated before rendering Exchange capacity views so counts are active-only.

**Validation:**
- Focused analytics/API tests: `tests/analytics/test_operations.py` + `tests/analytics/test_operations_api.py` → 35 tests pass (backend unchanged).
- JS syntax: `node --check` PASS.
- Rebuild/recreate: only `operations-ui` service recreated (`operations-api` unchanged).
- Runtime parity: `scripts/check_runtime_parity.py` → all modules MATCH.
- Live reconciliation: ACTIVE=19, INACTIVE=11, UNKNOWN=9; visible LOW/MEDIUM/HIGH/NO DATA = 19/0/0/0 = 19 = visible eligible detail rows; Display Name + UPN present; no INACTIVE rows visible; backend evidence unchanged.
- UI health: `/` and `/app.js` HTTP 200; `operations-ui` healthy; deployed app.js matches host.

**Scope:** Exchange presentation only. SQL analytical view, quota/capacity formulas, canonical user joins, persistence, OneDrive, SharePoint, license semantics, SEND_MAIL/security scenarios, and cosmetic styling unchanged. No migration, no browser harness, no token/credit logging.

Next: `STD-15H1-ONEDRIVE-CAPACITY-CONTRACT-PREFLIGHT-001`.
