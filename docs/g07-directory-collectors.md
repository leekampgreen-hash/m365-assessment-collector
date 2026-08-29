# G07-A — Directory / Licensing / RBAC Workload Adapters

> **Worker:** G07-A
> **Scope:** `collectors/workloads/directory/**`, `tests/workloads/directory/**`
> **Inputs:** `config/api_inventory.json`, `docs/data-catalog.md`,
> `docs/database-schema-design.md`, `database/migrations/`
> **Out of scope:** `collectors/core/*`, `collectors/run_collector.py`,
> `config/*`, `database/migrations/*`, `agents/discovery/*`,
> `data/discovery/*`, `secrets/*`, and any G07-B files.

G07-A delivers the **normalisation / adapter layer** for the ten Graph
endpoints owned by the directory, licensing, and RBAC workloads:

| Inventory ID | Workload | Adapter module | Target table | History mode |
|---|---|---|---|---|
| G01-001 | Entra ID | `users.py` | `core."user"` | CURRENT_ONLY |
| G01-002 | Entra ID | `groups.py` | `core."group"` | CURRENT_ONLY |
| G01-003 | Entra ID | `organization.py` | `core.organization` | CURRENT_ONLY |
| G01-004 | Microsoft 365 Licensing | `subscribed_skus.py` | `core.subscribed_sku` + `core.subscribed_sku_snapshot` | HISTORICAL_WITH_SNAPSHOT |
| G01-007 | Microsoft Entra ID | `applications.py` | `core.application` | CURRENT_ONLY |
| G01-008 | Microsoft Entra ID | `service_principals.py` | `core.service_principal` | CURRENT_ONLY |
| G01-009 | Microsoft Entra ID | `devices.py` | `core.device` | CURRENT_ONLY |
| G01-010 | Entra ID Governance | `administrative_units.py` | `core.administrative_unit` | CURRENT_ONLY |
| G01-018 | Microsoft Entra RBAC | `directory_role_definitions.py` | `core.directory_role_definition` | REFERENCE |
| G01-019 | Microsoft Entra RBAC | `directory_role_assignments.py` | `core.directory_role_assignment` + `core.directory_role_assignment_snapshot` | HISTORICAL_WITH_SNAPSHOT |

The adapter layer is **pure transformation**. It does NOT call live
Microsoft Graph, does NOT persist anything, does NOT touch tokens or
secrets, and does NOT modify the G05 collector framework. Its only job
is to convert Graph record dicts into row-shaped dicts aligned with the
accepted database design (`docs/database-schema-design.md` and
`database/migrations/003_*.sql` / `004_*.sql`).

---

## 1. Module contract

Every adapter module exposes the same five-module-attribute contract:

```
ENDPOINT_ID:        str    # Graph inventory identifier, e.g. "G01-001"
TARGET_TABLE:       str    # core.<table> (or quoted variant) for upsert
SNAPSHOT_TABLE:     Optional[str]   # set only for HISTORICAL_WITH_SNAPSHOT
HISTORY_MODE:       str    # CURRENT_ONLY | HISTORICAL_WITH_SNAPSHOT | REFERENCE
RETENTION_CLASS:    str    # SHORT | STANDARD | LONG | REFERENCE

normalize(record, *, tenant_id, collection_run_id,
          endpoint_run_id, observed_at) -> row_dict | (row_dict, snapshot_dict)

ADAPTER_SPEC:       AdapterSpec    # frozen contract object
```

`normalize` consumes a single Graph record dict plus the runtime
lineage (`tenant_id`, `collection_run_id`, `endpoint_run_id`,
`observed_at`) and returns:

- a single row dict for `CURRENT_ONLY` and `REFERENCE` adapters;
- a `(current_row, snapshot_row)` tuple for the two
  `HISTORICAL_WITH_SNAPSHOT` adapters (G01-004, G01-019).

`AdapterSpec` is a frozen dataclass in `collectors/workloads/directory/common.py`
that carries the four pieces of metadata required by the worker scope
contract: endpoint identifier, target table metadata, normalisation
function reference, and persistence/history mode metadata.

