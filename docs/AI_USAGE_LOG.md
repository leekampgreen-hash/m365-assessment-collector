## COLLECTOR-STANDARDIZATION-P01-P05-001

- **Date:** 2026-09-04
- **Model:** `Gemini 3.8 Flash`
- **Result:** `COLLECTOR_STANDARDIZATION_SEALED`
- **Scope:** Completed 5-phase collector standardization: (1) CLI & scheduler argument standardization; (2) Registered 12 specialized script collectors to `config/api_inventory.json` establishing SSOT (45 endpoints); (3) Unified CLI runner (`collectors/run_collector.py --collector <ID_OR_NAME>`) and dual-key checkpoint reconciliation; (4) Operations Admin UI enhancement with instant search, workload filtering, and CLI copy shortcuts; scheduler modernization; and publication of `docs/COLLECTORS_REFERENCE.md`; (5) On-demand execution API (`POST /api/admin/collector/trigger`), health metric cards, and interactive Collector Inspector modal.
- **Validation:** Live API & UI tested on port 18080; scheduler jobs executed cleanly; 153 CLI and framework tests PASS; complete test suite passes 100%.
- **Files changed:** `collectors/scheduler.py`, `collectors/run_collector.py`, `config/api_inventory.json`, `api/admin.py`, `operations-ui/public/admin.html`, `operations-ui/public/styles.css`, `docs/COLLECTORS_REFERENCE.md`, `docs/COLLECTOR_STANDARDIZATION_BACKLOG.md`.

## TECH-DEBT-TD009-TD010-RESOLUTION-001

- **Date:** 2026-09-04
- **Model:** `Gemini 3.8 Flash`
- **Result:** `TECH_DEBT_RESOLUTION_PASS`
- **Scope:** Resolved TD-009 by formalizing `collector_type: "declarative" | "specialized"` in `EndpointSpec` and updating invariant tests (`test_registry.py`, `test_security_wiring.py`). Resolved TD-010 by removing shadowing `tests/agent/__init__.py`, installing system dependencies (`pytest`, `openai`, `psycopg3`, `pyotp`), and fixing DB cursor mock in `test_operations_api.py`. Marked `LIC-OPTIMIZER-P01` sealed in backlog.
- **Validation:** 1,360 pytest and 730 unittest tests pass 100% with 0 errors.
- **Files changed:** `collectors/core/inventory.py`, `collectors/core/models.py`, `tests/agent/__init__.py`, `tests/agent/test_research.py`, `tests/analytics/test_operations_api.py`, `tests/architecture/test_security_wiring.py`, `tests/security/test_security_findings.py`, `tests/workloads/test_registry.py`, `docs/TECHNICAL_DEBT.md`, `docs/progress/backlog.md`.

## OPS-UI-LICENSE-OPTIMIZATION-REDESIGN-001

- **Date:** 2026-09-04
- **Model:** `Gemini 3.8 Flash`
- **Result:** `OPS_UI_LICENSE_REDESIGN_PASS`
- **Scope:** Complete redesign of the License Optimization & FinOps UI in `operations-ui/public/index.html`, `operations-ui/public/app.js`, and `operations-ui/public/styles.css`. Implemented 3-column Command Center, interactive SKU efficiency table with drilldown, and 1-user-1-row Identities Reclamation Pipeline with filter chips, search, and AI audit integrations.
- **Validation:** JavaScript syntax check passed (`node -c operations-ui/public/app.js`); Docker container `graph-agent-operations-ui-dev` up and healthy (HTTP 200).
- **Files changed:** `docker-compose.yml`, `operations-ui/public/index.html`, `operations-ui/public/app.js`, `operations-ui/public/styles.css`, `docs/CHANGELOG.md`, `docs/progress/license.md`, `docs/progress/current.md`, and this log.

## OPS-UI-SESSION-CACHE-CONSISTENCY-001

- **Date:** 2026-09-04
- **Model:** `Gemini 3.7 Flash`
- **Result:** `OPS_UI_SESSION_CACHE_PASS`
- **Scope:** Frontend consistency and session-scoped telemetry caching. Added `getSessionTelemetry`, `setSessionTelemetry`, and `clearSessionTelemetry` in `operations-ui/public/app.js`. Removed duplicate DOM financial hydration from `hydrateKpiCards()` to ensure `hydrateFinancialSummary()` is the single source of truth for License FinOps metrics and sidebar savings badge. Synchronized HTML initial placeholder in `operations-ui/public/index.html`.
- **Validation:** JavaScript syntax check passed (`node --check operations-ui/public/app.js`); `operations-ui` rebuilt and container healthy (HTTP 200); single source of truth across Overview, Sidebar, and License Optimizer verified.
- **Files changed:** `operations-ui/public/app.js`, `operations-ui/public/index.html`, `docs/CHANGELOG.md`, and this log.

## SP-P12-SHAREPOINT-WORKLOAD-SEAL-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `SP_P12_SEALED`
- **Scope:** Documentation/handover only. Final SharePoint chain SP-P03 through SP-P11 reconciled and locked in the seal evidence. Completed phases: SP-P03 tenant settings collector + G01-020 registered; SP-P04 migration 021; SP-P05 production pipeline + integration tests PASS; SP-P06 orphaned-sites analytics + API; SP-P07 external-sharing analytics + API; SP-P08 live acceptance `externalUserAndGuestSharing`; SP-P09 audit collector + migration 022; SP-P10 audit live acceptance PASS_WITH_LIMITATIONS (zero-content trial tenant, controlled synthetic proof); SP-P11 audit analytics + API 54/54 PASS.
- **Safety:** No production code, tests, migrations, database, UX, runtime rebuild, or Microsoft 365 calls. Synthetic residue NONE. No token/credit logging.
- **Closure:** `SHAREPOINT_WORKLOAD_SEALED = YES`; `OPEN_BLOCKERS = NONE`; next planned direction is the License data workstream.

## OD-P10-ONEDRIVE-WORKLOAD-SEAL-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P10_SEALED`
- **Scope:** Documentation/handover only. Final OneDrive chain OD-P01 through OD-P09 reconciled; OD-R01 accepted with non-blocking findings. Durable production, hardening, analytics/API, validation, freeze, and SharePoint-next-workload contracts recorded in the seal evidence.
- **Safety:** No production code, tests, migrations, database, UX, runtime rebuild, or Microsoft 365 calls. Synthetic residue NONE. No token/credit logging.
- **Closure:** `ONEDRIVE_WORKLOAD_SEALED = YES`; `OPEN_BLOCKERS = NONE`; next planned direction is SharePoint data workstream.

## OD-P09A-ONEDRIVE-AUDIT-ANALYTICS-API-PRODUCTION-VALIDATION-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P09A_PASS_WITH_LIMITATIONS`
- **Validation:** Migration inventory expectations updated for 019/020; migration 020 applied through the canonical PostgreSQL migrator path and semantic view/runtime grant verified. Operations API runtime was refreshed because parity initially mismatched; final parity passed. Tenant 2 DB summary (3 total, 3 external, 1 anonymous, 0 malware, latest 2026-08-29 07:53:22+00) exactly reconciled with the deployed API and ordered detail.
- **Tests:** Focused migration and analytics/API suite passed 81/81; deployed API health, existing KPI route, limit clamp, capacity view, and OneDrive audit production-path tests were exercised. No Microsoft 365 call or synthetic fixture used.
- **Closure:** `ANALYTICS_API_READY = YES`; `OD_P09_CLOSED = YES`; `READY_FOR_OD_R01 = YES`.

## OD-P09-ONEDRIVE-HIGH-VALUE-AUDIT-ANALYTICS-API-CLOSURE-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P09_BLOCKED`
- **Implementation:** Added migration 020 semantic view, tenant-filtered analytics loading and aggregation, bounded recent detail, and `GET /api/operations/onedrive/high-value-audit?limit=N`.
- **Validation:** Focused analytics/API tests pass. Migration inventory suite reports stale repository expectations for existing migrations 019/020. PostgreSQL production reconciliation, runtime parity, and capacity regression were not executable in this environment.
- **Safety:** No Microsoft 365 call, mutation, synthetic fixture, persistence semantic change, or token/credit logging. Synthetic residue NONE.
- **Closure:** ANALYTICS_API_READY = NO; OD_P09_CLOSED = NO; READY_FOR_OD_R01 = NO.

