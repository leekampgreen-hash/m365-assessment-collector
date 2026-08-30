# Quick File Map

Use `docs/PROJECT_FILE_MAP.md` for the complete ownership map.

## Key directories

- `collectors/` — Graph collection, auth, runtime, workload registry, adapters, persistence.
- `database/migrations/` — forward-only PostgreSQL DDL; migrations 001–020 are locked.
- `analytics/` — read-only persisted-row analytics.
- `api/` — read-only Operations API.
- `operations-ui/` — static dashboard HTML, JavaScript, and CSS.
- `tests/` — focused unit, integration, and environment-dependent validation.
- `scripts/` — runtime parity and validation tools.
- `docs/` — architecture, contracts, progress, evidence, and procedures.

## Key files

- `collectors/run_collector.py` — production collector entry point.
- `collectors/workloads/registry.py` — endpoint ownership, modes, adapters, and targets.
- `collectors/persistence/core.py` — transaction boundary and persistence writers.
- `analytics/operations.py` — read-only analytics and KPI projections.
- `api/operations.py` — read-only Operations API routes.
- `operations-ui/public/index.html` — dashboard shell.
- `operations-ui/public/app.js` — dashboard behavior and rendering.
- `scripts/check_runtime_parity.py` — required host/runtime hash gate.
- `docs/PROJECT_PROGRESS.md` — progress index; detailed status is under `docs/progress/`.

## Key rules

- Read `docs/WORKER_HANDOVER.md` and the relevant quick map/progress file before work.
- Confirm paths before editing; touch only task-scoped files.
- Keep Graph and dashboard operations read-only unless explicitly authorized.
- Preserve tenant isolation, fail-closed validation, parameter-bound SQL, and transaction rollback.
- Never log or commit credentials, tokens, secrets, raw sensitive payloads, or authorization headers.
- Do not reopen sealed workloads or locked migrations without an approved exception.
- Run focused validation and runtime parity after applicable production-file changes.
