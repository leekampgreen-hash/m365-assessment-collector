# STD-15I2 User identity display wiring

- **Task:** `STD-15I2-USER-IDENTITY-DISPLAY-WIRING-001`
- **Result:** `STD_15I2_PASS`
- **Scope:** Human-readable user identity wiring only (analytics, API contract, workload UI). Canonical/internal identity (`source_object_id`/`user_id`, tenant-safe joins, opaque `user_ref`) is unchanged.
- **Proven (from prior STD-15I1 evidence):** `core."user"` already contains `display_name` and `user_principal_name`.

## 1. Analytics

In `analytics/operations.py`:

- `from_connection` canonical `core."user"` SELECT now includes `display_name` alongside the existing `user_principal_name`:
  `SELECT tenant_id, user_id, source_object_id, user_principal_name, display_name, account_enabled FROM core."user" WHERE tenant_id = %s`.
- `cross_workload_user_status()` now emits per row: `display_name`, `user_principal_name`, and `user_ref`.

No join was changed to use `display_name` or `user_principal_name` as a join key. Joins remain grounded on the canonical directory identity via `_directory_key` (UPN) and `user_id`. `display_name`/`user_principal_name` are read-only presentation fields and never participate in joins.

## 2. API

No new endpoint. The existing `GET /api/operations/correlation/users` returns the `cross_workload_user_status()` rows, which now carry `display_name`, `user_principal_name`, and `user_ref` per row. Existing fields/contracts preserved.

## 3. UI

In `operations-ui/public/app.js`:

- `renderUsers` (low workload users overview) and `renderDetail` (Exchange/OneDrive/SharePoint workload detail) now render:
  - **Display Name** as the first (primary) identity column.
  - **User / UPN** as the second identity column.
  - **User Ref (technical)** as the last, secondary/technical column (styling via new `.technical-cell` in `styles.css`).
- The opaque `user_ref` is no longer the first customer-facing column. It is retained internally and rendered last with muted, monospaced styling.
- Applied consistently to Exchange/OneDrive/SharePoint detail rendering because they all reuse the correlation rows.

No usage calculations, Exchange active-user hiding, summary counts, Exchange capacity semantics, or OneDrive/SharePoint semantics changed. No migration. No browser harness.

## 4. Validation

- **Focused tests:** `tests/analytics/test_operations.py` + `tests/analytics/test_operations_api.py` → 35 tests, all pass. Added assertions for `display_name`/`user_principal_name` exposure in `cross_workload_user_status()`, in the `from_connection` user SELECT, and in the correlation API serialization.
- **JS syntax:** `node --check` PASS (node:22-alpine).
- **Rebuild:** Recreated only affected runtime components:
  - `docker compose up -d --build --no-deps operations-api` (analytics change baked into image)
  - `docker compose up -d --build --no-deps operations-ui` (UI change)
- **Runtime parity:** `scripts/check_runtime_parity.py` → all modules MATCH (host hash == runtime hash).
- **Live API check:** `/api/operations/correlation/users` first row returned:
  - `display_name`: `"Conf Room Adams"`
  - `user_principal_name`: `"Adams@M365B899688.OnMicrosoft.com"`
  - `user_ref`: `"user-237457cff1e95e44"`
  - `exchange_status`: `"UNKNOWN"`
  Canonical `user_ref` derivation and join behavior unchanged.
- **UI health:** `/` and `/app.js` HTTP 200; `operations-ui` container healthy. Deployed `app.js` md5 matches host file and contains the new "Display Name", "User / UPN", and "User Ref (technical)" columns.

## Files changed

- `analytics/operations.py`
- `operations-ui/public/app.js`
- `operations-ui/public/styles.css`
- `tests/analytics/test_operations.py`
- `tests/analytics/test_operations_api.py`
- `docs/evidence/STD-15I2-USER-IDENTITY-DISPLAY-WIRING-001.md` (this file)
- `docs/PROJECT_PROGRESS.md`
- `docs/AI_USAGE_LOG.md`

No token/credit logging. Canonical join semantics unchanged.
