# STD-09 License Inventory Baseline Evidence

- **Task ID:** `STD-09-LICENSE-INVENTORY-BASELINE-001`
- **Result:** `STD_09_PASS_WITH_BLOCKERS`
- **Scope:** Standard Version tenant/SKU inventory only; user-level license mapping remains STD-10.

## Canonical Contract

- **Endpoint:** `GET /v1.0/subscribedSkus`
- **Authentication:** application
- **Permission:** `LicenseAssignment.Read.All`
- **SKU identity:** Graph `id` as `source_object_id`; `skuId` and `skuPartNumber` are retained identifiers.
- **Purchased/enabled units:** normalized `prepaid_units = prepaidUnits.enabled + prepaidUnits.suspended + prepaidUnits.warning`.
- **Consumed/assigned units:** normalized `consumed_units = consumedUnits`.
- **Available units:** `available_units = prepaid_units - consumed_units` when both values are present; otherwise unavailable. Negative results are retained as observed arithmetic and flagged for data-quality review, not clamped.
- **Utilization:** `utilization_percentage = consumed_units / prepaid_units * 100` when `prepaid_units > 0` and consumed units are present; otherwise unavailable. Zero purchased units never produces a division result.

The minimal canonical inventory row is tenant, source identity, SKU identifiers, capability status, purchased/enabled units, consumed/assigned units, derived available units, derived utilization, observation timestamp, and established lineage/retention metadata. `service_plans` remains an accepted persisted field but is not required for the locked tenant/SKU KPIs.

## Production Path

- **Inventory:** `config/api_inventory.json` G01-004.
- **Permission gate:** application permission gate checks `LicenseAssignment.Read.All`; collection is skipped when unavailable.
- **Normalization:** `collectors/workloads/directory/subscribed_skus.py` retains the approved field boundary and scalarizes `prepaidUnits`.
- **Persistence:** registry dispatches G01-004 as `CURRENT_WITH_SNAPSHOT` to `core.subscribed_sku` and `core.subscribed_sku_snapshot`; current and snapshot writes are transactional and replay-safe.
- **Analytics/API:** `analytics/operations.py` read-only loads `core.subscribed_sku`; its existing `license_utilization` endpoint is currently user-assignment/evidence oriented and is not a canonical tenant/SKU KPI implementation. STD-09 therefore closes the inventory contract without expanding analytics scope.
- **Runtime:** accepted G01-004 production wiring is reused; no source or deployment change was made, so no new parity run is required.

## Evidence

- Existing accepted Graph discovery: HTTP 200, 1 page, 3 rows, last tested `2026-08-19T12:58:23.579123+00:00`.
- Existing accepted offline implementation evidence: 233 focused/regression tests passed, including pagination, normalization, registry, current/snapshot persistence, replay, tenant boundary, and rollback.
- No new live read was performed; existing evidence remains sufficient for the baseline.

## Schema Assessment

`core.subscribed_sku` and `core.subscribed_sku_snapshot` are sufficient for the accepted source fields and deterministic KPI derivation. No migration or redesign is required. `available_units` and `utilization_percentage` should remain derived analytics values rather than duplicated stored columns unless a later KPI contract explicitly requires materialization.

## STD-10 Boundary

Reusable data already exists: `core.subscribed_sku.sku_id`, user identity rows in `core."user"`, and the existing `core.user_license_assignment` persistence path populated from user `assignedLicenses` when the field is available. STD-10 still needs to formalize completeness, identity join, tenant isolation, SKU foreign/reference behavior, partial-data handling, and API semantics. The app-only constraint remains: no `licenseDetails` expansion is authorized by this baseline; STD-10 may use only the existing supported `assignedLicenses` contract and `LicenseAssignment.Read.All`.

## Blocker

A pre-existing metadata drift remains: the runtime registry declares G01-004 retention `REFERENCE`, while the accepted adapter, catalog, schema, and migration contract declare `STANDARD`. This task does not silently alter that controlled debt.
