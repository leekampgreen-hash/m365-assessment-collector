# G01-002-FIX2 Runtime Persistence Wiring Evidence

**Result:** PASS
**Date:** 2026-08-23

## Root Cause

The production CLI injected `_trusted_tenant_resolver` into `RuntimeOptions`, but constructed `CollectorRuntime` without `database_connection` or `collection_writer`. Consequently, successful normalized collections had no writer and could not reach persistence.

## Runtime Flow

```text
Production CLI
  -> trusted tenant resolver
  -> CollectorRuntime
  -> Dispatcher
  -> Security Boundary
  -> Writer
  -> Database
```

The CLI now opens the configured PostgreSQL DB-API connection and passes both it and the canonical `CollectionWriter` to `CollectorRuntime`. `--dry-run` does not open the connection.

## Persistence Flow

`CollectionWriter(connection, dispatch_persistence)` remains the only production writer construction. Runtime normalization invokes `collection_writer.write(normalized)`. The writer retains pre-transaction tenant and registry validation, executes `dispatch_persistence`, and commits or rolls back exactly as before.

No SQL, registry mapping, security-boundary rule, alternate writer, or transaction behavior was changed.

## Tests

Focused command:

```text
python3 -m unittest tests.core.test_auth_runtime_cli tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core
```

Result: **107 tests passed**.

Coverage includes:

- Production CLI database and `CollectionWriter` injection.
- Runtime dispatcher and writer handoff through the existing persistence path.
- Controlled failure when the persistence dependency is unavailable.
- Dry-run persistence non-initialization.
- Existing trusted tenant validation, missing resolver, and lineage mismatch regressions.
- Existing transaction, dispatcher, SQL, and tenant-boundary persistence tests.

## Limitations

The evidence is offline. Live Microsoft Graph and PostgreSQL integration remain deployment-level validation concerns. Production requires the `psycopg` driver and the protected runtime settings in `secrets/graph-agent-postgres-runtime.env` plus the separate password file.
