# G07-B Security, Governance & Service-Health Adapters

> **Task**: G07-B — Security, Governance & Service Workload Adapters
> **Status**: PASS (215 existing + 59 new = 274 tests passing)
> **Scope**: workload-specific normalization/adapters for G01-005, G01-006,
> G01-011, G01-012, G01-013, G01-014, G01-015, G01-016, G01-017
> **Inputs**: `config/api_inventory.json`, `docs/data-catalog.md`,
> `docs/database-schema-design.md`, `database/migrations/004..005`,
> the existing G05 collector framework.
> **Out of scope**: any database writer, any Graph call, any
> `collectors/core/*` modification, any G07-A work.

---

## 1. Surface

```
collectors/workloads/security_service/
  __init__.py          # public surface (ENDPOINT_TABLE_MAP, adapter fns, Lineage, versioning)
  lineage.py           # tenant + run lineage (Lineage dataclass + helpers)
  versioning.py        # deterministic version-identity for G01-016/G01-017
  adapters.py          # 9 endpoint-specific adapter functions

tests/workloads/security_service/
  test_adapters.py     # 59 offline tests covering all 9 endpoints
```

No file under `collectors/core/*`, `collectors/run_collector.py`,
`config/*`, `database/migrations/*`, `agents/discovery/*`, `data/discovery/*`,
or `secrets/*` is modified.  No G07-A file exists yet; nothing in its
expected footprint was touched.

## 2. Endpoint map

| Endpoint ID | Inventory key               | Pattern                | Current table                  | Snapshot table                                 | History table                              |
| ----------- | --------------------------- | ---------------------- | ------------------------------ | ---------------------------------------------- | ------------------------------------------ |
| G01-005     | `directoryAuditLogs`        | `EVENT_LOG`            | `core.audit_event` (DIRECTORY_AUDIT) | —                                          | —                                          |
| G01-006     | `signIns`                   | `EVENT_LOG`            | `core.audit_event` (SIGN_IN)   | —                                              | —                                          |
| G01-011     | `conditionalAccessPolicies` | `HISTORICAL_WITH_SNAPSHOT` | `core.conditional_access_policy` | `core.conditional_access_policy_snapshot` | —                                          |
| G01-012     | `namedLocations`            | `CURRENT_ONLY`         | `core.named_location`          | —                                              | —                                          |
| G01-013     | `riskyUsers`                | `HISTORICAL_WITH_SNAPSHOT` | `core.risky_user`           | `core.risky_user_snapshot`                    | —                                          |
| G01-014     | `riskDetections`            | `EVENT_LOG`            | `core.risk_detection`          | —                                              | —                                          |
| G01-015     | `serviceHealthOverview`     | `HISTORICAL_WITH_SNAPSHOT` | `core.service_health_overview` | `core.service_health_overview_snapshot`    | —                                          |
| G01-016     | `serviceHealthIssues`       | `INCREMENTAL_HISTORICAL` | `core.service_health_issue`  | —                                              | `core.service_health_issue_history`        |
| G01-017     | `serviceUpdateMessages`     | `INCREMENTAL_HISTORICAL` | `core.service_update_message` | —                                              | `core.service_update_message_history`      |

The complete mapping lives in `ENDPOINT_TABLE_MAP` in
`collectors/workloads/security_service/adapters.py`.

## 3. Adapter contract

Every adapter function has the same call signature:

```python
def adapter(records: Iterable[Mapping[str, Any]],
            lineage: Optional[Mapping[str, Any] | Lineage] = None
           ) -> List[Dict[str, Any]]:
```

* `records` is an iterable of Graph record dicts (already produced by
  the G05 collector framework).
* `lineage` is a `Lineage` instance, a mapping, or `None`. Adapters
  coerce it through `normalize_lineage()`.
* The return value is a list of row dicts shaped to the exact column
  names declared in the migration files.

Adapters **never**:

* call Microsoft Graph;
* import or use `GraphTransport`, `BaseCollector`, `Paginator`,
  `RetryPolicy`, or any credential-bearing type;
