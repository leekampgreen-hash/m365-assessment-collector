# CH-2.2 Registry Catalog Consistency Validation

**Usage mark:** `CH-2.2-REGISTRY-CATALOG-CONSISTENCY-001`  
**Date:** 2026-08-23  
**Status:** PASS WITH DOCUMENTED DRIFT  
**Review mode:** Offline documentation and source review only

## Scope Reviewed

All 19 registered G01 workloads (`G01-001` through `G01-019`) were reviewed against:

- `collectors/workloads/registry.py` for the registered endpoint identity, owner, adapter, persistence mode, target tables, and registry retention value.
- `docs/data-catalog.md` for Graph path, workload/classification context, collection pattern, history requirement, retention class, and sensitivity class.
- `docs/database-schema-design.md` for logical mapping, persistence semantics, physical target, retention, and sensitivity.
- `database/migrations/` for implemented table targets, persistence shape, and database retention defaults.

This was a review and documentation task. No collectors, adapters, registry runtime, persistence runtime, or migrations were modified.

## Validation Rules

- **PASS:** The compared metadata represents the same contract across the reviewed sources.
- **DRIFT:** The sources assert incompatible metadata for the same endpoint.
- **INTENTIONAL DIFFERENCE:** The values describe different concepts or a deliberate shared-table/design implementation and are not defects.

`EVENT_LOG`/`INCREMENTAL`/`SNAPSHOT`/`REFERENCE` are catalog collection-pattern values. `EVENT`/`CURRENT`/`CURRENT_WITH_SNAPSHOT`/`CURRENT_WITH_HISTORY`/`REFERENCE` are registry persistence modes. These vocabularies are compared by their documented semantics, not by literal equality.

## Validation Matrix

| Endpoint | Graph path and identity | Owner / workload classification | Adapter mapping | Persistence / database target | Retention | Sensitivity | Result |
|---|---|---|---|---|---|---|---|
| G01-001 | `/v1.0/users`; identity matches | `directory`; Entra ID | `directory.users` | CURRENT; `core."user"` | REFERENCE | SENSITIVE | PASS |
| G01-002 | `/v1.0/groups`; identity matches | `directory`; Entra ID | `directory.groups` | CURRENT; `core."group"` | REFERENCE | INTERNAL | PASS |
| G01-003 | `/v1.0/organization`; identity matches | `directory`; Entra ID | `directory.organization` | CURRENT; `core.organization` | REFERENCE | INTERNAL | PASS |
| G01-004 | `/v1.0/subscribedSkus`; identity matches | `directory`; Microsoft 365 Licensing | `directory.subscribed_skus` | CURRENT_WITH_SNAPSHOT; `core.subscribed_sku` + `core.subscribed_sku_snapshot` | **Registry REFERENCE; catalog/schema/migration STANDARD** | INTERNAL | **DRIFT** |
| G01-005 | `/v1.0/auditLogs/directoryAudits`; identity matches | `security_service`; Microsoft Entra ID | `security_service.directory_audit_logs` | EVENT; `core.audit_event`, source `DIRECTORY_AUDIT` | **Registry HIGH_SENSITIVITY; catalog/schema/migration LONG** | HIGH_SENSITIVITY | **DRIFT** |
| G01-006 | `/v1.0/auditLogs/signIns`; identity matches | `security_service`; Microsoft Entra ID | `security_service.sign_in_logs` | EVENT; `core.audit_event`, source `SIGN_IN` | **Registry HIGH_SENSITIVITY; catalog/schema/migration LONG** | HIGH_SENSITIVITY | **DRIFT** |
| G01-007 | `/v1.0/applications`; identity matches | `directory`; Microsoft Entra ID | `directory.applications` | CURRENT; `core.application` | REFERENCE | SENSITIVE | PASS |
| G01-008 | `/v1.0/servicePrincipals`; identity matches | `directory`; Microsoft Entra ID | `directory.service_principals` | CURRENT; `core.service_principal` | REFERENCE | SENSITIVE | PASS |
| G01-009 | `/v1.0/devices`; identity matches | `directory`; Microsoft Entra ID | `directory.devices` | CURRENT; `core.device` | REFERENCE | SENSITIVE | PASS |
| G01-010 | `/v1.0/directory/administrativeUnits`; identity matches | `directory`; Microsoft Entra ID Governance | `directory.administrative_units` | CURRENT; `core.administrative_unit` | REFERENCE | INTERNAL | PASS |
| G01-011 | `/v1.0/identity/conditionalAccess/policies`; identity matches | `security_service`; Microsoft Entra Conditional Access | `security_service.conditional_access_policies` | CURRENT_WITH_SNAPSHOT; `core.conditional_access_policy` + snapshot | REFERENCE | SENSITIVE | PASS |
| G01-012 | `/v1.0/identity/conditionalAccess/namedLocations`; identity matches | `security_service`; Microsoft Entra Conditional Access | `security_service.named_locations` | CURRENT; `core.named_location` | REFERENCE | SENSITIVE | PASS |
| G01-013 | `/v1.0/identityProtection/riskyUsers`; identity matches | `security_service`; Microsoft Entra ID Protection | `security_service.risky_users` | CURRENT_WITH_SNAPSHOT; `core.risky_user` + snapshot | **Registry HIGH_SENSITIVITY; catalog/schema/migration LONG** | HIGH_SENSITIVITY | **DRIFT** |
| G01-014 | `/v1.0/identityProtection/riskDetections`; identity matches | `security_service`; Microsoft Entra ID Protection | `security_service.risk_detections` | EVENT; `core.risk_detection` | **Registry HIGH_SENSITIVITY; catalog/schema/migration LONG** | HIGH_SENSITIVITY | **DRIFT** |
| G01-015 | `/v1.0/admin/serviceAnnouncement/healthOverviews`; identity matches | `security_service`; Microsoft 365 Service Health | `security_service.service_health_overview` | CURRENT_WITH_SNAPSHOT; `core.service_health_overview` + snapshot | STANDARD | INTERNAL | PASS |
| G01-016 | `/v1.0/admin/serviceAnnouncement/issues`; identity matches | `security_service`; Microsoft 365 Service Health | `security_service.service_health_issues` | CURRENT_WITH_HISTORY; `core.service_health_issue` + history | STANDARD | INTERNAL | PASS |
| G01-017 | `/v1.0/admin/serviceAnnouncement/messages`; identity matches | `security_service`; Microsoft 365 Message Center | `security_service.service_update_messages` | CURRENT_WITH_HISTORY; `core.service_update_message` + history | STANDARD | INTERNAL | PASS |
| G01-018 | `/v1.0/roleManagement/directory/roleDefinitions`; identity matches | `directory`; Microsoft Entra RBAC | `directory.directory_role_definitions` | REFERENCE; `core.directory_role_definition` | REFERENCE | INTERNAL | PASS |
| G01-019 | `/v1.0/roleManagement/directory/roleAssignments`; identity matches | `directory`; Microsoft Entra RBAC | `directory.directory_role_assignments` | CURRENT_WITH_SNAPSHOT; `core.directory_role_assignment` + snapshot | LONG | HIGH_SENSITIVITY | PASS |

