"""G07-A workload package root.

Exposes the ``directory`` subpackage and provides a tiny helper that
returns the adapter-mapping for a given endpoint id. The framework
imports from here when iterating per-endpoint work; the directory
subpackage is the only scope owned by G07-A.

The G07-C integration layer also re-exports the registry, the
persistence-mode vocabulary, and the normalized-result envelope
defined in :mod:`collectors.workloads.models` and
:mod:`collectors.workloads.registry` so callers only need a single
``from collectors.workloads import ...`` line.
"""
from __future__ import annotations

from .directory import (
    ADAPTER_MODULES,
    ENDPOINT_IDS,
    AdapterSpec,
    get_adapter,
    iter_adapters,
)
from .models import (
    PERSISTENCE_CURRENT,
    PERSISTENCE_CURRENT_WITH_HISTORY,
    PERSISTENCE_CURRENT_WITH_SNAPSHOT,
    PERSISTENCE_EVENT,
    PERSISTENCE_MODES,
    PERSISTENCE_REFERENCE,
    NormalizedWorkloadRecord,
    PersistenceMode,
    WorkloadDispatchError,
    WorkloadEntry,
)
from .registry import (
    EXPECTED_ENDPOINT_IDS,
    VALID_RETENTION_CLASSES,
    LineageContext,
    REGISTRY,
    RegistryCoverageError,
    endpoint_ids,
    get_entry,
    iter_entries,
    normalize_record,
    normalize_records,
    validate_registry,
)

__all__ = [
    "ADAPTER_MODULES",
    "ENDPOINT_IDS",
    "AdapterSpec",
    "EXPECTED_ENDPOINT_IDS",
    "VALID_RETENTION_CLASSES",
    "LineageContext",
    "NormalizedWorkloadRecord",
    "PERSISTENCE_CURRENT",
    "PERSISTENCE_CURRENT_WITH_HISTORY",
    "PERSISTENCE_CURRENT_WITH_SNAPSHOT",
    "PERSISTENCE_EVENT",
    "PERSISTENCE_MODES",
    "PERSISTENCE_REFERENCE",
    "PersistenceMode",
    "REGISTRY",
    "RegistryCoverageError",
    "WorkloadDispatchError",
    "WorkloadEntry",
    "endpoint_ids",
    "get_adapter",
    "get_entry",
    "iter_adapters",
    "iter_entries",
    "normalize_record",
    "normalize_records",
    "validate_registry",
]