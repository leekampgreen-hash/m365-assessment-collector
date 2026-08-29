"""Workload adapters for Microsoft Entra ID security, governance and
Microsoft 365 service-health / change-communication endpoints.

Scope (G07-B):

  G01-005 Directory Audit Logs             -> core.audit_event (DIRECTORY_AUDIT)
  G01-006 Sign-in Logs                     -> core.audit_event (SIGN_IN)
  G01-011 Conditional Access Policies      -> core.conditional_access_policy (+ snapshot)
  G01-012 Conditional Access Named Locations -> core.named_location
  G01-013 Risky Users                      -> core.risky_user (+ snapshot)
  G01-014 Risk Detections                  -> core.risk_detection
  G01-015 Service Health Overview          -> core.service_health_overview (+ snapshot)
  G01-016 Service Health Issues            -> core.service_health_issue (+ history)
  G01-017 Service Update Messages          -> core.service_update_message (+ history)

Security boundary
-----------------
This package contains no Graph transport, no token handling, no
credential material, and no database writers. Adapters are pure
Python functions that:

  * consume Graph record dicts (already produced by the G05 framework);
  * project them onto the curated fields defined by
    ``docs/database-schema-design.md``;
  * preserve ``source_object_id`` (Graph ``id``) and a supplied
    tenant/run lineage envelope;
  * build deterministic ``version_identity`` values for G01-016 / G01-017
    from source ``last_modified_date_time`` (primary) or curated
    lifecycle fields (fallback).

The adapters do NOT call Microsoft Graph. The adapters do NOT write to
any database. Persistence is the responsibility of a later G07 writer.
"""
from .lineage import (
    DEFAULT_LINEAGE,
    Lineage,
    lineage_from_mapping,
    normalize_lineage,
)
from .versioning import (
    compute_version_identity,
    fallback_version_identity,
    primary_version_identity,
)
from .adapters import (
    EVENT_SOURCE_DIRECTORY_AUDIT,
    EVENT_SOURCE_SIGN_IN,
    ENDPOINT_TABLE_MAP,
    adapt_directory_audit_logs,
    adapt_named_locations,
    adapt_risk_detections,
    adapt_risky_users,
    adapt_service_health_issues,
    adapt_service_health_overview,
    adapt_service_update_messages,
    adapt_sign_in_logs,
    conditional_access_policies,
    named_locations,
    risky_users,
    service_health_issues,
    service_health_overview,
    service_update_messages,
)

__all__ = [
    "DEFAULT_LINEAGE",
    "ENDPOINT_TABLE_MAP",
    "EVENT_SOURCE_DIRECTORY_AUDIT",
    "EVENT_SOURCE_SIGN_IN",
    "Lineage",
    "adapt_directory_audit_logs",
    "adapt_named_locations",
    "adapt_risk_detections",
    "adapt_risky_users",
    "adapt_service_health_issues",
    "adapt_service_health_overview",
    "adapt_service_update_messages",
    "adapt_sign_in_logs",
    "compute_version_identity",
    "conditional_access_policies",
    "fallback_version_identity",
    "lineage_from_mapping",
    "named_locations",
    "primary_version_identity",
    "normalize_lineage",
    "risky_users",
    "service_health_issues",
    "service_health_overview",
    "service_update_messages",
]