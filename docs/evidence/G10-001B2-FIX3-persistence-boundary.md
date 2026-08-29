# G10-001B2-FIX3 Persistence Boundary Hardening Evidence

## Execution Metadata

- Usage mark: `G10-001B2-FIX3-PERSISTENCE-BOUNDARY-001`
- Session: NEW
- Model: kl/gpt-5.6-luna
- Purpose: IMPLEMENTATION
- Token mode: NORMAL
- Date: 2026-08-23

## Public Write Paths Reviewed

- `BoundSqlExecutor.execute`
- `CollectionWriter.write`
- `dispatch_persistence`
- `write_current_record`
- `write_reference_record`
- `write_event_record`
- `write_snapshot_record`
- `write_history_record`

## Security Boundary

`CollectionWriter.write` validates trusted collection tenant, record tenants, endpoint identity, and registry persistence mode before `BEGIN`. `dispatch_persistence` validates all records for endpoint and mode alignment before invoking SQL handlers. Every public mode-specific handler validates populated row tenant IDs before SQL execution. Event-source validation remains enforced in the event handler.

Validation failures occur before SQL execution and before transaction start at the collection boundary. Existing transaction rollback remains in effect for failures after `BEGIN`; no validation failure can commit or partially write a dispatcher batch.

## Files Changed

- `collectors/persistence/core.py`
- `tests/persistence/test_core.py`
- `docs/PROJECT_PROGRESS.md`
- `docs/CHANGELOG.md`
- `docs/ARCHITECTURE.md`
- `docs/AI_USAGE_LOG.md`
- `docs/evidence/G10-001B2-FIX3-persistence-boundary.md`

## Test Results

```text
python3 -m unittest tests.persistence.test_core tests.persistence.test_g01_015_event tests.persistence.test_g01_016_017_history
........................................................................
----------------------------------------------------------------------
Ran 72 tests in 0.010s

OK
```

Focused coverage includes successful `CollectionWriter` flow, dispatcher mismatch rejection before SQL, direct low-level malformed tenant rejection before SQL, event-source validation, and no transaction activity for pre-transaction validation failures.

A full `python3 -m unittest discover -s tests -p 'test_*.py'` run executed 589 tests and produced 3 failures limited to `tests/scenario/live/test_d2_operator_entrypoint.py`. Those live tests attempted external device-code networking and their mocked request-count/socket expectations did not hold. The scoped persistence suites passed, and `python3 -m py_compile collectors/persistence/core.py tests/persistence/test_core.py` passed.

## Known Limitations

The low-level writer APIs validate row-local tenant correctness but cannot establish a caller's trusted tenant context without a `NormalizedCollection`; trusted tenant matching is therefore enforced by `CollectionWriter`. Live PostgreSQL integration coverage and operational rejection metrics remain future work.
