# TD-001 Registry-Catalog Reconciliation

**Usage mark:** `TD-001-REGISTRY-CATALOG-RECONCILIATION-001`  
**Date:** 2026-08-23  
**Purpose:** GOVERNANCE_VALIDATION  
**Scope:** Offline reconciliation of all G01 registry metadata against the data catalog, database schema design, and applied migration definitions.

## Result

**Status: PASS WITH CONFIRMED DOCUMENTED DRIFT**

All 19 registry endpoint identities are present exactly once. Persistence modes and target tables reconcile with the catalog's history requirements and the schema/migration table mappings. G01-011 Conditional Access and G01-012 Named Locations are aligned, including the previously identified `REFERENCE` retention classification.

Four confirmed retention drifts remain in the registry: the registry uses `HIGH_SENSITIVITY` as `retention_class`, while the authoritative catalog/schema contract maps those endpoints to `LONG`. No metadata was changed during this governance validation.

## Sources Reviewed

- `collectors/workloads/registry.py`
- `collectors/workloads/models.py`
- `collectors/workloads/security_service/adapters.py`
- `docs/data-catalog.md`
- `docs/database-schema-design.md`
- `database/migrations/001_create_schemas.sql` through `007_indexes.sql`

## Reconciliation Matrix

The registry adapter names below are the callable implementations represented by the registry wrappers. Catalog and schema documents do not define an independent owner or adapter field; those dimensions were therefore validated against the registry's package ownership and adapter module, while persistence and retention were compared to the catalog/schema contract.

| Endpoint | Registry mode | Registry target(s) | Owner / adapter | Catalog and schema contract | Result |
|---|---|---|---|---|---|
| G01-001 | CURRENT | `core."user"` | `directory` / `users` | CURRENT_ONLY; `core.user`; REFERENCE | Aligned |
| G01-002 | CURRENT | `core."group"` | `directory` / `groups` | CURRENT_ONLY; `core.group`; REFERENCE | Aligned |
| G01-003 | CURRENT | `core.organization` | `directory` / `organization` | CURRENT_ONLY; `core.organization`; REFERENCE | Aligned |
| G01-004 | CURRENT_WITH_SNAPSHOT | `core.subscribed_sku`; `core.subscribed_sku_snapshot` | `directory` / `subscribed_skus` | HISTORICAL_WITH_SNAPSHOT; same tables; STANDARD | Aligned |
| G01-005 | EVENT | `core.audit_event` | `security_service` / `adapt_directory_audit_logs` | HISTORICAL event; `core.audit_event`; LONG | **Confirmed drift: registry retention is HIGH_SENSITIVITY** |
| G01-006 | EVENT | `core.audit_event` | `security_service` / `adapt_sign_in_logs` | HISTORICAL event; `core.audit_event`; LONG | **Confirmed drift: registry retention is HIGH_SENSITIVITY** |
| G01-007 | CURRENT | `core.application` | `directory` / `applications` | CURRENT_ONLY; `core.application`; REFERENCE | Aligned |
| G01-008 | CURRENT | `core.service_principal` | `directory` / `service_principals` | CURRENT_ONLY; `core.service_principal`; REFERENCE | Aligned |
| G01-009 | CURRENT | `core.device` | `directory` / `devices` | CURRENT_ONLY; `core.device`; REFERENCE | Aligned |
| G01-010 | CURRENT | `core.administrative_unit` | `directory` / `administrative_units` | CURRENT_ONLY; `core.administrative_unit`; REFERENCE | Aligned |
| G01-011 | CURRENT_WITH_SNAPSHOT | `core.conditional_access_policy`; `core.conditional_access_policy_snapshot` | `security_service` / `conditional_access_policies` | HISTORICAL_WITH_SNAPSHOT; same tables; REFERENCE | Aligned |
| G01-012 | CURRENT | `core.named_location` | `security_service` / `named_locations` | CURRENT_ONLY; `core.named_location`; REFERENCE | Aligned |
| G01-013 | CURRENT_WITH_SNAPSHOT | `core.risky_user`; `core.risky_user_snapshot` | `security_service` / `risky_users` | HISTORICAL_WITH_SNAPSHOT; same tables; LONG | **Confirmed drift: registry retention is HIGH_SENSITIVITY** |
| G01-014 | EVENT | `core.risk_detection` | `security_service` / `adapt_risk_detections` | HISTORICAL event; `core.risk_detection`; LONG | **Confirmed drift: registry retention is HIGH_SENSITIVITY** |
| G01-015 | CURRENT_WITH_SNAPSHOT | `core.service_health_overview`; `core.service_health_overview_snapshot` | `security_service` / `service_health_overview` | HISTORICAL_WITH_SNAPSHOT; same tables; STANDARD | Aligned |
| G01-016 | CURRENT_WITH_HISTORY | `core.service_health_issue`; `core.service_health_issue_history` | `security_service` / `service_health_issues` | HISTORICAL incremental; same tables; STANDARD | Aligned |
| G01-017 | CURRENT_WITH_HISTORY | `core.service_update_message`; `core.service_update_message_history` | `security_service` / `service_update_messages` | HISTORICAL incremental; same tables; STANDARD | Aligned |
| G01-018 | REFERENCE | `core.directory_role_definition` | `directory` / `directory_role_definitions` | CURRENT_ONLY reference; `core.directory_role_definition`; REFERENCE | Aligned |
| G01-019 | CURRENT_WITH_SNAPSHOT | `core.directory_role_assignment`; `core.directory_role_assignment_snapshot` | `directory` / `directory_role_assignments` | HISTORICAL_WITH_SNAPSHOT; same tables; LONG | Aligned |

