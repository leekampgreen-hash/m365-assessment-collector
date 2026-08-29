# Foundation Acceptance Review: G01-002 Through G01-012

- **Usage mark:** `FOUNDATION-ACCEPTANCE-REVIEW-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `PROJECT_ACCEPTANCE_REVIEW`
- **Date:** 2026-08-23
- **Review result:** **PASS - DOCUMENTED OFFLINE ACCEPTANCE**

## 1. Executive Summary

The foundation objective is to provide one secure, deterministic Microsoft Graph Security Collector flow from authenticated Graph collection through approved normalization, registry-controlled dispatch, persistence security validation, and transactional database writing. The foundation must support multiple workload shapes without creating endpoint-specific transport, writer, or database designs.

This review covers the completed workload range G01-002 through G01-012. The range includes directory inventory, organization and licensing state, audit events, sign-ins, applications, service principals, devices, administrative units, Conditional Access policies, and Named Locations. Each reviewed workload has implementation evidence and reuses the accepted foundation boundaries.

Current maturity is **foundation-complete for offline validation and documentation acceptance**. The workload contracts, security controls, persistence modes, migrations, and shared runtime patterns are sufficiently established for the reviewed range. This is not a claim of live-tenant or live-PostgreSQL certification: live Graph authentication/permission behavior and live database behavior remain documented validation gaps under TD-003 and TD-004.

## 2. Workload Coverage Matrix

| Endpoint | Workload | Persistence Mode | Target Table | Event / Current / Snapshot | Status |
|---|---|---|---|---|---|
| G01-002 | Groups | `CURRENT` | `core."group"` | Current | PASS |
| G01-003 | Organization | `CURRENT` | `core.organization` | Current | PASS |
| G01-004 | Subscribed SKUs | `CURRENT_WITH_SNAPSHOT` | `core.subscribed_sku`; `core.subscribed_sku_snapshot` | Current / Snapshot | PASS |
| G01-005 | Directory Audit | `EVENT` | `core.audit_event` | Event | PASS |
| G01-006 | Sign-ins | `EVENT` | `core.audit_event` | Event | PASS |
| G01-007 | Applications | `CURRENT` | `core.application` | Current | PASS |
| G01-008 | Service Principals | `CURRENT` | `core.service_principal` | Current | PASS |
| G01-009 | Devices | `CURRENT` | `core.device` | Current | PASS |
| G01-010 | Administrative Units | `CURRENT` | `core.administrative_unit` | Current | PASS |
| G01-011 | Conditional Access Policies | `CURRENT_WITH_SNAPSHOT` | `core.conditional_access_policy`; `core.conditional_access_policy_snapshot` | Current / Snapshot | PASS |
| G01-012 | Named Locations | `CURRENT` | `core.named_location` | Current | PASS |

G01-005 and G01-006 intentionally share `core.audit_event`; the registry-controlled event source and conflict key keep the event streams distinct. G01-004 and G01-011 intentionally write both current state and run-scoped historical snapshots.

## 3. Architecture Validation

The accepted and frozen pattern is:

```text
Graph Collector
    -> Adapter
    -> Registry
    -> Persistence Dispatcher
    -> Security Boundary
    -> Writer
    -> Database