* accept `Authorization` headers, bearer tokens, or client secrets;
* perform any database I/O;
* store or log any secret-shaped substring.

## 4. Event-stream adapters (G01-005, G01-006, G01-014)

* G01-005 (`adapt_directory_audit_logs`) and G01-006
  (`adapt_sign_in_logs`) both write to `core.audit_event` but
  distinguish the two streams through the `event_source`
  discriminator (`DIRECTORY_AUDIT` vs `SIGN_IN`).
* `event_at` is the Graph `activityDateTime` for audits and the
  Graph `createdDateTime` for sign-ins; it is **always distinct**
  from `collected_at` (the lineage value).
* G01-014 (`adapt_risk_detections`) writes append-only rows to
  `core.risk_detection` with `detected_at` from the Graph
  `detectedDateTime` and `activity_at` from `activityDateTime`.

The catalogue Notes exclusions (IP, location, user-agent, correlation
IDs, etc.) are honoured by the field set — adapters never accept or
emit those fields.

## 5. Current + snapshot adapters (G01-011, G01-013, G01-015)

* Each Graph record yields **two** rows: one current-state row and
  one snapshot row.
* The current row carries `last_observed_at` (set from
  `lineage.collected_at`); the snapshot row carries `snapshot_at`
  (also from `lineage.collected_at`) and **does not** carry
  `last_observed_at`. The snapshot row's unique key is
  `(tenant_id, source_object_id, collection_run_id)`.
* G01-011 emits only metadata + state — never conditions / grants
  policy bodies.
* G01-013 omits risk-event detail bodies; only id + risk fields.
* G01-015 is `service` + `status` only.

## 6. Current-state only (G01-012)

* `named_locations()` emits one row per Graph record onto
  `core.named_location` with `display_name`, `created_date_time`,
  `modified_date_time`. IP / country ranges are excluded.

## 7. INCREMENTAL + HISTORICAL adapters (G01-016, G01-017)

* Each Graph record yields **two** rows: one current-state row and
  one versioned history row.
* The current row carries `last_observed_at`.
* The history row carries `observed_at`, `collected_at`, and the
  deterministic `version_identity` bytes (raw SHA-256 digest; the
  database stores them as `BYTEA`).

### 7.1 version_identity

Per `docs/database-schema-design.md` Sections 7.7.a, 7.7.b, and 10.3
(G06-001R):

```
primary rule (lastModifiedDateTime present):
    version_identity = SHA256("primary", tenant_id, source_object_id,
                              last_modified_date_time)

fallback rule (lastModifiedDateTime absent / blank):
    G01-016: SHA256("fallback", tenant_id, source_object_id,
                     status, is_resolved, start_date_time, end_date_time)
    G01-017: SHA256("fallback", tenant_id, source_object_id,
                     category, severity, is_major_change,
                     start_date_time, end_date_time,
                     action_required_by_date_time)
```

The hash is implemented in `versioning.py` with a deterministic
per-field encoding (`_encode_field`) so that `None`, `bool`, `int`,
`str`, and `list` inputs round-trip identically across Python versions
and platforms. Returns raw digest bytes — the database stores the
hash verbatim per migration 005.

### 7.2 stability guarantees (verified by tests)

* Identical observations across runs produce the **same**
  `version_identity`.
* A `lastModifiedDateTime` advance produces a **new** identity.
* When `lastModifiedDateTime` is missing, a real change in any
  fallback lifecycle field produces a **new** identity.
* When `lastModifiedDateTime` is present, the primary rule ignores
  changes to other lifecycle fields (this is the G06-001R
  contract).

The `UNIQUE (tenant_id, source_object_id, version_identity)`
constraint on `core.service_health_issue_history` and
`core.service_update_message_history` (see migration 005) prevents
duplicate history rows; the collector emits history rows for **every**
observation and relies on `ON CONFLICT DO NOTHING` to dedup, which
is the responsibility of the eventual writer.

## 8. Lineage

