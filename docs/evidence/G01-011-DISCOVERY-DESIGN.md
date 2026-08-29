# G01-011 Conditional Access Policies CURRENT_WITH_SNAPSHOT Design Evidence

- **Usage mark:** `G01-011-DISCOVERY-DESIGN-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `DESIGN_PREPARATION`
- **Status:** `PASS`
- **Scope:** Design only; no production code changes.

## 1. Graph Endpoint

- **Endpoint:** `GET /v1.0/identity/conditionalAccess/policies`.
- **Inventory:** `config/api_inventory.json`, endpoint `G01-011`, key `conditionalAccessPolicies`.
- **Workload:** Microsoft Entra Conditional Access.
- **Required permission:** Application permission `Policy.Read.All`.
- **Authentication model:** Application-only client-credentials authentication through the existing Graph authentication/runtime flow. The collector requests the existing Microsoft Graph `.default` scope; the endpoint permission is enforced by the inventory-driven collector contract. No delegated or interactive authentication is introduced.

## 2. Collection and Projection

- **Pagination:** The inventory marks the endpoint as paginated with `$top=100`. Reuse the shared paginator and follow `@odata.nextLink` until it is absent. Do not infer completion from page size.
- **Success envelope:** Accept `value: []` as a successful empty collection. A missing/non-list `value`, malformed later page, transport/API failure, or malformed `@odata.nextLink` fails the collection under the existing runtime contract.
- **Atomic handoff:** Materialize and validate the complete paginated collection before normalization/persistence. A failed page must not persist records collected from earlier pages.
- **Approved Graph projection:** `$select=id,displayName,state,createdDateTime,modifiedDateTime`.
- **Metadata-only rule:** Store policy metadata and state only. Do not request, normalize, persist, or log `conditions`, `grantControls`, `sessionControls`, authentication context details, or other policy body payloads.

### Source-to-normalized fields

| Graph source | Normalized field | Rule |
|---|---|---|
| `id` | `source_object_id` | Required stable Graph identity; reject missing/malformed identity. |
| `displayName` | `display_name` | Nullable text. |
| `state` | `state` | Nullable text; retain the Graph state value without inventing state semantics. |
| `createdDateTime` | `created_date_time` | Nullable timestamp string under the existing adapter convention. |
| `modifiedDateTime` | `modified_date_time` | Nullable timestamp string and change-awareness field. |
| trusted runtime | `tenant_id`, run IDs, observation fields | Runtime lineage is authoritative; never derive tenant identity from Graph data. |

Each Graph record produces two normalized rows:

- Current row: `last_observed_at` is the trusted collection timestamp.
- Snapshot row: `snapshot_at` is the trusted collection timestamp and `last_observed_at` is absent.

Unknown fields, policy bodies, credentials, tokens, authorization material, and unrelated nested payloads remain excluded.

## 3. Adapter Reuse and Required Changes

Reuse `collectors/workloads/security_service/adapters.py`:

- `conditional_access_policies(records, lineage)` already implements the G01-011 adapter contract.
- `_adapt_conditional_access` validates each record mapping and requires `id`.
- It emits only `display_name`, `state`, `created_date_time`, and `modified_date_time` in addition to trusted lineage.
- It emits one current row and one snapshot row per source object.

No new adapter is required. Implementation should add or verify focused G01-011 tests for malformed/non-object records, missing IDs, optional fields, field exclusion, deterministic two-row output, and pagination handoff. Any change to shared adapter behavior should be avoided unless a focused test exposes a concrete defect.

## 4. Registry Mapping

The existing `collectors/workloads/registry.py` entry is the required mapping:

- Endpoint ID: `G01-011`.
- Persistence mode: `CURRENT_WITH_SNAPSHOT`.
- Workload: `Microsoft Entra Conditional Access`.
- Owner: `security_service`.
- Adapter: `security_service.conditional_access_policies`.
- Current target: `core.conditional_access_policy`.
- Snapshot target: `core.conditional_access_policy_snapshot`.

The registry import-time coverage and adapter/mode validation must remain unchanged. No new persistence mode or registry abstraction is needed.

## 5. Persistence Design

Reuse the existing `CURRENT_WITH_SNAPSHOT` dispatcher and `write_snapshot_record` path. The migration and closed SQL mapping already define the required columns.

- **Current conflict key:** `(tenant_id, source_object_id)`.
- **Current replay:** `ON CONFLICT DO UPDATE` for `display_name`, `state`, `created_date_time`, `modified_date_time`, `last_observed_at`, and `retention_class`.
- **Snapshot conflict key:** `(tenant_id, source_object_id, collection_run_id)`.
- **Snapshot replay:** `ON CONFLICT DO NOTHING`, preventing duplicate snapshots during a replay of the same collection run.
- **SQL safety:** Table and column identifiers come only from the closed endpoint map; values use parameter-bound placeholders. Normalized input cannot select SQL identifiers.
- **Transaction:** `CollectionWriter` executes the current and snapshot writes in one transaction. Pre-transaction tenant/mode/endpoint validation rejects invalid batches without SQL; post-`BEGIN` writer failures roll back without commit.
- **Tenant boundary:** Trusted collection tenant and every populated current/snapshot row tenant must match before SQL execution.

No new writer, migration, dispatcher redesign, or persistence redesign is required.

## 6. Security Boundary Considerations

- Preserve the frozen flow: `Graph Collector -> Adapter -> Registry -> Persistence Dispatcher -> Security Boundary -> Writer -> Database`.
- Use only the trusted tenant resolver and runtime lineage.
- Keep policy conditions and grant/session controls outside the projection and persistence boundary because they can contain high-risk access-control detail and are explicitly outside this contract.
- Ensure malformed pages fail before adapter/persistence handoff, preventing partial collection writes.
- Continue to validate endpoint identity and registry persistence-mode agreement before transaction start.
- Retain parameter-bound SQL and closed endpoint mappings.

## 7. Test Plan

1. **Inventory contract:** Assert endpoint path, application authentication, `Policy.Read.All`, approved `$select`, `$top=100`, pagination enabled, and G01-011 registry mapping.
2. **Adapter normalization:** Assert current and snapshot rows, source identity, approved fields, trusted lineage, nullable optional fields, and deterministic output.
3. **Malformed input:** Assert non-mapping records and records missing `id` fail closed; no partial normalized batch is handed to persistence.
4. **Field exclusion:** Include `conditions`, `grantControls`, `sessionControls`, unknown fields, token strings, authorization fields, and credential-shaped values; assert none appear in normalized output.
5. **Pagination:** Return multiple pages through `@odata.nextLink`; assert all records are normalized exactly once in source order.
6. **Empty collection:** Return `value: []`; assert successful zero-row completion with no fabricated current or snapshot records.
7. **Malformed page/link:** Return missing/non-list `value` and malformed `@odata.nextLink` on initial and later pages; assert endpoint failure and no writer invocation.
8. **Current persistence:** Assert closed, parameter-bound current SQL, `(tenant_id, source_object_id)` conflict handling, and `DO UPDATE` replay behavior.
9. **Snapshot persistence:** Assert snapshot SQL, `(tenant_id, source_object_id, collection_run_id)` uniqueness, and `DO NOTHING` replay behavior.
10. **Security boundary:** Assert tenant mismatch, endpoint mismatch, mode mismatch, malformed row tenants, and invalid required columns fail before SQL/transaction where applicable.
11. **Rollback:** Inject a post-`BEGIN` current or snapshot writer failure; assert rollback and no commit.

## 8. Documentation Plan

If implementation is approved, update:

- `docs/PROJECT_PROGRESS.md` with implementation status, validated endpoint contract, adapter field boundary, registry mapping, persistence semantics, tests, and evidence link.
- `docs/CHANGELOG.md` with the G01-011 implementation summary.
- `docs/AI_USAGE_LOG.md` with implementation usage mark, files changed, validation result, and limitations.
- Create `docs/evidence/G01-011-CONDITIONAL-ACCESS-POLICIES-IMPLEMENT.md` containing focused test results and architecture-boundary evidence.

This design task updates only the progress record, AI usage record, and this design evidence file. Production code and tests remain unmodified.

## 9. Risks and Decisions

- **Retention metadata discrepancy:** `docs/data-catalog.md` and the schema reconciliation classify G01-011 retention as `REFERENCE`, while the current registry entry uses `STANDARD`, and the default security-service test lineage also uses `STANDARD`. This is a concrete metadata drift item. Implementation must resolve it explicitly with the authoritative contract; this design does not silently change either value.
- **Policy-body expansion risk:** Requesting or persisting conditions/grants/session controls would exceed the approved field boundary and increase security exposure. The implementation must retain metadata-only behavior.
- **Snapshot volume:** Every collected policy emits a current row plus one run-scoped snapshot row. The existing unique key and transaction behavior are sufficient; no new mode is justified.
- **Timestamp interpretation:** `modifiedDateTime` is a change-awareness field, not a request watermark in this design. Collection remains full paginated enumeration unless a future approved incremental contract is introduced.
- **Live validation gap:** Offline tests cannot validate live Graph permission consent or PostgreSQL behavior.

## 10. Blockers

No architectural blockers. Implementation is ready after the retention-class discrepancy is resolved or explicitly accepted in the implementation contract. The frozen pipeline and existing mode-specific writer fully cover G01-011.

## Architecture Alignment

The planned implementation follows the frozen architecture exactly:

```text
Graph Collector -> Security-Service Adapter -> Registry -> Persistence Dispatcher
    -> Security Boundary -> CURRENT_WITH_SNAPSHOT Writer -> Database
```

No foundation redesign, new persistence mode, new writer, migration, or dispatcher redesign is proposed.
