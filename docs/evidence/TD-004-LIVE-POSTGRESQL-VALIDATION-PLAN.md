# TD-004 Live PostgreSQL Validation Plan

- **Usage mark:** `TD-004-LIVE-POSTGRESQL-VALIDATION-PLAN-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `VALIDATION_DESIGN`
- **Status:** `DOCUMENTED / PLANNED`

## 1. Objective

Validate real PostgreSQL behavior against the persistence assumptions exercised by offline validation for G01-002 through G01-012. The live validation must confirm that the runtime database, approved schema, closed SQL mappings, constraints, transaction boundaries, and replay semantics behave as expected against an actual PostgreSQL instance.

This is a validation plan only. It does not authorize changes to collectors, adapters, registry metadata, persistence runtime, or database migrations.

## 2. Validation Scope

Use a controlled PostgreSQL database initialized from the approved migrations. The scenarios must exercise representative persistence patterns rather than every endpoint independently.

### CURRENT

- `core.application`
- `core.device`
- `core.named_location`

Validate current-state insert and update behavior using the registry-controlled table and column mappings.

### CURRENT_WITH_SNAPSHOT

- `core.conditional_access_policy`
- `core.conditional_access_policy_snapshot`

Validate the current upsert and per-collection-run snapshot insert behavior, including their distinct conflict keys and replay semantics.

### EVENT

- `core.audit_event`

Validate append-oriented event persistence and duplicate-ignore behavior using the registered event source and event identity.

## 3. Validation Areas

### Database Connectivity

Confirm that the approved runtime database driver can establish a connection, begin a transaction, execute parameter-bound statements, commit, roll back, and close the connection against the controlled PostgreSQL instance. Record only non-sensitive connection outcome metadata.

### Schema Existence

Confirm that the expected schemas and representative tables exist after migration initialization. Verify the required `core` schema and each table listed in the validation scope without accepting caller-provided schema or table identifiers.

### Column Mapping

For each representative table, compare the closed endpoint mapping and normalized field contract with PostgreSQL catalog metadata. Confirm expected column names, types, nullability, primary/unique keys, and lineage columns. Values supplied by normalized records must remain SQL parameters; they must not determine identifiers.

### Constraint Behavior

Exercise required-column, type, primary-key, unique-key, foreign-key, and check-constraint behavior where applicable. Confirm invalid rows fail with a controlled database error and are not silently converted into successful writes.

### Transaction Behavior

Confirm that a successful collection batch commits all intended writes in one transaction. Verify that the current-plus-snapshot path commits both portions together and that event writes use the same collection transaction boundary.

### Rollback Behavior

Cause a deterministic failure after an earlier representative write in the same batch. Confirm that PostgreSQL contains none of the batch writes after rollback, including current, snapshot, and event rows where applicable.

### Replay Behavior

Replay the same normalized records with the same tenant and identities. Confirm current records update deterministically, snapshots do not duplicate within the same collection run, and duplicate events are ignored according to the approved conflict keys.

## 4. Security Validation

The live run must verify the following assertions:

- **Tenant boundary:** matching tenant lineage is accepted; missing, malformed, or cross-tenant row lineage is rejected before SQL execution or database mutation.
- **Parameter-bound SQL:** all record values are passed through driver parameters; SQL text contains no interpolated record values.
- **Closed table mapping:** endpoint-to-table and column identifiers come only from code-owned closed mappings and cannot be selected by normalized payload data.
- **No raw payload persistence:** only approved normalized columns are written; raw Graph payloads, credentials, tokens, authorization material, and unrelated fields are absent from persisted rows.

Capture SQL shape or statement metadata only when it can be redacted safely. Do not capture parameter values if they contain tenant or source data that is not required as evidence.

## 5. Test Scenarios

Run each scenario with synthetic, minimally identifying records and isolated test identities. Record expected and observed row counts, transaction outcome, and constraint/error classification.

### Successful Insert

Insert valid representative rows for `CURRENT`, `CURRENT_WITH_SNAPSHOT`, and `EVENT`. Confirm commit, expected column values, trusted tenant lineage, and one current-plus-snapshot pair where applicable.

### Duplicate Replay

Replay a committed current record. Confirm the operation succeeds without an additional current row and that the existing row reflects the deterministic current update contract.

### Current Update

Write a current record with the same tenant and source object identity but changed approved values. Confirm one row remains and the approved mutable columns contain the new values.

### Event Duplicate Ignore

Replay an event with the same tenant, registered event source, and source object identity. Confirm the second write is ignored and the event row count remains unchanged.

### Snapshot Duplicate Ignore

Replay a snapshot with the same tenant, source object identity, and collection run identity. Confirm the second write is ignored while a new collection run can create a distinct snapshot row.

### Transaction Rollback

Place a valid write before a deterministic invalid write in one collection batch. Confirm the invalid operation causes rollback and no earlier or later batch row remains committed.

### Invalid Tenant Rejection

Submit a record with missing, malformed, or mismatched tenant lineage relative to the trusted collection tenant. Confirm rejection occurs without SQL execution, transaction mutation, or committed rows.

## 6. Expected Evidence

Capture an evidence record for each run containing:

- UTC timestamp
- PostgreSQL server version
- database connectivity result
- schema validation result
- table validation result
- column and mapping validation result
- constraint validation result
- transaction, rollback, and replay results
- scenario identifiers and pass/blocker classifications

Do not store:

- credentials
- connection strings
- passwords, tokens, certificates, or other secrets
- raw payloads
- unnecessary tenant identifiers or source data

Use redacted metadata, synthetic identifiers, row counts, schema/catalog facts, and error classifications. Evidence must be stored outside the database under the approved evidence-retention process.

## 7. Success Criteria

TD-004 live validation is **PASS** only when connectivity, schema/table presence, column mappings, constraints, commit, rollback, replay, and all security assertions pass for every representative persistence pattern. Any discrepancy must be resolved through an approved follow-up or recorded as an explicit blocker; a partial result is not a pass.

## 8. Limitations

- Requires a controlled database environment initialized from the approved migrations.
- Requires protected runtime database settings and an approved PostgreSQL driver.
- Test data volume and PostgreSQL version can affect observed behavior and must be recorded as metadata.
- Does not replace offline tests.
- This plan does not execute live PostgreSQL validation or establish credentials.