## OD-P08-ONEDRIVE-AUDIT-BOUNDED-LIVE-ACCEPTANCE-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P08_PASS_WITH_LIMITATIONS`
- **Validation:** One normal non-dry-run `docker exec graph-agent-collector-dev python -m collectors.run_collector --onedrive-audit --json` invocation completed successfully against the live Management Activity API and real PostgreSQL. The bounded window returned 1 page and zero content/blobs/records; the first durable `onedrive_audit` checkpoint advanced safely.
- **Post-run:** Historical legitimate audit rows remained 3, duplicate business keys 0, tenant consistency PASS, capacity 26 current / 79 account snapshots / 120 activity snapshots, semantic view available, runtime parity PASS, synthetic residue NONE.
- **Limitations:** No natural high-value candidate was present in the bounded window, so classification was not re-observed live. CLI JSON does not expose token claims or run IDs; no sensitive values were recorded. No production defect found.
- **Closure:** LIVE_ACCEPTANCE_READY = YES; OD_P08_CLOSED = YES; READY_FOR_OD_P09 = YES.
- **Safety:** No Microsoft 365 mutation, sharing fixture creation, malware generation, permission change, subscription change, or capacity mutation.

## OD-P07B-ONEDRIVE-AUDIT-INTEGRATION-MATRIX-RESEAL-001

- **Date:** 2026-08-29
- **Model:** `bbb/kl/deepseek-v4-flash`
- **Result:** `OD_P07B_PASS`
- **Integration setup:** Blocker was a missing `OD_P07_BOOTSTRAP_PASSWORD` env var in `graph-agent-collector-dev`, which caused the OD-P07 matrix suite to be skipped via `SkipTest` in OD-P07A. Classification: TEST_FIXTURE_CONFIGURATION / CONTAINER_ENVIRONMENT (not a production defect). Correction: injected the host-side bootstrap secret into the container at invocation. No production or test source change required.
- **Validation:** Exact safe-drop defect retest (internal Member + ambiguous) = normalized 0, persisted 0, dropped_out_of_scope 2, malformed 0, checkpoint advanced, PASS. Full OD-P07 matrix 18/18 PASS. Direct OneDrive regression (production_path + transport_retry) 10/10 PASS. Real PostgreSQL verification PASS. Runtime parity carried forward (onedrive_audit SHA `5bb2e5dabbf91f8915f6bfed4cec188edda31e659eda208330584997fe0ee49b`). Synthetic residue NONE; live tenant 3 rows preserved. No new production defect.
- **Closure:** PRODUCTION_PATH_INTEGRATION_READY = YES; OD_P07_CLOSED = YES; READY_FOR_OD_P08 = YES.
- **Safety:** No live Microsoft 365 call, no production source change, no synthetic residue, no OD-P06 repeat, no token/credit logging. OD-P08 not started in this task.

## OD-P07A-ONEDRIVE-AUDIT-SAFE-DROP-METRIC-CLASSIFICATION-FIX-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P07A_BLOCKED`
- **REAL_DEFECT_FOUND:** YES (OD-P07 safe-drop metrics misclassified valid Member/internal and ambiguous sharing as malformed); bounded correction applied only to the terminal metric-counting branch.
- **Correction:** Normalizer exclusions now increment `records_dropped_out_of_scope`; genuine locked-candidate schema failures remain `SCHEMA_CONTRACT_FAILURE`. No business, persistence, checkpoint, retry, auth, subscription, or normalization decision changed.
- **Validation:** Targeted OneDrive command ran 10 tests with 1 environment-dependent skip; runtime parity PASS with matching SHA-256 `5bb2e5dabbf91f8915f6bfed4cec188edda31e659eda208330584997fe0ee49b`. Required real-PostgreSQL OD-P07 matrix recheck was blocked by unavailable integration setup.
- **Safety:** No live Microsoft 365 call, database fixture mutation, synthetic residue, or token/credit logging. OD-P08 not started.

## OD-P07-ONEDRIVE-AUDIT-PRODUCTION-PATH-NEGATIVE-MATRIX-001

- **Date:** 2026-08-29
- **Model:** `bbb/kl/deepseek-v4-flash`
- **Result:** `OD_P07_BLOCKED`
- **Validation:** Validated the full OneDrive high-value audit production path against a bounded positive/negative matrix with a FAKE Management Activity source over the REAL orchestration, normalizer, `CollectionWriter` lifecycle, `control.collector_checkpoint`, audit persistence, and REAL PostgreSQL. Dedicated data-driven suite `tests/integration/test_onedrive_audit_production_path_matrix.py` (18 tests) in `graph-agent-collector-dev`: 17 PASS / 1 FAIL. Positive, safe-drop business outcome, malformed locked-candidate, auth/subscription/source/persistence failure, replay, tenant isolation, lifecycle, and checkpoint matrices PASS with real-PostgreSQL verification; synthetic residue NONE; live tenant rows preserved.
- **Real defect found (NOT auto-fixed):** `collectors/onedrive_audit.py` metric-counting loop counts valid-but-out-of-scope OneDrive internal/ambiguous sharing as `malformed_records` instead of `records_dropped_out_of_scope`, violating the locked OD-P03 contract and OD-P07 sections 3/13. Business persistence/no-false-success/checkpoint are correct; the single failing gate is this observability mis-classification. Smallest correction recommendation recorded in evidence.
- **Safety:** No production source changed; no live Management Activity call; no tenant/permission/subscription mutation; no token/credit logging; synthetic residue NONE; the 3 legitimate production OneDrive audit rows preserved.

## OD-P06F-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-RESUME-SEAL-001

- **Date:** 2026-08-29
- **Model:** `bbb/kl/deepseek-v4-flash`
- **Result:** `OD_P06F_PASS_WITH_LIMITATIONS`
- **Retest:** All previously blocked RETRY and BLOB gates pass against the corrected transport; `UnboundLocalError` not reproducible. Real-PostgreSQL production-path RUN 1-5 pass (initial/overlap-late-arrival/partial-failure/recovery/stale-writer) with checkpoint no-advance and lineage verified. Restart durability and runtime SHA-256 parity pass. One bounded live read-only dry-run proves the full read-only pipeline with business persistence delta = 0 and checkpoint delta = 0. Failure classification matrix and P05/capacity regression confirmed.
- **Limitation:** `complete_endpoint_run` records only the closed `CLASSIFICATIONS` vocabulary; a partial-failure control-state was recorded with `API_ERROR` while the actual transport classification (`RETRY_EXHAUSTED`) was proven at the transport boundary. No effect on checkpoint/business/no-false-success/collectibility.
- **Safety:** No production code changed in this acceptance; TEST-ONLY harnesses used and removed (not committed); synthetic residue is NONE; the 3 legitimate production OneDrive audit rows are preserved; no token/credit logging.

## OD-P06E-ONEDRIVE-AUDIT-DIRECT-TRANSPORT-RETRY-CORRECTION-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P06E_PASS`
- **Root cause/correction:** Direct `AuditTransportError` binding in `ManagementActivityTransport._get` left `error` unavailable after the exception clause; assigning `error = exc` preserves the original transport failure for retry/classification.
- **Validation:** Focused direct 429/Retry-After/5xx/auth/source, urllib HTTPError, and timeout regressions pass; existing OneDrive integration suite passes; compile/import and source/runtime SHA-256 parity pass.
- **Safety:** No live Management Activity call, checkpoint/business-row/tenant/permission mutation, unrelated refactor, or token/credit logging. OD-P06 acceptance was not resumed.

## OD-P06D-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-EXECUTION-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P06D_BLOCKED`
- **Real defect found:** `collectors/onedrive_audit.py` `ManagementActivityTransport._get` (lines 120-124) raises `UnboundLocalError` because `except AuditTransportError as error: pass` deletes `error` before `error.classification` is read. Blocks RETRY (429/Retry-After/5xx/bounded exhaustion) and BLOB (partial-failure/recovery) required scenarios; also blocks RUN 3/RUN 4 production-path scenarios. Reported with exact reproduction; not auto-fixed per task instruction.
- **Verified pass (unaffected):** window/overlap bounds and 4-hour first-run lookback; checkpoint advance/no-advance and dry-run non-mutation; late-arrival normalization; pagination multi-page/cyclic/bound; non-failure blob multi/duplicate-contentId/malformed; subscription enabled/absent; schema malformed/out-of-scope; timeout bounded-retry.
- **Safety:** No production code changed; TEST-ONLY harness removed; `test_onedrive_audit_production_path` still passes 3/3; no residue, tenant mutation, or token/credit logging.

