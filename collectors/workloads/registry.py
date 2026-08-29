"""G07-C central workload registry.

Maps every ``G01-001..G01-019`` endpoint id to a single
:class:`collectors.workloads.models.WorkloadEntry` that exposes:

* the persistence mode (the controlled vocabulary from
  :mod:`collectors.workloads.models`);
* the current / snapshot / history / event / reference target tables,
  reconciled against the G06 DDL;
* the unified adapter callable that consumes one Graph record and
  returns either a single row dict or a tuple ``(current_row, X)``
  where ``X`` is the snapshot or history row.

This module performs:

* NO database writes,
* NO Microsoft Graph calls,
* NO credential / token / Authorization handling.

The registry is the single integration point for the G05 Collector
Framework. It is deterministic, import-time validated, and exposes
helper functions for single-record dispatch and batch dispatch that
preserve source order and never mutate the caller's input.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .models import (
    PERSISTENCE_CURRENT,
    PERSISTENCE_CURRENT_WITH_HISTORY,
    PERSISTENCE_CURRENT_WITH_SNAPSHOT,
    PERSISTENCE_EVENT,
    PERSISTENCE_REFERENCE,
    NormalizedWorkloadRecord,
    PersistenceMode,
    WorkloadDispatchError,
    WorkloadEntry,
)


# ---------------------------------------------------------------------------
# Canonical expected set
# ---------------------------------------------------------------------------


EXPECTED_ENDPOINT_IDS: Tuple[str, ...] = tuple(
    "G01-{:03d}".format(index) for index in range(1, 20)
)


# ---------------------------------------------------------------------------
# Lineage context
# ---------------------------------------------------------------------------


class LineageContext:
    """Adapter-agnostic lineage shape consumed by the registry.

    A :class:`LineageContext` is the ONLY lineage shape the dispatcher
    accepts. It contains the same five fields the G07-A and G07-B
    adapters expect, but stored as plain attributes so the registry
    does not need to depend on either subpackage for the type.

    The context is intentionally small. It carries NO credentials, NO
    tokens, NO ``Authorization`` headers -- only safe identifiers used
    to stamp normalized rows.
    """

    __slots__ = (
        "tenant_id",
        "collection_run_id",
        "endpoint_run_id",
        "observed_at",
        "retention_class",
    )

    def __init__(
        self,
        *,
        tenant_id: Optional[int] = None,
        collection_run_id: Optional[int] = None,
        endpoint_run_id: Optional[int] = None,
        observed_at: Optional[str] = None,
        retention_class: Optional[str] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.collection_run_id = collection_run_id
        self.endpoint_run_id = endpoint_run_id
        self.observed_at = observed_at
        self.retention_class = retention_class

    @classmethod
    def from_mapping(cls, value: Optional[Mapping[str, Any]]) -> "LineageContext":
        """Build a :class:`LineageContext` from a mapping or ``None``.

        Accepts the same field names the G07-A and G07-B adapters use
        (``tenant_id``, ``collection_run_id``, ``endpoint_run_id``,
        ``observed_at`` for G07-A / ``collected_at`` for G07-B, and
        ``retention_class``). Unknown keys are ignored silently so the
        caller can pass either a G07-A-style mapping or a G07-B
        :class:`Lineage` mapping verbatim.
        """
        if value is None:
            return cls()
        if isinstance(value, LineageContext):
            return value
        if not isinstance(value, Mapping):
            raise TypeError(
                "lineage_context must be a LineageContext, mapping, or None"
            )
        observed_at = value.get("observed_at", value.get("collected_at"))
        kwargs: Dict[str, Any] = {}
        for field_name in (
            "tenant_id",
            "collection_run_id",
            "endpoint_run_id",
            "retention_class",
        ):
            if field_name in value:
                kwargs[field_name] = value[field_name]
        if observed_at is not None:
            kwargs["observed_at"] = observed_at
        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "collection_run_id": self.collection_run_id,
            "endpoint_run_id": self.endpoint_run_id,
            "observed_at": self.observed_at,
            "retention_class": self.retention_class,
        }


# ---------------------------------------------------------------------------
# Adapter wrappers
# ---------------------------------------------------------------------------


def _wrap_g07a(adapter_module: Any) -> Any:
    """Wrap a G07-A ``normalize`` callable as a single-record adapter.

    G07-A adapter signature::

        normalize(record, *,
                  tenant_id, collection_run_id,
                  endpoint_run_id, observed_at)

    Returns either a single dict (CURRENT_ONLY / REFERENCE) or a
    ``(current_row, snapshot_row)`` tuple (HISTORICAL_WITH_SNAPSHOT).
    """

    def _adapter(record: Mapping[str, Any], lineage: LineageContext) -> Any:
        return adapter_module.normalize(
            record,
            tenant_id=lineage.tenant_id,
            collection_run_id=lineage.collection_run_id,
            endpoint_run_id=lineage.endpoint_run_id,
            observed_at=lineage.observed_at,
        )

    return _adapter


def _wrap_g07b(callable_: Any) -> Any:
    """Wrap a G07-B batch adapter as a single-record adapter.

    G07-B adapter signature::

        fn(records, lineage=None) -> List[Dict]

    The wrapper feeds a single-record list to the batch adapter and
    returns the resulting first row (or ``(current_row, X)`` tuple for
    the two-row endpoints). The wrapped callable is closed over the
    lineage per call so the underlying adapter sees an isolated
    snapshot.
    """

    def _adapter(record: Mapping[str, Any], lineage: LineageContext) -> Any:
        lineage_mapping = {
            "tenant_id": lineage.tenant_id,
            "collection_run_id": lineage.collection_run_id,
            "endpoint_run_id": lineage.endpoint_run_id,
            "collected_at": lineage.observed_at,
            "retention_class": lineage.retention_class,
        }
        rows = callable_([record], lineage_mapping)
        if not rows:
            raise ValueError(
                "G07-B adapter returned no rows for a single record"
            )
        if len(rows) == 1:
            return rows[0]
        return rows[0], rows[1]

    return _adapter


# ---------------------------------------------------------------------------
# Entry construction
# ---------------------------------------------------------------------------


def _entry(
    endpoint_id: str,
    persistence_mode: str,
    *,
    current_table: Optional[str],
    snapshot_table: Optional[str] = None,
    history_table: Optional[str] = None,
    event_table: Optional[str] = None,
    reference_table: Optional[str] = None,
    event_source: Optional[str] = None,
    workload: str,
    retention_class: str,
    owner: str,
    adapter: Any,
    description: str = "",
) -> WorkloadEntry:
    """Build a :class:`WorkloadEntry` with mode-aware table defaults.

    For ``EVENT`` the event table falls back to ``current_table`` when
    no explicit ``event_table`` is supplied; for ``REFERENCE`` the
    reference table falls back to ``current_table``; for
    ``CURRENT_WITH_SNAPSHOT`` / ``CURRENT_WITH_HISTORY`` the
    ``current_table`` default comes from the adapter:
    ``core.<name>`` unless explicitly overridden.
    """
    mode = PersistenceMode(persistence_mode)
    if event_table is None and mode == PersistenceMode.EVENT:
        event_table = current_table
    if reference_table is None and mode == PersistenceMode.REFERENCE:
        reference_table = current_table
    return WorkloadEntry(
        endpoint_id=endpoint_id,
        persistence_mode=mode,
        current_table=current_table,
        snapshot_table=snapshot_table,
        history_table=history_table,
        event_table=event_table,
        reference_table=reference_table,
        event_source=event_source,
        workload=workload,
        retention_class=retention_class,
        owner=owner,
        adapter=adapter,
        description=description,
    )


# ---------------------------------------------------------------------------
# Registry population
# ---------------------------------------------------------------------------


def _build_registry() -> Dict[str, WorkloadEntry]:
    """Build the canonical G01-001..G01-019 registry.

    The mapping is hard-coded from the G07-A / G07-B adapter modules
    and the authoritative config / docs / DDL. It is intentionally
    constructed imperatively (rather than data-loaded) so the
    persistence-mode and table-mapping contract is provable at import
    time.
    """
    # Imported lazily so the registry module is importable even if a
    # workload subpackage has a transient import error -- the registry
    # will then surface a clear error at access time.
    from . import directory as g07a
    from .security_service import adapters as g07b_adapters
    from .security_service import (
        EVENT_SOURCE_DIRECTORY_AUDIT,
        EVENT_SOURCE_SIGN_IN,
    )

    entries: Dict[str, WorkloadEntry] = {}

    # --- G07-A: Directory / Licensing / RBAC -------------------------
    entries["G01-001"] = _entry(
        "G01-001",
        PERSISTENCE_CURRENT,
        current_table='core."user"',
        workload="Entra ID",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.users),
        description="Users -- CURRENT_ONLY upsert",
    )
    entries["G01-002"] = _entry(
        "G01-002",
        PERSISTENCE_CURRENT,
        current_table='core."group"',
        workload="Entra ID",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.groups),
        description="Groups -- CURRENT_ONLY upsert",
    )
    entries["G01-003"] = _entry(
        "G01-003",
        PERSISTENCE_CURRENT,
        current_table="core.organization",
        workload="Entra ID",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.organization),
        description="Organization -- CURRENT_ONLY single row",
    )
    entries["G01-004"] = _entry(
        "G01-004",
        PERSISTENCE_CURRENT_WITH_SNAPSHOT,
        current_table="core.subscribed_sku",
        snapshot_table="core.subscribed_sku_snapshot",
        workload="Microsoft 365 Licensing",
        retention_class="STANDARD",
        owner="directory",
        adapter=_wrap_g07a(g07a.subscribed_skus),
        description="Subscribed SKUs -- current + per-run snapshot",
    )
    entries["G01-007"] = _entry(
        "G01-007",
        PERSISTENCE_CURRENT,
        current_table="core.application",
        workload="Microsoft Entra ID",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.applications),
        description="Applications -- CURRENT_ONLY upsert",
    )
    entries["G01-008"] = _entry(
        "G01-008",
        PERSISTENCE_CURRENT,
        current_table="core.service_principal",
        workload="Microsoft Entra ID",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.service_principals),
        description="Service Principals -- CURRENT_ONLY upsert",
    )
    entries["G01-009"] = _entry(
        "G01-009",
        PERSISTENCE_CURRENT,
        current_table="core.device",
        workload="Microsoft Entra ID",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.devices),
        description="Devices -- CURRENT_ONLY upsert",
    )
    entries["G01-010"] = _entry(
        "G01-010",
        PERSISTENCE_CURRENT,
        current_table="core.administrative_unit",
        workload="Microsoft Entra ID Governance",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.administrative_units),
        description="Administrative Units -- CURRENT_ONLY upsert",
    )
    entries["G01-018"] = _entry(
        "G01-018",
        PERSISTENCE_REFERENCE,
        current_table="core.directory_role_definition",
        workload="Microsoft Entra RBAC",
        retention_class="REFERENCE",
        owner="directory",
        adapter=_wrap_g07a(g07a.directory_role_definitions),
        description="Directory Role Definitions -- REFERENCE upsert",
    )
    entries["G01-019"] = _entry(
        "G01-019",
        PERSISTENCE_CURRENT_WITH_SNAPSHOT,
        current_table="core.directory_role_assignment",
        snapshot_table="core.directory_role_assignment_snapshot",
        workload="Microsoft Entra RBAC",
        retention_class="LONG",
        owner="directory",
        adapter=_wrap_g07a(g07a.directory_role_assignments),
        description="Directory Role Assignments -- current + per-run snapshot",
    )

    # --- G07-B: Security / Governance / Service Health --------------
    entries["G01-005"] = _entry(
        "G01-005",
        PERSISTENCE_EVENT,
        current_table="core.audit_event",
        event_table="core.audit_event",
        workload="Microsoft Entra ID",
        retention_class="HIGH_SENSITIVITY",
        owner="security_service",
        event_source=EVENT_SOURCE_DIRECTORY_AUDIT,
        adapter=_wrap_g07b(g07b_adapters.adapt_directory_audit_logs),
        description="Directory Audit Logs -- append-only event rows",
    )
    entries["G01-006"] = _entry(
        "G01-006",
        PERSISTENCE_EVENT,
        current_table="core.audit_event",
        event_table="core.audit_event",
        workload="Microsoft Entra ID",
        retention_class="HIGH_SENSITIVITY",
        owner="security_service",
        event_source=EVENT_SOURCE_SIGN_IN,
        adapter=_wrap_g07b(g07b_adapters.adapt_sign_in_logs),
        description="Sign-in Logs -- append-only event rows",
    )
    entries["G01-011"] = _entry(
        "G01-011",
        PERSISTENCE_CURRENT_WITH_SNAPSHOT,
        current_table="core.conditional_access_policy",
        snapshot_table="core.conditional_access_policy_snapshot",
        workload="Microsoft Entra Conditional Access",
        retention_class="REFERENCE",
        owner="security_service",
        adapter=_wrap_g07b(g07b_adapters.conditional_access_policies),
        description="Conditional Access Policies -- current + per-run snapshot",
    )
    entries["G01-012"] = _entry(
        "G01-012",
        PERSISTENCE_CURRENT,
        current_table="core.named_location",
        workload="Microsoft Entra Conditional Access",
        retention_class="REFERENCE",
        owner="security_service",
        adapter=_wrap_g07b(g07b_adapters.named_locations),
        description="Conditional Access Named Locations -- current upsert",
    )
    entries["G01-013"] = _entry(
        "G01-013",
        PERSISTENCE_CURRENT_WITH_SNAPSHOT,
        current_table="core.risky_user",
        snapshot_table="core.risky_user_snapshot",
        workload="Microsoft Entra ID Protection",
        retention_class="HIGH_SENSITIVITY",
        owner="security_service",
        adapter=_wrap_g07b(g07b_adapters.risky_users),
        description="Risky Users -- current + per-run snapshot",
    )
    entries["G01-014"] = _entry(
        "G01-014",
        PERSISTENCE_EVENT,
        current_table="core.risk_detection",
        event_table="core.risk_detection",
        workload="Microsoft Entra ID Protection",
        retention_class="HIGH_SENSITIVITY",
        owner="security_service",
        adapter=_wrap_g07b(g07b_adapters.adapt_risk_detections),
        description="Risk Detections -- append-only event rows",
    )
    entries["G01-015"] = _entry(
        "G01-015",
        PERSISTENCE_CURRENT_WITH_SNAPSHOT,
        current_table="core.service_health_overview",
        snapshot_table="core.service_health_overview_snapshot",
        workload="Microsoft 365 Service Health",
        retention_class="STANDARD",
        owner="security_service",
        adapter=_wrap_g07b(g07b_adapters.service_health_overview),
        description="Service Health Overview -- current + per-run snapshot",
    )
    entries["G01-016"] = _entry(
        "G01-016",
        PERSISTENCE_CURRENT_WITH_HISTORY,
        current_table="core.service_health_issue",
        history_table="core.service_health_issue_history",
        workload="Microsoft 365 Service Health",
        retention_class="STANDARD",
        owner="security_service",
        adapter=_wrap_g07b(g07b_adapters.service_health_issues),
        description="Service Health Issues -- current + versioned history",
    )
    entries["G01-017"] = _entry(
        "G01-017",
        PERSISTENCE_CURRENT_WITH_HISTORY,
        current_table="core.service_update_message",
        history_table="core.service_update_message_history",
        workload="Microsoft 365 Message Center",
        retention_class="STANDARD",
        owner="security_service",
        adapter=_wrap_g07b(g07b_adapters.service_update_messages),
        description="Service Update Messages -- current + versioned history",
    )

    return entries


# Build the registry eagerly. The coverage invariant (see
# ``validate_registry``) runs at import time and raises on any
# inconsistency.
REGISTRY: Dict[str, WorkloadEntry] = _build_registry()


# ---------------------------------------------------------------------------
# Validation -- coverage invariant
# ---------------------------------------------------------------------------


class RegistryCoverageError(WorkloadDispatchError):
    """Raised when the registry does not match the expected 19 endpoints."""


def validate_registry(
    registry: Optional[Mapping[str, WorkloadEntry]] = None,
    *,
    expected_ids: Sequence[str] = EXPECTED_ENDPOINT_IDS,
) -> None:
    """Validate the registry against the 19-endpoint invariant.

    Checks:

    * exactly ``len(expected_ids)`` entries (default 19);
    * endpoint ids form ``set(expected_ids)`` exactly;
    * no duplicate endpoint ids (the ``Dict`` key invariant guarantees
      this, but the check is explicit for documentation purposes);
    * every entry has a non-empty ``current_table``;
    * every entry has a per-mode second table (``snapshot_table`` for
      ``CURRENT_WITH_SNAPSHOT``, ``history_table`` for
      ``CURRENT_WITH_HISTORY``, ``event_table`` for ``EVENT``,
      ``reference_table`` for ``REFERENCE``); the population helper
      already defaults these to ``current_table`` where appropriate.

    Raises :class:`RegistryCoverageError` if any check fails. The
    function is also called once at import time so any inconsistency
    surfaces as a hard import failure.
    """
    registry = registry if registry is not None else REGISTRY
    expected_set = set(expected_ids)
    actual_set = set(registry.keys())

    if len(registry) != len(expected_ids):
        raise RegistryCoverageError(
            "registry has {} entries, expected {}".format(
                len(registry), len(expected_ids)
            )
        )
    if actual_set != expected_set:
        missing = expected_set - actual_set
        extras = actual_set - expected_set
        raise RegistryCoverageError(
            "registry endpoint set mismatch: missing={} extra={}".format(
                sorted(missing), sorted(extras)
            )
        )

    # Per-entry invariant checks.
    for endpoint_id, entry in registry.items():
        if entry.endpoint_id != endpoint_id:
            raise RegistryCoverageError(
                "registry key {} does not match entry.endpoint_id {}".format(
                    endpoint_id, entry.endpoint_id
                )
            )
        if not entry.current_table:
            raise RegistryCoverageError(
                "{}: current_table must be set".format(endpoint_id)
            )
        mode = entry.persistence_mode
        if mode == PersistenceMode.CURRENT_WITH_SNAPSHOT:
            if not entry.snapshot_table:
                raise RegistryCoverageError(
                    "{}: CURRENT_WITH_SNAPSHOT requires snapshot_table".format(
                        endpoint_id
                    )
                )
        elif mode == PersistenceMode.CURRENT_WITH_HISTORY:
            if not entry.history_table:
                raise RegistryCoverageError(
                    "{}: CURRENT_WITH_HISTORY requires history_table".format(
                        endpoint_id
                    )
                )
        elif mode == PersistenceMode.EVENT:
            if not entry.event_table:
                raise RegistryCoverageError(
                    "{}: EVENT requires event_table".format(endpoint_id)
                )
        elif mode == PersistenceMode.REFERENCE:
            if not entry.reference_table:
                raise RegistryCoverageError(
                    "{}: REFERENCE requires reference_table".format(
                        endpoint_id
                    )
                )


validate_registry()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_entry(endpoint_id: str) -> WorkloadEntry:
    """Return the registry entry for ``endpoint_id`` or raise.

    Raises :class:`WorkloadDispatchError` with a message that
    identifies the unknown id. The error subclasses :class:`KeyError`
    so callers that already catch ``KeyError`` continue to work.
    """
    if not isinstance(endpoint_id, str) or not endpoint_id:
        raise WorkloadDispatchError("endpoint_id must be a non-empty string")
    entry = REGISTRY.get(endpoint_id)
    if entry is None:
        raise WorkloadDispatchError(
            "Unknown endpoint id: {}".format(endpoint_id)
        )
    return entry


def endpoint_ids() -> Tuple[str, ...]:
    """Return the deterministic tuple of registered endpoint ids."""
    return tuple(REGISTRY.keys())


def iter_entries() -> Iterable[WorkloadEntry]:
    """Yield registry entries in deterministic order."""
    for endpoint_id in EXPECTED_ENDPOINT_IDS:
        yield REGISTRY[endpoint_id]


def _row_kind_for_mode(mode: PersistenceMode) -> Tuple[str, ...]:
    """Return the row member names the envelope populates for ``mode``."""
    if mode == PersistenceMode.CURRENT:
        return ("current_row",)
    if mode == PersistenceMode.REFERENCE:
        return ("current_row", "reference_row")
    if mode == PersistenceMode.EVENT:
        return ("event_row",)
    if mode == PersistenceMode.CURRENT_WITH_SNAPSHOT:
        return ("current_row", "snapshot_row")
    if mode == PersistenceMode.CURRENT_WITH_HISTORY:
        return ("current_row", "history_row")
    raise WorkloadDispatchError("unsupported persistence mode: {}".format(mode))


def _build_envelope(
    entry: WorkloadEntry,
    adapter_output: Any,
) -> NormalizedWorkloadRecord:
    """Translate an adapter return value into a common envelope.

    Adapter contract:

    * ``CURRENT`` / ``REFERENCE`` -- a single dict.
    * ``CURRENT_WITH_SNAPSHOT`` / ``CURRENT_WITH_HISTORY`` -- a
      ``(current_row, secondary_row)`` tuple.

    The ``REFERENCE`` envelope populates both ``current_row`` and
    ``reference_row`` from the same dict so downstream writers can pick
    whichever shape fits their DDL.
    """
    mode = entry.persistence_mode
    if mode in (PersistenceMode.CURRENT, PersistenceMode.REFERENCE):
        if not isinstance(adapter_output, Mapping):
            raise WorkloadDispatchError(
                "{}: adapter must return a mapping for {}".format(
                    entry.endpoint_id, mode.value
                )
            )
        current_row = _copy_mapping(adapter_output)
        if mode == PersistenceMode.REFERENCE:
            return NormalizedWorkloadRecord(
                endpoint_id=entry.endpoint_id,
                persistence_mode=mode,
                current_row=current_row,
                reference_row=current_row,
            )
        return NormalizedWorkloadRecord(
            endpoint_id=entry.endpoint_id,
            persistence_mode=mode,
            current_row=current_row,
        )

    if mode in (
        PersistenceMode.CURRENT_WITH_SNAPSHOT,
        PersistenceMode.CURRENT_WITH_HISTORY,
    ):
        if (
            not isinstance(adapter_output, tuple)
            or len(adapter_output) != 2
        ):
            raise WorkloadDispatchError(
                "{}: adapter must return a (current, secondary) tuple for {}".format(
                    entry.endpoint_id, mode.value
                )
            )
        current, secondary = adapter_output
        if not isinstance(current, Mapping) or not isinstance(secondary, Mapping):
            raise WorkloadDispatchError(
                "{}: tuple members must be mappings".format(entry.endpoint_id)
            )
        if mode == PersistenceMode.CURRENT_WITH_SNAPSHOT:
            return NormalizedWorkloadRecord(
                endpoint_id=entry.endpoint_id,
                persistence_mode=mode,
                current_row=_copy_mapping(current),
                snapshot_row=_copy_mapping(secondary),
            )
        return NormalizedWorkloadRecord(
            endpoint_id=entry.endpoint_id,
            persistence_mode=mode,
            current_row=_copy_mapping(current),
            history_row=_copy_mapping(secondary),
        )

    if mode == PersistenceMode.EVENT:
        if not isinstance(adapter_output, Mapping):
            raise WorkloadDispatchError(
                "{}: EVENT adapter must return a mapping".format(
                    entry.endpoint_id
                )
            )
        event_row = _copy_mapping(adapter_output)
        if entry.event_source is not None:
            event_row["event_source"] = entry.event_source
        else:
            event_row.pop("event_source", None)
        return NormalizedWorkloadRecord(
            endpoint_id=entry.endpoint_id,
            persistence_mode=mode,
            event_row=event_row,
        )

    raise WorkloadDispatchError(
        "unsupported persistence mode: {}".format(mode)
    )


def _copy_mapping(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise WorkloadDispatchError(
            "row must be a mapping, got {}".format(type(value).__name__)
        )
    return dict(value)


def normalize_record(
    endpoint_id: str,
    graph_record: Mapping[str, Any],
    lineage_context: Optional[Any] = None,
) -> NormalizedWorkloadRecord:
    """Dispatch a single Graph record to the matching workload adapter.

    Contract:

    * exact endpoint lookup; unknown endpoint ids raise
      :class:`WorkloadDispatchError`;
    * the adapter receives a :class:`LineageContext` (or a mapping / a
      G07-B :class:`Lineage` that is coerced via
      :meth:`LineageContext.from_mapping`);
    * the adapter result is converted into a
      :class:`NormalizedWorkloadRecord` whose row members are
      defensive copies -- the caller cannot mutate the adapter output
      by holding on to the returned envelope;
    * ``graph_record`` is *not* mutated by the dispatcher.

    No database writes happen here.
    """
    entry = get_entry(endpoint_id)
    lineage = LineageContext.from_mapping(lineage_context)
    adapter_output = entry.adapter(graph_record, lineage)
    return _build_envelope(entry, adapter_output)


def normalize_records(
    endpoint_id: str,
    records: Iterable[Mapping[str, Any]],
    lineage_context: Optional[Any] = None,
) -> List[NormalizedWorkloadRecord]:
    """Batch-dispatch an iterable of Graph records.

    Contract:

    * preserves source order -- the result list has the same length
      and the same per-record ordering as the input iterable;
    * one :class:`NormalizedWorkloadRecord` per source record;
    * an empty input returns an empty list;
    * a malformed record fails predictably: the adapter is invoked
      per record, and the underlying error propagates -- the
      dispatcher does not silently drop records.
    """
    entry = get_entry(endpoint_id)
    lineage = LineageContext.from_mapping(lineage_context)
    # The registry entry owns the authoritative retention_class for the
    # endpoint. Adapters (e.g. the security-service current+snapshot
    # adapters) only emit ``retention_class`` when the lineage carries it,
    # but the production runtime lineage does not propagate it. Default it
    # from the registry so produced rows always satisfy the persistence
    # column contract.
    if lineage.retention_class is None and entry.retention_class is not None:
        lineage.retention_class = entry.retention_class
    out: List[NormalizedWorkloadRecord] = []
    materialized = list(records)
    for record in materialized:
        adapter_output = entry.adapter(record, lineage)
        out.append(_build_envelope(entry, adapter_output))
    return out


__all__ = [
    "EXPECTED_ENDPOINT_IDS",
    "LineageContext",
    "REGISTRY",
    "RegistryCoverageError",
    "WorkloadDispatchError",
    "endpoint_ids",
    "get_entry",
    "iter_entries",
    "normalize_record",
    "normalize_records",
    "validate_registry",
]
