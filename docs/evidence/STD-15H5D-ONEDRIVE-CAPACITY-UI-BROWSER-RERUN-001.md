# STD-15H5D OneDrive Capacity UI Browser Rerun

- Date: 2026-08-28
- Task: STD-15H5D-ONEDRIVE-UI-BROWSER-RERUN-001
- Model: 9router/my_ulti
- Scope: OneDrive UI browser validation only
- Result: STD_15H5D_BLOCKED

## Preflight

- Runtime parity: PASS; all five required production modules matched deployed runtime hashes.
- Operations UI: PASS; HTTP 200.
- Operations health: PASS; HTTP 200, `status=READY`, `database=READY`.
- OneDrive API: PASS; HTTP 200, `status=READY`; accepted API evidence remains 26 account details, LOW 26, MEDIUM 0, HIGH 0, NO_DATA 0, aggregate storage 113932223 bytes, files 156, source refresh 2026-08-25.

## Browser

Isolated Playwright/Chromium ran against the deployed UI at 1440x900 and 390x844. Navigation used `domcontentloaded`, followed by a deterministic wait for `window.dashboardOnedrive.account_details.length === 26`; validation did not inspect the DOM immediately after navigation.

- JavaScript: executed.
- Console errors: none.
- Page errors: none.
- Failed requests: none.
- Operations API responses observed by the page: HTTP 200.

## Findings

At both viewports the OneDrive workload card rendered:

- LOW: `Data currently unavailable` instead of 26
- MEDIUM: `Data currently unavailable` instead of 0
- HIGH: `Data currently unavailable` instead of 0
- NO DATA: `Data currently unavailable` instead of 0
- Data Last Refreshed: `Data currently unavailable` instead of 2026-08-25
- Total Storage: `108.65 MB` (human-readable; aggregate value present)
- Files: `156`

The OneDrive usage summary rendered High 0, Medium 0, Low 0, No Data 0. Opening OneDrive drilldown rendered the required headers but 0 account rows; filters were HIGH 0, MEDIUM 0, LOW 0, NO DATA 0. Therefore readable identity, utilization reconciliation, and filter behavior cannot be accepted. No `Data currently unavailable` or `[object Object]` appeared for Files, but unavailable placeholders remain in required capacity fields.

Responsive table overflow was measurable and usable in the narrow viewport: detail table scroll width 720px versus client width 312px. Desktop table width was 1166px.

## Defect

The deployed `operations-ui/public/app.js` OneDrive rendering path does not consume the accepted API-authoritative `capacity_usage` account details consistently: `renderWorkloads` receives no usable OneDrive bucket/date values and `renderDetail` sees an empty account-details pool, while the API is READY with 26 details. This is a OneDrive UI defect only.

No Exchange, SharePoint, SQL, analytics/API, backend, cosmetic, or unrelated numeric-normalization changes were made.
