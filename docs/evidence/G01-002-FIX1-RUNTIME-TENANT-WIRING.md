# G01-002-FIX1 Runtime Tenant Wiring Evidence

**Usage mark:** G01-002-FIX1-RUNTIME-TENANT-WIRING-001  
**Session:** NEW  
**Model:** kl/gpt-5.6-luna  
**Purpose:** IMPLEMENTATION  
**Date:** 2026-08-23

## Result

**PASS**

## Root Cause

`collectors/run_collector.py` constructed `RuntimeOptions(max_retries=...)` without a `tenant_resolver`. `CollectorRuntime` already required this dependency before binding lineage and normalizing G01 records, so a normal CLI execution reached `_resolve_trusted_tenant()` and failed closed with `trusted tenant resolver is required`.

## Files Changed

- `collectors/run_collector.py`
- `tests/core/test_auth_runtime_cli.py`
- `docs/PROJECT_PROGRESS.md`
- `docs/CHANGELOG.md`
- `docs/AI_USAGE_LOG.md`
- `docs/evidence/G01-002-FIX1-RUNTIME-TENANT-WIRING.md`

## Runtime Flow

1. The CLI loads the existing trusted auth source and creates `RuntimeOptions`.
2. The CLI injects `_trusted_tenant_resolver` into those options.
3. The resolver reads only protected runtime configuration `GRAPH_TENANT_DB_ID`, representing the internal positive `core.tenant.tenant_id` surrogate.
4. `CollectorRuntime.run()` loads the authenticated `CollectorAuthConfig`, resolves the trusted internal tenant, and binds lineage to it.
5. Graph collection, normalization, registry dispatch, persistence security validation, and writers continue through the existing foundation flow.

Dry-run still resolves inventory and validates auth configuration without invoking the resolver, requesting a token, or calling Graph.

## Security Impact

- Tenant identity is supplied by trusted runtime configuration, not by endpoint arguments, request payloads, or Graph records.
- The external Entra GUID in `CollectorAuthConfig.tenant_id` is not confused with the internal database surrogate.
- Missing, non-numeric, zero, and negative internal tenant IDs fail closed.
- Existing lineage tenant mismatch and persistence tenant-boundary validation remain active.
- No database schema, authentication design, dispatcher, writer, or persistence boundary was changed.

## Test Results

Command:

```text
python3 -m unittest tests.core.test_auth_runtime_cli tests.core.test_g09_r2_normalization_handoff
```

Result: **70 tests passed**.

Coverage includes:

- T001: CLI creates `RuntimeOptions` with the trusted tenant resolver.
- T002: Missing and malformed trusted tenant configuration fails closed.
- T003: Valid resolver wiring preserves collection flow.
- T004: Existing tenant mismatch validation rejects before writer invocation.

## Known Limitations

- The focused tests use offline fakes and do not exercise live Microsoft Graph or PostgreSQL.
- Deployment/runtime configuration must provide `GRAPH_TENANT_DB_ID` with the internal `core.tenant.tenant_id` for non-dry-run CLI execution.
- This fix does not add a database lookup or redesign authentication; provisioning and management of the trusted mapping remain outside this task.
