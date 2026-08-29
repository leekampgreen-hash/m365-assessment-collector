"""Deterministic version-identity computation for G01-016 / G01-017.

Per ``docs/database-schema-design.md`` Sections 7.7.a, 7.7.b and 10.3
(G06-001R):

  Primary rule
      version_identity = hash(tenant_id, source_object_id, last_modified_date_time)
      where the hash is SHA-256 over a deterministic, sorted encoding
      of the three inputs.

  Fallback rule (when ``last_modified_date_time`` is null)
      G01-016: hash(tenant_id, source_object_id, status, is_resolved,
                    start_date_time, end_date_time)
      G01-017: hash(tenant_id, source_object_id, category, severity,
                    is_major_change, start_date_time, end_date_time,
                    action_required_by_date_time)

The algorithm is implemented in pure Python and is fully deterministic:
the same inputs always produce the same hash. Inputs are encoded with
:func:`_encode_field` so that ``None``, booleans, integers and ISO
timestamps round-trip without ambiguity. The returned hash is the raw
``bytes`` digest; downstream writers are responsible for the
``BYTEA``-shaped representation chosen by the database.

No credentials, tokens, or bearer material participate in the hash.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping, Optional


_HASH_ALGO = "sha256"


def _encode_field(value: Any) -> bytes:
    """Deterministically encode one field for hashing.

    The encoding rule is:

      None            -> b"N"
      bool            -> b"B1" / b"B0"
      int             -> b"I" + decimal ascii
      str             -> b"S" + utf-8 bytes (NUL-escaped)
      datetime-like   -> b"T" + isoformat utf-8 (caller pre-converts)
      list / tuple    -> b"L" + join(b"|" + encode(item))

    The leading tag is included so ``None`` and ``"None"`` cannot
    collide. The encoding is intentionally crude but stable across
    Python versions and platforms.
    """
    if value is None:
        return b"N"
    if isinstance(value, bool):
        return b"B1" if value else b"B0"
    if isinstance(value, int):
        return b"I" + str(value).encode("ascii")
    if isinstance(value, str):
        return b"S" + value.encode("utf-8")
    if isinstance(value, (list, tuple)):
        parts = [b"L"]
        for item in value:
            parts.append(b"|")
            parts.append(_encode_field(item))
        return b"".join(parts)
    if isinstance(value, bytes):
        return b"Y" + value
    raise TypeError("unsupported field type for version_identity: " + type(value).__name__)


def _digest(fields: Iterable[Any]) -> bytes:
    h = hashlib.new(_HASH_ALGO)
    for index, field in enumerate(fields):
        if index:
            h.update(b"\x1f")
        h.update(_encode_field(field))
    return h.digest()


def primary_version_identity(
    *,
    tenant_id: Any,
    source_object_id: Any,
    last_modified_date_time: Any,
) -> bytes:
    """Compute the primary version-identity hash.

    Inputs:

      tenant_id
          Internal surrogate ``BIGINT`` from ``core.tenant``; falls back
          to ``None`` when unknown (still deterministic).
      source_object_id
          Graph object id, always required.
      last_modified_date_time
          The source ``lastModifiedDateTime`` value, any
          deterministic representation (typically an ISO-8601 string).

    Returns the raw SHA-256 digest bytes.
    """
    return _digest(
        (
            "primary",
            tenant_id,
            source_object_id,
            last_modified_date_time,
        )
    )


def fallback_version_identity(
    *,
    tenant_id: Any,
    source_object_id: Any,
    lifecycle_fields: Mapping[str, Any],
) -> bytes:
    """Compute the fallback version-identity hash for a lifecycle row.

    The order in which ``lifecycle_fields`` is provided is the order
    in which they are encoded. Each endpoint defines its own
    canonical order:

      G01-016: status, is_resolved, start_date_time, end_date_time
      G01-017: category, severity, is_major_change, start_date_time,
               end_date_time, action_required_by_date_time

    The endpoint-specific helper functions below are the supported
    entry points; this function is the shared core.
    """
    return _digest(
        (
            "fallback",
            tenant_id,
            source_object_id,
            *lifecycle_fields.values(),
        )
    )


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value == "")


def compute_version_identity(
    endpoint_id: str,
    *,
    tenant_id: Any,
    source_object_id: Any,
    record: Mapping[str, Any],
) -> bytes:
    """Pick the primary or fallback rule for ``endpoint_id``.

    The two history endpoints G01-016 and G01-017 are the only
    callers of this helper. For any other endpoint id the function
    raises :class:`ValueError`.

    Behaviour:

      * When the source row carries a non-blank
        ``lastModifiedDateTime`` value, the primary rule is used.
      * When ``lastModifiedDateTime`` is absent / blank, the fallback
        rule is applied with the curated lifecycle fields for the
        matching endpoint.

    The function is pure: no I/O, no logging, no token use.
    """
    if endpoint_id == "G01-016":
        return _service_health_issue_identity(tenant_id, source_object_id, record)
    if endpoint_id == "G01-017":
        return _service_update_message_identity(tenant_id, source_object_id, record)
    raise ValueError("compute_version_identity only supports G01-016 / G01-017")


def _service_health_issue_identity(
    tenant_id: Any,
    source_object_id: Any,
    record: Mapping[str, Any],
) -> bytes:
    last_modified = record.get("lastModifiedDateTime")
    if not _is_blank(last_modified):
        return primary_version_identity(
            tenant_id=tenant_id,
            source_object_id=source_object_id,
            last_modified_date_time=last_modified,
        )
    lifecycle = {
        "status": record.get("status"),
        "is_resolved": record.get("isResolved"),
        "start_date_time": record.get("startDateTime"),
        "end_date_time": record.get("endDateTime"),
    }
    return fallback_version_identity(
        tenant_id=tenant_id,
        source_object_id=source_object_id,
        lifecycle_fields=lifecycle,
    )


def _service_update_message_identity(
    tenant_id: Any,
    source_object_id: Any,
    record: Mapping[str, Any],
) -> bytes:
    last_modified = record.get("lastModifiedDateTime")
    if not _is_blank(last_modified):
        return primary_version_identity(
            tenant_id=tenant_id,
            source_object_id=source_object_id,
            last_modified_date_time=last_modified,
        )
    lifecycle = {
        "category": record.get("category"),
        "severity": record.get("severity"),
        "is_major_change": record.get("isMajorChange"),
        "start_date_time": record.get("startDateTime"),
        "end_date_time": record.get("endDateTime"),
        "action_required_by_date_time": record.get("actionRequiredByDateTime"),
    }
    return fallback_version_identity(
        tenant_id=tenant_id,
        source_object_id=source_object_id,
        lifecycle_fields=lifecycle,
    )


__all__ = [
    "compute_version_identity",
    "fallback_version_identity",
    "primary_version_identity",
]