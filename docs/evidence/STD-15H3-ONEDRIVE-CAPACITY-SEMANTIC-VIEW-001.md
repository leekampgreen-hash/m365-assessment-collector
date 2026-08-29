# STD-15H3 OneDrive Capacity Semantic View

- **Task:** `STD-15H3-ONEDRIVE-CAPACITY-SEMANTIC-VIEW-001`
- **Result:** `STD_15H3_PASS`
- **Scope:** OneDrive only; authoritative per-account capacity semantic layer.

## View

- **Name:** `analytics.onedrive_account_capacity`
- **Migration:** `database/migrations/016_onedrive_account_capacity.sql`
- **Source:** `core.usage_onedrive_account_usage`
- **Rows:** 26; source rows 26
- **Duplicates:** 0 by `(tenant_id, entity_key)`
- **Preservation:** storage_used, storage_allocated, and report_refresh_date matched source for 26/26 rows.

## Semantics

`utilization_percent` is `storage_used * 100.0 / storage_allocated`, and is NULL when storage_used is NULL or storage_allocated is NULL or non-positive. `usage_level` is LOW below 50%, MEDIUM from 50% through below 80%, HIGH at 80% or above, and NO_DATA when utilization cannot be calculated. `report_refresh_date` is the refresh date; no activity date or SKU/license inference is used.

## Live validation

- Migration applied successfully to the live `graph_agent` database.
- Threshold cases produced LOW (49.99), MEDIUM (50), MEDIUM (79.99), HIGH (80), NO_DATA (NULL allocation), and NO_DATA (zero allocation).
- Live distribution: LOW 26, MEDIUM 0, HIGH 0, NO_DATA 0.
- Reconciliation: LOW + MEDIUM + HIGH + NO_DATA = 26 = view row count.

**Next task:** `STD-15H4-ONEDRIVE-CAPACITY-API-WIRING-001`
