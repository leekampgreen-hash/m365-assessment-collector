# STD-12 Cross-workload Correlation Contract Evidence

- **Task ID:** `STD-12-CROSS-WORKLOAD-CORRELATION-CONTRACT-001`
- **Category:** `ARCHITECTURE / INTEGRATION-WIRING`
- **Role:** `CORRELATION_CONTRACT_DISCOVERY`
- **Purpose:** Define the minimal tenant-safe User ↔ License ↔ Exchange ↔ OneDrive ↔ SharePoint correlation contract for the Standard Version, and verify the existing persistence/analytics wiring can support it without DB redesign.
- **Result:** `STD_12_CONTRACT_PASS`
- **Implementation ready:** `YES` (a single bounded read-only analytics/API surface is the only missing component; no DB redesign).

## 1. Locked Correlation Scope

Per canonical user, determine only:

- `licensed`: YES / NO
- `assigned_skus`: the assigned SKU list (and count)
- `exchange_status`: ACTIVE / INACTIVE / UNKNOWN, plus latest activity where supported
- `onedrive_status`: ACTIVE / INACTIVE / UNKNOWN, plus latest activity where supported
- `sharepoint_status`: ACTIVE / INACTIVE / UNKNOWN, plus latest activity where supported

No optimization / reclaim recommendation is produced. No license is classified as wasted or reclaimable. No AI recommendation is produced.

## 2. Canonical Identity Join (traced)

The join path resolves a single directory user to its license set and per-workload usage evidence.

```
core."user"                              (G01-001; canonical directory user)
   │  tenant_id, user_id (surrogate), source_object_id, user_principal_name,
   │  display_name, account_enabled, created_date_time
   │
   ├─ user_id → core.user_license_assignment (migration 009)
   │        (tenant_id, user_id, sku_id) UNIQUE
   │        │
   │        └─ sku_id → core.subscribed_sku.sku_id (migration 003; immutable Graph SKU id)
   │
   └─ user_principal_name (casefolded) → each user-kind usage report table
        core.usage_exchange_mailbox_usage
        core.usage_onedrive_activity
        core.usage_sharepoint_user_activity
        joined on the usage report's stored UPN identity
        (identity_value / entity_key, both casefolded)
```

1. **Directory user:** `core."user"` is the canonical per-user identity, keyed by `(tenant_id, source_object_id)` (Graph user `id`). Its stable surrogate `user_id` is the FK target for license assignments.
2. **License join:** `core.user_license_assignment` maps `user_id` → `sku_id` (one row per `(user, sku)`). The `sku_id` references the immutable Graph SKU id in `core.subscribed_sku` (per STD-10, only SKUs present in the subscribed-SKU inventory are persisted).
3. **Exchange join:** `core.usage_exchange_mailbox_usage` is the locked STD-03 Exchange Basic evidence source (`getMailboxUsageDetail`, D7). It is a **user-kind** report: each row carries the user's UPN as `identity_value` and casefolded `entity_key`, plus `last_activity_date`, `is_deleted`, `deleted_date`, `report_refresh_date`.
4. **OneDrive join:** `core.usage_onedrive_activity` is the locked STD-05 OneDrive per-user evidence source (`getOneDriveActivityUserDetail`, D7). Same user-kind identity shape as Exchange.
5. **SharePoint join:** `core.usage_sharepoint_user_activity` is the locked STD-07 SharePoint per-user evidence source (`getSharePointActivityUserDetail`, D7). Same user-kind identity shape.

**SharePoint site usage (`core.usage_sharepoint_site_usage`, `getSharePointSiteUsageDetail`) is explicitly NOT a user identity source.** It is tenant/site capacity evidence (active sites, storage, files, utilization) and is out of the per-user correlation contract.

## 3. Authoritative Tenant-safe Correlation Key

- **canonical_user_key:** `core."user".(tenant_id, source_object_id)` — the accepted canonical directory identity (per STD-02 / STD-10). This is the deterministic identity for a canonical user row.
- **correlation_key (join into usage reports):** **casefolded User Principal Name** = casefold(`core."user".user_principal_name`) ↔ casefold usage `identity_value` (or `entity_key`). This is the only stable, tenant-safe key present in BOTH the directory user and the usage reports. The existing accepted analytics layer already joins on this exact key (`analytics/operations.py::_directory_key` / `_key`).

**Explicitly rejected keys:**
- **`source_object_id` / Graph `id`:** authoritative for directory but NOT present in usage reports (reports expose UPN, not object id). Cannot be the cross-workload join key.
- **`display_name`:** rejected. `display_name` is non-unique, human-editable, and NOT a stable identity. It is never used for correlation. (The usage-report adapter falls back to Display Name only for `entity_key` when UPN is absent — that fallback path is treated as UNKNOWN in correlation, never joined.)
- **fuzzy matching:** none. No substring, edit-distance, or phonetic matching is used.