## Classification Details

### Confirmed drift

- **G01-005, G01-006, G01-013, G01-014:** Registry `retention_class=HIGH_SENSITIVITY`; catalog Section 1 and schema Section 15 require `LONG`. `HIGH_SENSITIVITY` is the sensitivity class, not the controlled retention class. The corresponding migrations also default these tables to `LONG`.

### Intentional difference

- Catalog collection patterns (`SNAPSHOT`, `EVENT_LOG`, `REFERENCE`, and `INCREMENTAL`) are not registry persistence-mode names. The registry uses the more operational modes `CURRENT`, `REFERENCE`, `EVENT`, `CURRENT_WITH_SNAPSHOT`, and `CURRENT_WITH_HISTORY`. The mappings are intentional and are explicitly defined by the schema design's pattern/history semantics.
- G01-005 and G01-006 intentionally share `core.audit_event`; their `event_source` discriminators preserve endpoint identity. This is documented as a deliberate multi-endpoint table mapping in the schema design.
- Owner and adapter are runtime registry/package concerns. Their absence as independent catalog or DDL columns is an intentional separation of collection orchestration from storage design, not a mismatch.

### Documentation inconsistency

- The registry's four `HIGH_SENSITIVITY` retention values are a metadata/documentation inconsistency in the registry contract. This reconciliation records the inconsistency but does not silently change it because the task explicitly prohibits automatic metadata changes.
- No independent endpoint identity, owner, adapter, or target-table documentation inconsistency was found for G01-011 or G01-012.

## Focused Findings

- **G01-011 Conditional Access:** identity, `security_service` owner, conditional-access adapter, `CURRENT_WITH_SNAPSHOT` mode, current and snapshot tables, and `REFERENCE` retention all align across registry, catalog, schema design, and migration `004_core_security_governance_rbac.sql`.
- **G01-012 Named Locations:** identity, `security_service` owner, named-locations adapter, `CURRENT` mode, `core.named_location`, and `REFERENCE` retention all align across registry, catalog, schema design, and migration `003_core_directory_and_licensing.sql`.

## Validation

- Registry coverage invariant reviewed: 19 entries, `G01-001` through `G01-019`, no omissions or extras.
- Every registry target was matched to the schema table inventory and migration DDL.
- Every catalog persistence/history classification was matched to the registry mode using the intentional pattern-to-mode mapping.
- No collectors, adapters, persistence runtime, or migrations were modified.
- No live Graph or database validation was attempted; this is an offline metadata reconciliation.

## Recommendation

Resolve the four confirmed retention drifts in a separate controlled implementation task after owner approval. The required target value is `LONG`; this evidence intentionally leaves production metadata unchanged.