```

The reviewed workloads confirm that this pattern is reused across directory and security-service owners. Endpoint identity, owner, adapter, persistence mode, target, retention, and event source are registry-controlled. Adapters perform approved field projection and trusted lineage handoff. The dispatcher selects the mode-specific persistence path, and `CollectionWriter` preserves the transaction boundary.

- No foundation redesign was introduced or required.
- No custom writer was introduced.
- No custom Graph transport was introduced.
- Existing collectors, adapters, paginator, registry, dispatcher, security boundary, writers, SQL maps, and migration contracts were reused.

## 4. Security Validation

The offline evidence validates the following security properties across the reviewed workload range:

- **Application authentication:** Workload inventories declare application authentication and the required Graph application permission, including `Group.Read.All`, `Organization.Read.All`, `LicenseAssignment.Read.All`, `AuditLog.Read.All`, `Application.Read.All`, `Device.Read.All`, `AdministrativeUnit.Read.All`, and `Policy.Read.All` as applicable.
- **Permission enforcement:** The collector inventory and authentication/runtime flow enforce the endpoint's declared permission before collection; permission-specific live tenant behavior remains subject to TD-003.
- **Tenant boundary:** Trusted runtime tenant lineage is established outside Graph payloads. Missing, malformed, or mismatched tenant identifiers fail closed before SQL or writer execution.
- **Field minimization:** Adapters retain only approved metadata fields and reject malformed records or missing required IDs. Unknown Graph properties are not propagated.
- **Credential exclusion:** Credentials, secrets, keys, tokens, authorization material, and related sensitive fields are excluded from normalized records.
- **Raw payload exclusion:** Raw Graph response objects are not persisted or included in the normalized persistence envelope.
- **Parameter-bound SQL:** Values are passed as database parameters; closed endpoint/table/column mappings retain control of SQL identifiers.

Security status is **PASS for offline evidence**, with live permission and tenant-payload variation still requiring controlled validation.

## 5. Persistence Validation

### EVENT

G01-005 and G01-006 use append-only event persistence in the shared `core.audit_event` table. The conflict key is `(tenant_id, event_source, source_object_id)`, with replay handled by conflict-safe no-op behavior (`ON CONFLICT DO NOTHING`). Event source is registry-controlled, and duplicate replay does not create another event row. Collection-level failures roll back the transaction and do not leave partial batches.

### CURRENT

G01-002, G01-003, G01-007, G01-008, G01-009, G01-010, and G01-012 use current-state upsert persistence. The normal conflict key is `(tenant_id, source_object_id)`; G01-003 organization uses its tenant-scoped `(tenant_id)` identity. Replay uses `ON CONFLICT DO UPDATE`, preserving one current representation per tenant and source object while updating approved state and observation metadata.

### CURRENT_WITH_SNAPSHOT

G01-004 and G01-011 update the current row using `(tenant_id, source_object_id)` and write a historical snapshot in the same collection transaction. Snapshot identity is `(tenant_id, source_object_id, collection_run_id)` and replay uses `ON CONFLICT DO NOTHING`. Current update and snapshot insertion are atomic; post-transaction-start failures roll back both operations.

Persistence status is **PASS for offline evidence and migration-aligned mappings**. Live PostgreSQL execution remains open under TD-004.

## 6. Testing Summary

The focused test pattern combines workload adapter and normalization tests with registry validation, collector handoff/pagination tests, persistence SQL and replay tests, tenant-boundary tests, credential/field exclusion tests, and transaction rollback tests. The implementation evidence records passing focused suites for each workload, including representative results from 213 to 266 tests depending on the workload and shared regression scope.

Migration regression validation is documented as passing 100 tests in the endpoint implementation evidence where recorded. The migration contract, registry mappings, closed SQL maps, and schema targets were reviewed together; no database migration was changed for this acceptance review.

Full offline validation is accepted as the basis for this review. Existing evidence records full discovery results in the 602-611 test range, with all workload-relevant tests passing. Three unrelated `scenario.live` operator-entrypoint tests fail when live interactive authentication or network/socket expectations are unavailable. These are known live authentication/environment limitations, not failures of the reviewed offline workloads.

Known live limitations:

- No live Microsoft Graph credentials or consented tenant were used.
- Application permission behavior and tenant-specific response variation remain unverified live.
- No live PostgreSQL instance was used to validate runtime schema, constraints, commit/rollback, or replay behavior.

## 7. Technical Debt Status

| Item | Classification | Status |
|---|---|---|
| TD-001 Registry metadata drift | Open implementation | Reconciliation is documented; four retention drifts remain for G01-005, G01-006, G01-013, and G01-014 and require separately approved implementation. |
| TD-002 Registry and persistence metadata duplication | Deferred | Validation tooling or eventual consolidation is deferred until equivalent behavior can be proven. |
| TD-003 No live Microsoft Graph integration validation | Open implementation | Live Graph validation plan is documented; execution requires a controlled tenant and consented permissions. |
| TD-004 No live PostgreSQL integration validation | Open implementation | Live PostgreSQL validation plan is documented; execution requires a controlled database environment. |
| TD-005 Limited rejection metrics and tracing | Deferred | Bounded metrics, tracing, and rejection visibility remain future implementation scope. |
| TD-006 Retry recovery hardening | Completed documentation | Retry classification, bounded recovery policy, and redacted evidence requirements are documented; runtime implementation remains future work. |

The classifications distinguish documentation completion from implementation completion. No technical debt item authorizes changing runtime, persistence, or schema behavior as part of this review.

## 8. Future Capability Direction

The accepted foundation is the substrate for the documented future validation and security-analysis capabilities:

- **FB-001 Scenario Agent:** Execute controlled scenarios, collect evidence, and validate outcomes.
- **FB-002 Golden Scenario Repository:** Store preconditions, actions, expected evidence, actual evidence, and validation results.
- **FB-003 Purview/DLP Integration:** Extend evidence collection to Purview and DLP events.
- **FB-004 Intune Automation:** Automate controlled Intune security scenarios.
- **FB-005 Agentic Security Analyst:** Answer evidence-based questions about changes, actors, subsequent effects, and reproducibility.

These are future capabilities, not part of the present acceptance scope.

## 9. Acceptance Criteria

Acceptance is **PASS** when all of the following are true:

- The G01-002 through G01-012 workloads are implemented and their endpoint contracts are documented.
- The shared security boundary is validated for authentication context, permissions, tenant lineage, field minimization, sensitive-data exclusion, and parameter-bound SQL.
- EVENT, CURRENT, and CURRENT_WITH_SNAPSHOT persistence patterns are validated for conflict keys, replay behavior, and transaction safety.
- Foundation architecture documentation and workload evidence are complete.
- Offline validation results and known live authentication/database limitations are explicitly recorded.

All criteria are met for this documentation review. The result is **FOUNDATION ACCEPTANCE: PASS - DOCUMENTED OFFLINE ACCEPTANCE**. Live validation remains a separately tracked requirement and does not block this documentation result, provided the limitations above remain visible and no live-production claim is made.
