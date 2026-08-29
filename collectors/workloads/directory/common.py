"""Shared types and utilities for the G07-A directory / licensing / RBAC
adapters.

Scope of G07-A:
- Normalisation adapters for the ten Graph endpoints owned by G07-A
  (G01-001, G01-002, G01-003, G01-004, G01-007, G01-008, G01-009,
  G01-010, G01-018, G01-019).
- Each adapter consumes Graph record dictionaries produced by the
  upstream G05 collector framework, normalises only the fields
  supported by the accepted database design (see
  ``docs/database-schema-design.md`` and
  ``database/migrations/00[34]*``), and emits row-shaped dicts ready
  for a later persistence layer.
- This module does NOT perform database writes, does NOT call live
  Microsoft Graph, and does NOT touch credentials / tokens.

Module contract for each adapter (consistent across all 10 endpoints):
- ``endpoint_id`` -- stable Graph inventory identifier (e.g. ``G01-001``)
- ``target_table`` -- the canonical ``core.<name>`` table the adapter
  writes to (or the first table when more than one is involved).
- ``normalize(record, *, tenant_id, collection_run_id, endpoint_run_id,
  observed_at)`` -- returns either a single row-shaped dict
  (``CURRENT_ONLY`` / ``REFERENCE``) or a tuple ``(current_row,
  snapshot_row)`` for the two ``HISTORICAL_WITH_SNAPSHOT`` adapters
  (G01-004 and G01-019).
- ``history_mode`` -- one of ``CURRENT_ONLY`` or
  ``HISTORICAL_WITH_SNAPSHOT`` or ``REFERENCE``. The runtime can use
  this to decide which physical tables to upsert.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

HISTORY_MODE_CURRENT_ONLY = "CURRENT_ONLY"
HISTORY_MODE_HISTORICAL_WITH_SNAPSHOT = "HISTORICAL_WITH_SNAPSHOT"
HISTORY_MODE_REFERENCE = "REFERENCE"

HISTORY_MODES = (
    HISTORY_MODE_CURRENT_ONLY,
    HISTORY_MODE_HISTORICAL_WITH_SNAPSHOT,
    HISTORY_MODE_REFERENCE,
)


def _is_mapping(value: Any) -> bool:
    """Return True when ``value`` behaves like a JSON object (dict-like)."""
    return isinstance(value, Mapping)


def _require_mapping(record: Any, endpoint_id: str) -> Dict[str, Any]:
    """Validate that ``record`` is a mapping.

    Adapters call this at the top of ``normalize`` so a non-object input
    is rejected with a deterministic, framework-style error. The original
    record is returned untouched by callers that want to handle the
    exception themselves; this helper simply centralises the check.
    """
    if not _is_mapping(record):
        raise TypeError(
            "{}: expected Graph record dict, got {}".format(
                endpoint_id, type(record).__name__
            )
        )
    return dict(record)


def _get_text(record: Mapping[str, Any], *keys: str) -> Optional[str]:
    """Return the first string-coercible value among ``keys`` or None.

    Treats ``None`` and non-string scalars as missing. Booleans and
    numbers are intentionally rejected -- column types in the accepted
    schema are explicit and never coerced from random Graph payloads.
    """
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return value
    return None


def _get_bool(record: Mapping[str, Any], *keys: str) -> Optional[bool]:
    """Return the first boolean value among ``keys`` or None.

    Non-boolean values are treated as missing rather than coerced; this
    matches the schema's strict booleans.
    """
    for key in keys:
        value = record.get(key)
        if isinstance(value, bool):
            return value
    return None


def _get_int(record: Mapping[str, Any], *keys: str) -> Optional[int]:
    """Return the first integer value among ``keys`` or None.

    Accepts Python ``int`` only -- rejects ``bool`` (which subclasses
    ``int`` in Python) and floats, so callers cannot accidentally
    truncate a numeric Graph field.
    """
    for key in keys:
        value = record.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _get_timestamp(record: Mapping[str, Any], *keys: str) -> Optional[str]:
    """Return the first ISO-8601 timestamp string among ``keys`` or None.

    Schema columns are ``TIMESTAMPTZ``; the normalised adapter layer
    preserves Graph's string timestamp verbatim -- the persistence
    layer (a later G-task) is responsible for parsing it into a
    timezone-aware datetime.
    """
    for key in keys:
        value = record.get(key)
        if isinstance(value, str):
            return value
    return None


def _get_json_value(record: Mapping[str, Any], *keys: str) -> Any:
    """Return the first non-null JSON-compatible value among ``keys``.

    Used for the Graph ``servicePlans`` and ``verifiedDomains`` arrays,
    which the accepted schema stores as ``JSONB``. The adapter layer
    does not interpret the contents; it only ensures the value is not
    a string the caller mistook for JSON.
    """
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, (list, dict)):
            return value
    return None


@dataclass(frozen=True)
class AdapterSpec:
    """Static, immutable metadata for one adapter.

    Exposes the four attributes the worker scope contract requires:
    endpoint identifier, target table metadata, normalisation function,
    and persistence/history mode metadata.
    """

    endpoint_id: str
    target_table: str
    snapshot_table: Optional[str]
    history_mode: str
    retention_class: str
    normalize: Any = field(compare=False)
    description: str = ""


def _wrap_current(
    endpoint_id: str,
    target_table: str,
    retention_class: str,
    description: str = "",
):
    """Decorator helper: tag a ``normalize`` function as CURRENT_ONLY.

    The decorator does not change the function's behaviour; it just
    returns the function unchanged so adapters can be declared with a
    single line per endpoint.
    """

    def _decorator(func):
        func.__adapter_spec__ = AdapterSpec(
            endpoint_id=endpoint_id,
            target_table=target_table,
            snapshot_table=None,
            history_mode=HISTORY_MODE_CURRENT_ONLY,
            retention_class=retention_class,
            normalize=func,
            description=description,
        )
        return func

    return _decorator


def _wrap_reference(
    endpoint_id: str,
    target_table: str,
    retention_class: str,
    description: str = "",
):
    """Decorator helper: tag a ``normalize`` function as REFERENCE."""

    def _decorator(func):
        func.__adapter_spec__ = AdapterSpec(
            endpoint_id=endpoint_id,
            target_table=target_table,
            snapshot_table=None,
            history_mode=HISTORY_MODE_REFERENCE,
            retention_class=retention_class,
            normalize=func,
            description=description,
        )
        return func

    return _decorator


def _wrap_snapshot(
    endpoint_id: str,
    target_table: str,
    snapshot_table: str,
    retention_class: str,
    description: str = "",
):
    """Decorator helper: tag a ``normalize`` function as
    HISTORICAL_WITH_SNAPSHOT.

    The decorated function must return ``Tuple[Dict, Dict]`` -- the
    current row first, the snapshot row second. The runtime uses
    ``history_mode`` to decide that both physical tables receive rows
    from a single call.
    """

    def _decorator(func):
        func.__adapter_spec__ = AdapterSpec(
            endpoint_id=endpoint_id,
            target_table=target_table,
            snapshot_table=snapshot_table,
            history_mode=HISTORY_MODE_HISTORICAL_WITH_SNAPSHOT,
            retention_class=retention_class,
            normalize=func,
            description=description,
        )
        return func

    return _decorator


def _lineage_prefix(
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
    source_object_id: str,
) -> Dict[str, Any]:
    """Build the lineage block shared by every emitted row.

    Every normalised row carries:
      - ``tenant_id``
      - ``collection_run_id`` (current rows; snapshot rows only carry
        them on the snapshot table per schema)
      - ``endpoint_run_id``  (snapshot rows only)
      - ``last_observed_at`` (current rows)
      - ``source_object_id``
    The persistence layer is responsible for mapping ``last_observed_at``
    into the right column and dropping fields that do not belong on the
    snapshot table; the adapter always emits them so that callers can
    compose the row uniformly.
    """
    return {
        "tenant_id": tenant_id,
        "collection_run_id": collection_run_id,
        "endpoint_run_id": endpoint_run_id,
        "last_observed_at": observed_at,
        "source_object_id": source_object_id,
    }


def _ensure_lineage(
    endpoint_id: str,
    record: Mapping[str, Any],
    tenant_id: int,
    collection_run_id: int,
    endpoint_run_id: int,
    observed_at: str,
) -> Tuple[Dict[str, Any], str]:
    """Apply the lineage prefix and validate required keys.

    Returns ``(lineage_dict, source_object_id)``. The
    ``source_object_id`` is taken from the Graph record's ``id`` field
    -- the only field the schema mandates as NOT NULL on every
    operational table.
    """
    source_object_id = _get_text(record, "id")
    if source_object_id is None:
        raise ValueError(
            "{}: Graph record is missing required source id field 'id'".format(
                endpoint_id
            )
        )
    lineage = _lineage_prefix(
        tenant_id=tenant_id,
        collection_run_id=collection_run_id,
        endpoint_run_id=endpoint_run_id,
        observed_at=observed_at,
        source_object_id=source_object_id,
    )
    return lineage, source_object_id
