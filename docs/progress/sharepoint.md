# SharePoint Progress

SharePoint phases and related SharePoint Standard progress.

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

### STD-08 SharePoint Basic live acceptance rerun (PASS)

The independent bounded native rerun completed after the STD-08A site identity correction. Runtime parity ran first and passed. With `Reports.Read.All`, USAGE-006 returned 30 rows and USAGE-007 returned 12 rows; both normalized and persisted successfully. Without the permission, both endpoints returned `SKIP_PERMISSION_REQUIRED` with zero rows and no Graph or persistence activity.

The canonical Site Id produced 12 distinct site `entity_key` values despite blank Site URLs. Identity-less rows still fail closed as `ENTITY_IDENTITY_UNAVAILABLE`. API and DB agree for tenant 2: active_users 24, active_sites 3, latest_activity 2026-06-26, total_storage_used 36964667, total_file_count 43, storage_utilization 1.1206389596433534e-07. Active status is grounded only in non-deleted rows with non-empty `last_activity_date`; viewed/synced/page-view thresholds are not used.

- **Evidence:** `docs/evidence/STD-08-SHAREPOINT-BASIC-LIVE-ACCEPTANCE-001.md`.
- **Status:** `STD_08_PASS`; SharePoint Basic `ACCEPTED`.
- **Next:** `STD-09-LICENSE-INVENTORY-BASELINE-001`.
