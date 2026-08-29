# G09-A E2E Validation Preflight

## Result

**G09-A RESULT: FAIL (preflight complete; implementation blockers prevent a
collector-to-database E2E execution).**

This is a read-only preflight grounded in the checked repository and the
running `graph-agent-dev` container on 2026-08-22. It did not request a token,
call Microsoft Graph, modify the tenant, create scenario activity, apply a
migration, or write application data.

The collector configuration is present and all 19 endpoints are enabled, but
the shipped CLI intentionally has no live HTTP opener and the runtime returns
only `CollectionResult` objects. Normalized rows are never passed to a writer;
there is no database connection, migration runner, tenant provisioning, or
SQL persistence entrypoint.

## Evidence And Preflight Checks

| Check | Result | Evidence |
|---|---|---|
| Inventory selection | PASS: 19 enabled endpoints | `python3 -m collectors.run_collector --all --dry-run --json` returned `selected_count=19`, `enabled_endpoint_count=19`, and no token/Graph request. |
| Protected collector auth configuration | PASS: present, not disclosed | The same dry-run returned `auth_config_present=true`; the secret mount is read-only (`docker-compose.yml:30`; `docker inspect graph-agent-dev`). |
| Collector live execution | BLOCKED | `collectors/run_collector.py:232-243` intentionally does not wire `http_open`; `CollectorRuntime.run()` requires it (`collectors/core/runtime.py:251-255`). |
| Endpoint-to-adapter mapping | PASS: 19/19 | Import-time registry validation enforces the exact `G01-001..G01-019` set (`collectors/workloads/registry.py:47-49,502-586`). |
| Normalization contract | PASS offline | `normalize_record(s)` produces mode-specific envelopes without Graph or DB I/O (`collectors/workloads/registry.py:735-787`). |
| DDL artifact contract | PASS offline | 234 targeted core/database/workload tests passed, including all 19 mappings, DDL shape, pagination/retry, and normalization semantics. |
| Deployed PostgreSQL and migrations | NOT READY | `docs/database-migrations.md:5,161-175,212-223` states migrations are not applied and connection/loading are future work; compose has no PostgreSQL service. |
| Database persistence entrypoint | BLOCKED | Registry and adapters explicitly have no DB writes (`collectors/workloads/registry.py:14-23,755`; `docs/g07-workload-integration.md:22-29`). |
| G08 accepted evidence | PASS, existing evidence only | G08 is limited to `SCN-AUTH-001`; its direct observation endpoint is G01-006 (`docs/g08-scenario-catalog.md:53,69,87`). G08 acceptance supplied device-code login, mandatory `/me` verification, and final G01-006 `errorCode=0`; no new login is authorized for G09-A. |

The full repository suite was also run as a diagnostic: 585 tests passed and
three `tests/scenario/live/test_d2_operator_entrypoint.py` tests failed due
unexpected/no mocked network-call expectations. Those failures are outside the
collector/persistence path and are not used to claim G09 readiness. The
targeted preflight suite passed: `234 tests ... OK`.

## Endpoint Matrix

`CURRENT` maps to G03 `CURRENT_ONLY`; `EVENT` maps to `EVENT_LOG`;
`CURRENT_WITH_SNAPSHOT` maps to `HISTORICAL_WITH_SNAPSHOT`;
`CURRENT_WITH_HISTORY` maps to `INCREMENTAL_HISTORICAL`; and `REFERENCE`
maps to `REFERENCE` (`docs/g07-workload-integration.md:74-100`). All endpoint
calls are `GET`, application-authenticated, and read-only per
`config/api_inventory.json`.

