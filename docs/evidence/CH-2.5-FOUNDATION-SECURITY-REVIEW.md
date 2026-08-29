# CH-2.5 Foundation Security Review

- **Usage mark:** `CH-2.5-FOUNDATION-SECURITY-REVIEW-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `SECURITY_REVIEW`
- **Date:** 2026-08-23
- **Scope:** G01-002 through G01-012
- **Review type:** Documentation review only
- **Security acceptance:** **PASS WITH LIMITATIONS**

## 1. Executive Summary

This review assesses the foundation security posture for G01-002 through
G01-012 using the existing workload evidence, permission matrix, catalog,
schema documentation, controlled-validation plan, and security-boundary
evidence. The reviewed design is a shared flow:

```text
Application-authenticated Graph Collector
    -> approved Adapter projection
    -> Registry contract
    -> Persistence Dispatcher
    -> security boundary
    -> parameter-bound Writer
    -> PostgreSQL
```

The documentation supports the following security conclusions for offline
validation:

- Application-only Graph authentication is the declared authentication model.
- Endpoint permissions are inventory and registry controlled rather than
  selected by payload data.
- Tenant identity comes from trusted runtime lineage, not from Graph payloads.
- Missing, malformed, or cross-tenant lineage fails closed before SQL/writer
  execution.
- Adapters use approved projections and exclude unknown fields, credentials,
  tokens, authorization material, and raw Graph payloads.
- Persistence uses parameter-bound values, closed table/column mappings,
  tenant-scoped conflict keys, replay protection, and transaction rollback.
- Evidence has a bounded allowlist and must not contain secrets or raw payloads.

The result is not a live certification. No live Graph execution, live tenant,
or live PostgreSQL instance was used for this review. The G01-003 observed
permission anomaly and previously documented registry retention drift remain
visible follow-up items. Accordingly, the foundation security posture is
accepted as **PASS WITH LIMITATIONS** for documented offline evidence.

## 2. Authentication Review

### Application Authentication

The reviewed G01 workload contracts declare application authentication and use
the existing Microsoft Graph application-only runtime boundary. The reviewed
security workload evidence explicitly describes client-credentials
authentication and the `.default` scope. No delegated or interactive
authentication path is introduced for these workloads.

Offline evidence validates that the collector inventory, authentication
context, endpoint contract, and permission declaration are connected. The
evidence does not establish that a future or differently configured tenant
will grant exactly the declared permissions; that requires controlled live
validation.

### Tenant Binding

Tenant lineage is established by trusted runtime context and carried through
the normalized persistence envelope. It is not taken from a Graph response
property. The tenant-boundary evidence states that the trusted collection
tenant and each populated normalized row tenant must be present, well formed,
and equal before transaction start. Missing, malformed, or mismatched values
are rejected without writer or SQL invocation.

### Token Handling Boundary

Token acquisition and authorization headers are confined to the Graph
authentication/transport boundary. Tokens, bearer values, credentials, client
secrets, authorization material, and connection strings are not accepted as
normalized data or evidence fields. Adapters do not pass token-bearing
structures through to persistence. This is an offline boundary assertion;
secret-store, process, network, and production logging behavior remains
outside this documentation review.

**Assessment:** PASS for documented offline controls; live authentication and
token-boundary behavior remains unverified.

## 3. Permission Review

The permission matrix records application authentication for the relevant
endpoints and confirms the following requested permission groups:

| Permission | Workloads | Offline assessment |
|---|---|---|
| `AuditLog.Read.All` | G01-005 Directory Audit; G01-006 Sign-ins | Required, present in the recorded collector token, and both endpoints returned HTTP 200 in the historical discovery evidence. Shared permission is explicitly documented. |
| `Device.Read.All` | G01-009 Devices | Required and present in the recorded collector token; endpoint was classified PASS in discovery. |
| `Policy.Read.All` | G01-011 Conditional Access Policies; G01-012 Named Locations | Required, present in the recorded collector token, and both endpoints returned HTTP 200 in discovery. Shared permission is explicitly documented. |
| `Application.Read.All` | G01-007 Applications; G01-008 Service Principals | Required, present in the recorded collector token, and both endpoints returned HTTP 200 in discovery. Shared permission is explicitly documented. |

The inventory-driven contract binds each endpoint to its documented permission,
and the collector/runtime flow checks the endpoint contract before collection.
The review does not treat a historical HTTP 200 as proof of least privilege
for every tenant or future Graph behavior.

**Preserved finding:** G01-003 Organization returned HTTP 200 while
`Organization.Read.All` was absent from the recorded discovery token. This is
outside the four requested permission groups but is security-relevant and
remains an unresolved documented permission-behavior anomaly for G02 analysis.

**Assessment:** PASS for offline contract and historical evidence, with live
consent and effective-permission validation outstanding.

## 4. Tenant Isolation Review

### Tenant Identity Source

The authoritative tenant identity source is trusted runtime collection
lineage. Graph payload fields cannot override it. The persistence boundary
validates both the trusted collection tenant and every populated normalized row
tenant before SQL execution.

### Cross-Tenant Rejection

Cross-tenant records, missing tenant IDs, malformed tenant IDs, and missing
trusted tenant context fail closed. The documented tests assert that rejected
inputs do not invoke a writer or execute SQL. Tenant-scoped foreign keys and
unique/conflict keys further preserve isolation at the persistence contract:

- Current state generally uses `(tenant_id, source_object_id)`.
- Event state uses `(tenant_id, event_source, source_object_id)`.
- Snapshots use `(tenant_id, source_object_id, collection_run_id)`.
- G01-003 organization uses tenant-scoped `(tenant_id)` identity.

**Assessment:** PASS for documented offline tenant-boundary behavior. A live
tenant test is required to verify runtime identity configuration and actual
deployment behavior.

## 5. Data Minimization Review

### Approved Field Projections

The reviewed adapters retain only endpoint-approved fields. Representative
approved projections include:

- G01-005: `id`, `activityDateTime`, `activityDisplayName`, `category`,
  `result`, `loggedByService`.
- G01-006: the documented seven-field sign-in projection, with sensitive
  location/network and correlation details excluded.
- G01-007: `id`, `appId`, `displayName`, `createdDateTime`, `signInAudience`.
- G01-009: the documented seven-field device projection.
- G01-011: `id`, `displayName`, `state`, `createdDateTime`,
  `modifiedDateTime`.
- G01-012: `id`, `displayName`, `createdDateTime`, `modifiedDateTime`.

Unknown properties and unrelated nested objects are not propagated. Required
identifiers and malformed records fail closed; optional approved fields remain
nullable where documented.

### Credential and Token Exclusion

Evidence across the reviewed workloads excludes passwords, secrets, keys,
password/key credentials, bearer values, tokens, authorization fields, and
other credential-shaped material. Service-principal and application reviews
specifically exclude permission, assignment, key, password, and authorization
structures.

### Raw Payload Exclusion

Raw Graph response objects, response bodies, payload fragments, and unapproved
nested data are not part of the normalized persistence envelope or bounded
evidence model. This prevents a broad payload from bypassing the projection
boundary.

**Assessment:** PASS for documented offline projection and exclusion tests.

## 6. Persistence Security Review

### Parameter-Bound SQL

SQL values are passed as parameters. Table and column identifiers come only
from closed, code-owned endpoint mappings; normalized input cannot select SQL
identifiers. The controlled-validation plan preserves these requirements for
future live testing.

### Closed Mappings

Registry endpoint identity, persistence mode, target table, event source, and
adapter mapping are controlled metadata. The dispatcher selects the approved
mode-specific path. No payload-controlled table, column, writer, or event
source selection is accepted.

### Replay Protection

- `EVENT` workloads use tenant/event-source/object identity and conflict-safe
  no-op behavior (`ON CONFLICT DO NOTHING`).
- `CURRENT` workloads use tenant/object upsert identity and deterministic
  `ON CONFLICT DO UPDATE` behavior.
- `CURRENT_WITH_SNAPSHOT` workloads update current state and create a
  run-scoped snapshot using `(tenant_id, source_object_id, collection_run_id)`;
  snapshot replay is conflict-safe.

Replay does not bypass tenant validation or the approved persistence path.

### Transaction Rollback

`CollectionWriter` preserves one transaction for a collection batch. Current
and snapshot writes are atomic where both are required. Documented failure
injection tests assert rollback and no commit after post-`BEGIN` writer
failure; malformed pages fail before persistence, preventing partial batches.

**Assessment:** PASS for offline SQL, mapping, replay, and rollback evidence;
live PostgreSQL behavior remains unverified.

## 7. Evidence Security Review

### Allowed Evidence Fields

Evidence may contain only bounded operational metadata needed to reproduce and
review an outcome:

- review/validation or execution identifier;
- UTC timestamp;
- code-owned endpoint or database target identity;
- declared/effective permission name, or `not_applicable` for database checks;
- bounded page, record, accepted, persisted, replayed, or rolled-back counts;
- result/status such as `PASS`, `FAIL`, `BLOCKED`, `ACCEPTED`, or `REJECTED`;
- controlled failure category and normalized reason code;
- schema/type/constraint/transaction outcome metadata;
- bounded HTTP status class, duration, retry count, or synthetic correlation ID;
- short redacted discrepancy classification and recommended action.

### Forbidden Sensitive Fields

Evidence must not contain:

- access, refresh, bearer, or session tokens;
- client secrets, passwords, private keys, credentials, or authorization
  headers;
- connection strings, SQL parameters, or secret-store material;
- raw Graph responses, raw database rows, response bodies, payload fragments,
  free-form sensitive text, or unredacted exception details;
- unnecessary tenant IDs, source IDs, user identifiers, IP/location data, or
  other high-cardinality sensitive values.

URLs with query data, headers, SQL parameters, response bodies, and exception
text require redaction and normalization before evidence capture. Evidence is
intended to remain outside the runtime data path under controlled access and
retention procedures.

**Assessment:** PASS as a documented evidence contract; actual sink access,
retention, and logging configuration require future controlled validation.

## 8. Security Limitations

This review is documentation-only and offline. Specifically:

- No live Microsoft Graph execution was performed.
- No live Graph credentials, consented validation tenant, or production tenant
  was used.
- Application permission grants and endpoint behavior were not independently
  revalidated in a live tenant.
- Tenant-specific payload variation, nullable behavior, and pagination were
  not tested against live responses.
- No live PostgreSQL instance was used.
- Runtime database constraints, parameter binding, commit/rollback, replay,
  and deployment-specific access controls were not live-certified.
- No production tenant testing was performed and production must not be used
  as a test environment.
- Four registry retention metadata drifts remain open for G01-005, G01-006,
  G01-013, and G01-014; these are governance follow-up items and were not
  changed by this review.
- Operational metrics, evidence sinks, dashboards, alerting, and recovery
  workflows remain planned under CH-2.4/TD-005/TD-006.

These limitations prevent an unrestricted PASS claim but do not invalidate the
documented offline foundation controls.

## 9. Security Acceptance Decision

### Decision: PASS WITH LIMITATIONS

The foundation security posture for G01-002 through G01-012 is accepted for
documentation and offline validation because the reviewed evidence supports
authentication boundaries, permission contracts, tenant isolation, data
minimization, evidence restrictions, parameter-bound closed persistence,
replay protection, and rollback behavior.

The decision is explicitly limited to the reviewed artifacts and offline
evidence. It is not production security certification, live Graph permission
certification, live tenant-isolation certification, or live PostgreSQL
certification. Promotion beyond this documented foundation requires the
controlled validation activities in CH-2.3, TD-003, and TD-004.

**Production code changed:** None.

**Restricted areas unchanged:** `collectors/`, adapters, registry runtime,
persistence runtime, and database migrations.