## OD-P06C-ONEDRIVE-AUDIT-DATA-HANDLING-PRODUCTION-VALIDATION-SEAL-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P06C_BLOCKED`
- **Validation:** Applied migration 019 idempotently through `graph_agent_migrator`; real PostgreSQL checkpoint create/read/monotonic/stale/source-scope contract passed; focused collector/persistence/auth regression passed 125/125; SHA-256 source/runtime parity passed for affected artifacts; capacity remained current 26, snapshot 79, semantic view available.
- **Gaps:** Full A-AA matrix, real PostgreSQL production-path runs 1-5, restart durability capture, and one bounded live read-only dry-run were not executed, so closure gates remain blocked.
- **Safety:** SQL fixtures were transactional and rolled back; checkpoint residue is none; no tenant mutation, permissions/subscriptions change, or token/credit logging.

## OD-P06B-ONEDRIVE-AUDIT-DURABLE-CHECKPOINT-OVERLAP-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P06B_PASS_WITH_LIMITATIONS`
- **Implementation:** Added migration 019 and tenant/source-scoped durable checkpoint reads/monotonic advances, bounded four-hour first-run lookback, configurable two-hour overlap, effective-window and checkpoint observability, and read-only dry-run semantics.
- **Validation:** Fake Management Activity production-path suite passed 3/3; diff checks passed. Full failure/restart/real PostgreSQL matrix was limited by the current host/container test environment. No live acceptance, tenant mutation, or token/credit logging.
- **Runtime parity:** Source/runtime parity was not re-sealed after this change; bind-mounted deployment requires the OD-P06C parity check.

## OD-P06A-ONEDRIVE-AUDIT-RUNTIME-PARITY-CORRECTION-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P06A_PASS`
- **Root cause:** `STALE_CONTAINER`; Compose wiring was authoritative and correct: `/opt/docker/graph-agent/collectors` bind-mounted to `/workspace/collectors`. The prior runtime mismatch was resolved by recreating only the collector container.
- **Validation:** SHA-256 parity passed for `collectors/onedrive_audit.py`, `collectors/run_collector.py`, `collectors/persistence/core.py`, and directly imported `collectors/core/errors.py`. Import/compile smoke passed; service remained running with zero restarts and expected mounts.
- **Safety:** No Compose/image/business/schema/tenant changes; no live Management Activity collection or token/credit logging.

## OD-P06-ONEDRIVE-AUDIT-DATA-HANDLING-HARDENING-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P06_BLOCKED`
- **Implementation:** Added bounded UTC windows, defensive pagination, bounded shared-policy retries, Retry-After handling, contentId replay suppression, explicit schema/source failures, subscription verification, and bounded operational counters. No new business event, permission, sharing, UX, analytics, API, or tenant mutation was added.
- **Validation:** Dedicated existing OneDrive integration suite passed 3/3; Python compilation and diff checks passed. Current runtime parity check reports an existing bind-mounted `collectors/persistence/core.py` mismatch until runtime refresh.
- **Open items:** Durable checkpoint/watermark semantics, source-history classification mapping, focused OD-P06 matrix, production fixture rerun, parity re-seal, capacity regression, and one post-change bounded live dry-run.
- **Safety:** No live read or persistence was run after code changes; no synthetic residue or token/credit logging.

## OD-P05G-ONEDRIVE-AUDIT-FINAL-INTEGRATION-CLOSURE-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P05G_PASS_WITH_LIMITATIONS`
- **Implementation:** Added a dedicated fake-source OneDrive audit production-path suite and corrected malware normalization to emit the persistence-contract value `external_flag=False`.
- **Validation:** Dedicated suite passed 3/3; focused persistence/auth regression command passed 125/125 in `graph-agent-collector-dev`. Fresh manage.office.com token claims verified audience, tenant, app, and `ActivityFeed.Read`; negative `invalid_scope` gate passed. Current fake-source path no longer reproduces the historical PersistenceError, classified `RESOLVED_BY_CURRENT_WIRING`.
- **Evidence reused:** OD-P05F live read-only evidence remains valid: 3 content entries, 3 blobs, 197 records, 3 normalized duplicate candidates, and zero persistence delta. No live failure injection was performed; `NOT_REQUIRED_FOR_CLOSURE`. Synthetic residue is none. Fresh relational DB query was limited by unavailable PostgreSQL driver in the collector test process; prior OD-P04B/OD-P05F database evidence remains valid.
- **Safety:** No tenant mutation, permission change, new share, live failure injection, malware test, or token/credit logging.
- **Files:** `collectors/onedrive_audit.py`, `tests/integration/test_onedrive_audit_production_path.py`, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, `docs/evidence/OD-P05G-ONEDRIVE-AUDIT-FINAL-INTEGRATION-CLOSURE-001.md`

## OD-P05F-ONEDRIVE-AUDIT-PRODUCTION-CLOSURE-RECHECK-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P05F_BLOCKED`
- **Validation:** In `graph-agent-collector-dev`, `python -m unittest tests.persistence.test_core tests.core.test_auth_runtime_cli` passed 122/122. Source/runtime SHA-256 parity passed for all three OD-P05E production files. Bounded production read completed with 3 content entries, 3 blobs, 197 records, 3 normalized duplicate candidates, and zero business-row delta; capacity current remained 26 and the semantic view remained available.
- **Gaps:** Isolated synthetic production-path PostgreSQL lineage proof, controlled live failure lifecycle proof, and fresh manage.office.com token claim verification remain open. Legacy three rows were not modified and synthetic residue is none.
- **Safety:** No tenant mutation, permission change, schema change, malware test, synthetic fixture, or token/credit logging.

## OD-P05E-ONEDRIVE-AUDIT-LINEAGE-CONTRACT-CORRECTION-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P05E_PASS_WITH_LIMITATIONS`
- **Implementation:** Reconciled OD-P03 optional nullable `UserId`/`actor_upn` and `RecordType`/`record_type` semantics; added canonical collection/endpoint run creation and lineage threading to the OneDrive production persistence path.
- **Validation:** Offline focused verification and existing persistence contract coverage targeted; live synthetic PostgreSQL production-path proof and deployed parity were not available. Dry-run remains non-persisting.
- **Safety:** No tenant mutation, permission change, new source, malware test, or token/credit logging.

## OD-P05B-ONEDRIVE-AUDIT-COLLECTOR-PRODUCTION-VALIDATION-SEAL-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P05B_BLOCKED`
- **Validation:** `graph-agent-collector-dev` is running; bind-mounted requested artifacts matched source SHA-256 hashes; `--onedrive-audit --dry-run --json` passed; existing 53-test persistence suite passed; direct filter smoke checks passed.
- **Gaps:** No focused collector suite or fake-source PostgreSQL production-path fixture was available. Fresh `https://manage.office.com` token gate and bounded live read-only proof were not established. Non-dry production invocation failed with `PersistenceError`.
- **Safety:** No tenant mutation, permission change, subscription change, malware test, synthetic fixture, or synthetic residue was introduced. No token/credit logging.
- **Files:** `docs/evidence/OD-P05B-ONEDRIVE-AUDIT-COLLECTOR-PRODUCTION-VALIDATION-SEAL-001.md`, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`

## OD-P05A-ONEDRIVE-AUDIT-COLLECTOR-WIRING-VALIDATION-CLOSURE-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P05A_PASS_WITH_GAPS`
- **Implementation:** Added explicit `collectors.run_collector --onedrive-audit` production invocation, separate Management Activity resource transport, and direct OD-P04 normalized persistence handoff.
- **Validation:** In `graph-agent-collector-dev`, compile passed with a temporary writable pycache and `python -m unittest tests.persistence.test_core` passed 53/53. Dry-run entrypoint passed. Host Docker parity helper could not execute inside the container; live read-only proof and production-path PostgreSQL fixture were not run.
- **Scope:** No retry/watermark hardening, UX, analytics/API, permission, tenant mutation, malware test, or token/credit logging.

## OD-P05-ONEDRIVE-AUDIT-COLLECTOR-NORMALIZATION-WIRING-001

- **Date:** 2026-08-29
- **Model:** `9router/my_ulti`
- **Result:** `OD_P05_PASS_WITH_GAPS`
- **Implementation:** Added separate Management Activity API auth resource support, Audit.SharePoint transport with subscription/content pagination/blob retrieval, and fail-closed OneDrive high-value normalization.
- **Validation:** Module compilation and focused persistence idempotency/rejection tests passed. Live proof and deployed parity remain unavailable.

