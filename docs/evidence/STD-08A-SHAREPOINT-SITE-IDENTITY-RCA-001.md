# STD-08A SharePoint Site Identity RCA and Correction

- **Task ID:** `STD-08A-SHAREPOINT-SITE-IDENTITY-RCA-001`
- **Date:** 2026-08-27
- **Project:** graph-agent
- **Role:** `BOUNDED_IDENTITY_CONTRACT_RCA`
- **Purpose:** Prove and correct the USAGE-007 `ENTITY_IDENTITY_UNAVAILABLE`
  blocker for `getSharePointSiteUsageDetail(D7)` without changing accepted
  SharePoint KPI semantics.
- **Result:** `STD_08A_FIXED_PASS`; USAGE-007 live collection PASS.

## ROOT_CAUSE

- **live_source_identity_fields:** The real `getSharePointSiteUsageDetail`
  response provides a populated, stable `Site Id` (a per-site GUID) for every
  site row, but masks/omits the `Site URL` value (persisted `site_url` is blank
  across the live set).
- **expected_identity:** The existing persistence contract designates `Site Id`
  as the canonical site identity (`entity_key`); `Site URL` is a secondary
  persisted field (`site_url`).
- **actual_failure:** `collectors/usage_reports/registry.py::_identity`
  required BOTH a valid (non-zero) `Site Id` AND a non-empty `Site URL` before
  accepting any site identity. The live report has a valid `Site Id` but an
  empty `Site URL`, so every row returned `None` → `ENTITY_IDENTITY_UNAVAILABLE`
  and the whole report failed closed with `rows=0`.
- **classification:** `identity-policy logic` (adapter `_identity`
  over-constrains the site identity by co-requiring `Site URL` when a valid,
  canonical `Site Id` is already present). Not a persistence-contract mismatch
  (schema supports `entity_key` = `Site Id`), not report schema drift (both
  columns are documented), and not an adapter mapping defect.

### Canonical site identity

`Site Id` is the correct canonical site identity under the existing persistence
contract (`Site Id` → `entity_key`, unique `(tenant_id, entity_key)`). It is
present and stable in the live report. `Site URL` is used only as a fallback for
rows where the `Site Id` is masked/absent, matching the OneDrive account-usage
precedent of falling back to a stable report key when a site field is masked.

## IDENTITY_CONTRACT

- **canonical_site_identity:** `Site Id` (per-site GUID) → `entity_key`.
  Preferred whenever present and non-zero.
- **masked_identity_behavior:** When `Site Id` is masked/absent, fall back to a
  non-empty `Site URL` as the site identity (stable, unique site key). The
  persisted `site_url` field remains unchanged.
- **fail_closed_behavior:** A row with neither a usable `Site Id` nor a non-empty
  `Site URL` is genuinely identity-less and still fails closed with
  `ENTITY_IDENTITY_UNAVAILABLE`; no identity is fabricated and distinct sites
  never collapse under one key.

## FIX

Bounded change to `collectors/usage_reports/registry.py::_identity` (site branch
only). No schema, migration, permission, KPI semantics, or Graph behavior changed.

- `Site Id` used as identity whenever it is present and not all-zeros.
- `Site URL` used as a fallback identity when `Site Id` is unusable.
- `None` returned (fail closed) only when neither a usable `Site Id` nor a
  non-empty `Site URL` is present.

## FILES_CHANGED

- `collectors/usage_reports/registry.py` — site identity fallback (the only
  production source change).
- `tests/usage_reports/test_usage_reports.py` — focused site-identity tests.
- `docs/evidence/STD-08A-SHAREPOINT-SITE-IDENTITY-RCA-001.md` (this document).
- `docs/PROJECT_PROGRESS.md`, `docs/AI_USAGE_LOG.md` — progress/activity records.

## TESTS

- `tests/usage_reports/test_usage_reports.py` (21 tests) — added:
  - `test_site_identity_falls_back_to_site_url_when_site_id_masked`
  - `test_site_identity_falls_back_to_site_url_when_site_id_absent`
  - `test_site_identity_accepts_site_id_without_site_url`
  - `test_site_identity_still_fails_closed_when_both_absent`
  - Existing fail-closed tests (`test_site_identity_rejects_zero_id_and_empty_url`,
    `test_sharepoint_rows_cannot_collapse_under_one_key`,
    runtime `test_sharepoint_identity_unavailable_*`) still pass.
- `tests/core/test_usage_reports_runtime.py` (7 tests) — PASS.
- Full offline suite: `706 tests` OK (1 skipped for missing DB driver).

## WIRING

- **inventory:** `config/api_inventory.json` USAGE-007 unchanged
  (`getSharePointSiteUsageDetail`, `Reports.Read.All`, `USAGE_REPORT_CSV`).
- **adapter/registry:** `sharepoint_site_usage` spec/alias/adapter entry unchanged;
  only the site `_identity` selection was corrected.
- **normalization:** USAGE-007 normalizes 12 live rows with distinct valid site
  `entity_key` values (no collapsing); `site_url` blank as supplied by the report.
- **persistence:** current `DELETE + INSERT` upsert on `(tenant_id, entity_key)`
  and snapshot `(tenant_id, entity_key, report_refresh_date)` both executed;
  12 current rows / 13 snapshot rows.
- **runtime parity:** `scripts/check_runtime_parity.py` exit `0` after rebuild
  and recreate of `collector` + `operations-api`; all five checked modules MATCH
  host (including the corrected `collectors/usage_reports/registry.py`).
- **permission gate:** withholding `Reports.Read.All` still returns
  `SKIP_PERMISSION_REQUIRED` for USAGE-007 (no permission broadening).
- **live proof:** native `USAGE-007` collection returns `PASS`, `rows=12`,
  `source_rows=12`, `persisted_rows=12`, `identity_unavailable=false`.
  Site adoption API readback reflects the new set: `active_sites=3`,
  `total_storage_used=36964667`, `total_file_count=43`,
  `latest_activity=2026-06-26`.

## DOCUMENTATION

- Root cause and correction recorded here and in `docs/PROJECT_PROGRESS.md` and
  `docs/AI_USAGE_LOG.md`.
- The locked STD-07 contract remains authoritative: `Site Id` → `entity_key`,
  `Site URL` → `site_url`. Canonical identity semantics are unchanged; only the
  fail-closed edge (empty `Site URL`) is relaxed to accept a valid `Site Id`.
  No `docs/database-schema-design.md` change is required.
- `docs/PROJECT_FILE_MAP.md` unchanged: no durable path/component was added; the
  changed module `collectors/usage_reports/registry.py` is already mapped.

## BLOCKERS

None. `STD08_RERUN_READY=YES`.

## Safety

No migrations, DB schema/grants, permissions, tenant privacy settings, Graph
writes, License work, sharing/oversharing/Purview, or SharePoint KPI definition
changes were made. Only the bounded site-identity selection and its focused tests
changed, plus the runtime parity rebuild/recreate required to deploy it.
