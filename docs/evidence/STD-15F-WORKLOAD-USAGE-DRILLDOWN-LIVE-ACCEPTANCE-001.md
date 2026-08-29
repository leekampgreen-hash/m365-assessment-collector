# STD-15F Workload Usage Drilldown Live Acceptance Evidence

- **Task ID:** `STD-15F-WORKLOAD-USAGE-DRILLDOWN-LIVE-ACCEPTANCE-001`
- **Result:** `STD_15F_BLOCKED`
- **Date:** 2026-08-28

## Runtime preflight

- Runtime parity: PASS; all five required production modules matched.
- Deployed UI root: HTTP 200.
- `/health`: HTTP 200, `status=READY`, `database=READY`.
- `/api/operations/kpi`: HTTP 200, `status=READY`, envelope `as_of=2026-08-28`.
- Correlation route used by the deployed UI: `/api/operations/correlation/users`. The requested `/api/operations/correlation` route returns 404; this is not the UI contract. Browser/API correlation execution could not be completed because browser harness startup was blocked.

## Browser validation

- JavaScript execution: BLOCKED by ephemeral harness startup.
- Console/page/request failures: NOT OBSERVABLE because Chromium did not launch.
- Harness attempts remained isolated and did not install dependencies into production runtime:
  1. Playwright image: `playwright` module was not resolvable.
  2. Temporary Node container: Playwright package installed only in the disposable container, but required browser OS libraries were unavailable.
  3. Playwright image Chromium executable path was not compatible with the temporary Node container.
- No application source, backend, database, dependency, or runtime deployment changes were made.

## Contract and source-level evidence

STD-15E evidence establishes the accepted usage contract: HIGH 0–1 days, MEDIUM 2–7 days, LOW >7 days, NO DATA missing/UNKNOWN/unreliable, reference date from API `as_of`, and Exchange wording `Last Email Activity`. Existing implementation remains unchanged during this acceptance.

## Status

The HTTP/runtime preflight passed. Real-browser overview, drilldown, filtering, responsive, and regression assertions remain unverified due solely to the isolated browser harness blocker.

- **USAGE_UX_STATUS:** `BLOCKED`
- **FINAL_STATUS:** `STD_15F_BLOCKED`
- **SEND_MAIL:** deferred; not started.