| ID | Graph endpoint | Required application permission | Collector adapter | Mode and normalized target | G09 validation point |
|---|---|---|---|---|---|
| G01-001 | `/v1.0/users` | `User.Read.All` | directory `users` | CURRENT -> `core."user"` | Id-keyed current upsert contract; page traversal. |
| G01-002 | `/v1.0/groups` | `Group.Read.All` | directory `groups` | CURRENT -> `core."group"` | Id-keyed current upsert contract; page traversal. |
| G01-003 | `/v1.0/organization` | `Organization.Read.All` documented | directory `organization` | CURRENT -> `core.organization` | One-row current contract; preserve G01 observed-without-documented-role anomaly. |
| G01-004 | `/v1.0/subscribedSkus` | `LicenseAssignment.Read.All` | directory `subscribed_skus` | CURRENT_WITH_SNAPSHOT -> `core.subscribed_sku`, `core.subscribed_sku_snapshot` | Current and one snapshot per source ID/run. |
| G01-005 | `/v1.0/auditLogs/directoryAudits` | `AuditLog.Read.All` | security `adapt_directory_audit_logs` | EVENT -> `core.audit_event` (`DIRECTORY_AUDIT`) | Append-only event identity and source discriminator. |
| G01-006 | `/v1.0/auditLogs/signIns` | `AuditLog.Read.All` | security `adapt_sign_in_logs` | EVENT -> `core.audit_event` (`SIGN_IN`) | Append-only sign-in identity; G08 correlation evidence. |
| G01-007 | `/v1.0/applications` | `Application.Read.All` | directory `applications` | CURRENT -> `core.application` | Id-keyed current upsert contract. |
| G01-008 | `/v1.0/servicePrincipals` | `Application.Read.All` | directory `service_principals` | CURRENT -> `core.service_principal` | Multi-page read and deterministic ID normalization. |
| G01-009 | `/v1.0/devices` | `Device.Read.All` | directory `devices` | CURRENT -> `core.device` | Id-keyed current upsert contract. |
| G01-010 | `/v1.0/directory/administrativeUnits` | `AdministrativeUnit.Read.All` | directory `administrative_units` | CURRENT -> `core.administrative_unit` | Empty result is valid; do not synthesize a row. |
| G01-011 | `/v1.0/identity/conditionalAccess/policies` | `Policy.Read.All` | security `conditional_access_policies` | CURRENT_WITH_SNAPSHOT -> `core.conditional_access_policy`, `core.conditional_access_policy_snapshot` | Metadata-only current plus per-run snapshot. |
| G01-012 | `/v1.0/identity/conditionalAccess/namedLocations` | `Policy.Read.All` | security `named_locations` | CURRENT -> `core.named_location` | Current-state field minimization. |
| G01-013 | `/v1.0/identityProtection/riskyUsers` | `IdentityRiskyUser.Read.All` | security `risky_users` | CURRENT_WITH_SNAPSHOT -> `core.risky_user`, `core.risky_user_snapshot` | Current state plus sensitive per-run snapshot. |
| G01-014 | `/v1.0/identityProtection/riskDetections` | `IdentityRiskEvent.Read.All` | security `adapt_risk_detections` | EVENT -> `core.risk_detection` | Append-only event ID deduplication. |
| G01-015 | `/v1.0/admin/serviceAnnouncement/healthOverviews` | `ServiceHealth.Read.All` | security `service_health_overview` | CURRENT_WITH_SNAPSHOT -> `core.service_health_overview`, `core.service_health_overview_snapshot` | Status current row plus per-run snapshot. |
| G01-016 | `/v1.0/admin/serviceAnnouncement/issues` | `ServiceHealth.Read.All` | security `service_health_issues` | CURRENT_WITH_HISTORY -> `core.service_health_issue`, `core.service_health_issue_history` | Current upsert plus deterministic versioned history. |
| G01-017 | `/v1.0/admin/serviceAnnouncement/messages` | `ServiceMessage.Read.All` | security `service_update_messages` | CURRENT_WITH_HISTORY -> `core.service_update_message`, `core.service_update_message_history` | Current upsert plus deterministic versioned history. |
| G01-018 | `/v1.0/roleManagement/directory/roleDefinitions` | `RoleManagement.Read.Directory` | directory `directory_role_definitions` | REFERENCE -> `core.directory_role_definition` | Reference upsert; `rolePermissions` must remain excluded. |
| G01-019 | `/v1.0/roleManagement/directory/roleAssignments` | `RoleManagement.Read.Directory` | directory `directory_role_assignments` | CURRENT_WITH_SNAPSHOT -> `core.directory_role_assignment`, `core.directory_role_assignment_snapshot` | Sensitive current assignment plus per-run snapshot. |

