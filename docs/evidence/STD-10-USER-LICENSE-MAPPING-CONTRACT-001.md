# STD-10 User ↔ License Mapping Contract Evidence

- **Task ID:** `STD-10-USER-LICENSE-MAPPING-CONTRACT-001`
- **Category:** `ARCHITECTURE / INTEGRATION-WIRING`
- **Role:** `CONTRACT_AND_WIRING_DISCOVERY`
- **Purpose:** Define the canonical app-only User ↔ License mapping contract for the Standard Version, and verify that the accepted collection/persistence wiring already satisfies it.
- **Result:** `STD_10_CONTRACT_PASS`
- **Implementation ready:** `YES` (contract is satisfied by existing wiring; STD-10B closes any documentation/verification gaps).

## 1. Contract Scope

The locked scope is a reliable, app-only mapping:

```
User
 → assigned SKU (user.assignedLicenses[].skuId)
 → subscribed SKU inventory (core.subscribed_sku by tenant + sku_id)
```

Future use (Exchange / OneDrive / SharePoint / License correlation) depends on this mapping. No cross-workload utilization, KPI correlation, assignment/unassignment, Graph writes, Graph permission changes, or `/licenseDetails` expansion is in scope. Only the existing supported `assignedLicenses` contract and `LicenseAssignment.Read.All` application permission are used.

## 2. End-to-End AssignedLicenses Flow (Traced)

1. **Graph source:** `GET /v1.0/users` (G01-001), `$select` includes `assignedLicenses` (`config/api_inventory.json`), application auth with `LicenseAssignment.Read.All`.
2. **Adapter:** `collectors/workloads/directory/users.py` — normalizes each Graph user into a `core."user"` row; extracts the immutable `assignedLicenses[].skuId` values into a private handoff field `_assigned_licenses` (sorted unique string list) and flags `_assigned_licenses_available` (True only when the property is present and a list). No database or Graph I/O in the adapter.
3. **User identity persistence:** registry (`G01-001`, `CURRENT_ONLY`) upserts `core."user"` by `(tenant_id, source_object_id)`. The handoff fields ride through the normalized row only; they are not persisted to `core."user"` columns.
4. **Assignment persistence:** `collectors/persistence/core.py::dispatch_persistence` special-cases `G01-001` to `write_users_with_assignments(executor, records)`, which runs inside the same collection transaction after user upserts.
5. **Subscribed SKU join:** the assignment insert joins to `core.subscribed_sku` on `(tenant_id, sku_id)` so only SKUs present in the subscribed-SKU inventory are persisted; unknown SKUs are silently omitted (application-level reference behavior).

## 3. Canonical Mapping Keys

- **user_key:** `core."user".(tenant_id, source_object_id)` — Graph user `id` scoped by tenant; `user_id` (surrogate) is used for the FK into `user_license_assignment`.
- **sku_key:** `core.subscribed_sku.sku_id` — the immutable Graph SKU identifier (`assignedLicenses[].skuId` matches `subscribedSku.skuId`), scoped by tenant. (`subscribed_sku.source_object_id` is the Graph subscribedSku `id`; the mapping joins on `sku_id`, not on `source_object_id`.)
- **tenant_isolation:** all three tables (`core."user"`, `core.subscribed_sku`, `core.user_license_assignment`) carry `tenant_id` with `ON DELETE RESTRICT` FKs to `core.tenant`. The assignment refresh DELETE and every INSERT/join are tenant-scoped.
- **assignment_source:** `core.user_license_assignment` rows derived solely from the app-only `user.assignedLicenses` field (G01-001), joined against the G01-004 subscribed-SKU inventory. No delegated-user source and no `licenseDetails`.

## 4. Verified Semantics / Edge Cases

| Case | Behavior | Evidence |
|---|---|---|
| Tenant isolation | Delete is `WHERE tenant_id = %s`; inserts/joins are tenant-scoped; FK `ON DELETE RESTRICT` | `core.py:262`, migrations 003/009 |
| Stable user join | `core."user"` upsert by `(tenant_id, source_object_id)`; assignment uses `u.source_object_id` to resolve `u.user_id` | `core.py:270-273`; migration 003 |
| Stable SKU join | Assignment insert `JOIN core.subscribed_sku s ON s.tenant_id = u.tenant_id AND s.sku_id = %s`; only subscribed SKUs persist | `core.py:272`; migration 009 comment |
| Duplicate handling | `UNIQUE(tenant_id, user_id, sku_id)` with `ON CONFLICT ... DO UPDATE SET last_observed_at` | `core.py:274-275`; migration 009 |
| Multiple licenses per user | One row per `(user, sku)`; a user with N skuIds yields N assignment rows | `users.py:_license_ids`; test_core `u-1 -> [sku-1, sku-2]` |
| No license (empty list) | Empty `assignedLicenses` → zero assignment rows after the tenant delete/re-insert; user still persists | `users.py`; test_core `u-3 -> []` |
| Stale / removed assignment | On a complete user refresh where `assignedLicenses` is fully available, the tenant's assignment set is `DELETE`d then rebuilt, so removed SKUs disappear | `core.py:262` |
| Partial / incomplete evidence | If ANY normalized user record lacks `assignedLicenses` (`_assigned_licenses_available` False), the refresh is aborted: current users upsert but existing assignments are **preserved** (never wrongly cleared) | `core.py:258-261`; test `test_user_assignment_refresh_preserves_existing_set_when_property_missing` |
| Unknown SKU | `sku_id` not present in `core.subscribed_sku` is silently not inserted (application reference behavior, not an FK) | migration 009 comment |

