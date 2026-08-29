"""Tenant / run lineage helpers.

Adapters under :mod:`collectors.workloads.security_service` must
preserve tenant and run lineage that is supplied by the caller
(the Collector / G07-A writer). This module defines the lineage
shape and the helpers used by every adapter.

The lineage is intentionally small: it carries ``tenant_id``
(internal surrogate, matches ``core.tenant.tenant_id``),
``collection_run_id`` and ``endpoint_run_id`` (both
``BIGINT`` references matching the ``control`` schema).

No credential material lives here. Adapters never accept
``Authorization`` headers, bearer tokens, or client secrets;
they accept only safe identifiers that the caller has already
isolated from any secret-bearing context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class Lineage:
    """Tenant + run lineage propagated onto every normalized row.

    All fields are safe Graph / control-schema identifiers; nothing
    in this dataclass is a credential or token.
    """

    tenant_id: Optional[int] = None
    collection_run_id: Optional[int] = None
    endpoint_run_id: Optional[int] = None
    collected_at: Optional[str] = None
    retention_class: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "collection_run_id": self.collection_run_id,
            "endpoint_run_id": self.endpoint_run_id,
            "collected_at": self.collected_at,
            "retention_class": self.retention_class,
        }


DEFAULT_LINEAGE = Lineage()


def normalize_lineage(value: Any) -> Lineage:
    """Coerce an input into a :class:`Lineage`.

    Accepts:

    * a :class:`Lineage` instance (returned verbatim);
    * a mapping whose keys match the dataclass field names;
    * ``None`` (returned as :data:`DEFAULT_LINEAGE`).

    Any field missing from the mapping becomes ``None`` on the
    returned lineage. No validation beyond type checks is performed;
    callers are expected to pass safe identifiers.
    """
    if value is None:
        return DEFAULT_LINEAGE
    if isinstance(value, Lineage):
        return value
    if isinstance(value, Mapping):
        kwargs: Dict[str, Any] = {}
        for field_name in (
            "tenant_id",
            "collection_run_id",
            "endpoint_run_id",
            "collected_at",
            "retention_class",
        ):
            if field_name in value:
                kwargs[field_name] = value[field_name]
        return Lineage(**kwargs)
    raise TypeError("lineage must be a Lineage, mapping, or None")


def lineage_from_mapping(value: Optional[Mapping[str, Any]]) -> Lineage:
    """Sugar over :func:`normalize_lineage` for explicit mappings.

    This helper exists so callers that always pass a mapping can
    use a clear name; it is otherwise identical to
    :func:`normalize_lineage`.
    """
    if value is None:
        return DEFAULT_LINEAGE
    return normalize_lineage(value)


__all__ = [
    "DEFAULT_LINEAGE",
    "Lineage",
    "lineage_from_mapping",
    "normalize_lineage",
]