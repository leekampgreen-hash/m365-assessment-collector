# STD-07 SharePoint Basic Contract Discovery

- **Task ID:** `STD-07-SHAREPOINT-BASIC-CONTRACT-001`
- **Date:** 2026-08-27
- **Project:** graph-agent
- **Role:** CONTRACT_AND_WIRING_DISCOVERY
- **Purpose:** Define the minimal SharePoint Standard usage contract that reuses
  the existing, accepted usage-report infrastructure (Reports.Read.All gate,
  usage transport, normalization, current/snapshot persistence, analytics,
  generic API, runtime-parity safeguard). This is a contract/wiring discovery
  only; no SharePoint KPI implementation, migrations, permissions, sharing
  analysis, or Graph writes are introduced here.
- **Result:** `STD_07_CONTRACT_PASS`; `IMPLEMENTATION_READY=YES`.

## Authoritative SharePoint scope (locked)

**Smallest contract:** the two-report pair `USAGE-006`
(`sharepoint_user_activity` / `getSharePointActivityUserDetail`, period `D7`
default) and `USAGE-007` (`sharepoint_site_usage` /
`getSharePointSiteUsageDetail`, period `D7` default). Both already exist in
`config/api_inventory.json`, the usage-report registry, adapters, transport,
persistence mapping, DB schema, and the generic collection path. They declare
`Reports.Read.All`, application auth, and `transport_type=USAGE_REPORT_CSV`.
Neither report alone satisfies the locked scope: per-user active/activity
evidence lives in `USAGE-006`, while site storage, file count, and allocated
capacity live only in `USAGE-007`.

### In scope

- **Active sites** (from `USAGE-007` evidence only):
  `usage_sharepoint_site_usage` rows that are not deleted and have a non-empty
  `last_activity_date`. No file-count or activity-count threshold semantics are
  invented.
- **Active users** (from `USAGE-006` evidence only):
  `usage_sharepoint_user_activity` rows that are not deleted and have a non-empty
  `last_activity_date`. No viewed/synced threshold semantics are invented.
- **Last activity** (`last_activity_date`, max over the active set).
- **Total storage used** (`storage_used`, summed across the current
  `usage_sharepoint_site_usage` report set).
- **Total file count** (`file_count`, summed across the current
  `usage_sharepoint_site_usage` report set).
- **Storage utilization**, directly supported by the standard report:
  `storage_used / storage_allocated` (per site and aggregate), because
  `getSharePointSiteUsageDetail` exposes both `Storage Used (Byte)` and
  `Storage Allocated (Byte)` in the locked report schema (same shape as the
  accepted OneDrive `USAGE-005` contract).

### Out of scope (explicitly excluded, do not collect or surface)

- site permission analysis;
- oversharing / external-sharing investigation;
- shared-internal/shared-external file counts (`internal_share_count`,
  `external_share_count` on user rows);
- file-level / per-file inventory;
- DLP / Purview;
- Defender / security posture;
- advanced analytics.

### KPI source rule

SharePoint basic KPIs must be derived from `usage_sharepoint_site_usage` and
`usage_sharepoint_user_activity` evidence only (per the semantics above). The
existing `analytics/operations.py::sharepoint_user_adoption()` derives active
users via the generic `_adoption()` using `_evidence_status()` on
`sharepoint_user_activity`, which for that workload falls back to
`viewed_count`/`edited_count`/`synced_count`/`page_view_count` counts when
`last_activity_date` is absent. That activity-count fallback is OUT of the
locked STD-07 scope; the STD-07 KPI derivation must use `last_activity_date`
presence on non-deleted rows only. There is currently no site-level
(`sharepoint_site_usage`) analytics method or API route; both are identified as
missing SharePoint-specific implementation (see MISSING_COMPONENTS).

## REPORT_CONTRACT

- **endpoints:**
  - `USAGE-006` — `GET /v1.0/reports/getSharePointActivityUserDetail(period='D7')`
  - `USAGE-007` — `GET /v1.0/reports/getSharePointSiteUsageDetail(period='D7')`
- **permission:** `Reports.Read.All` (application auth), shared fail-closed
  capability gate via `--granted-graph-permissions`.
- **reporting_period:** `D7` default (approved periods `D7/D30/D90/D180`);
  period is part of the canonical function path, never a query param.
- **source_fields → canonical_fields (USAGE-006 / user):**
  | Source column | Canonical persisted field |
  |---|---|
  | `User Principal Name` | `entity_key` / `identity_value` (lowercased entity_key, case-insensitive UPN pick) |
  | `Is Deleted` | `is_deleted` |
  | `Last Activity Date` | `last_activity_date` |
  | `Viewed Or Edited File Count` | `viewed_count` (legacy, not KPI source) |
  | `Synced File Count` | `synced_count` (legacy, not KPI source) |
  | `Shared Internally File Count` | `internal_share_count` (excluded from scope) |
  | `Shared Externally File Count` | `external_share_count` (excluded from scope) |
  | `Visited Page Count` | `page_view_count` (legacy, not KPI source) |
  | `Report Refresh Date` | `report_refresh_date` |
- **source_fields → canonical_fields (USAGE-007 / site):**
  | Source column | Canonical persisted field |
  |---|---|
  | `Site Id` | `entity_key` |
  | `Site URL` | `site_url` |
  | `Owner Display Name` | `display_name` |
  | `Last Activity Date` | `last_activity_date` |
  | `Storage Used (Byte)` | `storage_used` |
  | `Storage Allocated (Byte)` | `storage_allocated` |
  | `Total File Count` | `file_count` |
  | `Root Web Template` | `site_template` |
  | `Is Deleted` | `is_deleted` |
  | `Report Refresh Date` | `report_refresh_date` |