## OD-P04B-ONEDRIVE-AUDIT-PERSISTENCE-VALIDATION-SEAL-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** OneDrive high-value audit persistence production validation seal.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P04B_PASS_WITH_LIMITATIONS`
- **Baseline/parity:** Migration 018, runtime table/grants, zero prior residue, and capacity regression passed. Bind-mounted collector persistence artifact hashes matched deployed runtime; migration remains migrator-owned and is not image-baked.
- **Tests:** Collector container ran `python -m unittest tests.persistence.test_core`; 53 focused tests passed. Live runtime-role proofs passed for Guest external, synthetic FileMalwareDetected with nullable optional fields, duplicate idempotency, late arrival, and fail-closed rejection matrix. Bootstrap-only cleanup left zero synthetic audit rows.
- **Isolation/rollback:** One authoritative tenant prevented a live second-tenant fixture; focused SQL/contract semantics prove tenant-scoped uniqueness/isolation and this is non-blocking. Transaction rollback/atomicity is proven by focused transaction tests; no unsafe live fault injection was used.
- **Scope:** No collector transport, OD-P05 wiring, UX, analytics/API, capacity-table, or tenant business-data mutation.

## OD-P04A-ONEDRIVE-AUDIT-PERSISTENCE-RUNTIME-VALIDATION-CLOSURE-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Production-equivalent OneDrive audit persistence runtime validation closure.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P04A_PASS_WITH_GAPS`
- **DB preflight:** Authoritative Compose target is `postgres:5432`, database `graph_agent`, runtime role `graph_agent_runtime`; original unavailable-role finding was wrong target/environment. Role exists and connects.
- **Migration:** Migration 018 applied through `graph_agent_migrator`. A real sequence-grant defect was corrected using `pg_get_serial_sequence`; no existing capacity or Exchange tables were modified.
- **Validation:** Runtime INSERT/SELECT, anonymous insertion, duplicate idempotency, fail-closed rejection, and synthetic residue cleanup passed. Full cross-tenant, guest/malware/late-arrival, and rollback matrix remain incomplete because the authoritative database has one tenant and the collector image lacks pytest.
- **Scope:** No collector, API, UX, analytics, new permission, or tenant mutation change.
- **Files changed:** migration and required OD-P04A evidence/progress/usage documentation.

## OD-P04-ONEDRIVE-HIGH-VALUE-AUDIT-PERSISTENCE-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Implement normalized, fail-closed, append-only OneDrive high-value audit persistence.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P04_PASS_OFFLINE_PENDING_DB`
- **Implementation:** Migration 018 creates `core.onedrive_high_value_audit_event`; persistence API validates the locked filter/classification contract before parameter-bound immutable inserts with tenant-scoped idempotency on `(tenant_id, audit_record_id)`.
- **Validation:** Focused persistence and migration tests passed. Production-equivalent PostgreSQL validation was unavailable.
- **Scope:** No collector, API, UX, analytics, permissions, tenant mutation, or raw payload retention change.
- **Files changed:** migration, persistence core/export, focused persistence and migration tests, schema design, progress, and usage log.

## OD-P03C-R2-OPERATOR-CLEANUP-ATTESTATION-CLOSURE-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Documentation reconciliation of operator/UI confirmation for controlled sharing-fixture cleanup.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P03C_R2_PASS`
- **Operator/UI evidence:** OneDrive `notes.txt` is Private with the controlled external share removed; `Laporan bulanan.docx` is Private with the Anyone link removed. In SharePoint site `SP-Audit-Test`, `SP-AUDIT-EXTERNAL.txt` has the controlled external share removed and `SP-AUDIT-ANONYMOUS.txt` has the Anyone link removed.
- **Cleanup:** `CLEANUP_STATUS=OPERATOR_VERIFIED`; `SYNTHETIC_SHARING_RESIDUE=NONE`. Files and the `SP-Audit-Test` site remain preserved as reusable test fixtures.
- **Verification capability:** `AUTOMATED_PERMISSION_VERIFICATION=UNAVAILABLE_NON_BLOCKING`. OD-P03C-R1 was blocked by verification capability, not evidence of failed cleanup; historical pre-cleanup evidence is not treated as current residue. No technical-debt automation work is required.
- **Gate:** `DATA_CONTRACT_LOCKED=YES`; `READY_FOR_OD_P04=YES`. OD-P03 is not reopened and cleanup tooling does not block OD-P04.
- **Scope:** Documentation/handover only. No mutation, code, database, UX, permission-inspection harness, subscription, or token/credit logging.
- **Files changed:** `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, and `docs/evidence/OD-P03C-R2-OPERATOR-CLEANUP-ATTESTATION-CLOSURE-001.md`

## OD-P03C-R1-CONTROLLED-SHARING-CLEANUP-VERIFICATION-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Read-only verification that four controlled OneDrive/SharePoint sharing permissions were removed and fixtures remain.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P03C_R1_BLOCKED`
- **Verification:** Not executable in this repository session: no supported live Graph permission-inspection harness or configured operator inspection entry point is present. No credentials were accessed.
- **Scope:** No mutation, database, code, UX, subscription, permission, or audit-event change. Historical audit records were not treated as cleanup state.
- **Fixtures:** Not independently re-read through Graph; prior OD-P03C evidence recorded all four targeted shares as present/not revoked.
- **Files changed:** `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, and `docs/evidence/OD-P03C-R1-CONTROLLED-SHARING-CLEANUP-VERIFICATION-001.md`

## OD-P03C-CONTROLLED-SHARING-FIXTURE-CLEANUP-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Clean up only the four controlled OneDrive/SharePoint sharing permissions while preserving reusable fixtures.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P03C_BLOCKED`
- **Precheck:** Evidence safely identifies notes.txt, Laporan bulanan.docx, SP-AUDIT-EXTERNAL.txt, and SP-AUDIT-ANONYMOUS.txt, including Guest-specific and anonymous-link semantics, but exact permission IDs/controlled recipient identity are not available for safe revocation.
- **Execution:** No mutation performed. No supported sharing-permission revoke action or live cleanup harness exists in the repository; file deletion was not attempted because it is prohibited. No audit ingestion was awaited.
- **Fixtures:** Preserved without mutation; all four controlled sharing residues remain present/unknown pending operator cleanup.
- **Scope:** Documentation-only blocker record. No collector, database, UX, registration permission, subscription, site, file, ownership, membership, or unrelated sharing changes; no token/credit logging.
- **Files changed:** `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, `docs/evidence/OD-P03C-CONTROLLED-SHARING-FIXTURE-CLEANUP-001.md`

## OD-P03-ONEDRIVE-HIGH-VALUE-AUDIT-DATA-CONTRACT-LOCK-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Lock the production OneDrive Basic high-value audit data contract from OD-P02D-R3 live evidence and documented Microsoft capability.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P03_PASS_WITH_GAPS`
- **Source contract:** Microsoft 365 Management Activity API, `contentType=Audit.SharePoint`, `https://manage.office.com`, application permission `ActivityFeed.Read`; Microsoft Graph Reports capacity remains separate and unchanged.
- **Locked semantics:** `Workload=OneDrive` is the discriminator and `Workload=SharePoint` is excluded. Anonymous `AnonymousLinkCreated` is external/high-value. `SharingInvitationCreated` and `SharingSet` are external only with `TargetUserOrGroupType=Guest`; Member/internal and unknown/ambiguous targets are dropped or fail closed. `FileMalwareDetected` is in scope when encountered, documented-supported but not live-observed.
- **Identity/persistence input:** One immutable event row per tenant plus audit `Id`; `contentId` is transport metadata only. OD-P04 requires append/event history, idempotency, overlap windows, late-arrival safety, nullable optional fields, and no destructive replacement.
- **Gaps:** SecureLinkCreated/AddedToSecureLink correlation is deferred; malware detail fields and event observation remain unproven; numeric overlap/pagination/ordering policy is not locked. No blocker to OD-P04.
- **Scope:** Documentation-only contract lock. No implementation, database change, UX, permission, audit event, sharing, malware test, cleanup, or token/credit logging.
- **Files changed:** `docs/evidence/OD-P03-ONEDRIVE-HIGH-VALUE-AUDIT-DATA-CONTRACT-LOCK-001.md`, `docs/PROJECT_PROGRESS.md`, and this log.

## OD-P02D-R3-AUDIT-BLOB-CONTENT-FIELD-PROOF-001

