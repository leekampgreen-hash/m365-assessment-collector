# STD-14 Standard API Contract Evidence

- **Task ID:** `STD-14-STANDARD-API-CONTRACT-001`
- **Category:** `ARCHITECTURE / INTEGRATION-WIRING`
- **Role:** `API_GAP_ASSESSMENT`
- **Purpose:** Define the minimal Standard Version read-only API surface for dashboard consumption and identify only real implementation gaps before dashboard work.
- **Result:** `STD_14_CONTRACT_PASS`
- **Implementation required:** `NO` (all required Standard product functions map to existing accepted read-only routes; no real API implementation gap).

## 1. Context (accepted contracts reused, not rediscovered)

- Four workload basics (`STD-03/04 Exchange`, `STD-05/06 OneDrive`, `STD-07/08 SharePoint`, `STD-02 User`): **ACCEPTED**.
- License inventory (`STD-09`) and user↔license mapping (`STD-10`): **ACCEPTED**.
- Cross-workload correlation (`STD-12/12C`): **ACCEPTED**; `cross_workload_user_status()` implemented.
- Standard KPI Engine (`STD-13/13B/13C`): **ACCEPTED**; `standard_kpi_summary()` + `GET /api/operations/kpi` live-proven.

This task does not redefine KPI/correlation/workload semantics. It inventories the existing read-only API and maps each required Standard product function to an existing route.

## 2. Existing read-only Standard-version API routes (inventory)

All under `api/operations.py` (`OperationsApiHandler`, GET only), analytics owned by `analytics/operations.py::OperationsAnalyticsQueryService`:

| Route | Handler method | Read-only | Tenant-scoped | Response envelope |
|---|---|---|---|---|
| `/api/operations/kpi` | `standard_kpi_summary()` | GET | yes | `_response(status, data, quality=...)` |
| `/api/operations/correlation/users` | `cross_workload_user_status()` | GET | yes | `_response` |
| `/api/operations/summary` | `tenant_summary` + adoption + `license_utilization` | GET | yes | `_response` (legacy composite) |
| `/api/operations/adoption/exchange` | `exchange_adoption()` | GET | yes | `_response` |
| `/api/operations/adoption/onedrive` | `onedrive_adoption()` | GET | yes | `_response` |
| `/api/operations/adoption/sharepoint` | `sharepoint_user_adoption()` | GET | yes | `_response` |
| `/api/operations/adoption/sharepoint/sites` | `sharepoint_site_adoption()` | GET | yes | `_response` |
| `/api/operations/license-utilization` | `license_utilization()` | GET | yes | `_response` |
| `/api/operations/inactivity?days=30/60/90` | `inactivity_candidates()` | GET | yes | `_response` |
| `/api/operations/data-quality` | `build()` data-quality + limitations | GET | yes | `_response` |
| `/api/security/summary` , `/api/security/findings`, `/api/security/findings/{id}`, `/api/security/data-quality` | security findings | GET | yes | `_response` |
| `/api/capabilities` | capability list | GET | yes | `_response` |
| `/health` | DB health | GET | n/a | custom |

All routes are read-only GETs over persisted, normalized rows; none issue Graph calls or DB writes.

## 3. Product-function → route mapping and classification

| Required product function | Existing route(s) | Classification |
|---|---|---|
| tenant/KPI overview | `/api/operations/kpi` (`standard_kpi_summary`) | **READY** |
| Exchange usage | `/api/operations/kpi` (exchange) and `/api/operations/adoption/exchange` | **READY** |
| OneDrive usage | `/api/operations/kpi` (onedrive) and `/api/operations/adoption/onedrive` | **READY** |
| SharePoint user usage | `/api/operations/kpi` (sharepoint) and `/api/operations/adoption/sharepoint` | **READY** |
| SharePoint site usage | `/api/operations/kpi` (sharepoint.active_sites/storage/files/utilization) and `/api/operations/adoption/sharepoint/sites` | **READY** |
| user/license/workload correlation | `/api/operations/correlation/users` | **READY** |
| license inventory / per-SKU visibility | `/api/operations/kpi` (license section, per-SKU keyed) | **READY** |
| user↔SKU mapping (Standard UI) | `/api/operations/correlation/users` (`assigned_skus`, `assigned_sku_count`) | **READY** |

