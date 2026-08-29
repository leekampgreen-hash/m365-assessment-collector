# EX-P04A Exchange Persistence Safety Correction

- **Task ID:** `EX-P04A-EXCHANGE-PERSISTENCE-SAFETY-CORRECTION-001`
- **Date:** 2026-08-29
- **Result:** `EX_P04A_PASS`

## Corrections

- Complete acquisition is required before destructive current replacement; incomplete reports fail before SQL execution.
- Normalized source business keys are case-folded and duplicate `(tenant_id, entity_key)` rows are rejected before persistence with a safe tenant/key/count error.
- Current and snapshot writes remain in one transaction; validation occurs before `BEGIN`.
- Numeric normalization assertion was corrected from string `"10"` to integer `10`.

## Data safety

Partial/source-failed reports preserve current state. Duplicate reports preserve current and snapshot state through pre-write rejection and transaction rollback. Repeated complete generations remain idempotent through existing upsert/snapshot conflict behavior. Tenant IDs remain part of all business keys.

**Schema changed:** NO

**Semantics changed:** YES — intended persistence-safety semantics only: current replacement is permitted only for complete acquisition and duplicate source keys fail closed.

**Runtime parity:** Not required; production Python modules changed, so run the parity check where the deployed runtime is available.

**Live acceptance:** Not performed; credentials/environment-dependent validation is deferred to EX-P04B.

No token or credit data is recorded.
