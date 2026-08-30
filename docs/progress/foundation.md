# Foundation Progress

G01, CH, and Standard Version shared progress (STD-01 through STD-15).

## API-P01 Operations API endpoint completion (PASS)

API-P01 PASS — Added missing endpoints:

- GET /api/operations/sharepoint/tenant-settings
- GET /api/operations/license/expiry
- 1300/1300 PASS, parity PASS

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
