# CH-2.3 Controlled Validation Environment Plan

- **Usage mark:** `CH-2.3-CONTROLLED-VALIDATION-ENVIRONMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `VALIDATION_ARCHITECTURE`
- **Status:** `DOCUMENTED / PLANNED`

## 1. Objective

Define a controlled validation approach between offline tests and production. The approach must validate live Microsoft Graph behavior and real PostgreSQL persistence without using production tenants or production data, and must preserve the existing offline acceptance suite as the repeatable baseline.

This document is a design and evidence plan only. It does not authorize changes to `collectors/`, adapters, registry runtime, persistence runtime, or database migrations.

## 2. Environment Separation

Validation environments must have separate identity, configuration, data, access, and evidence boundaries. Promotion is based on evidence, not on shared runtime state.

### Development

- Uses offline tests, fixtures, mocks, static mappings, and migration regression checks.
- Uses synthetic or sanitized test data only.
- May develop and diagnose changes, but must not use production credentials, production Graph tenants, or production database connections.
- Produces local test output and design evidence; it does not establish live compatibility.

### Controlled Validation

- Uses a dedicated, non-production Microsoft Entra tenant or explicitly isolated validation scope with consented application permissions.
- Uses a dedicated PostgreSQL database initialized from the approved migrations and isolated credentials with least privilege.
- Runs representative workloads through the normal collection and persistence path, with bounded records, controlled test identities, and a defined cleanup policy.
- Captures redacted evidence outside the application data path. Access is limited to the validation operators and reviewers.
- Requires a pre-run checklist covering tenant/database identity, permission grants, schema version, test-data scope, time window, rollback plan, and evidence destination.
- No result is promoted to production until all required scenarios pass or a discrepancy is approved as a documented blocker.

### Production

- Remains isolated from controlled-validation credentials, databases, tenants, fixtures, and evidence.
- Receives only approved runtime artifacts after offline acceptance and controlled-validation evidence are reviewed.
- Does not serve as a test environment. Production validation, if separately approved, must use production-safe observability and change-control procedures rather than test writes or replay data.

## 3. Microsoft Graph Validation

Execute the following representative workloads in the controlled tenant using their configured application authentication, approved permissions, projections, pagination settings, and normal runtime path.

| Workload | Graph endpoint | Permission | Persistence mode |
|---|---|---|---|
| G01-005 Directory Audit | `GET /v1.0/auditLogs/directoryAudits` | `AuditLog.Read.All` | `EVENT` |
| G01-006 Sign-ins | `GET /v1.0/auditLogs/signIns` | `AuditLog.Read.All` | `EVENT` |
| G01-009 Devices | `GET /v1.0/devices` | `Device.Read.All` | `CURRENT` |
| G01-011 Conditional Access | `GET /v1.0/identity/conditionalAccess/policies` | `Policy.Read.All` | `CURRENT_WITH_SNAPSHOT` |
| G01-012 Named Locations | `GET /v1.0/identity/conditionalAccess/namedLocations` | `Policy.Read.All` | `CURRENT` |

For each workload, validate:

- **Authentication:** the controlled application can authenticate, the expected tenant is reached, and the configured permission is effective.
- **Permissions:** the endpoint succeeds with the documented least-privilege application permission; denied or missing permission is recorded as a controlled blocker, not bypassed.
- **Payload schema:** the response envelope and approved field set match the offline contract. Unapproved fields, raw payload retention, credentials, tokens, and authorization material must not enter evidence or persistence.
- **Field types:** observed scalar, nullable, nested, date/time, identifier, enum, and converted values match adapter assumptions. Missing and null optional fields are tested where the tenant permits.
- **Pagination:** all returned pages are followed, valid next links terminate correctly, record and page counts reconcile, and malformed pagination is treated as a failure rather than a successful empty result.
- **Adapter mapping:** approved live fields map to the expected normalized fields, trusted lineage is preserved, and unknown or sensitive fields are excluded.

Capture endpoint metadata, permission, page/record counts, observed field/type metadata, mapping result, and discrepancy classification only. Do not retain raw sensitive Graph responses.

## 4. PostgreSQL Validation

Use a dedicated PostgreSQL database initialized from the approved migrations. Validate the following representative persistence targets:

### EVENT

- `core.audit_event`

Exercise directory-audit and sign-in event identities, append behavior, duplicate replay, event-source binding, constraints, transaction commit, and rollback.

### CURRENT

- `core.application`
- `core.device`
- `core.named_location`

Exercise valid insert, deterministic update/upsert, duplicate replay, tenant lineage, closed column mapping, constraints, commit, and rollback.

### CURRENT_WITH_SNAPSHOT

- `core.conditional_access_policy`

Validate current-state upsert and the associated per-run snapshot behavior defined by the approved persistence contract. Where the contract uses a snapshot companion table, validate that companion as part of the same transaction and record its result without changing schema design.

Across all three modes, validate:

- **Schema:** expected schema/table existence, columns, types, nullability, keys, and lineage fields.
- **Constraints:** required fields, type checks, primary/unique keys, foreign keys, and applicable check constraints reject invalid writes safely.
- **Replay:** current rows update deterministically, event duplicates are ignored, and snapshots do not duplicate within the same collection run while a new run can create its own snapshot.
- **Rollback:** a deterministic failure after an earlier write leaves no partial batch committed, including current, snapshot, and event rows.
- **Transaction:** successful batches commit atomically, current-plus-snapshot writes share one transaction, and invalid tenant lineage is rejected before mutation.

Use synthetic, minimally identifying records and isolated test identities. Keep SQL parameter-bound and use only code-owned table/column mappings. Never use payload values as SQL identifiers or persist raw Graph payloads.

## 5. Evidence Model

Each validation scenario produces a bounded evidence record containing:

- **Validation ID:** unique scenario/run identifier.
- **Timestamp:** UTC execution timestamp.
- **Endpoint:** Graph method/path or PostgreSQL validation target/scenario.
- **Permission:** effective Graph permission, or `not_applicable` for database-only checks.
- **Record count:** observed, accepted, persisted, replayed, or rolled-back count as applicable.
- **Result:** `PASS`, `FAIL`, or `BLOCKED`, with a short redacted reason and discrepancy classification.

Evidence may also include page count, schema/type metadata, table/constraint outcome, transaction outcome, server-version metadata, and synthetic correlation identifiers when required to reproduce the result.

Evidence must exclude:

- tokens
- secrets
- credentials
- raw sensitive payload

Tenant identifiers, source identifiers, parameter values, connection strings, and error text must be minimized or redacted unless strictly required for review. Evidence is stored outside the runtime database under the approved retention and access procedure.

## 6. Success Criteria

The controlled validation is **PASS** only when all required representative scenarios have a recorded result and:

- the live API response matches the approved contract;
- database persistence is validated for `EVENT`, `CURRENT`, and `CURRENT_WITH_SNAPSHOT` behavior;
- evidence is captured using the bounded model above; and
- no unresolved discrepancy weakens authentication, permission, schema, mapping, tenant, transaction, rollback, replay, or sensitive-data controls.

A live response or database connection alone is not sufficient. Any unavailable permission, tenant configuration, database setup, or environmental dependency is a documented `BLOCKED` result and requires approved follow-up before production promotion.

## 7. Future Automation

This plan can become a **Scenario Validation Agent** by representing each scenario as a versioned definition containing preconditions, permitted actions, endpoint/database target, expected contract, evidence allowlist, cleanup steps, and pass/fail rules. The agent can then:

1. Verify environment identity and preconditions before execution.
2. Run Graph and PostgreSQL scenarios through approved interfaces with bounded limits.
3. Compare observed schemas, types, counts, mappings, and persistence outcomes with the contract.
4. Redact evidence at collection time and reject prohibited fields.
5. Execute cleanup or rollback and verify no test residue remains.
6. Produce a reviewable evidence bundle and promotion decision, escalating blockers without changing runtime code.

Automation remains future scope. Implementation requires a separately approved design, security review, permission model, evidence-retention policy, and operational runbook.

## 8. Relationship to Existing Plans

- `docs/evidence/TD-003-LIVE-GRAPH-VALIDATION-PLAN.md` provides endpoint-level Microsoft Graph execution detail.
- `docs/evidence/TD-004-LIVE-POSTGRESQL-VALIDATION-PLAN.md` provides database-level execution detail.

CH-2.3 provides the environment separation, gating, common evidence model, and future orchestration layer that connects those plans without replacing offline acceptance.
