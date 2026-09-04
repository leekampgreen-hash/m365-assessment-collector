"""Typed models for the collector framework.

These dataclasses describe a single Graph endpoint to be collected and the
structured result of one collection run. They contain NO credentials.

Notes for future workloads (G07):
- ``EndpointSpec`` is data-driven; nothing in this module hard-codes the
  current 19 discovery endpoints.
- ``CollectionResult`` is what callers persist / aggregate.  It never
  carries access tokens, client secrets, or raw ``Authorization`` headers.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


COLLECTION_PATTERN_PAGED = "paged"
COLLECTION_PATTERN_SINGLE = "single"
COLLECTION_PATTERN_UNKNOWN = "unknown"
COLLECTION_PATTERNS = (
    COLLECTION_PATTERN_PAGED,
    COLLECTION_PATTERN_SINGLE,
    COLLECTION_PATTERN_UNKNOWN,
)

ENDPOINT_TYPE_WORKLOAD = "WORKLOAD"
ENDPOINT_TYPE_SECURITY_ONLY = "SECURITY_ONLY"
ENDPOINT_TYPES = (ENDPOINT_TYPE_WORKLOAD, ENDPOINT_TYPE_SECURITY_ONLY)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EndpointSpec:
    """Specification for one collector endpoint.

    The fields below intentionally mirror the keys used in
    ``config/api_inventory.json`` so the same file can drive G01 and G07
    collectors, but the framework does not depend on the file format
    itself -- the inventory module is a thin adapter.
    """

    endpoint_id: str
    name: str
    path: str
    api_version: str = "v1.0"
    workload: str = ""
    method: str = "GET"
    collection_pattern: str = COLLECTION_PATTERN_UNKNOWN
    pagination: bool = True
    select: Optional[List[str]] = None
    top: Optional[int] = None
    permission: str = ""
    documented_permissions: List[str] = field(default_factory=list)
    data_domain: str = ""
    enabled: bool = True
    auth_type: str = "application"
    transport_type: str = "NORMAL_GRAPH_JSON"
    report_key: Optional[str] = None
    period: Optional[str] = None
    required_capabilities: List[str] = field(default_factory=list)
    endpoint_type: str = ENDPOINT_TYPE_WORKLOAD
    collector_type: str = "declarative"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionResult:
    """Structured result of a single endpoint collection run."""

    endpoint_id: str = ""
    status: str = "UNKNOWN"
    pages: int = 0
    rows: int = 0
    source_rows: int = 0
    persisted_rows: int = 0
    identity_unavailable: bool = False
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    http_status: Optional[int] = None
    error_classification: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    retry_after: Optional[str] = None
    graph_error_code: Optional[str] = None
    pagination_detected: bool = False
    feature_status: Optional[str] = None
    capability_decision: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