**Determinism note:** `core."user"` has `UNIQUE(tenant_id, source_object_id)` but NO uniqueness constraint on `(tenant_id, user_principal_name)`. UPN is expected unique per tenant, but is not DB-enforced. Correlation is built on the resolved `source_object_id`/`user_id` (deterministic). If duplicate UPNs were ever present, the correlation must fail closed to UNKNOWN for that key rather than guess — the read model keys on the canonical directory user, not on UPN.

## 4. Privacy / Masked-Identity Behavior

Inspect `collectors/usage_reports/registry.py`:

- For user-kind reports, `_identity` returns the UPN; if UPN is blank it falls back to Display Name; if both are unusable it returns the literal string `"masked"`.
- `identity_is_masked` is set `TRUE` when the persisted `identity_value` is literally `"masked"`.
- Tenant privacy masking surfaces as a `"masked"` UPN in the report. Such a row carries `entity_key="masked"` and `identity_is_masked=True`, and it **cannot** be resolved to a directory user.

**Fail-safe semantics (authoritative):**

| State | Rule (all are per canonical user, per workload) |
|---|---|
| `ACTIVE` | There is complete, non-masked evidence for the user's workload row: a non-deleted row with a non-empty `last_activity_date`. (STD-03/05/07 accepted semantics: active is grounded only in non-deleted rows with a non-empty `last_activity_date`; no activity-count thresholds.) |
| `INACTIVE` | Inactivity is **provable from complete evidence**, AND the user's workload identity is resolved (non-masked). Two provable forms: (a) a non-deleted workload row exists for the user with an **empty** `last_activity_date` (the report explicitly lists the user with no activity in the window); or (b) a **deleted** workload row exists (`is_deleted=True`, optionally with `deleted_date`) — deleted mailbox/account evidence. |
| `UNKNOWN` | Default fail-safe. Applies when inactivity cannot be proven from complete evidence: (a) no workload row for the user in the current report set (absence of evidence is NOT proof of inactivity); (b) masked / unresolvable workload identity; (c) ambiguous or partial evidence. |

**Critical rule:** masked or otherwise unresolvable users are **never** classified INACTIVE. They are `UNKNOWN`. Absence of a workload row (no report row for an existing directory user) is `UNKNOWN`, not INACTIVE, because we cannot prove their inactivity from complete evidence.

## 5. Report-window Semantics (D7 Standard baseline)

- **Period:** `D7` (rolling 7-day window) — the accepted Standard baseline for all three workloads (STD-03 Exchange, STD-05 OneDrive, STD-07 SharePoint) and for the usage-report inventory (`period="D7"` in `config/api_inventory.json`).
- **Report refresh:** each report row carries `report_refresh_date`; `last_activity_date` falls within the D7 window as of that refresh.
- **Current set selection:** the analytics layer (`OperationsAnalyticsQueryService.from_connection`) selects the **newest `observed_at` generation** of each usage table per tenant. Correlation reads only this current generation so all three workload statuses reflect the same report window.
- **Latest observed activity per workload:** `MAX(last_activity_date)` over the user's ACTIVE (non-deleted, dated) rows in the current set. This is surfaced where supported (Exchange `last_activity_date`; OneDrive `last_activity_date`; SharePoint `last_activity_date`).

## 6. User Representation Matrix

| Case | Licensed | Assigned SKUs | Workload status |
|---|---|---|---|
| Multiple SKUs | YES | one `sku_id` per `core.user_license_assignment` row for the user; count = row count (STD-10 semantics) | per-workload as normal |
| No license | NO | empty list (no `user_license_assignment` rows) | per-workload as normal |
| No workload row | (as normal) | (as normal) | **UNKNOWN** for that workload (absence of evidence) |
| Deleted workload evidence | (as normal) | (as normal) | **INACTIVE** (deleted row, `is_deleted=True` / `deleted_date`) |
| Masked workload identity | (as normal) | (as normal) | **UNKNOWN** (`identity_is_masked=True` or unresolvable) — never INACTIVE |

`licensed = YES` iff the canonical user has ≥1 row in `core.user_license_assignment`. `licensed = NO` iff the user has zero rows (and the assignment evidence is complete). Multiple SKUs are represented as a list (with count); no single-SKU collapsing is performed.

## 7. Existing DB / Analytics Support (no redesign)

**Verified YES.** The needed data already exists with tenant-safe shape:

- `core."user"` — canonical user, `tenant_id` FK `ON DELETE RESTRICT`, `UNIQUE(tenant_id, source_object_id)`, `user_id` surrogate, `user_principal_name`.
- `core.user_license_assignment` — `(tenant_id, user_id, sku_id)` UNIQUE, FK to `core."user"`, `UNIQUE` per (user, sku). Migration 009.
- `core.subscribed_sku` — `sku_id` reference. Migration 003.
- `core.usage_exchange_mailbox_usage`, `core.usage_onedrive_activity`, `core.usage_sharepoint_user_activity` — `(tenant_id, entity_key)` UNIQUE, `identity_value`, `identity_is_masked`, `last_activity_date`, `is_deleted`, `deleted_date`, `report_refresh_date`, `observed_at`. Migration 008.