No required Standard product function is `MISSING`. No `DUPLICATE` is created by this contract; the existing `/summary` composite and per-workload `adoption/*` routes are retained as detail sources (not introduced as new duplicates).

## 4. Authoritative smallest Standard API contract (dashboard consumption)

Dashboard backend should consume the following **existing** read-only routes. No new endpoints are introduced.

### Primary overview source

- **`GET /api/operations/kpi`** — the authoritative tenant-level overview. Confirmed consumable as the primary overview source (STD-13C live-proven). Payload shape:
  - `status` / `as_of`
  - `data.tenant`: `total_users`, `licensed_users`, `unlicensed_users` (metric envelopes)
  - `data.license`: one key per subscribed SKU (key = `sku_part_number`, fallback `sku_id`) with `purchased_units`, `consumed_units`, `available_units`, `utilization_percent`, `assigned_user_count`
  - `data.exchange`: `active_users`, `inactive_users`, `unknown_users`, `latest_activity`, `total_storage_used`, `total_mailbox_item_count`
  - `data.onedrive`: `active_users`, `inactive_users`, `unknown_users`, `latest_activity`, `total_storage_used`, `total_file_count`, `storage_utilization`
  - `data.sharepoint`: `active_users`, `inactive_users`, `unknown_users`, `active_sites`, `latest_activity`, `total_storage_used`, `total_file_count`, `storage_utilization`
  - `data.cross_workload`: `active_all_3`, `active_exactly_2`, `active_exactly_1`, `inactive_all_complete_evidence`, `users_with_unknown_evidence`
  - `data_quality`: `source_freshness_exposed`, `missing_workload_data`, `missing_entitlement_data`, `partial_tenant_coverage`, `identity_joins`

### Drilldown / mapping sources

- **Per-workload detail:** `/api/operations/adoption/exchange`, `/api/operations/adoption/onedrive`, `/api/operations/adoption/sharepoint`, `/api/operations/adoption/sharepoint/sites` for richer per-workload capacity/adoption detail.
- **Correlation / user↔SKU mapping:** `/api/operations/correlation/users` (one row per canonical user): `user_ref`, `licensed`, `assigned_sku_count`, `assigned_skus[]` (`sku_id`, `sku_part_number`), and per-workload `{exchange,onedrive,sharepoint}_status` + `{...}_last_activity`.
- **Data quality / limitations:** `/api/operations/data-quality`.

### Response conventions

- Envelope: `{"status", "as_of", "data", "data_quality", "limitations"}` (optional keys omitted when absent).
- Metric envelope (`_metric`): `{"value", "source_refresh_date", "source_period", "status", "missing_dependency"}`.
- Top-level `status`: `READY` unless any metric is `DATA_DEPENDENCY_UNAVAILABLE`, then `DATA_DEPENDENCY_UNAVAILABLE` (see `_service_status`).
- `as_of`: ISO date of the request day.

### Tenant isolation

- Single tenant per service instance: `create_server()` sets `tenant_id = GRAPH_TENANT_DB_ID`; `OperationsAnalyticsQueryService.from_connection(connection, tenant_id)` issues only `WHERE tenant_id = %s`-scoped queries across `core."user"`, `core.subscribed_sku`, `core.user_license_assignment`, and all `core.usage_*` tables (all with `tenant_id` FK `ON DELETE RESTRICT` to `core.tenant`).

### Metadata

- `source_refresh_date` (per metric) and `report_refresh_date`/`observed_at` newest-generation selection per tenant; `source_period` (`D7` baseline for usage reports); `as_of` at envelope level.
- `data_quality` aggregates missing-workload/entitlement coverage and identity-join quality without exposing identities.

