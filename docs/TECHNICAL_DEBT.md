# Technical Debt Register

This register maintains known technical debt, limitations, accepted design decisions, and future improvement items identified during G01-002 through G01-012.

## TD-008: Foundation Security Review Limitations

**Status:** DOCUMENTED / CONTROLLED VALIDATION REQUIRED

**CH-2.5 decision:** The foundation security posture is `PASS WITH LIMITATIONS`
for offline documentation evidence. Authentication boundaries, permission
contracts, trusted tenant lineage, data minimization, evidence restrictions,
parameter-bound SQL, closed mappings, replay protection, and rollback behavior
are documented and covered by offline validation.

**Limitations:** No live Microsoft Graph execution, consented validation tenant,
live PostgreSQL instance, or production tenant testing was performed. Live
permission effectiveness, tenant-specific payload behavior, deployment access
controls, evidence-sink controls, and database runtime behavior remain open.

**Follow-up:** Execute the controlled validation boundary defined by CH-2.3 and
the TD-003/TD-004 plans before making an unrestricted production security claim.
The G01-003 permission anomaly and existing retention metadata drifts remain
separately tracked and were not changed by CH-2.5.

**Evidence:** `docs/evidence/CH-2.5-FOUNDATION-SECURITY-REVIEW.md`

## TD-001: Registry Metadata Drift

**Status:** DECISION DOCUMENTED / IMPLEMENTATION PENDING

**Affected:**

- G01-011 Conditional Access
- G01-012 Named Locations

**Issue:** Registry retention metadata required alignment with catalog/schema classification.

**Resolution:** G01-011 and G01-012 are aligned to `REFERENCE`. Full reconciliation was completed under `TD-001-REGISTRY-CATALOG-RECONCILIATION-001`.

**Result:** 19 endpoint identities reviewed. Persistence modes and target tables align. Four confirmed retention drifts remain: G01-005, G01-006, G01-013, and G01-014 use registry `HIGH_SENSITIVITY` where the catalog/schema retention contract requires `LONG`; G01-019 is aligned to `LONG`.

**Decision:** `HIGH_SENSITIVITY` and `LONG` are different governance dimensions. `HIGH_SENSITIVITY` is the sensitivity classification; `LONG` is the retention class. The registry values for G01-005, G01-006, G01-013, and G01-014 are therefore confirmed metadata drift, not an alternate retention vocabulary.

**Remaining:** Correct the four confirmed registry retention metadata drifts in a separately approved implementation task. No automatic metadata change was made during reconciliation or governance review.

**Evidence:** `docs/evidence/TD-001-REGISTRY-CATALOG-RECONCILIATION.md`; `docs/evidence/CH-2.1-DATA-CLASSIFICATION-GOVERNANCE-DECISION.md`

## TD-002: Registry and Persistence Metadata Duplication

**Status:** GOVERNANCE VALIDATION - DRIFT CONFIRMED

**Description:** Endpoint metadata exists in multiple locations:

- Registry
- SQL mapping
- Documentation

**Risk:** Potential future drift.

**CH-2.2 finding:** Review of all 19 G01 workloads confirmed five retention
metadata drifts: G01-004 is `REFERENCE` in the registry but `STANDARD` in the
catalog/schema/migrations; G01-005, G01-006, G01-013, and G01-014 are
`HIGH_SENSITIVITY` in the registry but require `LONG` retention in the
catalog/schema/migrations. `HIGH_SENSITIVITY` remains the sensitivity
classification for those four workloads and is not a retention value.

Endpoint identity, owner/workload classification, adapter mapping, persistence
semantics, database targets, and sensitivity classification otherwise reconcile.
Catalog collection-pattern vocabulary versus registry persistence-mode vocabulary
and the shared `core.audit_event` target are intentional differences.

**Recommendation:** Create read-only validation tooling before considering
consolidation. Correct the five registry retention values only through separately
approved implementation work.

**Evidence:** `docs/evidence/CH-2.2-REGISTRY-CATALOG-CONSISTENCY-REPORT.md`

## TD-003: No Live Microsoft Graph Integration Validation

**Status:** DOCUMENTED / PLANNED

**Description:** Current validation relies on the offline test framework.

**Risk:** The project cannot validate:

- Live permission behavior
- Tenant-specific payload variation
- Real API changes

**Plan:** `docs/evidence/TD-003-LIVE-GRAPH-VALIDATION-PLAN.md`

## TD-004: No Live PostgreSQL Integration Validation

**Status:** DOCUMENTED / PLANNED

**Description:** Persistence validation currently uses framework/offline validation.

**Risk:** Runtime database behavior requires additional validation.

**Plan:** `docs/evidence/TD-004-LIVE-POSTGRESQL-VALIDATION-PLAN.md`

## TD-007: No Controlled Validation Environment

**Status:** DOCUMENTED / PLANNED

**Description:** Offline acceptance and the separately documented live Microsoft Graph and PostgreSQL plans do not yet have a unified, environment-separated execution and evidence boundary between development and production.

**Risk:** Live tenant permissions, tenant-specific payload behavior, database transaction behavior, replay, rollback, and evidence handling remain unvalidated as one controlled promotion gate. Direct testing against production would create unacceptable data, security, and operational risk.

**Plan:** `docs/evidence/CH-2.3-CONTROLLED-VALIDATION-ENVIRONMENT-PLAN.md`

**Scope:** Define Development, Controlled Validation, and Production separation; coordinate representative G01-005, G01-006, G01-009, G01-011, and G01-012 Graph workloads with representative `EVENT`, `CURRENT`, and `CURRENT_WITH_SNAPSHOT` PostgreSQL targets; define bounded evidence and pass criteria; and describe a future Scenario Validation Agent. No runtime or schema change is authorized by the plan.

## TD-005: Limited Rejection Metrics and Tracing

**Description:** Rejected and malformed records require richer operational visibility.

**Status:** DOCUMENTED / PLANNED - CH-2.4 DESIGN COMPLETE

**Plan:** `docs/evidence/TD-005-REJECTION-METRICS-TRACING-PLAN.md`; consolidated in `docs/evidence/CH-2.4-COLLECTOR-OPERATIONAL-HARDENING.md`

**Scope:** Add bounded rejection categories, redacted evidence fields, metrics, and trace correlation around existing fail-closed validation. Possible future implementation includes a rejection table, metrics dashboard, and alerting. No runtime or schema change is authorized by the plan.

## TD-006: Retry Recovery Hardening

**Description:** Improve operational recovery visibility after transient failures.

**Status:** DOCUMENTED / PLANNED - CH-2.4 DESIGN COMPLETE

**Plan:** `docs/evidence/TD-006-RETRY-RECOVERY-HARDENING-PLAN.md`; consolidated in `docs/evidence/CH-2.4-COLLECTOR-OPERATIONAL-HARDENING.md`

**Scope:** Define retryable and permanent failure categories, a bounded retry/backoff/timeout policy, redacted recovery evidence, agentic operations questions, and possible future metrics, dashboard, alerting, and recovery workflow. No runtime or schema change is authorized by the plan.
