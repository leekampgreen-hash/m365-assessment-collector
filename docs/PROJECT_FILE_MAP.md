# Project File Map

This document is the source of truth for project navigation. Future AI workers and reviewers MUST read it before modifying or reviewing code.

## Project Root

- **Repository location:** `/opt/docker/graph-agent`
- **Main technology stack:** Python 3.13 application and test code, Microsoft Graph collection adapters, PostgreSQL 16 persistence, SQL migration files, and Docker Compose runtime orchestration.
- **`.dockerignore` (project root):** Excludes `secrets/` (root-owned 0600 files that otherwise fail the Docker build-context read) plus build-irrelevant directories from the `Dockerfile.collector` context. The image relies on runtime Docker secrets, not baked-in secret files.

## Active Delivery Roadmap

- **Authoritative roadmap and progress record:** `docs/PROJECT_PROGRESS.md`.
- **Task execution log:** `docs/AI_USAGE_LOG.md`.
- **Current track:** Standard Version, with the ordered STD-00 through STD-22
  sequence recorded in `docs/PROJECT_PROGRESS.md`.
- Entra/security-posture expansion is deferred until the Standard Version is
  complete; completed historical G/CH work remains preserved.

## Directory Map

### `collectors/`

Owns the Microsoft Graph collection framework, runtime behavior, normalization, workload dispatch, adapters, and persistence boundaries.

Important modules include:

- `collectors/core/` — collection runtime, authentication, HTTP transport, configuration, retries, inventory, and normalized results.
- `collectors/run_collector.py` — collector entry point.
- `collectors/workloads/` — endpoint workload registry, models, and adapters.
- `collectors/persistence/` — database-agnostic transaction and record-writing boundary.

### `collectors/workloads/`

- `registry.py` owns the central endpoint registry and dispatch integration point. It maps endpoint IDs to persistence modes, target tables, and adapter callables.
- Adapter modules own workload-specific translation of Graph records into normalized row dictionaries. Adapters perform no database I/O or Graph calls.
- `models.py` owns shared workload vocabulary and definitions, including `PersistenceMode`, `WorkloadEntry`, and `NormalizedWorkloadRecord`.
- Workload definitions describe endpoint identity, data domain, persistence pattern, target tables, and the adapter used to normalize records.
- Adapter locations include `collectors/workloads/directory/` and `collectors/workloads/security_service/`.

### `collectors/persistence/`

- `core.py` owns the database-agnostic persistence boundary, parameter-bound SQL execution, transaction handling, and current/event/reference/snapshot/history record writers.
- `__init__.py` owns the public persistence package surface and re-exports supported persistence primitives from `core.py`.

### Persistence Mode Map

| Mode | Purpose | Responsible handler area | Related tests |
|------|---------|--------------------------|---------------|
| `CURRENT` | Maintain the latest normalized state for an endpoint using deterministic upsert behavior. | `collectors/persistence/core.py` current writer; endpoint selection is coordinated through `collectors/workloads/registry.py`. | `tests/persistence/test_core.py` and current-mode workload/registry coverage under `tests/workloads/`. |
| `REFERENCE` | Maintain shared or slowly changing reference data with deterministic upsert behavior. | `collectors/persistence/core.py` reference writer; endpoint mapping is owned by `collectors/workloads/registry.py`. | `tests/persistence/test_core.py` and related workload coverage under `tests/workloads/`. |
| `EVENT` | Append immutable audit or activity events with deterministic idempotency. | `collectors/persistence/core.py` event writer; security-service normalization is in `collectors/workloads/security_service/adapters.py`. | `tests/persistence/test_g01_015_event.py` and related tests under `tests/workloads/security_service/`. |
| `HISTORY` | Preserve versioned records alongside current state for change tracking and historical reconstruction. | `collectors/persistence/core.py` history writer; version identity support is in `collectors/workloads/security_service/versioning.py`. | `tests/persistence/test_g01_016_017_history.py` and related tests under `tests/workloads/security_service/`. |
| `SNAPSHOT` | Capture point-in-time records associated with current-state collection where snapshot semantics are required. | `collectors/persistence/core.py` snapshot writer; endpoint dispatch is coordinated through `collectors/workloads/registry.py`. | `tests/persistence/test_core.py` and related workload/registry coverage under `tests/workloads/`. |

`CURRENT_WITH_HISTORY` and `CURRENT_WITH_SNAPSHOT` are the implementation-level modes that combine `CURRENT` behavior with the corresponding `HISTORY` or `SNAPSHOT` writer.

### `database/`

- `database/migrations/` owns ordered, forward-only PostgreSQL DDL migration files. Migration `015_exchange_mailbox_capacity.sql` creates the authoritative analytical VIEW `analytics.exchange_mailbox_capacity` (the single derived-data contract for Exchange mailbox capacity); migration `016_onedrive_account_capacity.sql` creates the authoritative analytical VIEW `analytics.onedrive_account_capacity` (the single derived-data contract for OneDrive account capacity); migration `020_onedrive_high_value_audit_analytics.sql` creates the tenant-scoped `analytics.onedrive_high_value_audit` semantic view.
- `database/runtime/init/` owns database container bootstrap and runtime initialization scripts. `00-create-graph-agent-database.sh` enables `pgcrypto` so the capacity view can compute the sha256-based tenant-safe `user_ref`.
- `docs/database-schema-design.md` is the schema design source of truth; migration files materialize that design and must remain aligned with it.

### `analytics/`

- `analytics/operations.py` owns read-only persisted-row analytics, including the Standard KPI tenant summary projection and OneDrive high-value audit summary/recent-event projection.