The runtime can iterate the package via:

```
from collectors.workloads.directory import iter_adapters, get_adapter

for module in iter_adapters():
    row_or_pair = module.normalize(record, **lineage)
```

---

## 2. Lineage and source-object preservation

Every emitted row carries:

- `tenant_id` — internal `core.tenant` surrogate (BIGINT).
- `source_object_id` — Graph `id` from the record; the schema's natural
  upsert key when scoped to `tenant_id`.
- `collection_run_id` — runtime lineage identifier from `control.collection_run`.
- `endpoint_run_id` — runtime lineage identifier from `control.endpoint_run`.
- `last_observed_at` — runtime-supplied observation timestamp
  (`collected_at`).

The two snapshot-style adapters additionally emit `snapshot_at` on the
snapshot row, mirroring the schema's snapshot timestamp.

The source object id is the **only** field the adapter requires as
non-null. If the record is missing an `id`, `normalize` raises a
deterministic `ValueError` so a future persistence layer never writes a
row with a NULL natural key.

---

## 3. Field minimisation

Every adapter retains **only** the fields enumerated by the G03 catalog
(`docs/data-catalog.md`) and the G06 accepted design. The following
Graph-side material is intentionally dropped:

| Endpoint | Excluded fields / payloads |
|---|---|
| G01-001 | `mail`, `businessPhones`, `mobilePhone`, `otherMails`, `aboutMe`, profile enrichment |
| G01-002 | `members`, mail / calendar payloads |
| G01-007 | `passwordCredentials`, `keyCredentials`, `web`, `spa`, `publicClient`, `requiredResourceAccess` |
| G01-008 | `appRoleAssignments`, `oauth2PermissionGrants`, `keyCredentials`, `passwordCredentials` |
| G01-018 | `rolePermissions` |

Every adapter also rejects unrecognised Graph fields by construction —
the `normalize` function only reads the curated keys and never copies
unknown keys into the row.

---

## 4. Snapshot row handling (G01-004, G01-019)

The two `HISTORICAL_WITH_SNAPSHOT` adapters emit **two** row-shaped
dicts per Graph record:

1. A current-state row targeting `core.subscribed_sku` /
   `core.directory_role_assignment`.
2. A per-run snapshot row targeting `core.subscribed_sku_snapshot` /
   `core.directory_role_assignment_snapshot`.

The snapshot row carries the trio required by the schema's
`UNIQUE (tenant_id, source_object_id, collection_run_id)` constraint,
plus `endpoint_run_id` and `snapshot_at`. The current row carries
`last_observed_at` only — re-runs advance `last_observed_at` without
producing duplicate snapshot rows because of the uniqueness trio.

For G01-004 the Graph `prepaidUnits` object
(`{enabled, suspended, warning}`) is summed into a single integer to
match the schema's `INTEGER` column. When the Graph field is absent or
non-dict the column is normalised to `0`.

---

## 5. Reference semantics (G01-018)

`core.directory_role_definition` is the **single** REFERENCE table in
G07-A. The adapter keeps the curated reference fields only
(`displayName`, `description`, `isBuiltIn`) and never copies the
`rolePermissions` payload into the row. The retention class is
`REFERENCE` per the G03 catalog.

---

## 6. Determinism and input validation

- Every adapter is deterministic: two `normalize` calls with identical
  inputs produce byte-identical row dicts. Tests pin this property
  cross-cutting (`LineageAndDeterminismTests`).
- Non-object input (None, str, int, float, list, bool) is rejected with
  a `TypeError` that names the endpoint id.
- Records missing the required `id` field raise `ValueError`.

The adapter layer never raises silently. A future persistence layer
that consumes the row dicts can rely on the adapter's contract.

---

## 7. Security boundaries

G07-A inherits the G05 framework invariants:

- No module imports or references tokens, client secrets, or
  `Authorization` header values.
