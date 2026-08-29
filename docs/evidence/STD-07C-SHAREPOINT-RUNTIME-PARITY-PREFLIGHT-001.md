# STD-07C SharePoint Runtime Parity Preflight

- **Task ID:** `STD-07C-SHAREPOINT-RUNTIME-PARITY-PREFLIGHT-001`
- **Date:** 2026-08-27
- **Project:** graph-agent
- **Role:** RUNTIME_DEPLOYMENT_VALIDATION
- **Session:** NEW
- **Purpose:** Rebuild/recreate only the runtime containers required for the
  accepted STD-07B source and prove host-to-deployed runtime parity before the
  STD-08 SharePoint live acceptance begins.
- **Result:** `PASS` / `STD_07C_PASS`. `STD08_READY=YES`.

## Context / problem

STD-07B changed two production modules:

- `analytics/operations.py` (added `sharepoint_site_adoption()`; re-grounded
  `sharepoint_user_adoption()` on `last_activity_date` presence only).
- `api/operations.py` (routed `/api/operations/adoption/sharepoint/sites` to
  `sharepoint_site_adoption()`; `/api/operations/adoption/sharepoint` to
  `sharepoint_user_adoption()`).

The running runtime was not rebuilt or recreated during the STD-07B
implementation, so the deployed `graph-agent-collector:dev` image still carried
the pre-STD-07B `analytics/operations.py` and `api/operations.py`. This is the
same stale-runtime condition previously identified as Defect B in STD-06 and
corrected by STD-06A. `scripts/check_runtime_parity.py` is the required
host-to-runtime hash gate before any SharePoint API acceptance.

## Before-rebuild parity gate (confirms the defect)

Run before any rebuild:

```
analytics/operations.py: MISMATCH
collectors/usage_reports/registry.py: MATCH
api/operations.py: MISMATCH
collectors/persistence/core.py: MATCH
collectors/core/runtime.py: MATCH
EXIT=1
```

The two STD-07B-changed modules were stale; the shared usage-report and
persistence/runtime modules were already in parity.

## Deployment steps (bounded to STD-07B)

Only the two containers that run the `graph-agent-collector:dev` image and need
the updated `analytics/` and `api/` code were rebuilt and recreated:

1. `docker compose build collector` — rebuilt `graph-agent-collector:dev` from
   current host source (bakes `analytics`, `api`, `collectors`, `security`,
   `capabilities` into the image).
2. `docker compose up -d --no-deps --force-recreate collector operations-api`
   — recreated only `collector` and `operations-api`.

`operations-api` and `collector` have no source bind mount for `analytics`/`api`,
so they must read the baked image copies; the rebuild is what restores parity.
No other container (postgres, operations-ui, scenario) was touched.

- **collector container:** `graph-agent-collector-dev` (recreated).
- **operations_api container:** `graph-agent-operations-api-dev` (recreated).

## Runtime parity (after rebuild)

`scripts/check_runtime_parity.py` was run FIRST (before any SharePoint API
acceptance) against the recreated `graph-agent-operations-api-dev`:

```
analytics/operations.py: MATCH
collectors/usage_reports/registry.py: MATCH
api/operations.py: MATCH
collectors/persistence/core.py: MATCH
collectors/core/runtime.py: MATCH
EXIT=0
```

All five production modules match host hashes. The collector container
(`graph-agent-collector-dev`) was independently verified to carry the same five
matching hashes. Both `sharepoint_user_adoption()` and `sharepoint_site_adoption()`
methods are present on the deployed `OperationsAnalyticsQueryService`, and both
deployed API routes resolve.

- **analytics:** `analytics/operations.py` MATCH host.
- **api:** `api/operations.py` MATCH host.
- **shared_usage_modules:** `collectors/usage_reports/registry.py`,
  `collectors/persistence/core.py`, `collectors/core/runtime.py` all MATCH host.
- **parity_script:** `scripts/check_runtime_parity.py` exit `0`.

## API health

`GET /health` on the recreated operations API:

```
{"status":"READY","database":"READY"}
```

## Deployed routes

| Route | HTTP | Deployed handler |
|---|---|---|
| `GET /api/operations/adoption/sharepoint` | 200 | `sharepoint_user_adoption()` |
| `GET /api/operations/adoption/sharepoint/sites` | 200 | `sharepoint_site_adoption()` |

## Deployed semantics = accepted STD-07B semantics

`GET /api/operations/adoption/sharepoint` (live readback, tenant 2):

- `active_users` = 24, `status=READY` — derived only from non-deleted
  `sharepoint_user_activity` rows with a non-empty `last_activity_date`; no
  viewed/edited/synced/page-view thresholds drive the active-user KPI.
- `inactive_users` and `adoption_rate` = `DATA_DEPENDENCY_UNAVAILABLE` with
  `missing_dependency="inactive user semantics not in contract"` /
  `"directory denominator not in contract"` — matching the locked STD-07 scope.

`GET /api/operations/adoption/sharepoint/sites` (live readback, tenant 2):

- `active_sites` = 0, `latest_activity` (null/`last_activity_date`), and the
  storage block — `total_storage_used` = 1550100, `total_file_count` = 0,
  `storage_utilization` = `5.639230948872864e-08` — all `status=READY`.
- `storage_utilization` = `storage_used / storage_allocated` from the current
  `usage_sharepoint_site_usage` set, failing closed to `None` for
  zero/missing allocation.

Both routes respond `200`. The deployed behavior is exactly the accepted
STD-07B semantics: user adoption grounded in `last_activity_date` presence on
non-deleted rows, and site adoption exposing active sites, latest activity,
total storage, file count, and fail-closed storage utilization.

## Safety / scope accounting

No live Graph collection, no Graph writes, no KPI/source-logic change, no
database schema/grants change, no permission change, no License work, and no
other container was modified. Only the two STD-07B-required runtime containers
were rebuilt/recreated from unchanged host source. This is deployment/runtime
parity evidence only; it does not constitute SharePoint live acceptance (STD-08).
