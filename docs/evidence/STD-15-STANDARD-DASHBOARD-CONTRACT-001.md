# STD-15 Standard Dashboard Contract Evidence

- **Task ID:** `STD-15-STANDARD-DASHBOARD-CONTRACT-001`
- **Category:** `ARCHITECTURE / PRODUCT-DESIGN`
- **Role:** `DASHBOARD_CONTRACT_DESIGN`
- **Purpose:** Define the smallest management-facing Standard dashboard using accepted read-only KPI/API contracts.
- **Result:** `STD_15_CONTRACT_PASS`
- **Implementation ready:** `YES`

## Dashboard contract

The Standard page is one responsive management snapshot: metadata/header, overview cards, license table, three workload panels, cross-workload cards, user correlation table, and data-quality state. It uses no charts, recommendations, reclaim logic, writes, or Graph calls.

### Overview

Use `GET /api/operations/kpi` `data.tenant` and workload/site metrics. Render seven cards: total users, licensed users, unlicensed users, Exchange active users, OneDrive active users, SharePoint active users, and active SharePoint sites. Each card uses the metric envelope value only when its status is `READY`; show the metric status and source metadata beside unavailable values.

### License

Render `data.license` as one row/card per SKU key. Show SKU label, purchased units, consumed units, available units, utilization percent, and assigned user count. Preserve negative available values. Do not render a cross-SKU purchased, consumed, available, or utilization total. SKU identity is the `/kpi` key (`sku_part_number`, fallback `sku_id`); correlation assignment display joins on `sku_part_number` where needed.

### Exchange

Use `data.exchange`: active, inactive, unknown users; latest activity; total mailbox storage used; total mailbox item count. No Exchange storage utilization is shown because no accepted quota denominator exists.

### OneDrive

Use `data.onedrive`: active, inactive, unknown users; latest activity; total storage used; total file count; storage utilization. Utilization is displayed only when its metric is `READY`.

### SharePoint

Use `data.sharepoint`: active, inactive, unknown users; active sites; latest activity; total storage used; total file count; storage utilization. Site metrics remain site aggregates and are not treated as user evidence.

### Cross-workload

Use `data.cross_workload`: active in all three, active in exactly two, active in exactly one, inactive in all with complete evidence, and users with unknown evidence. These are labeled counts, not a forced partition; unknown users must not be added to inactive.

### User table

Use `GET /api/operations/correlation/users`, one row per canonical user. Columns: opaque user reference (`user_ref`), licensed yes/no, assigned SKUs, Exchange status and last activity, OneDrive status and last activity, SharePoint status and last activity. Render `ACTIVE`, `INACTIVE`, and `UNKNOWN` as distinct visible status labels. Do not expose raw UPN/object identifiers. If the existing UI has no table filtering convention, provide no filter in V1; a simple status/workload filter may be added only if it fits the existing native controls without new dependency.

## API mapping

- **kpi:** Primary source for all overview cards, per-SKU license rows, workload aggregates, cross-workload counts, `as_of`, metric envelopes, source refresh/period metadata, and `data_quality` summary.
- **correlation:** Primary source for the user detail table and assigned SKU display: `user_ref`, `licensed`, `assigned_skus[]`, workload statuses, and workload last-activity fields.
- **adoption:** Existing `/api/operations/adoption/exchange`, `/onedrive`, `/sharepoint`, and `/sharepoint/sites` are optional drilldown/detail sources only. They do not replace locked KPI semantics or duplicate aggregate cards.
- **data_quality:** `/api/operations/data-quality` supplies the dedicated limitations/dependency panel when the KPI envelope does not contain enough detail. It is read-only and tenant-scoped.

## UX states

- **ready:** Render the page and each metric with its value, status badge, source refresh/date metadata, and visible data-quality/limitations section. A metric-level unavailable state does not fabricate a value.
- **loading:** Keep the existing loading panel visible until the primary KPI request and required correlation request resolve; use existing hidden/dashboard transition.
- **dependency_unavailable:** Show the existing error/banner treatment and keep affected section values as `Data currently unavailable`; do not substitute legacy adoption values. If KPI succeeds but correlation fails, keep aggregate sections ready and show the user table unavailable independently.
- **unknown:** Render `UNKNOWN` and an explicit unknown count/label. Never map missing rows, masked identities, ambiguity, partial reports, or incomplete evidence to `INACTIVE`.

## Reuse

- **existing_ui:** `operations-ui/public/index.html` single-page shell, topbar, metadata row, section headings, panels, and existing dashboard lifecycle.
- **components:** Existing card grids, metric rows, status/badge classes, loading state, error banner, source metadata, quality items, and security-independent fetch helper patterns in `operations-ui/public/app.js`.
- **styles:** Existing CSS variables, cards/panels, responsive grids, two-column layout, status colors, and `@media` breakpoints in `operations-ui/public/styles.css`.

## Missing components and bounded STD-15B work

- Replace legacy `/api/operations/summary` aggregate rendering with `/api/operations/kpi`.
- Add Standard overview card mapping for seven locked metrics.
- Add per-SKU license table/card rows using independent metric envelopes.
- Add workload detail panels with status counts and accepted capacity fields.
- Add cross-workload count section.
- Add correlation user table with safe escaping and explicit UNKNOWN labels.
- Add section-level loading/error handling for KPI and correlation requests.
- Add only the minimum table/grid styles needed; preserve existing responsive breakpoints.
- Remove or exclude legacy inactivity, optimization-oriented license candidate content from the Standard V1 page; security content is outside this Standard dashboard contract unless retained as an existing separate page section.

No new endpoint, component library, charting library, backend field, database object, Graph operation, or write path is required.

## Validation

- Every locked visual maps to an accepted `/kpi` or correlation field.
- No cross-SKU license total is defined.
- UNKNOWN remains distinct from INACTIVE in cards, counts, and rows.
- Latest activity is displayed as a date, not a recency score.
- Exchange utilization is intentionally absent; OneDrive and SharePoint utilization are fail-closed.
- Existing responsive grids support basic mobile rendering; the user table should use horizontal overflow or stacked rows rather than a new responsive framework.
- Existing opaque `user_ref` behavior is preserved; no raw identity exposure is introduced.

## Decision

- **Backend change required:** `NO`
- **Blockers:** none for contract or implementation start.
- **Next task:** `STD-15B-STANDARD-DASHBOARD-IMPLEMENTATION-001`
- **Final status:** `STD_15_CONTRACT_PASS`

## Files changed

- `docs/evidence/STD-15-STANDARD-DASHBOARD-CONTRACT-001.md`
- `docs/PROJECT_PROGRESS.md`
- `docs/AI_USAGE_LOG.md`

No token/credit usage logging was added.
