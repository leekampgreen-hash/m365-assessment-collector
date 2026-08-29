"""Integration models for the G07-C workload layer.

This module defines the cross-package vocabulary the registry uses to
dispatch every G01-001..G01-019 Graph endpoint through a single
deterministic surface. It contains:

* A controlled ``PersistenceMode`` enum with five values.
* A ``WorkloadEntry`` dataclass holding per-endpoint dispatch metadata
  (endpoint id, persistence mode, current / snapshot / history / event
  / reference target tables, the adapter callable, etc.).
* A ``NormalizedWorkloadRecord`` dataclass acting as the common result
  envelope; only the row members applicable to the endpoint's
  persistence mode are populated.
* A :class:`WorkloadDispatchError` raised by the registry for unknown
  endpoint ids.

The integration boundary deliberately does NOT change any G07-A or
G07-B adapter implementation. Each adapter is wrapped by a thin
*unified* callable that maps the integration lineage shape onto the
adapter-specific keyword arguments; the underlying adapters stay
frozen.

This module performs NO database writes, NO Microsoft Graph calls, and
contains NO credential / token / Authorization material.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional


# ---------------------------------------------------------------------------
# Persistence mode vocabulary
# ---------------------------------------------------------------------------


class PersistenceMode(str, Enum):
    """Controlled persistence-mode vocabulary used by the registry.

    The five members reconcile the G07-A ``HISTORY_MODE_*`` constants
    and the G07-B ``pattern`` strings into one deterministic taxonomy.
    """

    CURRENT = "CURRENT"
    REFERENCE = "REFERENCE"
    EVENT = "EVENT"
    CURRENT_WITH_SNAPSHOT = "CURRENT_WITH_SNAPSHOT"
    CURRENT_WITH_HISTORY = "CURRENT_WITH_HISTORY"


# String constants for ergonomics. They equal the ``PersistenceMode``
# string values one-to-one.
PERSISTENCE_CURRENT = PersistenceMode.CURRENT.value
PERSISTENCE_REFERENCE = PersistenceMode.REFERENCE.value
PERSISTENCE_EVENT = PersistenceMode.EVENT.value
PERSISTENCE_CURRENT_WITH_SNAPSHOT = (
    PersistenceMode.CURRENT_WITH_SNAPSHOT.value
)
PERSISTENCE_CURRENT_WITH_HISTORY = (
    PersistenceMode.CURRENT_WITH_HISTORY.value
)


PERSISTENCE_MODES: tuple = tuple(mode.value for mode in PersistenceMode)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WorkloadDispatchError(KeyError):
    """Raised for controlled, offline-detectable registry problems.

    Subclasses :class:`KeyError` so existing code that catches
    ``KeyError`` for missing inventory keys still works; ``args`` keeps
    the endpoint id for diagnostics.
    """


# ---------------------------------------------------------------------------
# Registry entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkloadEntry:
    """Static, immutable metadata for one G01 endpoint.

    Fields:
        endpoint_id
            The ``G01-XXX`` inventory id.
        persistence_mode
            One of the five :class:`PersistenceMode` values.
        current_table
            ``schema.table`` for the current-state target; always set.
        snapshot_table
            ``schema.table`` for the snapshot target (only for
            ``CURRENT_WITH_SNAPSHOT``); ``None`` otherwise.
        history_table
            ``schema.table`` for the history target (only for
            ``CURRENT_WITH_HISTORY``); ``None`` otherwise.
        event_table
            ``schema.table`` for the event target (only for ``EVENT``);
            ``None`` otherwise. For the two audit endpoints this equals
            ``current_table`` because the event is the only target.
        reference_table
            ``schema.table`` for the reference target (only for
            ``REFERENCE``); ``None`` otherwise.
        event_source
            Discriminator string for the two audit endpoints
            (``DIRECTORY_AUDIT`` / ``SIGN_IN``); ``None`` for others.
        workload
            Human-readable workload / domain label (e.g. ``"Entra ID"``,
            ``"Microsoft 365 Service Health"``).
        retention_class
            Retention-class string the adapter propagates onto rows.
        owner
            Owning workload package (``"directory"`` or
            ``"security_service"``).
        adapter
            Unified callable that takes one Graph ``record`` mapping and
            a :class:`LineageContext` and returns either a dict (single
            row), a ``(current_row, snapshot_row)`` tuple, or a
            ``(current_row, history_row)`` tuple. The dispatcher is
            responsible for normalising the return value into a
            :class:`NormalizedWorkloadRecord`.
        description
            Short human-readable description.
    """

    endpoint_id: str
    persistence_mode: PersistenceMode
    adapter: Callable[..., Any]
    current_table: Optional[str]
    snapshot_table: Optional[str] = None
    history_table: Optional[str] = None
    event_table: Optional[str] = None
    reference_table: Optional[str] = None
    event_source: Optional[str] = None
    workload: str = ""
    retention_class: str = "STANDARD"
    owner: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint_id, str) or not self.endpoint_id:
            raise ValueError("endpoint_id must be a non-empty string")
        if not isinstance(self.persistence_mode, PersistenceMode):
            raise ValueError(
                "persistence_mode must be a PersistenceMode member"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe representation of this entry."""
        as_d = asdict(self)
        as_d["persistence_mode"] = self.persistence_mode.value
        as_d.pop("adapter", None)
        return as_d


