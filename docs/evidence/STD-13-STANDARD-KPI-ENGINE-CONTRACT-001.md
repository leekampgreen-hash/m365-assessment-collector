# STD-13 Standard KPI Engine Contract Evidence

- **Task ID:** `STD-13-STANDARD-KPI-ENGINE-CONTRACT-001`
- **Category:** `ARCHITECTURE / INTEGRATION-WIRING`
- **Role:** `KPI_CONTRACT_DESIGN`
- **Purpose:** Define the minimal customer-facing Standard KPI contract from accepted live-proven evidence only.
- **Result:** `STD_13_CONTRACT_PASS`
- **Implementation ready:** `YES`

## 1. Locked V1 BASIC KPI contract

All values are tenant-scoped, derived read-only analytics over the newest complete/current report generation selected by the existing analytics loader. No KPI is materialized.

### Tenant

- `tenant.total_users = COUNT(canonical users)`.
- `tenant.licensed_users = COUNT(users with >=1 complete user_license_assignment row)`.
- `tenant.unlicensed_users = total_users - licensed_users`.
- The license assignment refresh is complete only when its accepted completeness condition holds; otherwise licensed/unlicensed counts are unavailable rather than inferred.

### License

For each subscribed SKU independently, keyed by `(tenant_id, sku_id)`:

- `license.purchased_units = prepaid_units`.
- `license.consumed_assigned_units = consumed_units` from the subscribed-SKU inventory.
- `license.available_units = prepaid_units - consumed_units` (negative values are retained).
- `license.utilization_percent = consumed_units / prepaid_units * 100` only when both values exist and `prepaid_units > 0`; otherwise null with dependency status.
- `license.assigned_user_count = COUNT(DISTINCT user_id)` from the complete user-license assignment set joined to that SKU.
- Multiple SKU assignments are preserved. No aggregate purchased/consumed/utilization value across unrelated SKUs is defined.

### Exchange

From current `usage_exchange_mailbox_usage` only:

- `exchange.active_users = COUNT(non-deleted rows with non-empty last_activity_date)`.
- `exchange.inactive_users = COUNT(resolved non-deleted rows with empty last_activity_date, plus resolved deleted rows)`, only where evidence is complete.
- `exchange.unknown_users = COUNT(canonical users whose status is UNKNOWN)`.
- `exchange.latest_activity = MAX(last_activity_date)` over active rows, or null when none.
- `exchange.total_mailbox_storage_used = SUM(storage_used)` over valid current mailbox rows.
- `exchange.total_mailbox_item_count = SUM(mailbox_item_count)` over valid current mailbox rows.
- No quota-based Exchange utilization is defined.

### OneDrive

Activity status is from `usage_onedrive_activity`; capacity metrics are from `usage_onedrive_account_usage`:

- `onedrive.active_users`, `inactive_users`, and `unknown_users` use the accepted per-user status rules.
- `onedrive.latest_activity = MAX(last_activity_date)` over active activity/account evidence.
- `onedrive.total_storage_used = SUM(storage_used)` over valid current account rows.
- `onedrive.total_file_count = SUM(file_count)` over valid current account rows.
- `onedrive.storage_utilization_percent = SUM(storage_used) / SUM(storage_allocated) * 100` only when allocation is complete, numeric, and positive; otherwise null.
- Activity counts are not thresholds for active status.

### SharePoint

User status is from `usage_sharepoint_user_activity`; site metrics are from `usage_sharepoint_site_usage`:

- `sharepoint.active_users`, `inactive_users`, and `unknown_users` use the accepted per-user status rules.
- `sharepoint.active_sites = COUNT(non-deleted site rows with non-empty last_activity_date)`.
- `sharepoint.latest_activity = MAX(last_activity_date)` over active user/site evidence.
- `sharepoint.total_storage_used = SUM(storage_used)` over valid current site rows.
- `sharepoint.total_file_count = SUM(file_count)` over valid current site rows.
- `sharepoint.storage_utilization_percent = SUM(storage_used) / SUM(storage_allocated) * 100` only when allocation is complete, numeric, and positive; otherwise null.
- Site identity is Site Id first, URL fallback; site rows are never user identity evidence.

### Cross-workload

Using the accepted one-row-per-canonical-user correlation result:

- `cross_workload.active_in_all_3 = COUNT(users with ACTIVE in Exchange, OneDrive, SharePoint)`.
- `cross_workload.active_in_2 = COUNT(users with exactly 2 ACTIVE statuses)`.
- `cross_workload.active_in_1 = COUNT(users with exactly 1 ACTIVE status)`.
- `cross_workload.inactive_in_all_observed = COUNT(users with all three INACTIVE)` only when all three workload evidence sets are complete.
- `cross_workload.unknown_workload_evidence = COUNT(users with at least one UNKNOWN workload status)`.
- Categories are intentionally not forced into a mutually exclusive total when UNKNOWN exists; users with UNKNOWN are not classified inactive.

## 2. Status handling and denominators

- **ACTIVE:** resolved, non-masked, non-deleted current row with non-empty `last_activity_date`.
- **INACTIVE:** resolved complete evidence proves inactivity: non-deleted row with empty activity date, or deleted row. Deleted evidence is not silently discarded.
- **UNKNOWN:** no current row, masked/unresolvable identity, duplicate/ambiguous identity, partial report, missing dependency, or incomplete assignment/report generation. Absence of evidence is not proof of inactivity.
- User adoption denominators are explicit: `observed_user_denominator = active + inactive`; `directory_denominator = active + inactive + unknown` when all canonical users are included. V1 does not publish an adoption percentage unless its denominator is named. Unknown users are excluded from inactive and from observed-user rates.
- Capacity utilization denominators are allocated capacity, not users; zero, missing, malformed, or incomplete allocation fails closed to null.
- Latest activity is a date maximum, not a count or recency score.

## 3. Accepted sources and reusable wiring

Sources are already live-proven: `core."user"`, `core.subscribed_sku`, `core.user_license_assignment`, `core.usage_exchange_mailbox_usage`, `core.usage_onedrive_activity`, `core.usage_onedrive_account_usage`, `core.usage_sharepoint_user_activity`, and `core.usage_sharepoint_site_usage`. Accepted report baseline is D7; analytics reads newest `observed_at` generation per tenant.

Reuse `OperationsAnalyticsQueryService.from_connection`, tenant-scoped loaders, `_metric` envelopes, numeric/date/deletion helpers, `cross_workload_user_status()`, and existing API `_response` conventions. Do not reuse legacy activity-count fallback semantics for these locked KPIs.

## 4. Smallest read-only output model

One tenant-level object with:

- `tenant`: `total_users`, `licensed_users`, `unlicensed_users`.
- `license.skus[]`: `sku_id`, `sku_part_number`, `purchased_units`, `consumed_assigned_units`, `available_units`, `utilization_percent`, `assigned_user_count`.
- `exchange`, `onedrive`, `sharepoint`: status counts, latest activity, totals, and supported utilization.
- `cross_workload`: the five counts above.
- `as_of`, source refresh/period metadata, overall status, and metric-level dependency/status metadata.

No raw identities are needed. This is a derived response/read model, not a table.

## 5. Architecture, missing components, and bounded STD-13B work

Existing analytics/API/database architecture supports this without DB redesign. No migration, table, index, Graph call, write, or persistence change is required.

STD-13B is bounded to: one read-only analytics method that loads/validates the accepted current evidence, computes the formulas above, and returns the read model; one read-only API route if exposed through the existing operations API boundary; focused tests for formulas, per-SKU isolation, duplicate prevention, complete/incomplete evidence, UNKNOWN handling, utilization fail-closed behavior, cross-workload buckets, tenant isolation, and API serialization. No dashboard implementation.

Out of scope: wasted/reclaimable licenses, savings, cost models, AI/recommendations, advanced adoption scores, new Graph collection, workload semantic changes, and aggregate cross-SKU license totals.

## 6. Validation and safety

The implementation must prove deterministic results against accepted live readbacks, count each canonical user/SKU/site once, select one current generation per tenant, and preserve tenant guards on every query/join. Unknown must never be silently converted to inactive. All work is read-only; no credentials, tokens, raw report URLs, or token/credit usage are recorded.

## 7. Documentation and status

- **Files changed:** this evidence file, `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md`.
- **PROJECT_FILE_MAP:** unchanged; no durable component/path introduced.
- **Blockers:** none.
- **Next task:** `STD-13B-STANDARD-KPI-ENGINE-IMPLEMENTATION-001`.
- **DB redesign required:** `NO`.
- **Final status:** `STD_13_CONTRACT_PASS`.