## Findings

### PASS

- All 19 endpoint IDs are present exactly once in the registry and are represented in the catalog and schema mapping.
- All Graph path references, ownership/workload classifications, and registry adapter mappings reviewed are consistent with the catalog/schema workload descriptions and existing implementation evidence.
- Persistence semantics reconcile across the sources: 3 event streams, 5 current-plus-snapshot workloads, 2 current-plus-history incremental workloads, and current/reference workloads for the remaining endpoints.
- Every G01 workload has a database target in the schema design and corresponding migration coverage. The shared `core.audit_event` target is deliberate and source-discriminated.
- Sensitivity classifications agree for all reviewed endpoints. The five HIGH_SENSITIVITY workloads are G01-005, G01-006, G01-013, G01-014, and G01-019.

### DRIFT

Five retention metadata inconsistencies are confirmed:

| Endpoint | Registry | Catalog / schema / migration | Evidence |
|---|---|---|---|
| G01-004 | REFERENCE | STANDARD | Registry entry; catalog row; schema table inventory and retention table; migration `003_core_directory_and_licensing.sql` defaults |
| G01-005 | HIGH_SENSITIVITY | LONG | Registry entry; catalog row; schema endpoint mapping and retention table; migration `004_core_security_governance_rbac.sql` |
| G01-006 | HIGH_SENSITIVITY | LONG | Registry entry; catalog row; schema endpoint mapping and retention table; migration `004_core_security_governance_rbac.sql` |
| G01-013 | HIGH_SENSITIVITY | LONG | Registry entry; catalog row; schema endpoint mapping and retention table; migration `004_core_security_governance_rbac.sql` |
| G01-014 | HIGH_SENSITIVITY | LONG | Registry entry; catalog row; schema endpoint mapping and retention table; migration `004_core_security_governance_rbac.sql` |

The G01-005, G01-006, G01-013, and G01-014 findings carry forward the CH-2.1 decision: `HIGH_SENSITIVITY` is sensitivity, while `LONG` is retention. They are not alternate spellings of one value. G01-004 is a separate retention-class mismatch: its registry value is `REFERENCE`, while all catalog/schema/migration sources define `STANDARD`.

### INTENTIONAL DIFFERENCE

- Catalog collection patterns and registry persistence modes use different controlled vocabularies. For example, catalog `EVENT_LOG` maps to registry `EVENT`, and catalog `SNAPSHOT` plus `HISTORICAL_WITH_SNAPSHOT` maps to registry `CURRENT_WITH_SNAPSHOT`.
- The catalog's `HISTORICAL` requirement for G01-016 and G01-017 is implemented by registry `CURRENT_WITH_HISTORY` and paired current/history tables. This is a semantic implementation mapping, not drift.
- G01-005 and G01-006 intentionally share `core.audit_event`; `event_source` distinguishes `DIRECTORY_AUDIT` and `SIGN_IN`. This is documented in both schema design and migration comments.
- The catalog's Graph endpoint label and the registry's adapter callable name are different identifiers for the same workload, not duplicate endpoint identities.

## Recommended Actions

1. Correct the registry retention value for G01-004 to `STANDARD` in a separately approved implementation task, after updating any associated tests and evidence.
2. Correct the registry retention values for G01-005, G01-006, G01-013, and G01-014 to `LONG` in the same or a separately approved metadata task. Preserve `HIGH_SENSITIVITY` as the sensitivity classification.
3. Add a read-only consistency validator that derives a canonical endpoint matrix and compares registry, catalog, schema, and migration metadata before future endpoint work is accepted.
4. Keep the shared audit-event table and persistence-vocabulary mappings documented as intentional design decisions; do not split or rename them solely to achieve literal text equality.

## Validation Result

| Measure | Result |
|---|---|
| Endpoints reviewed | 19 |
| PASS | 14 |
| DRIFT found | 5 endpoints |
| INTENTIONAL DIFFERENCE categories | 4 |
| Production code changed | None |
| Documentation consistency checked | Yes, offline across all four requested source groups |
| Blockers | None for review; retention corrections require separately approved implementation work |
