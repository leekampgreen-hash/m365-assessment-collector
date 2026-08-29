# STD-15E Workload Usage Drilldown Evidence

- **Task ID:** `STD-15E-WORKLOAD-USAGE-DRILLDOWN-001`
- **Result:** `STD_15E_PASS` for implementation; deployed browser acceptance pending
- **Date:** 2026-08-28

## Usage contract

- High: 0–1 days since valid workload last activity
- Medium: 2–7 days
- Low: greater than 7 days
- No Data: missing, UNKNOWN, or unreliable activity evidence
- Reference date: API envelope `as_of`; workload evidence is sourced from authoritative correlation last-activity fields and source metadata.

## Implementation

Overview now contains clickable Email, OneDrive, and SharePoint usage summaries. Each detail view provides High/Medium/Low/No Data filters and user rows. Exchange uses **Last Email Activity** wording. Overview attention rows contain only LOW users; No Data is never classified as LOW.

## API wiring

Existing KPI and correlation contracts are sufficient. No backend changed. Accepted adoption APIs remain available for workload metrics; existing OneDrive and SharePoint capacity/site metrics remain rendered.

## Validation

- `python3 -m unittest tests.analytics.test_operations tests.analytics.test_operations_api`: PASS (32 tests)
- `python3 scripts/check_runtime_parity.py`: PASS
- `git diff --check`: unavailable because this directory is not a git repository
- JavaScript syntax check: unavailable because Node is not installed
- Browser/deployed UI validation: pending runtime deployment

SEND_MAIL remains explicitly deferred; Mail.Send was not implemented.
