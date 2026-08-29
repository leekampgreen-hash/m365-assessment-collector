---
# STD-09A License Retention Wiring Closure

- **Task ID:** `STD-09A-LICENSE-RETENTION-WIRING-CLOSURE-001`
- **Project:** graph-agent
- **Role:** `BOUNDED_CONTRACT_WIRING_REVIEW`
- **Purpose:** Close the G01-004 retention-class drift (registry `REFERENCE`
  versus authoritative contract `STANDARD`) before STD-10 user-license mapping
  begins.
- **Result:** `STD_09A_FIXED_PASS`; `STD10_READY=YES`.

## RETENTION_CONTRACT

- **authoritative_value:** `STANDARD`
- **registry_value_before:** `REFERENCE`
- **persistence_mode:** `CURRENT_WITH_SNAPSHOT` (`core.subscribed_sku` current +
  `core.subscribed_sku_snapshot`)
- **root_cause:** stale registry metadata. `collectors/workloads/registry.py`
  hard-coded `G01-004` `retention_class="REFERENCE"` while every authoritative
  source defines `STANDARD`:
  - adapter `collectors/workloads/directory/subscribed_skus.py`
    `RETENTION_CLASS = "STANDARD"` (written to both current and snapshot rows);
  - `docs/data-catalog.md` (G01-004 Retention = `STANDARD`);
  - `docs/database-schema-design.md` (line 1145 and §13 mapping = `STANDARD`);
  - `database/migrations/003_core_directory_and_licensing.sql` (`retention_class
    TEXT NOT NULL DEFAULT 'STANDARD'` on both tables).

### Proof of drift (registry stale, contract correct)

- The G01-004 adapter **hard-codes** `STANDARD` into the normalized current and
  snapshot rows; G07-A directory adapters (via `_wrap_g07a`) do **not** consume
  `lineage.retention_class`. The registry `retention_class` is therefore
  metadata-only for G01-004 and has no effect on the persisted value.
- The registry value (`REFERENCE`) was out of alignment with the adapter,
  catalog, schema, and migration — all `STANDARD`.

## CORRECTION

Smallest bounded correction:

- `collectors/workloads/registry.py`: `G01-004` `retention_class` `REFERENCE` →
  `STANDARD`. Metadata only.
- `tests/workloads/test_registry.py`: added focused contract test
  `test_g01_004_contract_and_standard_retention` asserting
  `CURRENT_WITH_SNAPSHOT`, owner `directory`, current `core.subscribed_sku`,
  snapshot `core.subscribed_sku_snapshot`, retention `STANDARD`.

No persistence-mode, snapshot, schema, migration, permission, Graph, or durable
retention-contract change. The durable retention semantics remain `STANDARD`.

## FILES_CHANGED

- `collectors/workloads/registry.py` (registry metadata correction)
- `tests/workloads/test_registry.py` (focused contract test)
- `.dockerignore` (new; excludes root-owned 0600 `secrets/` from the
  `Dockerfile.collector` build context so production images can be rebuilt)
- `docs/PROJECT_PROGRESS.md` (STD-09A closure record)
- `docs/PROJECT_FILE_MAP.md` (record `.dockerignore`)
- `docs/evidence/STD-09A-LICENSE-RETENTION-WIRING-CLOSURE-001.md` (this file)

## TESTS

Focused registry/normalization/persistence contract suites (242 relevant tests):
`tests/workloads/test_registry.py`,
`tests/workloads/directory/test_directory_adapters.py`,
`tests/workloads/test_integration.py`,
`tests/persistence/test_core.py`,
`tests/core/test_g09_r2_normalization_handoff.py` — all PASS.

Full workload suite: 235 tests PASS.

Pre-existing, environment-only failures (unrelated to this change):
- `tests/persistence/test_g01_015_event.py` — `database/migrations/` not mounted
  in the test container (migration-file read returns empty).
- `tests/discovery/test_discovery_agent.py` — `agents` module not importable in
  the test container.

## RUNTIME_PARITY

- Rebuilt `graph-agent-collector:dev` (`Dockerfile.collector`) and recreated
  `graph-agent-operations-api-dev`.
- Both the collector (bind-mounted) and the operations API (rebuilt image)
  runtime now report `G01-004 retention=STANDARD`.
- `scripts/check_runtime_parity.py` gate: all modules `MATCH`.
- operations-api health: `healthy`.

## DOCUMENTATION

- `docs/PROJECT_PROGRESS.md` STD-09A record added; STD-09 blocker marked closed.
- Durable retention contract unchanged (`STANDARD`), so `database-schema-design.md`
  and `data-catalog.md` were not modified.
- No token/credit usage logging.

## BLOCKERS

None. G01-004 is usable by STD-10.

## STD10_READY

YES

## NEXT_TASK

`STD-10-USER-LICENSE-MAPPING-CONTRACT-001`
