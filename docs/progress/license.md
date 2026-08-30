# License Progress

License phases STD-09 through STD-11.

### STD-09 License Inventory Baseline (PASS WITH BLOCKER)

- Closed the tenant/SKU inventory contract by reusing accepted G01-004 `GET /v1.0/subscribedSkus` collection, `LicenseAssignment.Read.All` application permission, normalization, and current-plus-snapshot persistence.
- Canonical KPIs use only persisted `prepaid_units` and `consumed_units`: available units are `prepaid_units - consumed_units`; utilization is `consumed_units / prepaid_units * 100` only when purchased units are positive and both operands are present.
- Existing `core.subscribed_sku` and `core.subscribed_sku_snapshot` are sufficient; no migration, live read, permission change, or production source change was required. Existing Graph evidence is HTTP 200, one page, three rows; accepted implementation evidence covers 233 tests.
- Existing analytics/API wiring reads the inventory, but its current license endpoint is user-assignment/evidence oriented; tenant/SKU KPI exposure remains future KPI/API scope and does not block the baseline contract.
- A pre-existing retention metadata drift was open at baseline: registry `REFERENCE` versus authoritative adapter/catalog/schema/migration `STANDARD`. This drift is now closed by `STD-09A-LICENSE-RETENTION-WIRING-CLOSURE-001`.
- **Evidence:** `docs/evidence/STD-09-LICENSE-INVENTORY-BASELINE-001.md`.
- **Status:** `STD_09_PASS_WITH_BLOCKERS`; `STD10_READY=YES`.
- **Next:** `STD-10-USER-LICENSE-MAPPING-CONTRACT-001`.

### STD-09A License Retention Wiring Closure (PASS / FIXED)

**Status:** `STD_09A_FIXED_PASS`

- Closed the G01-004 retention-class drift. Root cause was stale registry metadata: `collectors/workloads/registry.py` set `G01-004` `retention_class="REFERENCE"` while the authoritative adapter (`collectors/workloads/directory/subscribed_skus.py` `RETENTION_CLASS="STANDARD"`), `docs/data-catalog.md`, `docs/database-schema-design.md`, and `database/migrations/003_core_directory_and_licensing.sql` all define `STANDARD`.
- **Proved registry drift, not contract error:** the adapter hard-codes `STANDARD` into both the current and snapshot rows at normalization, so the persisted retention value has always been `STANDARD`; the registry value is metadata-only for G01-004 (G07-A directory adapters do not consume `lineage.retention_class`).
- **Correction:** updated the registry `G01-004` `retention_class` from `REFERENCE` to `STANDARD` (smallest correction). No persistence-mode, snapshot, schema, migration, permission, or Graph change; no change to the durable retention contract (`STANDARD`). Added a focused registry contract test `test_g01_004_contract_and_standard_retention`.
- **Runtime parity:** rebuilt `graph-agent-collector:dev` and recreated `graph-agent-operations-api-dev`; both the collector and operations-api runtime now report `G01-004 retention=STANDARD`. `scripts/check_runtime_parity.py` gate passes (all MATCH) and the operations API is healthy.
- **Validation:** focused registry/normalization/persistence contract suites pass (242 relevant tests: registry, directory adapters, workload integration, persistence core, normalization handoff). Pre-existing, environment-only failures remain in `tests/persistence/test_g01_015_event` (migration dir not mounted in test container) and `tests/discovery/test_discovery_agent` (`agents` module not importable there); both are unrelated to this change.
- **Result:** `G01-004` is usable by `STD-10` user-license mapping; `STD10_READY=YES`.

### STD-10 User ↔ License Mapping Contract (PASS)

**Status:** `STD_10_CONTRACT_PASS`