- **Date:** 2026-08-29
- **Task:** Direct bounded retrieval and safe field/schema proof from surfaced Audit.SharePoint content blobs.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P02D_R3_PASS_WITH_GAPS`
- **Auth/subscription:** Fresh `https://manage.office.com` app-only token passed; `ActivityFeed.Read` present; tenant/app matched; `Audit.SharePoint` present exactly once and enabled.
- **Content:** One bounded listing resolved two entries; both direct blob retrievals returned HTTP 200. Parsed 83 and 88 records (171 total). Newest content was created `2026-08-29T08:19:22.756Z`.
- **Proof:** All four controlled fixtures safely matched. Structured `Guest` target evidence proves specific external sharing; `AnonymousLinkCreated` plus link identity proves anonymous/external semantics; `Workload` and workload-specific `SiteUrl`/`ObjectId` distinguish OneDrive and SharePoint. `Id` was present and unique across the sample.
- **Gaps/scope:** Secure-link operation-pair correlation and `FileMalwareDetected` were not observed. No mutation, database/subscription/permission change, cleanup, persistence, malware test, or token/credit logging occurred. Known shares remain active for separate cleanup.
- **Next action:** Exactly one bounded action: retain this evidence and proceed to OD-P03 using tenant plus audit `Id` deduplication and fail-closed classification.

## OD-P02D-R2-KNOWN-SHARING-SCHEMA-PROOF-001

- **Date:** 2026-08-29
- **Task:** Bounded read-only retrieval attempt for the two known sharing events and live Audit.SharePoint schema proof.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P02D_R2_EVENT_INGESTION_PENDING`
- **Content:** Two newer blob metadata entries surfaced; newest `2026-08-29T08:19:22.756Z`. Complete audit records were not safely validated, so no schema, event operation, classification, OneDrive discriminator, or record-level dedup claim was made.
- **Scope:** No mutation, database/subscription change, cleanup, new share, malware test, persistence, or token/credit logging. Known shares remain active for separate cleanup.
- **Next action:** Exactly one bounded action: retry read-only retrieval of the two surfaced blobs within the same limits and capture field presence only.

## OD-P02D-R1-KNOWN-EXTERNAL-SHARING-AUDIT-PROOF-001

- **Date:** 2026-08-29
- **Task:** Bounded read-only proof of the known controlled external-sharing event.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P02D_R1_EVENT_INGESTION_PENDING`
- **Auth:** Fresh app-only token for `https://manage.office.com`; ActivityFeed.Read present; tenant/app/audience matched. Audit.SharePoint present exactly once and enabled. No token material recorded.
- **Content:** One bounded Audit.SharePoint content blob was listed; `contentCreated=2026-08-29T07:51:21.886Z`, expiration `2026-09-12T07:48:32.071Z`. The matching record was not safely validated from the retrieved output, so no schema or classification claim was made.
- **Scope:** Read-only only; no mutation, database change, subscription change, permission change, cleanup, or malware generation. No token/credit logging.
- **Next action:** Exactly one bounded action: retry the identified blob read-only within the same limits.

## OD-P02D-CONTROLLED-EXTERNAL-SHARING-EVENT-001

- **Date:** 2026-08-29
- **Task:** Attempt the single controlled external-sharing event and bounded Audit.SharePoint ingestion proof.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P02D_TEST_INPUT_REQUIRED`
- **Preflight:** Required project configuration was reviewed without broad repository exploration. It defines logical actor aliases only and explicitly defers runtime UPN resolution; no designated harmless file or external recipient/email is configured. Existing evidence confirms ActivityFeed.Read and an enabled Audit.SharePoint subscription, but those do not identify the authorized mutation inputs.
- **Mutation:** Not attempted. No Graph write, sharing change, file mutation, database change, collector implementation, UX change, or token/credit logging occurred.
- **Blocker:** Missing designated test owner/account, harmless test file and sensitivity confirmation, external recipient/email with tenant-external proof, and supported bounded Graph/user-test mutation path with required authorization.
- **Next action:** Provide the missing designated test inputs and approved mutation path; then perform exactly one bounded event.

## OD-P02C-R1-ONEDRIVE-AUDIT-CONTENT-SCHEMA-PROOF-001

- **Date:** 2026-08-29
- **Task:** Bounded read-only proof of Audit.SharePoint content availability, schema, OneDrive discrimination, and locked event semantics.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P02C_R1_CONTENT_PENDING`
- **Auth:** Fresh app-only token for `https://manage.office.com` returned HTTP 200; ActivityFeed.Read was present and tenant/app/audience matched. No token material was recorded.
- **Subscription:** Audit.SharePoint was present exactly once and enabled.
- **Content probe:** Fresh four-hour listing returned HTTP 200, one page, zero blobs, zero records, zero retries; 24-hour expansion returned HTTP 200, one page, zero blobs, zero records, zero retries. Classified CONTENT_PENDING_AGAIN / CONTENT_EMPTY.
- **Next action:** Exactly one bounded next action recommended: after approval, create one controlled safe external-sharing test event, then rerun this read-only proof.
- **Schema/events:** No blobs or records were downloaded; all locked events and schema/discriminator fields are EVENT_NOT_OBSERVED/UNPROVEN. No full payload was output.
- **Scope:** Read-only bounded API calls only; no collector, database, UX, permission, subscription, file/sharing/malware mutation, persistence, or token/credit logging.

## OD-P02B-AUDIT-SHAREPOINT-SUBSCRIPTION-ACTIVATION-001

- **Date:** 2026-08-29
- **Task:** Activate exactly one pull `Audit.SharePoint` Microsoft 365 Management Activity API subscription and perform a bounded availability probe.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P02B_PASS_CONTENT_PENDING`
- **Auth:** New app-only token for `https://manage.office.com` matched tenant and app, had the correct audience, and contained `ActivityFeed.Read`. No token material was recorded.
- **Subscription:** Pre-state was empty; exactly one `Audit.SharePoint` subscription was started with HTTP 200, API status `enabled`, and no webhook. Post-state contained no other subscription.
- **Content probe:** Four-hour UTC listing probe returned HTTP 500 and was classified `CONTENT_PENDING`; zero blobs downloaded and no schemas inspected.
- **Scope:** No collector, database, UX, webhook, stop operation, other content type, file/sharing/malware mutation, or token/credit logging.

## OD-P02A-ONEDRIVE-AUDIT-PERMISSION-LIVE-ACCEPTANCE-001

- **Date:** 2026-08-29
- **Task:** Re-run the bounded OneDrive high-value audit capability proof after the requested permission grant/consent.
- **Model:** `9router/my_ulti`
- **Result:** `OD_P02A_PASS_WITH_GAPS`
- **Auth:** App-only token acquisition returned HTTP 200; tenant, app identity, audience/resource matched, and `ActivityFeed.Read` was present (`roles_count=1`). No token material was recorded.
- **Management Activity API:** Correct `activity/feed/subscriptions/list` route returned HTTP 200 and an empty subscription list. No `Audit.SharePoint` subscription exists, so content/event/schema proof was not run.
- **Scope:** No subscription start, content retrieval, database change, collector implementation, UX, file/sharing mutation, permission change, or malware test file. No token/credit logging.
- **Next action:** Tenant administrator starts an `Audit.SharePoint` subscription, then rerun the same bounded read-only proof.

## EX-P10-EXCHANGE-BASIC-SEAL-001