The `Lineage` dataclass carries only safe identifiers:

```python
@dataclass(frozen=True)
class Lineage:
    tenant_id:          Optional[int]    = None
    collection_run_id:  Optional[int]    = None
    endpoint_run_id:    Optional[int]    = None
    collected_at:       Optional[str]    = None
    retention_class:    Optional[str]    = None
```

These fields map directly to columns declared on the audit_event,
risk_detection, risky_user(_snapshot), conditional_access_policy(_snapshot),
named_location, service_health_overview(_snapshot),
service_health_issue(_history), and service_update_message(_history)
tables.

No `Authorization`, `Bearer`, client secret, or token endpoint
description lives in or passes through a `Lineage`. Adapters assert
this on every produced row.

## 9. Test coverage (59 tests, no live Graph)

Test classes:

* `PackageSurfaceTests` (3) — endpoint-table map and event_source
  discriminator constants.
* `LineageTests` (5) — `Lineage` coercion semantics.
* `VersioningTests` (10) — primary / fallback / stability rules.
* `DirectoryAuditLogsAdapterTests` (5) — G01-005 current-state
  shape, event vs collected_at, missing-field, determinism.
* `SignInLogsAdapterTests` (5) — G01-006 + event_source separation.
* `RiskDetectionsAdapterTests` (3) — G01-014 append-only shape.
* `ConditionalAccessPoliciesAdapterTests` (3) — current + snapshot
  + key parity.
* `NamedLocationsAdapterTests` (3) — current-only behaviour.
* `RiskyUsersAdapterTests` (2) — current + snapshot.
* `ServiceHealthOverviewAdapterTests` (2) — current + snapshot.
* `ServiceHealthIssuesAdapterTests` (6) — current + history, version
  identity stability / lmdt change / lifecycle change, key parity.
* `ServiceUpdateMessagesAdapterTests` (6) — current + history,
  version identity, services handling.
* `SecurityTests` (3) — no credential / token / bearer substrings
  in any produced row, no token in lineage pass-through,
  determinism across repeated runs.
* `NoLiveGraphCallTests` (2) — adapters do not import
  `GraphTransport` and do not require any network state.

Run:

```
python3 -m unittest tests.workloads.security_service.test_adapters
python3 -m unittest tests.core.test_collector_framework tests.core.test_auth_runtime_cli
python3 -m unittest tests.discovery.test_discovery_agent
python3 -m unittest tests.database.test_migrations
```

Observed run (G07-B + G05 + Discovery + Migrations):

```
Ran 274 tests in 3.5s
OK
```

Breakdown: G07-B 59, G05 framework 115, Discovery Agent 43, the
remaining 57 cover migrations and the auth/runtime/cli tests.

## 10. Security boundary

* No `collectors/core/*` module was imported into the workload
  adapters at runtime in any way that exposes credentials. Adapters
  only depend on the dataclass-style `Lineage` and pure-Python
  hashing utilities.
* No database writer, no SQL, no transaction was opened by this
  task. The persisted row is still G06's responsibility.
* Adapters never store `Bearer`, `Authorization`, or token-shaped
  substrings in any produced row — the security tests assert this.
* `lineage_from_mapping` does not echo unexpected keys onto
  produced rows; only the safe `Lineage` fields make it through.

## 11. Source files touched

Created:

* `collectors/workloads/security_service/__init__.py`
* `collectors/workloads/security_service/lineage.py`
* `collectors/workloads/security_service/versioning.py`
* `collectors/workloads/security_service/adapters.py`
* `tests/workloads/security_service/__init__.py`
* `tests/workloads/security_service/test_adapters.py`
* `docs/g07-security-service-collectors.md` (this file)

Modified:

* none.

Forbidden files explicitly NOT touched:

* `collectors/core/*`
* `collectors/run_collector.py`
* `config/*`
* `database/migrations/*`
* `agents/discovery/*`
* `data/discovery/*`
* `secrets/*`
* G07-A expected footprint (no such files exist yet)