- Defined the canonical app-only User ↔ License mapping contract (`STD-10-USER-LICENSE-MAPPING-CONTRACT-001`): User → assigned SKU (`user.assignedLicenses[].skuId`, G01-001) → subscribed SKU inventory (`core.subscribed_sku` by `(tenant_id, sku_id)`).
- **Verified the current collection/persistence already satisfies the contract:** Graph source (`GET /v1.0/users` with `assignedLicenses`, `LicenseAssignment.Read.All`), normalization (`collectors/workloads/directory/users.py` `_assigned_licenses`/`_assigned_licenses_available` handoff), persistence (`collectors/persistence/core.py::write_users_with_assignments` → `core.user_license_assignment`).
- **Canonical keys:** user = `core."user".(tenant_id, source_object_id)`; SKU = `core.subscribed_sku.sku_id` (immutable Graph SKU id); tenant isolation via `tenant_id` FKs `ON DELETE RESTRICT`; assignment source is app-only `assignedLicenses`.
- **Semantics confirmed:** stable user and SKU joins, duplicate handling (`UNIQUE(tenant_id, user_id, sku_id)` + `ON CONFLICT ... DO UPDATE last_observed_at`), multiple SKUs per user (one row per `(user, sku)`), users with no license (empty set), stale/removed assignment (tenant delete + rebuild on complete refresh), partial/incomplete evidence (refresh aborted and existing set preserved).
- **DB redesign:** NO — `core.user_license_assignment` (migration `009`) already has the canonical shape; no migration, schema, FK, or index change.
- **Read-only API/query semantics** (licensed users, users by SKU, assigned count by SKU, user↔SKU mapping) defined for later Standard API/KPI scope; not built now.
- **Documentation:** added durable `core.user_license_assignment` canonical mapping entry to `docs/database-schema-design.md` (table existed in migration 009 but was absent from the durable schema design doc); evidence at `docs/evidence/STD-10-USER-LICENSE-MAPPING-CONTRACT-001.md`.
- **No blockers.** No Graph write, permission, `/licenseDetails`, cross-workload, KPI, or assignment/unassignment work performed.
- **Next:** `STD-11-LICENSE-BASIC-LIVE-ACCEPTANCE-001`.

### STD-10B User-License Mapping Implementation

**Status:** `NOT_REQUIRED / SKIPPED`

Existing accepted G01-001/G01-004 production wiring already satisfies the STD-10 mapping contract; no implementation, migration, API, or source change is required.

### STD-11 License Basic Live Acceptance (PASS)

**Status:** `STD_11_PASS`; License Basic `ACCEPTED`.

Native runtime parity passed first. Real app-only Graph reads succeeded for G01-001 users with `assignedLicenses` (HTTP 200, 4 pages, 39 users) and G01-004 subscribed SKUs (HTTP 200, 1 page, 3 SKUs), gated by `User.Read.All` and `LicenseAssignment.Read.All`. Tenant 2 readback shows 3 SKUs, 1,000,026 purchased/enabled units, 28 consumed units, 999,998 available units, and 0.0027999% weighted utilization; 39 users comprise 25 licensed and 14 unlicensed users, with 28 assignment rows and 2 users carrying multiple SKUs. Per-SKU assigned counts are AAD_PREMIUM_P2=1, POWER_BI_STANDARD=2, SPB=25.

Database checks confirm current users, current-plus-snapshot SKU persistence (3 current / 6 snapshots), zero orphan assignments, tenant-scoped joins, complete refresh semantics, and read-only consistency between calculated metrics and persisted rows. Existing accepted implementation tests provide fail-closed partial assignedLicenses preservation evidence; no mutation was performed during acceptance.

- **Evidence:** `docs/evidence/STD-11-LICENSE-BASIC-LIVE-ACCEPTANCE-001.md`.
- **Next:** `STD-12-CROSS-WORKLOAD-CORRELATION-CONTRACT-001`.

### LIC-P01 License Parking Report

**Status:** `PASS`

- Added `GET /api/license/parking-report` with tenant-scoped detection of disabled licensed accounts, inactive licensed users at 30/60/90 days, and unassigned subscription capacity.
- Response exposes display names and SKU part numbers only; monthly and annual waste estimates use known SKU prices and estimate unknown SKUs at zero.
- Registered `get_license_parking` for mock and live agent modes with license-waste keyword routing.
- **Validation:** API report returned HTTP 200 with `READY`; agent routing selected `get_license_parking`. Collector pytest reached 303 passing tests before a pre-existing migration-order expectation failure.
