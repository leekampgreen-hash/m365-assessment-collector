# Engineering Baseline: Integration First

## Purpose

This is the canonical engineering baseline for production features and Security
rules. A component is not ready merely because its own tests pass. It is ready
only when production dependencies resolve, contracts are compatible, the
production entrypoint reaches it, the runtime image contains it, and its
persistence and product contracts accept its output.

Live Microsoft Graph testing confirms bounded real-tenant behavior. It must
not be the first place missing wiring is discovered.

## Required Delivery Sequence

1. **Contract first.** Define capability, license, Graph permission and
   permission type (`APPLICATION` or `DELEGATED`), inventory endpoint and
   endpoint type, auth mode, normalized output, evaluator, persistence payload,
   production entrypoint, API/UI exposure, runtime packaging, and DB/migration
   compatibility.
2. **Production wiring preflight.** Complete the Phase 0 checklist below before
   implementing or running a production feature. An unresolved mandatory
   dependency is `NOT_READY`; do not proceed directly to live execution.
3. **Unit tests.** Cover parsing, normalization, and deterministic rule
   semantics.
4. **Contract tests.** Cover module boundaries, inventory and registries,
   persistence shapes, and database vocabulary.
5. **Production-path integration test.** Exercise the real internal path with
   a fake Microsoft Graph boundary wherever practical.
6. **Runtime parity.** Prove the image build definition contains required
   production packages and configuration.
7. **One bounded live acceptance.** When external evidence is needed, perform
   one minimal, scoped tenant confirmation after the offline gates pass.

## Phase 0: Production Wiring Preflight

Every future production feature task report must include this reusable format:

```text
PRODUCTION_WIRING_PREFLIGHT:
- capability: PASS/MISSING/NOT_APPLICABLE
- license_requirement: PASS/MISSING
- graph_permission: PASS/MISSING
- auth_mode: PASS/MISSING
- inventory: PASS/MISSING
- collector_binding: PASS/MISSING
- evaluator: PASS/MISSING
- persistence_contract: PASS/MISSING
- production_entrypoint: PASS/MISSING
- api_surface: PASS/MISSING/NOT_APPLICABLE
- ui_surface: PASS/MISSING/NOT_APPLICABLE
- runtime_packaging: PASS/MISSING
- db_contract: PASS/MISSING/NOT_APPLICABLE

secret_contracts:
  <secret-name>:
    delivery_type: HOST_ENV_FILE | COMPOSE_FILE_SECRET | BIND_MOUNTED_SECRET | CONTAINER_GENERATED | OTHER
    host_contract:
      authoritative_source:
      expected_owner_group:
      expected_base_mode:
      expected_acl_entries: []
    container_contract:
      target_path:
      expected_runtime_consumer:
    configuration_reference:
    authorized_consumers: []
    status: PASS/FAIL/NOT_APPLICABLE

runtime_cleanup:
  candidate:
  provenance_proven_temporary: true/false
  active_reference_found: true/false
  cleanup_decision: SAFE_TO_DELETE / DO_NOT_DELETE / STOP

overall:
READY / NOT_READY
```

The evidence behind the entries must establish, where applicable: capability
vocabulary and license requirement; Graph permission and permission type; API
inventory endpoint and endpoint type; correct authentication; collector
binding; normalized observation contract; evaluator; persistence destination
and payload; orchestrator/entrypoint; generic API and UI paths; image package
or intentional mount; and database migration/constraint compatibility.

### SECRET_CONTRACT_PREFLIGHT

Every runtime secret must be checked by its own contract before runtime parity
or cleanup is approved. The contract records the secret name, delivery type,
authoritative host source, expected host owner/group, expected host base mode,
expected ACL entries, container target path, expected runtime consumer,
authorized consumers, active Compose/runtime references, and persistence
expectation. Supported delivery types are `HOST_ENV_FILE`,
`COMPOSE_FILE_SECRET`, `BIND_MOUNTED_SECRET`, `CONTAINER_GENERATED`, and
`OTHER`.

Validation is type-aware and secret-specific. It is explicitly prohibited to
assert that all secrets must be mode `0600` and owned by the runtime UID/GID.
`collector.env` is a `COMPOSE_FILE_SECRET` owned by `ubuntu:graphagent`
(`1000:1001`), with base mode `0640` and ACL `user:70:r--`; it is mounted
read-only and consumed by the Collector. `graph-agent-runtime-password` is an
independent `COMPOSE_FILE_SECRET` owned by `70:70`, mode `0600`, mounted
read-only, and consumed by database runtime clients. Both are
`VALID_BY_DESIGN` when their documented contracts hold. Secret values must
not be read, copied, logged, hashed, or checksum-tested by these tests.

### RUNTIME_ARTIFACT_SAFE_CLEANUP

Before deleting any runtime artifact, all of the following are mandatory:

- Verify actual path, type, size, ownership, and other metadata matches the
  expected temporary-artifact metadata.
- Verify it is not referenced by active Docker Compose configuration, active
  bind mounts, Docker/Compose secrets, deployment scripts, or runtime
  configuration.
- Verify provenance explicitly marks it `TEMPORARY`.
- Stop if expected state differs from actual state.
- Do not delete if temporary provenance cannot be proven.
- Never infer temporary status from a filename alone.

Active secret sources and active runtime references are never safe cleanup
targets. A cleanup report uses `SAFE_TO_DELETE` only after every invariant
passes; otherwise it uses `DO_NOT_DELETE` or `STOP` as applicable.

## Definition Of Ready

Implementation may begin only after the applicable Phase 0 items are known and
resolvable. A mandatory unresolved production dependency means `NOT_READY`.
Implementation-complete is not production-ready, and live testing is not an
exception to this gate.

Production features involving runtime or containers additionally require the
secret contract to be resolved, runtime artifacts to be classified, and every
cleanup operation to be provenance-checked.

## Definition Of Done

A feature or rule is `DONE` only after unit, contract, production-path
integration, runtime-parity, and persistence-contract tests pass; its
production entrypoint resolves it; and applicable generic API/UI paths resolve
it. One bounded live acceptance must also pass when external evidence is
required. Component tests alone are insufficient.

The completed feature must not remove a legitimate runtime secret or artifact,
must leave the documented secret delivery contract unchanged unless changing it
is explicitly part of the task, and must demonstrate runtime parity with
type-aware secret validation.

## Failure Semantics

Failures must retain their domain meaning. Missing entitlement is
`SKIP_NOT_LICENSED`, constructs no collector, makes zero Graph reads, produces
`NOT_EXECUTED` evaluation, and produces no false Security finding. Permission,
unknown capability, unavailable source, Graph, and persistence failures remain
distinct. Source failure is `NOT_EVALUATED`, never an `OPEN` finding. A
persistence retry reuses collected evidence and must not recollect Graph.

## Walking Skeleton Policy

A walking skeleton is required for a new domain, pipeline, runtime, or
persistence architecture. It is not required for every rule or feature added
to an already sealed production pipeline. Content expansion on a sealed
pipeline follows:

```text
PRECHECK -> IMPLEMENT CONTENT -> CONTRACT TEST -> PRODUCTION-PATH INTEGRATION TEST
-> RUNTIME PARITY -> LIVE ACCEPTANCE
```

Preserve the test pyramid: unit tests cover local semantics; contract tests
cover boundaries; integration tests use real internal production components and
a fake external Graph boundary; live tests are rare and bounded tenant
confirmations. Do not replace unit coverage with E2E tests.