### `api/`

- `api/operations.py` owns the standard-library read-only Operations API, including `GET /api/operations/kpi` and `GET /api/operations/onedrive/high-value-audit`.

### `scripts/`

- `check_runtime_parity.py` compares host production-module hashes with the deployed operations API container and is the required runtime-parity gate before live acceptance.

### `tests/`

- Unit tests are grouped with focused component coverage, including `tests/core/`, `tests/persistence/`, and `tests/database/`.
- Persistence tests are under `tests/persistence/` and cover `collectors/persistence/core.py`, including event and history behavior.
- Workload tests are under `tests/workloads/`, with directory and security-service subdirectories, and cover registry dispatch plus workload adapters such as `collectors/workloads/security_service/adapters.py`.
- Integration tests are primarily under `tests/scenario/integration/` and validate cross-component catalog, registry, permission, observability, cleanup, and end-to-end dry-run behavior.
- OneDrive high-value audit production-path tests live under `tests/integration/`: `test_onedrive_audit_production_path.py` (fake Management Activity source over the real orchestration, normalization, and persistence handoff) and `test_onedrive_audit_production_path_matrix.py` (OD-P07 data-driven positive/negative matrix over the real production orchestration, `CollectionWriter` lifecycle, `control.collector_checkpoint`, and real PostgreSQL). `test_onedrive_audit_transport_retry.py` covers direct Management Activity transport retry/classification.
- Live or environment-dependent tests are under `tests/scenario/live/` and must be treated separately from offline unit tests.

### `operations-ui/`

Owns the read-only management dashboard served as a static page. `operations-ui/public/index.html` defines the page shell and sections, `operations-ui/public/app.js` owns API fetch/render behavior, and `operations-ui/public/styles.css` owns reusable cards, panels, status states, and responsive layout. Standard Dashboard implementation is bounded to these existing UI paths and the accepted operations GET APIs.

### `docs/`

Owns architecture, schema, migration, security, scenario, validation, and project-navigation documentation. Documentation describing component ownership or navigation belongs here.

## Important Files Ownership Table

| File | Responsibility | Modify Rule |
|------|----------------|-------------|
| `collectors/persistence/core.py` | Parameter-bound SQL execution, transaction behavior, and persistence writers for normalized records. | Modify only for persistence-boundary behavior; preserve injected connections, safe parameter binding, and supported persistence modes. |
| `collectors/persistence/__init__.py` | Public exports for persistence primitives. | Modify only when the supported public persistence API changes; keep implementation in `core.py`. |
| `collectors/workloads/registry.py` | Canonical endpoint registry, dispatch, lineage handoff, and adapter integration. | Modify when endpoint mappings or dispatch behavior change; keep registry validation deterministic and free of I/O or credentials. |
| `collectors/workloads/models.py` | Shared persistence modes, workload entries, normalized record envelope, and dispatch errors. | Modify when workload contracts or controlled vocabulary change; update adapters, registry, and tests together. |
| `collectors/workloads/directory/*.py` | Directory workload definitions and adapters for identity, organization, groups, users, devices, applications, and related endpoints. | Modify only the affected directory workload; keep output aligned with registry mappings and migration columns. |
| `collectors/workloads/security_service/adapters.py` | Security, governance, RBAC, audit, risk, and service-health workload adapters. | Modify only the affected adapter; preserve normalized row shapes and no-I/O boundaries. |
| `collectors/workloads/security_service/lineage.py` | Shared lineage input normalization for security-service adapters. | Modify when adapter lineage contracts change; update dependent adapters and tests. |
| `collectors/workloads/security_service/versioning.py` | Version identity calculation for history records. | Modify only with an explicit schema/application versioning decision and corresponding tests. |
| `database/migrations/*.sql` | Ordered PostgreSQL schema, tables, constraints, and indexes. | Modify only through forward-compatible migration changes; reconcile with `docs/database-schema-design.md` and migration tests. |
| `database/runtime/init/00-create-graph-agent-database.sh` | Runtime database/bootstrap initialization. | Modify only for container initialization behavior; do not place application persistence logic here. |
| `tests/persistence/*.py` | Offline unit coverage for persistence execution and transaction semantics. | Update when persistence behavior or public persistence exports change. |
| `tests/database/*.py` | Migration structure and schema DDL validation. | Update when migration files or schema ownership changes. |
| `tests/scenario/integration/*.py` | Cross-component integration behavior. | Update when registry, catalog, permissions, observability, or end-to-end flows change. |
| `docs/PROJECT_FILE_MAP.md` | Authoritative project navigation and component ownership. | Update first when adding a component, module, task, or dependency. |

## AI Workflow Rules

### Before implementation

- Read `docs/PROJECT_FILE_MAP.md`.
- Confirm the affected component and its owner.
- Verify the target path exists before editing; do not guess paths.
- Check mapped dependencies and the relevant tests before changing code.

### Before review

- Verify the workspace and repository location.
- Verify that the referenced files exist.
- Review only the components mapped to the requested change.
- Confirm that ownership, dependency, and migration boundaries are respected.

### AI Review Preflight Rules

- Verify the workspace before review.
- Read `docs/PROJECT_FILE_MAP.md` before action.
- Do not guess file locations; confirm paths in the workspace.
- Confirm the actual adapter path before reviewing or modifying adapter behavior.

## Update Guideline

When adding a new endpoint, workload, persistence mode, or adapter:

- Update this file first.
- Record its ownership and responsibility.
- Record its dependencies and integration boundaries.
- Add or update the relevant test location in the map.
- Keep this document synchronized with the repository before implementation or review begins.