- **Date:** 2026-08-29
- **Task:** Formally seal the completed Exchange Basic EX-Pxx workstream and reconcile EX-P06 documentation chronology.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P10_SEALED`
- **Status:** EX-P01 PASS; EX-P02 CLOSED with quarantine architecture/platform boundary proven; EX-P03 through EX-P09 PASS; EX-R01 `PASS_WITH_NON_BLOCKING_FINDING`. Exchange Basic is SEALED / ACCEPTED.
- **EX-P06 reconciliation:** EX-P06 initially recorded BLOCKED at validation; validation subsequently CLOSED/PASS through EX-P06A and later EX-P07B/EX-P08 integration/live evidence. The historical initial result remains unchanged in the evidence, with annotation clarifying the subsequent closure.
- **Supported capability:** mailbox identity/UPN, storage used, mailbox capacity from `prohibit_send_receive_quota`, utilization percentage, LOW/MEDIUM/HIGH/NO_DATA, and report refresh date.
- **Protection boundary:** Spam is BASIC/EOP with `DATA_SOURCE_PENDING`; Quarantine is BASIC/EOP with `ARCHITECTURE_BLOCKED` at the supported platform boundary and is not technical debt; Phishing/Malware/Spoof retain Basic EOP capability while aggregate source is pending and richer Defender telemetry is deferred.
- **Exclusions:** raw Message Trace, per-message lifecycle/event/action, per-user sent/read/received activity, Top Senders, Top Sender Domains, Top Recipients, and Top Source IP remain outside Basic.
- **Accepted evidence:** current rows 30, semantic rows 30, duplicate rows 0, LOW 30, MEDIUM 0, HIGH 0, NO_DATA 0, refresh `2026-08-26`, Mailbox Capacity Risk 0, runtime parity PASS, production API READY, and bounded live Graph acceptance PASS. Counts/timestamp are acceptance evidence, not hardcoded future expectations.
- **Independent review:** EX-R01 concluded no dropped capability, production wiring regression, persistence regression, runtime drift, or deferred feature becoming a production dependency. Its sole finding was NON_BLOCKING EX-P06 documentation-status drift; EX-P10 closes it through chronology reconciliation.
- **Scope:** Documentation/handover only; no production code, tests, UX, feature, service rebuild, or token/credit logging.

## EX-P09-EXCHANGE-ANALYTICS-API-CLOSURE-001

- **Date:** 2026-08-29
- **Task:** Close the Exchange Basic authoritative semantic-layer, Operations analytics/API, Mailbox Capacity Risk KPI, tenant isolation, fail-closed behavior, and live acceptance contract using EX-P08-proven data only.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P09_PASS`
- **Implementation:** Forward-compatible capacity-view columns expose readable `identity_value`/UPN alongside the existing opaque `user_ref`; Operations consumes view-derived utilization/status, exposes report refresh date, and derives the tenant-scoped HIGH count KPI without a duplicate threshold/formula. Legacy activity/item fields remain non-blocking compatibility fields.
- **Live consistency:** Tenant 2 current rows 30, semantic rows 30, unique mailbox keys 30, duplicate rows 0, storage/capacity/refresh mismatches 0, utilization/threshold mismatches 0; latest refresh `2026-08-26`; LOW 30, MEDIUM 0, HIGH 0, NO_DATA 0.
- **API acceptance:** Production `operations-api` returned READY over the in-network read-only path. Exchange summary/detail contract returned LOW 30, MEDIUM 0, HIGH 0, NO_DATA 0, refresh `2026-08-26`, risk 0, and 30 detail rows with readable identity, storage, capacity, utilization, usage level, and refresh date.
- **Validation:** Focused analytics/API/production-path suite passed 41 tests with 1 unavailable-PostgreSQL skip; compile validation passed; runtime parity PASS for all five required modules; operations-api rebuilt/recreated only after code change.
- **Scope:** No UX, Graph collection, new source, protection feature, message trace, Defender telemetry, or token/credit logging. Existing protection gaps remain deferred/non-blocking.

## EX-P08-EXCHANGE-BOUNDED-LIVE-ACCEPTANCE-001

- **Date:** 2026-08-29
- **Task:** Perform one bounded live Microsoft Graph acceptance for the locked Exchange Basic USAGE-003 path.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P08_PASS`
- **Runtime:** `graph-agent-collector-dev` and healthy `graph-agent-operations-api-dev`; authoritative database `graph_agent` / `graph_agent_runtime`; parity PASS for all five required production modules after recreating only `operations-api`.
- **Live collection:** Exactly one native `python -m collectors.run_collector --endpoint USAGE-003` run with the `Reports.Read.All` gate. PASS, one page, 30 source rows, 30 normalized/persisted rows, zero retries, refresh `2026-08-26`.
- **Acceptance:** Current remained 30 unique rows with populated identity/storage/authoritative quota and no invalid values. Snapshot remained 120 rows across four generations (`2026-08-23` through `2026-08-26`) with no duplicate generation. Analytics remained 30 rows, all LOW, and agreed with persistence and locked utilization semantics. No synthetic residue, cross-tenant rows, partial replacement, schema drift, or runtime retry loop observed; audit/status was PASS/SUCCESS.
- **Regression:** Focused Exchange usage-report, runtime, and production-path tests passed 36 tests; final runtime parity PASS.
- **Scope:** No UX, new feature, protection telemetry, message trace, analytics redesign, or token/credit logging. Protection-source gaps from EX-P03 remain non-blocking.

## EX-P07B-NEGATIVE-PATH-INTEGRATION-MATRIX-001

- **Date:** 2026-08-29
- **Task:** Complete the Exchange production-path negative integration matrix and tenant isolation proof.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P07B_PASS`
- **Validation:** Real CollectorRuntime USAGE-003 path covered incomplete, duplicate, stale, repeated generation, identity/date schema failures, retry success/exhaustion, and isolated same-identity tenants. Focused integration/usage tests passed 29 tests; compile validation passed. Test-only changes; no production rebuild.
- **Environment:** Live tenant protection and runtime parity were not re-run because this environment lacked live database credentials/services; synthetic tests used isolated tenant IDs only.
- **Scope:** No UX, new feature, analytics redesign, or token/credit logging.

## EX-P07-EXCHANGE-PRODUCTION-PATH-INTEGRATION-001

- **Date:** 2026-08-29
- **Task:** Validate the complete Exchange USAGE-003 path with a bounded fake Graph source and production internal components.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P07_BLOCKED`
- **Validation:** Added a real-runtime/database integration fixture with LOW, MEDIUM, HIGH, and NO_DATA rows. Focused production-container runtime suite passed 33 tests; host compile and runtime parity passed. Tenant 2 remained at current 30, snapshots 120, latest refresh 2026-08-26, with no synthetic residue.
- **Blocker:** The new DB-backed integration test is reported as an error by the container unittest runner without an available traceback, and the complete negative-path matrix remains outstanding. No broad live Graph acceptance was performed.
- **Scope:** No UX, new API source, protection feature, analytics redesign, or token/credit logging.

## EX-P06-EXCHANGE-DATA-HANDLING-HARDENING-001

- **Date:** 2026-08-29
- **Task:** Harden Exchange USAGE-003 transport, generation safety, schema handling, and failure classification.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P06_BLOCKED`
- **Changes:** Added bounded usage-report retry handling with Retry-After propagation, terminal retry exhaustion classification, fail-closed refresh-date validation, and a forward-generation current-state persistence gate. Existing completeness, duplicate rejection, transaction safety, numeric NULL semantics, and empty-report no-op were preserved.
- **Validation:** Python module compilation passed. Focused unittest/container validation and runtime parity remain blocked by the available execution environment/test setup; no broad live Graph acceptance was performed.
- **Scope:** No UX, new API source, protection feature, analytics redesign, or token/credit logging.

## EX-P05-EXCHANGE-COLLECTOR-NORMALIZATION-WIRING-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Validate production Exchange USAGE-003 collector, normalization, completeness propagation, persistence wiring, and packaging.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P05_PASS`
- **Validation:** Corrected Exchange identity fail-closed behavior for missing UPN and propagated `complete` into usage persistence. Focused production-container suite passed 33 tests; compileall passed; runtime parity matched all five checked modules after rebuild/recreate.
- **Live check:** Bounded native `USAGE-003` run via `graph-agent-collector-dev` with `Reports.Read.All` returned 30 source/normalized/persisted rows, one page, and PASS. No synthetic business rows were committed.
- **Scope:** No UX, new API source, protection feature, analytics redesign, or token/credit logging.

## EX-P04B-EXCHANGE-PERSISTENCE-PRODUCTION-PROOF-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Prove EX-P04A Exchange persistence safety through the deployed runtime and authoritative database path.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P04B_PASS`
- **Runtime:** `operations-api` rebuilt/recreated only after parity mismatch; required production-module parity then passed. Collector/runtime persistence code was exercised from the collector container.
- **Database:** Confirmed `graph_agent` / `graph_agent_runtime`, tenant 2; baseline current 30 and snapshot 90, latest refresh 2026-08-25. No credentials recorded.
- **Safety:** Incomplete reports and normalized case-folded duplicate business keys rejected before SQL; empty reports no-op; repeated complete generation created no duplicate snapshot. Synthetic writes were rollback-only and baseline hashes/counts were preserved.
- **Integrity:** Current 30 rows / 30 unique keys / zero duplicates, nulls, or invalid numeric values; snapshot generations preserved; analytics view 30 rows, LOW 30, compatibility PASS.
- **Fixture issue:** Focused production-path persistence/runtime suite passed 30 tests; no unrelated fixture failure was encountered in this run.
- **Scope:** Validation/documentation only; no UX, API source, schema, analytics, Graph calls, or business-data contamination. No token/credit logging.