- No normalised row carries any credential-shaped substring (`Bearer`,
  `Authorization`, `secret`, `password`, `access_token`,
  `refresh_token`, `client_secret`). Tests
  (`SecurityAndExclusionTests`) pin this property.
- No raw Graph payload is copied into the row; only the curated column
  set is emitted.
- No calls to Microsoft Graph are made by the adapter layer; the layer
  is fully offline and deterministic.

---

## 8. What G07-A does NOT do

- No database writes — the persistence layer is a future G-task.
- No live Graph calls — the adapter layer transforms dicts only.
- No inventory changes — `config/api_inventory.json` is untouched.
- No framework changes — `collectors/core/*` is untouched.
- No schema changes — `database/migrations/*` is untouched.
- No discovery state changes — `data/discovery/*` and
  `agents/discovery/*` are untouched.

---

## 9. Tests

Offline unit tests live in
`tests/workloads/directory/test_directory_adapters.py` and cover:

- All ten endpoint ids and the deterministic ordering contract.
- The four-module-attribute contract (`ENDPOINT_ID`, `TARGET_TABLE`,
  `SNAPSHOT_TABLE`, `HISTORY_MODE`, `RETENTION_CLASS`,
  `normalize`, `ADAPTER_SPEC`).
- Full-record normalisation for every endpoint.
- Null / missing optional field handling for every endpoint.
- Source-object-id preservation.
- Tenant / collection-run / endpoint-run lineage preservation.
- Current-state mapping for the eight CURRENT_ONLY + REFERENCE adapters.
- G01-004 snapshot mapping (current row + per-run snapshot row).
- G01-019 snapshot mapping (current row + per-run snapshot row).
- Reference-semantics preservation for G01-018
  (`rolePermissions` never copied).
- Determinism — two calls with identical inputs produce identical output.
- Invalid / non-object input is rejected.
- Records missing the Graph `id` field are rejected.
- No credential / token / `Authorization` substring appears in any row.
- Per-endpoint excluded fields are not copied (`passwordCredentials`,
  `appRoleAssignments`, `members`, `rolePermissions`, etc.).

Run the tests:

```console
python3 -m unittest tests.workloads.directory.test_directory_adapters -v
```

---

## 10. File map

```
collectors/workloads/
    __init__.py                                  # re-exports directory package
    directory/
        __init__.py                              # iter_adapters / get_adapter
        common.py                                # AdapterSpec + lineage helpers
        users.py                                 # G01-001 CURRENT_ONLY
        groups.py                                # G01-002 CURRENT_ONLY
        organization.py                          # G01-003 CURRENT_ONLY
        subscribed_skus.py                       # G01-004 HISTORICAL_WITH_SNAPSHOT
        applications.py                          # G01-007 CURRENT_ONLY
        service_principals.py                    # G01-008 CURRENT_ONLY
        devices.py                               # G01-009 CURRENT_ONLY
        administrative_units.py                  # G01-010 CURRENT_ONLY
        directory_role_definitions.py            # G01-018 REFERENCE
        directory_role_assignments.py            # G01-019 HISTORICAL_WITH_SNAPSHOT

tests/workloads/
    __init__.py
    directory/
        __init__.py
        test_directory_adapters.py
```

---

## 11. Authoritative inputs (unchanged)

| File | Status |
|---|---|
| `config/api_inventory.json` | unchanged |
| `docs/data-catalog.md` | unchanged |
| `docs/database-schema-design.md` | unchanged |
| `database/migrations/001..007_*.sql` | unchanged |
| `docs/collector-framework.md` | unchanged |
| `collectors/core/*` | unchanged |
| `collectors/run_collector.py` | unchanged |
| `agents/discovery/*`, `data/discovery/*` | unchanged |
| `secrets/*` | unchanged |
| `docs/g07-directory-collectors.md` | **new (this file)** |
| `collectors/workloads/directory/**` | **new** |
| `tests/workloads/directory/**` | **new** |

---

## 12. Blockers

None.