## 5. Does Current Collection/Persistence Satisfy the Contract?

**YES — fully satisfied.** The Graph collection (G01-001 `assignedLicenses`), normalization (`users.py`), and persistence (`write_users_with_assignments` → `core.user_license_assignment`) together implement the canonical User → assigned SKU → subscribed SKU mapping, with tenant isolation, stable user and SKU joins, duplicate handling, multiple/no-license handling, stale removal, and safe partial-evidence behavior.

**No bounded persistence implementation is missing.** The only absent surface is the *read-only API/query* layer, which is explicitly a future requirement (Standard API / KPI scope) and not part of this contract's locked scope. STD-10B implementation is therefore bounded to closing the documentation/verification gap (durable schema doc entry for the canonical mapping table) rather than adding new persistence behavior.

## 6. Minimal Read-Only API/Query Semantics (future)

Defined for later implementation (STD-13 KPI / STD-14 API). These are **not** built now.

- **licensed users:** `SELECT DISTINCT a.user_id FROM core.user_license_assignment a WHERE a.tenant_id = %s` — optionally restricted to SKUs present in `core.subscribed_sku` (already guaranteed at write time).
- **users by SKU:** `SELECT a.user_id FROM core.user_license_assignment a WHERE a.tenant_id = %s AND a.sku_id = %s`.
- **assigned count by SKU:** `SELECT a.sku_id, count(DISTINCT a.user_id) FROM core.user_license_assignment a WHERE a.tenant_id = %s GROUP BY a.sku_id`.
- **user ↔ SKU mapping:** the canonical edge set `core.user_license_assignment a JOIN core."user" u ON u.tenant_id = a.tenant_id AND u.user_id = a.user_id JOIN core.subscribed_sku s ON s.tenant_id = a.tenant_id AND s.sku_id = a.sku_id` (tenant-filtered), exposing `user_id`, `user_principal_name`, `sku_id`, `sku_part_number`, `first_observed_at`, `last_observed_at`.

The existing `analytics/operations.py` `license_assignments` query and `license_utilization` endpoint already read `core.user_license_assignment` joined to `core."user"`, but they are evidence/KPI oriented and are **not** the canonical tenant/SKU mapping API; they are left unchanged.

## 7. DB Redesign

**NO.** `core.user_license_assignment` (migration `009`) already has the canonical shape: `(tenant_id, user_id, sku_id)` composite identity, observed timestamps, and a tenant+SKU index. No migration, schema, FK, or index change is required.

## 8. Production Path

- **graph_source:** `GET /v1.0/users` (G01-001) `$select=...assignedLicenses`; `LicenseAssignment.Read.All` application permission.
- **normalization:** `collectors/workloads/directory/users.py` (`_assigned_licenses`, `_assigned_licenses_available` handoff).
- **persistence:** `collectors/persistence/core.py::dispatch_persistence` → `write_users_with_assignments` → `core.user_license_assignment`; registry `G01-001` CURRENT_ONLY to `core."user"`; `G01-004` CURRENT_WITH_SNAPSHOT to `core.subscribed_sku` + snapshot.
- **user_join:** `core."user"` upsert by `(tenant_id, source_object_id)`; resolved surrogate `user_id` FK.
- **sku_join:** `(tenant_id, sku_id)` reference join to `core.subscribed_sku.sku_id`.
- **api_query:** future read-only surface per §6 (not built now).
- **runtime:** accepted G01-001/G01-004 production wiring reused; no source or deployment change; no new parity run required.

## 9. Missing Components

None for the persistence mapping contract. The read-only API/query layer (§6) is deferred to later Standard API/KPI scope. The only immediately actionable gap was a durable schema-design doc entry for `core.user_license_assignment`, closed in this task (see §10).

## 10. Documentation

- `docs/evidence/STD-10-USER-LICENSE-MAPPING-CONTRACT-001.md` (this file).
- `docs/PROJECT_PROGRESS.md` — STD-10 contract record.
- `docs/database-schema-design.md` — added §7.2 canonical `core.user_license_assignment` mapping documentation (table existed in migration 009 but was absent from the durable schema design contract).
- No token/credit usage logging.

## 11. Files Changed

- `docs/database-schema-design.md` (added `core.user_license_assignment` canonical mapping entry)
- `docs/PROJECT_PROGRESS.md` (STD-10 record)
- `docs/evidence/STD-10-USER-LICENSE-MAPPING-CONTRACT-001.md` (this file)

## 12. Blockers

None.

## NEXT_TASK

`STD-10B-USER-LICENSE-MAPPING-IMPLEMENTATION-001`

## FINAL_STATUS

`STD_10_CONTRACT_PASS`