## EX-P04A-EXCHANGE-PERSISTENCE-SAFETY-CORRECTION-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Correct Exchange persistence safety defects from EX-P04.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P04A_PASS`
- **Corrections:** Complete acquisition is required before destructive current replacement; normalized duplicate `(tenant_id, entity_key)` source rows fail before SQL writes; current/snapshot transaction boundary remains atomic.
- **Validation:** Focused usage-report tests added; numeric normalization assertion reconciled to integer `10`. Live acceptance and deployed runtime parity are deferred to EX-P04B.
- **Scope:** Persistence safety only; no UX, API, schema, analytics, quota, threshold, or historical snapshot redesign. No token/credit logging.

## EX-P03-EXCHANGE-BASIC-DATA-CONTRACT-LOCK-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Lock the canonical Exchange Basic DATA contract before persistence/data-handling reconciliation.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P03_PASS`
- **Decision:** Locked mailbox identity/UPN, storage_used, mailbox_capacity from `prohibit_send_receive_quota`, utilization, LOW/MEDIUM/HIGH/NO_DATA, and report_refresh_date with source, datatype, grain, authority, null, and timestamp semantics.
- **Capacity:** Utilization is `storage_used / mailbox_capacity * 100`; thresholds are `<50 LOW`, `>=50 and <80 MEDIUM`, `>=80 HIGH`; invalid/missing required values or non-positive capacity produce `NO_DATA`. Send/Receive Quota and license inference are prohibited; Last Activity is not refresh time.
- **Protection gaps:** Spam Filtered is `BASIC/EOP` and `DATA_SOURCE_PENDING`; Quarantine is `BASIC/EOP` and `ARCHITECTURE_BLOCKED` because supported app-only authorization/API is unavailable; Phishing, Malware, and Spoof retain Basic EOP capability while richer Defender telemetry is separate and current aggregate sources are `DATA_SOURCE_PENDING`.
- **Exclusions:** Raw Message Trace, per-message lifecycle/event/action, per-user sent/read/received activity, Top Senders, Top Sender Domains, Top Recipients, and Top Source IP are `EXCLUDED_BY_SCOPE`.
- **Path:** Graph usage report → collector → normalization → `core.usage_exchange_mailbox_usage` → `core.usage_exchange_mailbox_usage_snapshot` → `analytics.exchange_mailbox_capacity`.
- **Files changed:** `docs/evidence/EX-P03-EXCHANGE-BASIC-DATA-CONTRACT-LOCK-001.md`, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`.
- **Scope:** Documentation-only architecture lock. No UX, collector, permission, API discovery, token, or credit work.
- **Next required task:** `EX-P04 persistence/current/history reconciliation`

## EX-P02C-QUARANTINE-ARCHITECTURE-CLOSURE-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Close EX-P02 quarantine capability investigation with the final supported-platform decision.
- **Model:** `9router/my_ulti`
- **Result:** `EX_P02C_PASS`
- **Quarantine:** `service_capability=BASIC/EOP`; `collector_status=ARCHITECTURE_BLOCKED`; `blocker_type=SUPPORTED_PLATFORM_BOUNDARY`; `technical_debt=NO`.
- **Decision:** Exchange Online PowerShell app-only authentication supports `Exchange.ManageAsApp`, but it does not itself authorize quarantine access. Read-only quarantine authorization is documented for Security Reader, Global Reader, or Security Operator user/admin access; no documented supported service-principal authorization model exists for `Get-QuarantineMessage`. Exchange custom RBAC quarantine permissions are obsolete/unsupported, and no documented GA Exchange Admin API quarantine endpoint is available. Undocumented/Preview workarounds are excluded.
- **Future reopen condition:** Microsoft provides a supported app-only quarantine authorization/API, or the project explicitly approves delegated-user collection.
- **Correction:** The earlier `EX-P02 BLOCKED_AUTH` wording is superseded; quarantine is architecture-blocked at the supported-platform boundary, not unfinished implementation or technical debt.
- **Files changed:** `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, `docs/evidence/EX-P02A-BASIC-PROTECTION-SCOPE-CLOSURE-001.md`
- **Scope:** Documentation/handover only. No implementation, UX, tenant mutation, app, certificate, permission, Entra role, or PowerShell adapter changes.


## STD-20-BASIC-FEATURE-CLOSURE-PREFLIGHT-001

- **Date:** 2026-08-29
- **Project:** graph-agent
- **Task:** Final closure preflight for the locked Basic Feature / Standard track.
- **Model:** `9router/my_ulti`
- **Result:** `STD_20_PREFLIGHT_BLOCKED`
- **Validation:** Runtime parity PASS; Compose services running with operations API/UI and PostgreSQL healthy; focused unittest suite PASS (45 tests). Production KPI, Exchange, OneDrive, SharePoint sites, and license-utilization boundaries returned HTTP 200/READY. SharePoint user-adoption returned HTTP 200 but `DATA_DEPENDENCY_UNAVAILABLE`.
- **UI finding:** Overview card labels and drilldown source contracts are present, but the main dashboard HTML has no `#workloads` mount and `start()` does not invoke `renderWorkloads()`, so Usage Overview workload cards are not proven rendered. Final OneDrive source columns are present in `renderDetail()`.
- **Classification:** BLOCKING: SharePoint user-usage API dependency unavailable; Usage Overview dashboard wiring/rendering gap. NON_BLOCKING: none established. DEFERRED: all explicitly excluded Basic/Standard scopes.
- **Files changed:** `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, `docs/evidence/STD-20-BASIC-FEATURE-CLOSURE-PREFLIGHT-001.md`
- **Scope:** Validation/documentation only. No production source, permissions, schema, feature, or deferred-scope changes; no token/credit logging.

## STD-15K1A-DASHBOARD-DRILLDOWN-USABILITY-REFINEMENT-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Refine Exchange, OneDrive, and SharePoint drilldown usability.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15K1A_PASS`
- **Files changed:** `operations-ui/public/app.js`, `operations-ui/public/styles.css`, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, `docs/evidence/STD-15K1A-DASHBOARD-DRILLDOWN-USABILITY-REFINEMENT-001.md`
- **Validation:** `operations-ui` rebuilt/recreated; deployed UI HTTP 200; runtime parity PASS; static asset check passed for controls/formatters. Node/QuickJS syntax executables unavailable in host/container. No backend/API/SQL/collector changes. Browser acceptance deferred to STD-15K1B.
- **Scope:** Exchange/OneDrive/SharePoint presentation formatting, technical-column removal, search, filter integration, and 25/50/100 pagination.

## STD-15K1B-SHAREPOINT-AND-SKU-UI-CLEANUP-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Remove the redundant SharePoint usage mini menu and correct SharePoint storage and Assigned SKU rendering.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15K1B_PASS`
- **Files changed:** `operations-ui/public/app.js`, `operations-ui/public/index.html`, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`, `docs/evidence/STD-15K1B-SHAREPOINT-AND-SKU-UI-CLEANUP-001.md`
- **Scope:** Frontend-only; no analytics, API, database, migration, SQL view, collector, or KPI semantic changes. Browser acceptance deferred to STD-15K1C.

## STD-15H5-ONEDRIVE-CAPACITY-UI-IMPLEMENTATION-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Replace OneDrive activity presentation with API-authoritative capacity overview and drilldown.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H5_PASS`
- **Files changed:** `operations-ui/public/app.js`, `docs/AI_USAGE_LOG.md`
- **Validation:** UI image rebuilt/recreated; UI HTTP 200; deployed app.js contains capacity usage, human-readable storage, and capacity drilldown fields. Node syntax check unavailable because node is not installed. Backend unchanged.
- **Live contract values:** LOW 26, MEDIUM 0, HIGH 0, NO_DATA 0; refresh `2026-08-25`; aggregate storage `113932223` bytes rendered human-readable; files `156`.
- **Scope:** OneDrive UI only; no analytics/API, SQL, persistence, Exchange, SharePoint, browser harness, or token/credit logging.

## STD-15H4-ONEDRIVE-CAPACITY-API-WIRING-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Wire OneDrive analytics/API to the authoritative capacity view.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H4_BLOCKED`
- **Files changed:** `analytics/operations.py`
- **Validation:** Python compile passed; pytest unavailable because the environment has no pytest module. Runtime/API acceptance was not run.
- **Scope:** OneDrive only; no UI, Exchange, SharePoint, SQL view, raw persistence, browser tests, or token/credit logging.

