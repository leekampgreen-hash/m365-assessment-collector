# STD-15C Standard Dashboard Live Acceptance Evidence

- **Task ID:** `STD-15C-STANDARD-DASHBOARD-LIVE-ACCEPTANCE-001`
- **Category:** `TEST/VALIDATION`
- **Role:** `LIVE_UI_ACCEPTANCE`
- **Date:** 2026-08-28
- **Result:** `STD_15C_PASS`
- **Dashboard status:** `ACCEPTED`
- **Next task:** `STD-16-EXCHANGE-BASIC-SCENARIO-CONTRACT-001`

## Runtime

- **Parity:** PASS. `python3 scripts/check_runtime_parity.py` ran first and all five required runtime modules were `MATCH`.
- **UI health:** PASS. `GET http://127.0.0.1:18080/health` returned HTTP 200; the operations API reported `READY` / database `READY`.
- **Page and assets:** PASS. Dashboard page, `/app.js`, and `/styles.css` each returned HTTP 200 with expected content types.
- **API requests:** PASS. `/api/operations/kpi` and `/api/operations/correlation/users` each returned HTTP 200 and `status=READY`.
- **JavaScript runtime:** PASS. An ephemeral Debian-based Playwright + Chromium container executed the deployed dashboard on `graph-agent-net`; production images and dependencies were unchanged.

## UI validation

The live API payloads were independently read back and compared with the accepted STD-12C/STD-13C values. Ephemeral Playwright + Chromium browser validation observed the deployed DOM at desktop (1440x900) and narrow (390x844) viewports: page status 200, document readyState `complete`, expected title, no console errors, page errors, or failed requests; KPI and correlation API responses were both HTTP 200. The desktop DOM rendered 7 overview cards, 3 license rows, Exchange/OneDrive/SharePoint sections, cross-workload metrics, and 39 user rows. Narrow viewport rendered the same content and table wrappers retained horizontal overflow (license 744/312; users 983/312). Representative values matched the live API: total 39, licensed 25, unlicensed 14, Exchange 23, OneDrive 23, SharePoint 24, active sites 3.

- **Overview:** API-consistent expected values: total 39; licensed 25; unlicensed 14; Exchange active 23; OneDrive active 23; SharePoint active 24; active SharePoint sites 3.
- **License:** Three SKU rows present in API: AAD_PREMIUM_P2 1/1/0/100%/1; POWER_BI_STANDARD 1,000,000/2/999,998/0%/2; SPB 25/25/0/100%/25. No cross-SKU purchased total is present.
- **Exchange:** 23 active, 7 inactive, 9 unknown; latest activity 2026-07-25; storage 149438006; mailbox items 56340.
- **OneDrive:** 23 active, 7 inactive, 9 unknown; latest activity 2026-06-26; storage 113932223; files 156; utilization 3.985413583835068e-06.
- **SharePoint:** 24 active, 6 inactive, 9 unknown; 3 active sites; latest activity 2026-06-26; storage 36964667; files 43; utilization 1.1206389596433534e-07.
- **Cross-workload:** 22 active all 3; 2 active exactly 2; 0 active exactly 1; 6 inactive all complete; 9 unknown evidence.
- **User table:** Correlation API returned 39 rows. Accepted licensed flags, assigned SKUs, workload statuses, and last-activity values are present; UNKNOWN and INACTIVE are distinct in the deployed rendering logic. DOM row coverage was not browser-verified.

## State validation

- **Unknown:** API and rendering logic preserve UNKNOWN separately from INACTIVE.
- **Unavailable:** metric envelopes with non-READY status render `Data currently unavailable`, not zero; API live data was READY.
- **Loading/error:** static code contains safe loading/error fallback handling; browser execution not verified.
- **Sensitive data:** API returned opaque `user_ref` values and SKU identifiers only; no raw Graph payload observed.
- **Responsive:** PASS. Desktop and narrow viewport browser runs completed; narrow license and user tables were wider than the viewport and horizontally scrollable as designed.

## Acceptance classification

- **API/UI consistency:** `PASS`; representative rendered values matched `/api/operations/kpi` and `/api/operations/correlation/users` live responses.
- **Harness note:** the prior timeout was a `TEST_HARNESS_DEFECT`: `page.waitForSelector('#loading.hidden')` used the default visible-state expectation against an element already hidden. The bounded harness was corrected to wait for the hidden element in attached state.
- **Project activity:** recorded in `docs/AI_USAGE_LOG.md`.
- **Project progress:** STD-15 is CLOSED / ACCEPTED. The prior browser-execution blocker is closed by the complete STD-15D evidence and bounded final checks for this rerun.
- **File map:** unchanged; no durable path/component changed.

## Files changed

- `docs/evidence/STD-15C-STANDARD-DASHBOARD-LIVE-ACCEPTANCE-001.md`
- `docs/PROJECT_PROGRESS.md`
- `docs/AI_USAGE_LOG.md`

No production source, backend, database, permission, Graph, or collector behavior was changed. The isolated browser harness was run from `/tmp/opencode/std15d-browser.js` and was not added to the project.

## Final rerun closure checks

- **Runtime parity:** PASS. `python3 scripts/check_runtime_parity.py` reported `MATCH` for all five required runtime modules.
- **Deployed UI health:** PASS. Dashboard root and `/health` returned HTTP 200; health reported `READY` / database `READY`.
- **KPI API:** PASS. `/api/operations/kpi` returned HTTP 200 with top-level `status=READY`; live values remain internally consistent with STD-15D.
- **Correlation API:** PASS. `/api/operations/correlation/users` returned HTTP 200 with top-level `status=READY`; 39 user rows remain present.
- **STD-15D evidence:** PASS. The recorded Chromium, JavaScript, DOM, responsive, error-free, state-semantics, and API/UI consistency evidence is complete and consistent with the bounded live payload checks.

## Blockers

None. The prior STD-15C browser-execution blocker is closed by STD-15D evidence.

## Final status

`STD_15C_PASS`