# ---------------------------------------------------------------------------
# Normalized envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedWorkloadRecord:
    """Common normalized envelope produced by the dispatcher.

    Only the row members appropriate for the endpoint's
    :class:`PersistenceMode` are populated; the others stay ``None``.

    Members:
        endpoint_id
            The ``G01-XXX`` inventory id.
        persistence_mode
            One of the five :class:`PersistenceMode` values.
        current_row
            Current-state row (set for ``CURRENT``, ``REFERENCE``,
            ``CURRENT_WITH_SNAPSHOT``, ``CURRENT_WITH_HISTORY``).
        snapshot_row
            Snapshot row (set for ``CURRENT_WITH_SNAPSHOT`` only).
        history_row
            History row (set for ``CURRENT_WITH_HISTORY`` only). For
            G01-016 / G01-017 this row carries the deterministic
            ``version_identity`` column.
        event_row
            Append-only event row (set for ``EVENT`` only).
        reference_row
            Reference row (set for ``REFERENCE`` only). For G01-018 this
            equals ``current_row`` semantically; the registry populates
            both so downstream writers can pick whichever shape fits
            their DDL.
    """

    endpoint_id: str
    persistence_mode: PersistenceMode
    current_row: Optional[Mapping[str, Any]] = None
    snapshot_row: Optional[Mapping[str, Any]] = None
    history_row: Optional[Mapping[str, Any]] = None
    event_row: Optional[Mapping[str, Any]] = None
    reference_row: Optional[Mapping[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe copy of this envelope."""
        return {
            "endpoint_id": self.endpoint_id,
            "persistence_mode": self.persistence_mode.value,
            "current_row": _copy_mapping(self.current_row),
            "snapshot_row": _copy_mapping(self.snapshot_row),
            "history_row": _copy_mapping(self.history_row),
            "event_row": _copy_mapping(self.event_row),
            "reference_row": _copy_mapping(self.reference_row),
        }

    def rows(self) -> List[Mapping[str, Any]]:
        """Return the populated row members in a stable order.

        Useful for tests / serialization helpers. The order is:

            1. ``current_row``     (when set)
            2. ``snapshot_row``    (when set)
            3. ``history_row``     (when set)
            4. ``event_row``       (when set)
            5. ``reference_row``   (when set)
        """
        out: List[Mapping[str, Any]] = []
        for candidate in (
            self.current_row,
            self.snapshot_row,
            self.history_row,
            self.event_row,
            self.reference_row,
        ):
            if candidate is not None:
                out.append(candidate)
        return out


def _copy_mapping(value: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a defensive copy of ``value`` or ``None``.

    Keeps the envelope side-effect-free -- callers can mutate the
    returned dicts without touching the source adapter output.
    """
    if value is None:
        return None
    return dict(value)


__all__ = [
    "PERSISTENCE_CURRENT",
    "PERSISTENCE_CURRENT_WITH_HISTORY",
    "PERSISTENCE_CURRENT_WITH_SNAPSHOT",
    "PERSISTENCE_EVENT",
    "PERSISTENCE_MODES",
    "PERSISTENCE_REFERENCE",
    "NormalizedWorkloadRecord",
    "PersistenceMode",
    "WorkloadDispatchError",
    "WorkloadEntry",
]