# STD-15G3B Exchange UI contract fix

- **Task:** `STD-15G3B-EXCHANGE-API-UI-CONTRACT-FIX-001`
- **Result:** `STD_15G3B_PASS`
- **Scope:** Exchange UI only. Bounded to `operations-ui/public/app.js`. No backend/API/SQL view changes.
- **Root causes (from STD-15G3A):**
  1. `capacity_usage` low/medium/high/no_data are plain integers but UI `display()`/`value()` expected metric objects.
  2. `data_last_refreshed` is a plain string but UI treated it like a metric object.
  3. mailbox items read the wrong key `exchange.total_mailbox_items` instead of `exchange.total_mailbox_item_count`.
  4. `total_storage_used` is valid raw bytes but the `storage()` formatter was not applied.

## Fixes

- **capacity_buckets:** Added an explicit `primitive` renderer and applied it to the LOW/MEDIUM/HIGH/NO DATA fields. Live values render correctly: LOW=30, MEDIUM=0, HIGH=0, NO DATA=0.
- **refresh_date:** `data_last_refreshed` rendered via the `primitive` path. Live value renders `2026-08-25`.
- **mailbox_items:** Corrected mapping to `total_mailbox_item_count: exchange.total_mailbox_item_count`. Live value renders `56434`.
- **storage_formatting:** Added `storageValue` helper that extracts the numeric value from a metric object or primitive and applies the existing `storage()` formatter. Live `total_storage_used.value` = `150163617` renders `143.21 MB`.

`display()`/`value()` global semantics were not weakened; known primitive fields are handled explicitly via per-field render kinds in `workloadCard`.

## Validation

- **JS/source contract check:** `node --check` PASS (node:22-alpine). Simulated Exchange card produced the exact expected strings for all fields.
- **Rebuild:** Recreated only the `operations-ui` service via `docker compose up -d --build --no-deps operations-ui`. Image rebuilt; container `graph-agent-operations-ui-dev` healthy.
- **Runtime parity:** Confirmed against the live `/api/operations/kpi` response:
  - `capacity_usage` = `{'low': 30, 'medium': 0, 'high': 0, 'no_data': 0}`
  - `data_last_refreshed` = `'2026-08-25'`
  - `total_storage_used.value` = `150163617`
  - `total_mailbox_item_count.value` = `56434`
  - `total_mailbox_items` key absent (wrong-key defect confirmed and fixed)
- **UI health:** `/` and `/app.js` return HTTP 200; container healthcheck healthy.
- **No backend changes.**

Browser/Playwright acceptance deliberately deferred to `STD-15G3C-EXCHANGE-UI-BROWSER-ACCEPTANCE-001`.
