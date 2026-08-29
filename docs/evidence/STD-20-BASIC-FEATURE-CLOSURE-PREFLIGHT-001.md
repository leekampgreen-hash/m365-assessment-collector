# STD-20 Basic Feature Closure Preflight

- **Task:** `STD-20-BASIC-FEATURE-CLOSURE-PREFLIGHT-001`
- **Date:** 2026-08-29
- **Result:** `STD_20B_RECONCILIATION_PASS`
- **Scope:** User baseline; license inventory/attention; Exchange mailbox capacity; OneDrive account capacity; SharePoint basic usage; Operations KPI/API; Usage Overview; Usage Drilldown; License Capacity; customer-facing operational dashboard.

## Validation

- Runtime parity: PASS. `scripts/check_runtime_parity.py` reported MATCH for analytics, usage-report registry, API, persistence, and runtime modules.
- Production services: PASS. Compose collector, operations API, operations UI, and PostgreSQL services were running; API and UI healthchecks were healthy.
- Focused offline validation: PASS. `python3 -m unittest tests.analytics.test_operations tests.analytics.test_operations_api tests.core.test_usage_reports_runtime` reported 45 tests passed.
- Production API boundary: KPI, Exchange, OneDrive, SharePoint sites, and license-utilization routes returned HTTP 200; KPI, Exchange, OneDrive, SharePoint sites, and license-utilization were `READY`. SharePoint user adoption returned HTTP 200 with `DATA_DEPENDENCY_UNAVAILABLE` and no usable data payload.
- Production UI boundary: `/` returned HTTP 200. Source inspection confirms the three requested overview card labels and drilldown controls/columns, including the final OneDrive columns. The HTML has no rendered `#workloads` container, although `renderWorkloads()` remains defined in `app.js`; therefore workload usage cards are not proven present in the deployed main dashboard.

## Classification

- **BLOCKING:** Customer-facing main-dashboard Usage Overview is not wired/rendered because the `#workloads` mount is absent and `renderWorkloads()` is not invoked by `start()`. This is a separate UI acceptance issue; it is not caused by the SharePoint user-adoption route.
- **NON_BLOCKING:** `/api/operations/adoption/sharepoint` is not required by the locked Basic Overview KPI, Usage Overview, SharePoint Usage Drilldown, or any other customer-facing Basic feature. Those consumers use the READY `/api/operations/kpi`, `/api/operations/correlation/users`, and `/api/operations/adoption/sharepoint/sites` contracts as applicable. The route remains fail-closed with HTTP 200 and `DATA_DEPENDENCY_UNAVAILABLE` when inactive-user semantics or the directory denominator are unavailable.
- **DEFERRED:** Dedicated SharePoint user-adoption analytics and Adoption/User Activity UI are deferred; Defender Advanced Hunting, EmailEvents, Safe Links, Safe Attachments, advanced phishing/malware/spoof telemetry, incidents/alerts, SharePoint tenant storage admin integration, and SEND_MAIL remain out of scope.

## Acceptance Decision

`READY_FOR_FINAL_ACCEPTANCE=NO`; `READY_FOR_BROWSER_ACCEPTANCE=NO` pending the separate Usage Overview rendering and browser-validation issues. The unavailable SharePoint user-adoption route is not a Basic closure blocker. No source changes, permissions, schema changes, feature additions, or deferred-scope changes were made.
