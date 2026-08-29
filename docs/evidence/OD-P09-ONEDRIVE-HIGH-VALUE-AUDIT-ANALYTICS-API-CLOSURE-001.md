# OD-P09 OneDrive high-value audit analytics/API closure

**Task:** `OD-P09-ONEDRIVE-HIGH-VALUE-AUDIT-ANALYTICS-API-CLOSURE-001`
**Date:** 2026-08-29

## Contract

The semantic contract is tenant-scoped and preserves one row per `(tenant_id, audit_record_id)`. Summary fields are total, external sharing, anonymous sharing, malware detected, and latest event time. Recent detail is bounded to 100 rows maximum and exposes event time, category, operation, nullable actor, locked flags, safe object display name, and workload. No risk score, raw payload, recipient target, collection IDs, or transport data is exposed.

## Implementation

Migration `020_onedrive_high_value_audit_analytics.sql` creates `analytics.onedrive_high_value_audit` over `core.onedrive_high_value_audit_event`, with runtime `SELECT` grant. `analytics/operations.py` loads only the tenant-filtered semantic view, aggregates the contract, and orders recent detail by event time and audit record ID descending. `api/operations.py` exposes `GET /api/operations/onedrive/high-value-audit?limit=N`, reusing the trusted server tenant context and returning dependency failure rather than fabricated data when the semantic dependency is absent.

## Validation

Focused analytics and API tests pass, including the new endpoint serialization and bounded limit behavior. Existing OneDrive capacity API tests remain passing. Migration inventory tests report pre-existing repository expectations that stop before migrations 019/020; they are not compatible with the current migration set and do not indicate a defect in the new view migration. No live Microsoft 365 call or synthetic database fixture was performed. PostgreSQL production reconciliation, runtime parity, and capacity regression require the project deployment/database environment and remain pending.

`ANALYTICS_API_READY = NO`
`OD_P09_CLOSED = NO`
`READY_FOR_OD_R01 = NO`

**REAL_DEFECT_FOUND:** NO
**SYNTHETIC_RESIDUE:** NONE
**FINAL_STATUS:** `OD_P09_BLOCKED`
