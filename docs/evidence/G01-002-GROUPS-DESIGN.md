# G01-002 Groups CURRENT Endpoint Design Evidence

- **Usage mark:** G01-002-GROUPS-DISCOVERY-DESIGN-001
- **Session:** NEW
- **Model:** kl/gpt-5.6-luna
- **Purpose:** DESIGN
- **Status:** PASS
- **Scope:** Design only; no production code changes.

## 1. Graph API

- **Endpoint:** `GET /v1.0/groups` (`config/api_inventory.json` G01-002).
- **Authentication:** Application permission `Group.Read.All`; the runtime must enforce the inventory permission through the existing Graph collector flow.
- **Request projection:** `$select=id,displayName,mail,mailEnabled,securityEnabled,groupTypes`; use the inventory page size `$top=10`.
- **Pagination:** Follow Graph’s response `@odata.nextLink` until it is absent. Each page contributes its `value` records to the same endpoint collection and receives the same trusted tenant and run lineage. Do not infer completion from page size, and do not issue ad hoc membership requests.
- **Response handling:** Accept a successful collection response with `value` as an array, including an empty array. Preserve page traversal errors as endpoint collection failure according to the existing runtime retry/error contract; do not persist a partial successful collection as if pagination completed. Normalize records only after the runtime has supplied trusted lineage.
- **Excluded payload:** Group membership and other unselected properties are outside this endpoint’s contract.

## 2. Adapter

The existing directory adapter pattern from G01-001 applies: validate a mapping, obtain lineage through the shared helper, copy only the catalog-approved fields, and return a row-shaped dictionary.

### Source to normalized fields

| Graph source | Normalized field | Rule |
|---|---|---|
| `id` | `source_object_id` | Required stable source identity; reject missing identity. |
| `displayName` | `display_name` | Nullable text. |
| `mail` | `mail` | Nullable text. |
| `mailEnabled` | `mail_enabled` | Nullable boolean. |
| `securityEnabled` | `security_enabled` | Nullable boolean. |
| `groupTypes` | `group_types` | Preserve only string list members as `TEXT[]`; malformed/missing input normalizes to an empty list under the existing adapter convention. |
| runtime | `last_observed_at` | Observation timestamp, not Graph payload data. |
| constant | `retention_class` | `REFERENCE`. |

Membership payloads and unknown fields must not be copied. The normalized row must not contain credentials, authorization material, or unrelated Graph payloads.

### Lineage propagation

Propagate `tenant_id`, `collection_run_id`, `endpoint_run_id`, and `observed_at` from the trusted runtime context through the shared lineage helper. The adapter must not derive tenant identity from Graph data or accept caller-supplied row tenant data as authoritative.

## 3. Registry

Register/retain the G01-002 entry in `collectors/workloads/registry.py` with:

- endpoint ID `G01-002`;
- persistence mode `CURRENT`;
- target `core."group"`;
- workload `Entra ID`;
- owner `directory`;
- retention class `REFERENCE`;
- the directory groups adapter;
- description `Groups -- CURRENT_ONLY upsert`.

Validation rules:

- registry import validation must retain complete endpoint identity and mode metadata;
- adapter output must be normalized through the registered adapter and must match endpoint identity and `CURRENT` mode;
- required normalized identity is `tenant_id` plus `source_object_id`; required persistence columns are the closed G01-002 current column set;
- tenant values must match the trusted collection tenant before SQL execution;
- normalized input cannot select a table or SQL identifier;
- no event, snapshot, history, or membership persistence is introduced.

## 4. Persistence

Reuse the existing `CURRENT` dispatcher and writer. The accepted closed mapping already targets `core."group"` with columns:

`tenant_id`, `source_object_id`, `display_name`, `mail`, `mail_enabled`, `security_enabled`, `group_types`, `last_observed_at`, `retention_class`.

Use the existing parameter-bound `INSERT ... ON CONFLICT DO UPDATE` pattern. No new SQL pattern or migration is required. The idempotency/conflict key is `(tenant_id, source_object_id)`, matching the database unique constraint. Replay updates the current row deterministically and does not create duplicates. Transaction, security-boundary, and rollback behavior remain owned by the existing dispatcher/writer.

## 5. Testing Plan

1. **Successful collection:** Mock a 200 response containing representative group records; assert the selected endpoint/permission contract, normalized fields, lineage, `REFERENCE` retention, and current dispatch target.
2. **Pagination:** Return multiple pages linked by `@odata.nextLink`; assert all records are collected in source order, each is normalized once, and persistence receives one completed endpoint batch.
3. **Duplicate replay:** Submit the same tenant/source-object record twice or replay the same collection; assert the conflict key is `(tenant_id, source_object_id)`, SQL remains parameter-bound, and the second write updates rather than duplicates.
4. **Tenant mismatch:** Supply a normalized row whose tenant differs from the trusted collection tenant; assert rejection before transaction/SQL and no partial write.
5. **Empty result:** Return HTTP 200 with `value: []`; assert successful zero-row completion, no adapter/persistence rows, and no fabricated records.
6. **API failure handling:** Return permission failure, transient failure, malformed response, and terminal page failure; assert existing retry/error classification is used and incomplete pagination is not reported as successful persistence.

Adapter-focused coverage should also verify missing `id` rejection, non-mapping rejection, nullable optional fields, group type sanitization, exclusion of `members`, deterministic output, and absence of forbidden credential substrings.

## 6. Documentation and implementation boundary

Planned implementation files, if the design is approved, are the existing Graph inventory/runtime integration points, `collectors/workloads/directory/groups.py`, `collectors/workloads/registry.py`, the existing current persistence mapping only if verification finds drift, and corresponding workload/persistence/runtime tests. This design task changes documentation only; production code and tests are not modified here.

## Architecture alignment

The endpoint follows the frozen flow exactly:

`Graph Collector -> Adapter -> Registry -> Persistence Dispatcher -> Security Boundary -> CURRENT Writer -> Database`.

Known technical debt remains unchanged: duplicated registry/SQL metadata, no live PostgreSQL integration suite, limited rejection metrics/tracing, and retry recovery hardening.

## Blockers

None for design. Implementation should first verify the runtime’s exact response/error abstractions and add focused tests before any production change.