- Both reports share the common base columns: `tenant_id`, `entity_key`,
  `report_refresh_date`, `identity_value`, `identity_is_masked`,
  `last_activity_date`, `site_url`, `display_name`, `is_deleted`,
  `observed_at`, plus the numeric columns in `BASE_COLUMNS`.

## KPI_CONTRACT

- **active_sites:** non-deleted `usage_sharepoint_site_usage` rows with a
  non-empty `last_activity_date` (USAGE-007 evidence only).
- **active_users:** non-deleted `usage_sharepoint_user_activity` rows with a
  non-empty `last_activity_date` (USAGE-006 evidence only; no viewed/synced
  threshold).
- **latest_activity:** max `last_activity_date` over the active set.
- **total_storage_used:** sum of `storage_used` across the current
  `usage_sharepoint_site_usage` set.
- **total_file_count:** sum of `file_count` across the current
  `usage_sharepoint_site_usage` set.
- **storage_utilization:** `storage_used / storage_allocated` (aggregate over
  the current site set; fails closed to `None` for zero/missing allocation),
  directly supported by the locked report schema.

## REUSE (all verified present and accepted)

- **transport:** `collectors/usage_reports/transport.py` `UsageReportTransport`
  handles the 302 → allowlisted reports host redirect for CSV; reused unchanged.
- **normalization:** `collectors/usage_reports/registry.py::normalize_report_rows`
  already handles `sharepoint_user_activity` and `sharepoint_site_usage`
  (spec, alias, identity, metric-name mapping all present); adapter entry points
  exist in `collectors/usage_reports/adapters.py`.
- **persistence:** `collectors/usage_reports/persistence.py::write_report_rows`
  maps both SharePoint keys to `core.usage_sharepoint_user_activity[_snapshot]`
  and `core.usage_sharepoint_site_usage[_snapshot]`; current `DELETE + INSERT`
  + snapshot idempotent append contract is live-proven (migration `013` grants
  DELETE on all seven current usage tables including both SharePoint tables).
- **permission_gate:** `Reports.Read.All` fail-closed capability gate
  (accepted and live-proven via STD-04/STD-06).
- **analytics:** `analytics/operations.py` already registers both SharePoint
  usage tables and exposes `sharepoint_user_adoption()`; user-level KPI source
  must be tightened to the locked last-activity semantics in STD-07B.
- **api:** `api/operations.py` already routes `/api/operations/adoption/sharepoint`
  to `sharepoint_user_adoption()`. A site-level route
  `/api/operations/adoption/sharepoint-site` (or equivalent) does NOT yet exist
  and is the primary missing API surface.
- **runtime_parity:** `scripts/check_runtime_parity.py` provides the host-to-runtime
  hash gate; required before any SharePoint live acceptance (STD-08).

## MISSING_COMPONENTS (SharePoint-specific only)

1. **Site-level KPI derivation:** a `sharepoint_site_adoption()` (or equivalent)
   method in `analytics/operations.py` emitting the six locked site KPIs
   (active_sites, active_users where site-based, latest_activity,
   total_storage_used, total_file_count, storage_utilization) grounded strictly
   in `usage_sharepoint_site_usage`.
2. **User-level KPI source tightening:** adjust `sharepoint_user_adoption()`
   so `active_users` derives only from non-deleted `sharepoint_user_activity`
   rows with a non-empty `last_activity_date`, removing the generic
   `_evidence_status()` viewed/edited/synced/page-view fallback for the locked
   basic scope.
3. **Site KPI API route:** add a read-only site-adoption route in
   `api/operations.py` mirroring the accepted OneDrive/Exchange adoption route
   shape.
4. **Offline tests:** add focused analytics + API tests for the site KPI
   derivation (deleted/missing-activity filtering, zero/missing-allocation
   fail-closed utilization) and the tightened user semantics.

No migration, no DB schema change, no permission grant, no Graph write, and no
sharing/permission analysis is required.

## DB_REDESIGN_REQUIRED

**NO.** Existing `core.usage_sharepoint_site_usage[_snapshot]` and
`core.usage_sharepoint_user_activity[_snapshot]` tables (migration `008`) already
carry every canonical field required by the locked scope: `entity_key`,
`site_url`, `display_name`, `last_activity_date`, `storage_used`,
`storage_allocated`, `file_count`, `is_deleted`, `report_refresh_date`,
`observed_at`. No column, constraint, grant, or table change is needed.

## IMPLEMENTATION_READY

**YES.** The contract is fully grounded in accepted, live-proven shared
infrastructure. Only the SharePoint-specific KPI derivation, API route, and
focused tests listed under MISSING_COMPONENTS remain, to be delivered by
`STD-07B-SHAREPOINT-BASIC-IMPLEMENTATION-001`.

## Safety

No tenant permissions changed, no Graph writes, no migrations, no DB grants, no
credentials, no sharing/oversharing implementation, no SharePoint KPI logic
implemented. This task is documentation/contract-only: it produced this evidence
document, the authoritative PROJECT_PROGRESS scope record, and the activity-log
record.

## Scope accounting

Documentation-only contract discovery. No production Python, database migration,
inventory, permission, credential, Entra, or Graph behavior was changed.