The analytics layer (`analytics/operations.py::OperationsAnalyticsQueryService`) already loads all of these read-only via `from_connection` (users, license_assignments, subscribed_sku, and all usage tables), already performs the UPN key join (`_key`/`_directory_key`), and already filters to the newest `observed_at` generation. **No migration, schema, FK, index, or persistence change is required.**

## 8. Smallest Future Read Model / Output

One row per canonical user. This is a **derived read model** produced by a read-only analytics/API method (future STD-13 KPI / STD-14 API scope), not a new persisted table.

Proposed fields per canonical user (output only; identity presented as a stable `user_ref` hash / masked when identity is masked):

- `user_ref` (stable deterministic reference; masked for masked identities)
- `licensed` (YES/NO)
- `assigned_sku_count` (int)
- `assigned_skus` (list of `sku_id` / `sku_part_number`)
- `exchange_status` (ACTIVE/INACTIVE/UNKNOWN) + `exchange_last_activity` (date or null)
- `onedrive_status` (ACTIVE/INACTIVE/UNKNOWN) + `onedrive_last_activity` (date or null)
- `sharepoint_status` (ACTIVE/INACTIVE/UNKNOWN) + `sharepoint_last_activity` (date or null)

Note: `user_ref` uses the existing `_user_ref` hashing convention (SHA-256 of the canonical key, first 16 hex) so raw identities are not re-exposed in output; masked identities collapse to `"masked"`.

## 9. Implementation Work Required for STD-12B

Only a single bounded, read-only surface is needed; nothing else.

1. **Analytics:** add a method to `analytics/operations.py::OperationsAnalyticsQueryService` (e.g. `cross_workload_user_status()` / `user_correlation()`) that, from the already-loaded `from_connection` data, computes for each canonical `core."user"` row the licensed flag, assigned SKU list/count, and per-workload status + last activity using the fail-safe semantics above.
2. **API:** expose it as a read-only route in `api/operations.py` (mirroring the existing `/adoption/*` route pattern), e.g. `GET /api/operations/correlation/users`.
3. **Tests:** focused offline tests for `analytics/operations.py` covering the ACTIVE/INACTIVE/UNKNOWN matrix, masked-identity handling, no-workload-row UNKNOWN, deleted-evidence INACTIVE, multiple-SKU and no-license representation, and tenant isolation.

**Explicitly out of scope for STD-12B:** no Graph endpoints/permissions, no Graph calls/writes, no license optimization, no wasted/reclaimable-license logic, no AI recommendations, no change to accepted workload KPI semantics, no DB redesign, no new persisted table/migration.

## 10. Validation Summary

- **Tenant isolation:** every involved table carries `tenant_id` with `ON DELETE RESTRICT` FKs to `core.tenant`; all joins and reads are tenant-scoped (single tenant per query).
- **Identity determinism:** correlation keys on canonical `source_object_id`/`user_id`; usage join uses casefolded UPN; no display-name and no fuzzy matching.
- **Masked/unresolved handling:** `identity_is_masked=True` → workload UNKNOWN, never INACTIVE.
- **Completeness / UNKNOWN semantics:** absence of a workload row → UNKNOWN (inactivity must be proven from complete evidence).
- **Multiple-license handling:** one row per (user, sku); represented as list + count; licensed=YES.
- **Accepted D7 workload semantics:** active grounded only in non-deleted rows with non-empty `last_activity_date`; no activity-count thresholds; latest activity = MAX(last_activity_date).
- **No fuzzy / display-name joins:** confirmed.

## 11. Documentation

- `docs/evidence/STD-12-CROSS-WORKLOAD-CORRELATION-CONTRACT-001.md` (this file).
- `docs/PROJECT_PROGRESS.md` — STD-12 contract record.
- `docs/AI_USAGE_LOG.md` — bounded activity record.
- `docs/PROJECT_FILE_MAP.md` — unchanged (no durable component/path introduced; the read model is future analytics/API scope already owned by `analytics/operations.py` and `api/operations.py`).
- No token/credit usage logging.

## 12. Files Changed

- `docs/evidence/STD-12-CROSS-WORKLOAD-CORRELATION-CONTRACT-001.md` (created)
- `docs/PROJECT_PROGRESS.md` (STD-12 record)
- `docs/AI_USAGE_LOG.md` (bounded activity record)

## 13. Blockers

None.

## NEXT_TASK

`STD-12B-CROSS-WORKLOAD-CORRELATION-IMPLEMENTATION-001`

## FINAL_STATUS

`STD_12_CONTRACT_PASS`
