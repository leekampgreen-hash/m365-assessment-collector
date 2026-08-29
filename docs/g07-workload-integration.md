# G07-C — Workload Registry & Collector Integration

This document describes the G07-C integration layer that connects the
G07-A directory adapters and the G07-B security / service-health
adapters to the G05 Collector Framework. It is the single integration
point the next persistence step will consume.

## Scope

* **One central registry** for every ``G01-001..G01-019`` endpoint.
* **A controlled persistence-mode vocabulary** that reconciles the
  G07-A ``HISTORY_MODE_*`` constants and the G07-B ``pattern`` strings
  into five values.
* **A deterministic dispatch API** (``normalize_record`` /
  ``normalize_records``) that wraps every adapter behind a common
  signature.
* **A common normalized-result envelope** so the next persistence
  step can consume one shape instead of nineteen.
* **A coverage invariant** that the registry provably holds 19
  endpoints in sync with ``config/api_inventory.json``.

## Out of scope

* Database writes.
* Token acquisition, ``Authorization`` headers, credential handling.
* Discovery-agent evidence.
* Modifying any G07-A or G07-B adapter implementation.
* Wiring the dispatcher into ``collectors/run_collector.py`` -- that
  is the next acceptance step.

## Module map

```
collectors/workloads/
├── __init__.py            -- public re-exports
├── models.py              -- PersistenceMode enum,
│                            WorkloadEntry,
│                            NormalizedWorkloadRecord,
│                            WorkloadDispatchError
├── registry.py            -- REGISTRY dict, LineageContext,
│                            normalize_record, normalize_records,
│                            validate_registry
├── directory/             -- G07-A adapters (untouched)
└── security_service/      -- G07-B adapters (untouched)
```

## 19-endpoint coverage

The registry maps exactly the endpoints declared in
``config/api_inventory.json``:

```
G01-001  Users                                 CURRENT
G01-002  Groups                                CURRENT
G01-003  Organization                          CURRENT
G01-004  Subscribed SKUs                       CURRENT_WITH_SNAPSHOT
G01-005  Directory Audit Logs                  EVENT            (DIRECTORY_AUDIT)
G01-006  Sign-in Logs                          EVENT            (SIGN_IN)
G01-007  Applications                          CURRENT
G01-008  Service Principals                    CURRENT
G01-009  Devices                               CURRENT
G01-010  Administrative Units                  CURRENT
G01-011  Conditional Access Policies           CURRENT_WITH_SNAPSHOT
G01-012  Conditional Access Named Locations    CURRENT
G01-013  Risky Users                           CURRENT_WITH_SNAPSHOT
G01-014  Risk Detections                       EVENT
G01-015  Service Health Overview               CURRENT_WITH_SNAPSHOT
G01-016  Service Health Issues                 CURRENT_WITH_HISTORY
G01-017  Service Update Messages               CURRENT_WITH_HISTORY
G01-018  Directory Role Definitions            REFERENCE
G01-019  Directory Role Assignments            CURRENT_WITH_SNAPSHOT
```

## Persistence modes

Five values cover all 19 endpoints:

| Mode                     | Count | Endpoints |
|--------------------------|-------|-----------|
| ``CURRENT``              | 8     | G01-001, G01-002, G01-003, G01-007, G01-008, G01-009, G01-010, G01-012 |
| ``REFERENCE``            | 1     | G01-018 |
| ``EVENT``                | 3     | G01-005, G01-006, G01-014 |
| ``CURRENT_WITH_SNAPSHOT``| 5     | G01-004, G01-011, G01-013, G01-015, G01-019 |
| ``CURRENT_WITH_HISTORY`` | 2     | G01-016, G01-017 |

Mapping to accepted G03/G06 categories:

* ``CURRENT`` ↔ ``CURRENT_ONLY``.
* ``REFERENCE`` ↔ ``REFERENCE`` (no time-versioned state).
* ``EVENT`` ↔ ``EVENT_LOG`` (append-only fact tables; for G01-005
  and G01-006 the ``event_source`` discriminator separates audit from
  sign-in).