## STD-15H3-ONEDRIVE-CAPACITY-SEMANTIC-VIEW-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Create and live-validate the authoritative OneDrive account capacity semantic SQL view.
- **Model:** `9router/my_ulti`
- **Purpose:** `ONEDRIVE_CAPACITY_SEMANTIC_LAYER`
- **Result:** `STD_15H3_PASS`
- **Files changed:** `database/migrations/016_onedrive_account_capacity.sql`, `docs/evidence/STD-15H3-ONEDRIVE-CAPACITY-SEMANTIC-VIEW-001.md`, `docs/PROJECT_PROGRESS.md`, `docs/PROJECT_FILE_MAP.md`, and this log.
- **Validation:** Migration applied to `graph_agent`; view exists with 26 rows matching the authoritative source, zero duplicate `(tenant_id, entity_key)` accounts, and zero storage/refresh preservation mismatches. Threshold cases 49.99/50/79.99/80/null/zero classified LOW/MEDIUM/MEDIUM/HIGH/NO_DATA/NO_DATA. Live distribution LOW 26, MEDIUM 0, HIGH 0, NO_DATA 0; reconciliation equals 26.
- **Scope:** OneDrive only; no API/UI/Python changes, no Exchange/SharePoint changes, no raw persistence changes, no browser tests, and no token/credit logging.

## STD-15H4A-ONEDRIVE-CAPACITY-API-ACCEPTANCE-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Validate OneDrive capacity API wiring, runtime parity, and live view reconciliation.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H4A_BLOCKED`
- **Files changed:** `docs/AI_USAGE_LOG.md`, `docs/PROJECT_PROGRESS.md`
- **Validation:** Focused unittest run completed with 4 failures (3 stale base-table OneDrive expectations and 1 unrelated numeric-normalization expectation); no pytest installed or used. Operations API rebuilt/recreated. Runtime parity PASS for all required production modules. SQL view live state PASS: 26 rows, LOW 26, MEDIUM 0, HIGH 0, NO_DATA 0; aggregate storage 113932223, file count 156, refresh date 2026-08-25.
- **Live API:** Endpoint returned `DATA_DEPENDENCY_UNAVAILABLE` with no data payload, so account detail and view/API reconciliation could not be accepted.
- **Scope:** OneDrive only; no UI, browser tests, Exchange, SharePoint, SQL view, dependency installation, or token/credit logging.

## STD-15H4A-ONEDRIVE-CAPACITY-API-ACCEPTANCE-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Acceptance validation of STD-15H4 OneDrive capacity API wiring.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H4A_BLOCKED`
- **Validation:** `python3 -m unittest tests.analytics.test_operations tests.analytics.test_operations_api tests.usage_reports.test_usage_reports` ran 57 tests: 52 passed, 1 skipped, 4 failed. Rebuilt/recreated `operations-api`; `python3 scripts/check_runtime_parity.py` PASS. Direct SQL view reconciliation PASS with 26 rows, LOW 26, MEDIUM 0, HIGH 0, NO_DATA 0, report refresh `2026-08-25`, storage `113932223`, file count `156`.
- **API blocker:** `GET /api/operations/adoption/onedrive` returned `DATA_DEPENDENCY_UNAVAILABLE` despite database health and view availability; required API fields and row-level reconciliation could not be verified.
- **Scope:** OneDrive only; no UI, browser tests, Exchange, SharePoint, SQL view, dependency installation, or token/credit logging.

## STD-15H4D-ONEDRIVE-CAPACITY-API-LIVE-ACCEPTANCE-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Live acceptance of OneDrive capacity API and migration 017.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H4D_PASS`
- **Files changed:** `docs/AI_USAGE_LOG.md`, `docs/PROJECT_PROGRESS.md`
- **Migration:** 017 applied; view exists with `user_ref`; migration state recorded; runtime SELECT passed; view rows 26 matching authoritative current rows; LOW 26, MEDIUM 0, HIGH 0, NO_DATA 0.
- **Runtime/API:** operations-api recreated; health READY; runtime parity PASS; endpoint HTTP 200 READY with 26 account details.
- **API contract:** all details contain required identity/capacity fields; LOW/MEDIUM/HIGH/NO_DATA reconcile to 26; `data_last_refreshed=2026-08-25`.
- **View/API:** representative user_ref, utilization, and usage_level match SQL view; aggregate storage `113932223`, file count `156`, and utilization preserved.
- **Scope:** OneDrive only; no UI, Exchange, SharePoint, thresholds, migration edits, browser tests, dependency installation, unrelated numeric-normalization work, or token/credit logging.

## STD-15H4C-ONEDRIVE-VIEW-CONTRACT-FIX-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Forward-only correction of the OneDrive analytical view contract.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H4C_PASS`
- **Files changed:** `database/migrations/017_onedrive_account_capacity_user_ref.sql`, `tests/analytics/test_operations.py`, `tests/database/test_migrations.py`, and this log.
- **Validation:** OneDrive analytics and migration tests pass; runtime parity and Python compilation pass. The unrelated numeric-normalization test remains unchanged and fails because it expects `"10"` rather than `10`.
- **Scope:** OneDrive only; no UI, Exchange, SharePoint, live acceptance, browser tests, or token/credit logging.

## STD-15H5G-ONEDRIVE-UI-FINAL-BROWSER-ACCEPTANCE-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Final browser acceptance of deployed OneDrive capacity UI.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H5G_PASS`
- **Validation:** Runtime parity PASS; UI HTTP 200; OneDrive API HTTP 200/READY with 26 account details. Isolated Playwright/Chromium PASS at 1440x900 and 390x844; JavaScript executed with no console errors, page errors, or failed requests.
- **Acceptance:** Overview LOW 26, MEDIUM 0, HIGH 0, NO DATA 0; refresh 2026-08-25; storage rendered human-readable as 108.65 MB; files 156. Drilldown 26 rows, readable identities, required columns, LOW 26, MEDIUM/HIGH/NO DATA 0, utilization matched API, and narrow horizontal overflow usable.
- **Files changed:** `docs/evidence/STD-15H5G-ONEDRIVE-UI-FINAL-BROWSER-ACCEPTANCE-001.md`, `docs/PROJECT_PROGRESS.md`, and this log.
- **Scope:** OneDrive UI only; no backend/API, SQL view, Exchange, SharePoint, cosmetic redesign, unrelated numeric-normalization work, or token/credit logging.

## STD-15H5A-ONEDRIVE-CAPACITY-UI-LIVE-ACCEPTANCE-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Real-browser acceptance of deployed OneDrive capacity UI.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H5A_BLOCKED`
- **Validation:** Runtime parity PASS; operations UI HTTP 200; OneDrive API HTTP 200/READY. Isolated Chromium executed JavaScript with no console errors, page errors, request failures, or failed operations API responses at 1440x900 and 390x844. Rebuilt only operations-ui to ensure deployment parity; served app.js hash matched host.
- **Browser findings:** OneDrive overview rendered capacity fields unavailable, Files as `[object Object]`, and drilldown rendered 0 rows with all filters 0, despite API READY and 26 account details. Narrow table overflow was present. This is a real OneDrive UI defect; no source correction was made within this bounded acceptance.
- **Scope:** OneDrive UI only; no backend, SQL view, Exchange, SharePoint, cosmetic redesign, dependency installation into production, unrelated numeric-normalization work, or token/credit logging.

## STD-15H5D-ONEDRIVE-UI-BROWSER-RERUN-001

- **Date:** 2026-08-28
- **Project:** graph-agent
- **Task:** Browser rerun of deployed OneDrive capacity UI.
- **Model:** `9router/my_ulti`
- **Result:** `STD_15H5D_BLOCKED`
- **Validation:** Runtime parity PASS; UI and health HTTP 200; OneDrive API HTTP 200/READY. Isolated Chromium ran at 1440x900 and 390x844 after deterministic wait for 26 OneDrive account details. No console errors, page errors, or request failures.
- **Findings:** OneDrive buckets/date and usage summary rendered unavailable/zero, and drilldown rendered 0 rows despite accepted API state (LOW 26, 26 details, storage 113932223 bytes, files 156, refresh 2026-08-25). Total Storage was human-readable (108.65 MB) and Files 156; narrow table overflow was measurable. This remains a OneDrive UI defect; no source correction was made.
- **Evidence:** `docs/evidence/STD-15H5D-ONEDRIVE-CAPACITY-UI-BROWSER-RERUN-001.md`
- **Scope:** OneDrive UI only; no backend, API, SQL, Exchange, SharePoint, cosmetic redesign, unrelated numeric-normalization work, or token/credit logging.
