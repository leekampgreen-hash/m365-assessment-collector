# Architecture

## G10 Foundation Architecture Freeze

The G10 Foundation is **ACCEPTED**. Future endpoints must reuse the established pipeline and preserve its trust, validation, dispatch, and persistence boundaries:

```text
Graph Collector
    |
    v
Adapter
    |
    v
Registry
    |
    v
Persistence Dispatcher
    |
    v
Security Boundary
    |
    v
Writer
    |
    v
Database
```

The accepted foundation provides Graph runtime flow, trusted tenant handling, generic persistence dispatch, security validation, event validation, and documentation governance. Remaining debt is tracked for registry/SQL mapping duplication, live PostgreSQL integration coverage, rejection metrics/tracing, and retry recovery hardening.


## G10-001B2-FIX3 Persistence Security Boundary

`CollectionWriter.write` is the transactional trusted-context boundary for normalized collections. Before opening a transaction, it validates the trusted collection tenant, all populated record tenants, record endpoint identity, and registry persistence-mode agreement. This applies equally to the registry dispatcher and injected writer flows.

`dispatch_persistence` completes batch endpoint and mode validation before invoking a mode-specific handler. Each public low-level handler validates populated row tenant IDs before parameter-bound SQL execution. Closed endpoint maps retain control of SQL identifiers, and the event handler retains its registry-owned event-source discriminator validation. Rejections occur before SQL; transaction rollback remains responsible only for failures after `BEGIN`.

## G10-001B2 Persistence Metadata Debt

### Current State

- The registry controls endpoint metadata.
- Persistence contains additional SQL mapping metadata.

This duplication is currently retained because the implementation is stable and tested, while an immediate consolidation would introduce unnecessary regression risk.

### Target State

The registry becomes the authoritative persistence contract, including endpoint metadata and the mapping required by persistence. Persistence should consume that contract rather than maintain a parallel mapping.

### Reason

A single authoritative contract reduces metadata drift, clarifies ownership, and makes endpoint-to-persistence behavior easier to review and evolve. The change is deferred to avoid destabilizing the current tested implementation.

### Migration Approach

1. Inventory and compare registry metadata with the existing persistence SQL mapping.
2. Define the registry-authoritative contract and preserve compatibility for existing persistence modes.
3. Migrate persistence writers and dispatcher validation to consume the registry contract.
4. Remove redundant mappings only after focused and integration validation confirms equivalent SQL behavior, tenant boundaries, event controls, and transaction semantics.

### Risks

- A contract migration could alter endpoint-to-table or column behavior unintentionally.
- Metadata drift may persist until consolidation is complete.
- Removing parallel mappings too early could create regressions in persistence dispatch, event control, or schema alignment.
- The target design requires coordinated updates across registry, persistence, schema documentation, and validation coverage.