* ``CURRENT_WITH_SNAPSHOT`` ↔ ``HISTORICAL_WITH_SNAPSHOT`` (current
  upsert + per-run snapshot row).
* ``CURRENT_WITH_HISTORY`` ↔ ``INCREMENTAL_HISTORICAL`` (current
  upsert + versioned history row; ``version_identity`` carried on the
  history row).

The classification is intentionally unchanged from G03; the registry
just exposes a single closed vocabulary.

## Registry metadata

Every entry exposes:

* ``endpoint_id`` -- ``G01-XXX``.
* ``persistence_mode`` -- one of the five :class:`PersistenceMode`
  members.
* ``current_table`` -- ``schema.table`` for the current-state target.
* ``snapshot_table`` / ``history_table`` / ``event_table`` /
  ``reference_table`` -- the per-mode secondary target (when
  applicable).
* ``event_source`` -- ``"DIRECTORY_AUDIT"`` / ``"SIGN_IN"`` for the
  two audit endpoints; ``None`` for the other 17.
* ``workload`` -- human-readable label (e.g. ``"Entra ID"``).
* ``retention_class`` -- the retention class the adapter stamps onto
  every row.
* ``owner`` -- ``"directory"`` (G07-A) or ``"security_service"``
  (G07-B).
* ``adapter`` -- the unified single-record callable the dispatcher
  invokes.

## Dispatch contract

The dispatcher lives in ``collectors.workloads.registry``.

### ``normalize_record``

```python
from collectors.workloads import normalize_record, LineageContext

envelope = normalize_record(
    "G01-001",
    {"id": "user-1", "displayName": "Alice"},
    LineageContext(
        tenant_id=42,
        collection_run_id=1001,
        endpoint_run_id=9001,
        observed_at="2026-08-20T12:00:00+00:00",
        retention_class="REFERENCE",
    ),
)
```

Properties:

* exact endpoint lookup; unknown ids raise ``WorkloadDispatchError``.
* adapter receives a normalised ``LineageContext`` (constructed from a
  mapping, a ``LineageContext`` or ``None``).
* the returned envelope is a ``NormalizedWorkloadRecord`` whose row
  members are defensive copies; the caller's record is **not**
  mutated.
* no database writes happen here.

### ``normalize_records``

```python
from collectors.workloads import normalize_records

envelopes = normalize_records("G01-001", records, lineage)
```

Properties:

* one ``NormalizedWorkloadRecord`` per source record, in source order.
* an empty input returns an empty list.
* a malformed record fails predictably (the adapter's
  ``TypeError`` / ``ValueError`` propagates); records are **not**
  silently dropped.
* no concurrency.

## Normalized envelope

```python
@dataclass(frozen=True)
class NormalizedWorkloadRecord:
    endpoint_id: str
    persistence_mode: PersistenceMode
    current_row: Optional[Mapping[str, Any]] = None
    snapshot_row: Optional[Mapping[str, Any]] = None
    history_row: Optional[Mapping[str, Any]] = None
    event_row: Optional[Mapping[str, Any]] = None
    reference_row: Optional[Mapping[str, Any]] = None
```

Only the row members appropriate for the persistence mode are
populated:

| Mode                     | Populated members |
|--------------------------|-------------------|
| ``CURRENT``              | ``current_row`` |
| ``REFERENCE``            | ``current_row`` + ``reference_row`` (same dict) |
| ``EVENT``                | ``event_row`` |
| ``CURRENT_WITH_SNAPSHOT``| ``current_row`` + ``snapshot_row`` |
| ``CURRENT_WITH_HISTORY`` | ``current_row`` + ``history_row`` (carries ``version_identity``) |

The envelope never contains ``access_token``, ``refresh_token``,
``Authorization``, bearer strings, ``client_secret`` or ``password``
fields. Adapter-normalized rows only.

## Table mapping (G06 reconciliation)