**Mapped: 19/19.** Adapter/table ownership is the import-time checked registry
at `collectors/workloads/registry.py:278-482`; the endpoint paths, permissions,
pagination settings, and selected fields are in `config/api_inventory.json:3-271`.

## Runtime, Permissions, And Security Boundaries

The collector uses app-only client credentials and requests only
`https://graph.microsoft.com/.default` (`collectors/core/auth.py:171-175,213-230`).
The required configuration names are `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, and
`GRAPH_CLIENT_SECRET`; values were neither read into this plan nor printed.
Tokens are process-memory-only and the Graph transport does not retain them.

The required documented application roles are the 14 unique permissions listed
in `docs/permission-matrix.md:123-140`. G01 discovery already established
HTTP 200 coverage for all 19 endpoints with 13 confirmed token roles. G01-003
must retain its documented anomaly: its documented `Organization.Read.All` role
was absent from the observed token while the endpoint returned HTTP 200
(`docs/permission-matrix.md:13-31,78-103`). G09 must report a permission or
Graph regression; it must not grant, alter, or broaden roles.

The container is non-root (`1000:1001`) and mounts `secrets/` read-only. No
G09 execution may log tokens, secrets, `Authorization` headers, raw scenario
credentials, raw Graph bodies, or actor identities. Raw payload retention
remains off by default; a future writer would need recursive scrub before any
`raw.raw_graph_record` insert (`database/migrations/006_raw_traceability.sql:9-25`).

## Semantics And Validation Points

| Area | Current implementation evidence | G09 acceptance check | Status now |
|---|---|---|---|
| Pagination | `Paginator` follows `@odata.nextLink`; initial URL includes inventory `$select`/`$top` (`collectors/core/pagination.py:52-107`, `collector.py:114-123`). | Fixture: multi-page value set; real reads: verify `pages`, `rows`, and next-link completion for a naturally paged endpoint. | Offline PASS; real read pending. |
| Retry and errors | 401/403 never retry; 429/API/network are bounded, with integer `Retry-After` honored (`collectors/core/retry.py:34-83`). | Fixture injects 401, 403, 429, 5xx, and network error; assert final classification and retry count. Do not induce tenant-side errors. | Offline PASS. |
| Tenant isolation | Every normalized row carries supplied lineage tenant ID; DDL keys/FKs scope operational data by `tenant_id`. | Fixture with two distinct tenant IDs must produce distinct row keys. Persistence test later verifies no cross-tenant conflict/read. | Normalization/DDL PASS; DB test blocked. |
| Deterministic identity/versioning | Registry preserves source order; G01-016/017 use SHA-256 version identity based on tenant, source ID and modification/lifecycle fields. | Re-normalize identical record and assert equal identity; alter timestamp/fallback field and assert identity changes. | Offline PASS. |
| Duplicate/idempotency | DDL supplies tenant-scoped unique keys for current/event/snapshot/history rows. | Future writer: execute same normalized batch twice in one transaction set; assert no duplicate event/snapshot/history rows and stable current state. | BLOCKED: no writer or DB. |
| Snapshot | Five snapshot modes emit current + snapshot envelopes. DDL uniqueness is `(tenant_id, source_object_id, collection_run_id)`. | Fixture and future two-run DB test: new run creates a new snapshot, same run does not duplicate it. | Offline shape PASS; DB test blocked. |
| Event log | G01-005/006 share `core.audit_event` with source discriminator; G01-014 uses `core.risk_detection`. | Fixture and future repeat-insert test: unique event identities suppress duplicates without overwriting event time. | Offline shape PASS; DB test blocked. |
| Reference | G01-018 produces a reference/current envelope to one reference target. | Fixture verifies deterministic reference row and exclusion of `rolePermissions`; future writer upserts by tenant/source ID. | Offline shape PASS; DB test blocked. |
| Incremental/history | G01-016/017 emit current + history; history key is `(tenant_id, source_object_id, version_identity)`. | Fixture plus future two-version DB test: changed lifecycle creates a second history row; unchanged record does not. | Offline shape PASS; DB test blocked. |

## Executable G09 Test Matrix

The plan has **17 test cases: 9 offline/evidence tests and 8 real-Graph-read
tests**. It currently has **0 executable database-persistence tests** because
the required writer and deployed database do not exist. All real Graph tests
are GET-only, app-only collector reads. They must be run only after the live
HTTP wiring blocker is remediated, with no scenario invocation and with result
output restricted to safe counters/classifications.

| ID | Type | Scope | Procedure and expected result | Preconditions |
|---|---|---|---|---|
| OFF-01 | Offline | Inventory/runtime | Run `python3 -m collectors.run_collector --all --dry-run --json`; expect 19 selected/enabled, auth config present, no token and no Graph request. | None. |
| OFF-02 | Offline | 19 adapters/modes | Run targeted core/database/workload test suite; expect registry coverage, one adapter per endpoint, normalized envelope shape, field exclusion, and DDL mapping pass. | None. |
| OFF-03 | Offline | Pagination/retry/error | Run `tests.core.test_collector_framework`; expect next-link traversal, bounded retry, safe 401/403/429/5xx/network classifications. | None. |
| OFF-04 | Offline | Snapshot/event/reference/history | Run `tests.workloads.test_integration` and adapter tests; expect the five contract modes and event discriminators. | None. |
| OFF-05 | Offline | Identity/isolation/idempotency contract | Run workload/versioning and migration tests; expect deterministic tenant-scoped identities and DDL unique constraints. | None. |
| OFF-06 | Offline | DDL/security | Run `tests.database.test_migrations`; expect 29 DDL tables, no destructive DDL/credential columns, and raw guardrail metadata. This is not an applied-database test. | None. |
| OFF-07 | Offline | Persistence wiring negative test | Inspect runtime/CLI/registry; expect no SQL driver, connection setup, migration runner, writer, or normalization handoff. Record blocker rather than bypassing it. | None. |
| OFF-08 | Offline | G08 Scenario -> Entra -> G01-006 | Replay existing G08 acceptance evidence only: device-code success, `/me` actor match, and accepted G01-006 sign-in result with `errorCode=0`. Do not call device-code, `/me`, or Graph. | Existing accepted G08 evidence. |
| OFF-09 | Offline | Safety boundary | Run scenario/core safety tests that avoid real network; verify secret/token redaction, strict G08 action/scope gating, and no persistence to disk. Treat the three existing operator-entrypoint mock failures as diagnostic failures requiring separate remediation. | None. |
| READ-01 | Real Graph READ | Identity | Collect G01-001 Users. Assert PASS, safe page/row counters, selected-field URL, and normalize a sampled in-memory record; do not persist. | Remediated live HTTP wiring; current app roles. |
| READ-02 | Real Graph READ | Licensing | Collect G01-004 Subscribed SKUs. Assert PASS and in-memory current/snapshot envelopes for sampled rows; do not persist. | Same. |
| READ-03 | Real Graph READ | Audit/authentication | Collect G01-006 Sign-ins only. Assert PASS and `SIGN_IN` event normalization. This is a normal read, not a new G08 login. | Same; no scenario action. |
| READ-04 | Real Graph READ | Conditional Access | Collect G01-011 Policies. Assert PASS and metadata-only current/snapshot normalization; do not collect policy bodies. | Same. |
| READ-05 | Real Graph READ | Identity Protection | Collect G01-013 Risky Users. Assert PASS and current/snapshot contract using safe counters/field shapes only. | Same. |
| READ-06 | Real Graph READ | Service Health | Collect G01-016 Issues. Assert PASS and in-memory current/history version identity. | Same. |
| READ-07 | Real Graph READ | Change Communications | Collect G01-017 Messages. Assert PASS and in-memory current/history version identity; do not retain message bodies. | Same. |
| READ-08 | Real Graph READ | RBAC | Collect G01-018 Role Definitions. Assert PASS, reference normalization, and `rolePermissions` exclusion. | Same. |

The eight real-read cases cover all eight G03 data domains. The full 19-endpoint
real-read sweep remains a G09-B acceptance expansion after READ-01 through
READ-08 pass; it must use the endpoint matrix above and no persistence until
the persistence blocker is remediated.

## Database Readiness And Required Future Tests

The schema artifacts are internally validated but **database persistence is not
ready**:

1. `docker-compose.yml` contains only the graph-agent service, not PostgreSQL.
2. G06 explicitly left migrations unapplied, tenant provisioning, DB roles,
connection management, and all DML to later work (`docs/database-migrations.md:161-175,212-223`).
3. `CollectorRuntime` yields only `CollectionResult`; `BaseCollector` does not
return records to callers (`collectors/core/runtime.py:214-284`,
`collectors/core/collector.py:55-112`).
4. The G07 registry can normalize a caller-provided record but explicitly does
not write it (`collectors/workloads/registry.py:735-787`).

After remediation, G09-B must first run a disposable, isolated PostgreSQL
instance with migrations applied and a pre-provisioned test tenant. It must
then execute the following database-only validations without changing Entra:

| DB validation | Required assertion |
|---|---|
| Control lineage | One `collection_run` and one `endpoint_run` per selected endpoint, with safe status/counters. |
| Current/reference | Replaying a source ID updates/upserts only within `(tenant_id, source_object_id)`. |
| Snapshots | Same run is idempotent; a different run adds exactly one snapshot version per source ID. |
| Events | Repeat event insert is ignored by the relevant tenant/source/event identity; G01-005 and G01-006 remain distinguished by `event_source`. |
| Incremental history | Identical G01-016/017 version identity is ignored; changed modification/fallback state inserts a second history record and updates current state. |
| Isolation | The same source ID in two test tenants neither conflicts nor cross-reads. |
| Raw disabled/scrubbed | No raw writes by default. If explicitly enabled in a later approved task, verify recursive scrub, hash, size, lineage, and rejected credential-shaped payloads. |

## Blockers

1. **BLOCKER: no executable live collector entrypoint.** The CLI rejects normal
execution because it does not supply `RuntimeOptions.http_open`. A caller can
use the library programmatically, but no supported G09 command or deployment
wires the HTTP opener.
2. **BLOCKER: collector output is not connected to normalization.** The
collector counts paged records in `CollectionResult`; it does not expose their
safe in-memory records to the workload registry with collection/endpoint
lineage.
3. **BLOCKER: no database deployment or migration application.** No PostgreSQL
service, connection configuration, migration runner, or provisioned
`core.tenant` row exists in the runtime.
4. **BLOCKER: no persistence writer.** No transactional SQL implementation
creates control rows, executes mode-specific upserts/inserts, enforces conflict
behavior, or recursively scrubs optional raw payloads.
5. **Diagnostic gap: full suite has three G08 operator-entrypoint test
failures.** They are not a reason to rerun authentication or generate a new
login. Resolve their mocked transport behavior separately before using the
full suite as a G09 gate.

## Recommended G09 Execution Order

1. Run OFF-01 through OFF-09 and retain only safe test summaries.
2. Remediate and independently review live HTTP wiring while retaining
app-only, GET-only, secret-redaction boundaries.
3. Run READ-01 through READ-08 one at a time, then the 19-endpoint read-only
sweep if all domain representatives pass.
4. Remediate database deployment, migration application, collection-to-
normalization handoff, and transactional persistence writer.
5. Run the isolated database validations, then perform a final 19-endpoint
Graph-read-to-persistence acceptance in G09-B.

## G09-A Return Values

```text
G09-A RESULT=FAIL
ENDPOINTS_MAPPED=19/19
COLLECTOR_RUNTIME_READY=NO
DATABASE_PERSISTENCE_READY=NO
E2E_TESTCASES=17
REAL_GRAPH_READ_TESTS=8
OFFLINE_TESTS=9
BLOCKERS=LIVE_HTTP_OPENER_UNWIRED;COLLECTED_RECORDS_NOT_HANDED_TO_NORMALIZER;NO_POSTGRES_DEPLOYMENT_OR_MIGRATION_APPLICATION;NO_TRANSACTIONAL_PERSISTENCE_WRITER;THREE_EXISTING_G08_OPERATOR_ENTRYPOINT_TEST_FAILURES
RECOMMENDED_G09_EXECUTION_ORDER=OFF-01..OFF-09->remediate_live_runtime->READ-01..READ-08->19_endpoint_read_sweep->remediate_persistence->isolated_DB_validation->G09-B
NEXT_PHASE=REMEDIATION
```