### Read-only boundary

- All routes are GET; analytics reads only approved persisted tables; no Graph calls, no DB writes, no permission changes, no migration.

## 5. Gaps

### ready

- overview_kpi, exchange, onedrive, sharepoint_users, sharepoint_sites, correlation, license_inventory, user_license_mapping — all `READY` via existing routes above.

### partial

- `license_inventory` via `/api/operations/kpi` is keyed by `sku_part_number` (fallback `sku_id`) and does not emit `sku_id` as a separate field in each license value. This is the accepted, live-proven STD-13C shape and is fully consumable for per-SKU visibility; the dashboard can join to correlation `assigned_skus` on `sku_part_number`. Noted for documentation only; **not** a redesign requirement.

### missing

- **None.** Every required Standard product function maps to an existing read-only route. No real implementation gap for STD-14B.

### duplicate

- **None introduced.** The existing `/summary` composite and per-workload `adoption/*` detail routes are retained and are not created as new duplicates. No new endpoint is proposed merely for naming consistency.

## 6. Verification

- **Tenant isolation:** verified — all reads tenant-scoped, single tenant per service instance, FK `ON DELETE RESTRICT`.
- **Read-only behavior:** verified — all GET routes over persisted rows; no Graph/write.
- **Consistent response envelopes:** verified — shared `_response` and `_metric` conventions.
- **status / UNKNOWN semantics:** verified — `UNKNOWN` user status exposed explicitly (`unknown_users`, correlation `*_status=UNKNOWN`) and never conflated with `INACTIVE`; top-level `READY` vs `DATA_DEPENDENCY_UNAVAILABLE` via `_service_status`.
- **source / as_of metadata:** verified — `as_of`, `source_refresh_date`, `source_period`, `missing_dependency`, `report_refresh_date`.
- **API / runtime ownership:** `api/operations.py` (operations API container) + `analytics/operations.py` (analytics service), both mapped in `docs/PROJECT_FILE_MAP.md`.
- **No sensitive Graph payload exposure:** correlation returns `user_ref` (SHA-256 of canonical key) not raw UPN/object ids; `assigned_skus` exposes SKU identifiers (not user PII); tests confirm no `user_ref`/identities leak in aggregate endpoints. No raw report URLs, credentials, or tokens exposed.

## 7. Dashboard backend readiness

**YES.** The dashboard backend can consume the existing `/api/operations/kpi` endpoint as its primary overview source, plus the existing per-workload `adoption/*` routes and `/api/operations/correlation/users` for correlation and user↔SKU mapping. All required Standard product functions are covered by existing read-only routes.

## 8. Missing components / implementation

- **No API implementation is required for STD-14B.** The smallest authoritative Standard API contract is satisfied by existing routes.
- Optional (documentation-only, not required): note the `/api/operations/kpi` license-section keying convention so the dashboard joins license inventory to correlation `assigned_skus` on `sku_part_number`.

## 9. Documentation

- `docs/evidence/STD-14-STANDARD-API-CONTRACT-001.md` (this file).
- `docs/PROJECT_PROGRESS.md` — STD-14 contract record.
- `docs/AI_USAGE_LOG.md` — bounded activity record.
- `docs/PROJECT_FILE_MAP.md` — unchanged; no durable path/component introduced (contract is owned by existing `api/operations.py` / `analytics/operations.py`).
- No token/credit usage logging.

## 10. Files changed

- `docs/evidence/STD-14-STANDARD-API-CONTRACT-001.md` (created)
- `docs/PROJECT_PROGRESS.md` (STD-14 record)
- `docs/AI_USAGE_LOG.md` (bounded activity record)

## 11. Blockers

None.

## NEXT_TASK

`STD-15-STANDARD-DASHBOARD-CONTRACT-001`

## FINAL_STATUS

`STD_14_CONTRACT_PASS`