```
G01-001  -> core."user"
G01-002  -> core."group"
G01-003  -> core.organization
G01-004  -> core.subscribed_sku
           core.subscribed_sku_snapshot
G01-005  -> core.audit_event (event_source=DIRECTORY_AUDIT)
G01-006  -> core.audit_event (event_source=SIGN_IN)
G01-007  -> core.application
G01-008  -> core.service_principal
G01-009  -> core.device
G01-010  -> core.administrative_unit
G01-011  -> core.conditional_access_policy
           core.conditional_access_policy_snapshot
G01-012  -> core.named_location
G01-013  -> core.risky_user
           core.risky_user_snapshot
G01-014  -> core.risk_detection
G01-015  -> core.service_health_overview
           core.service_health_overview_snapshot
G01-016  -> core.service_health_issue
           core.service_health_issue_history
G01-017  -> core.service_update_message
           core.service_update_message_history
G01-018  -> core.directory_role_definition
G01-019  -> core.directory_role_assignment
           core.directory_role_assignment_snapshot
```

The reconciliation is asserted in ``tests/workloads/test_registry.py``
(``RegistryTableMappingTests``).

## G07-A / G07-B ownership

* The 10 directory endpoints (G01-001..G01-004, G01-007..G01-010,
  G01-018, G01-019) are owned by ``collectors.workloads.directory``
  (G07-A). The dispatcher wraps each adapter's
  ``normalize(record, *, tenant_id, collection_run_id,
  endpoint_run_id, observed_at)`` callable so the adapter itself is
  unchanged.
* The 9 security / service-health endpoints (G01-005, G01-006,
  G01-011..G01-017) are owned by
  ``collectors.workloads.security_service`` (G07-B). The dispatcher
  wraps each batch adapter ``fn(records, lineage) -> List[Dict]`` so
  the batch callable is invoked with a single-element list and the
  resulting one-or-two rows are mapped onto the envelope.

Neither subpackage is modified by this task.

## Coverage invariant

``validate_registry`` runs at module import time and asserts:

* exactly 19 entries;
* endpoint ids form ``{G01-001..G01-019}`` exactly;
* per-entry ``current_table`` is set;
* per-mode secondary table (``snapshot_table`` /
  ``history_table`` / ``event_table`` / ``reference_table``) is set
  when required.

A failing invariant surfaces as a hard import error so a broken
mapping cannot silently ship.

## Security contract

* No credential, token, ``Authorization`` header, ``client_secret``
  or ``password`` field is ever part of an envelope.
* The dispatcher does not accept a credential-shaped argument; the
  ``LineageContext`` exposes only safe identifiers
  (``tenant_id``, ``collection_run_id``, ``endpoint_run_id``,
  ``observed_at``, ``retention_class``).
* The adapters underlying the dispatcher already strip Graph-side
  fields like ``rolePermissions`` (G01-018) before rows reach the
  envelope.

## Next runtime / persistence boundary

G07-C deliberately leaves ``collectors.run_collector.py`` and
``collectors/core/*`` unchanged. The next acceptance step wires the
dispatcher into the runtime / persistence path:

1. The runtime calls ``normalize_records(endpoint_id, records,
   lineage)`` per endpoint after Graph returns;
2. The persistence step consumes ``NormalizedWorkloadRecord`` rows and
   routes them to ``current_table`` / ``snapshot_table`` /
   ``history_table`` / ``event_table`` / ``reference_table`` based on
   the entry metadata.

No DB writes happen in G07-C.

## Test layout

```
tests/workloads/
├── test_registry.py        -- 26 tests: coverage invariant,
│                              persistence-mode buckets, table mapping,
│                              owner metadata, validation errors.
├── test_integration.py     -- 36 tests: representative dispatch per
│                              mode, batch behaviour, deterministic
│                              version_identity for G01-016 / G01-017,
│                              event_source separation,
│                              non-mutation guarantees, credential
│                              contract.
├── directory/              -- G07-A tests (untouched).
└── security_service/       -- G07-B tests (untouched).
```