# Decision Log

## CH3-AUTH-ADR-001: Scenario Agent Canonical Delegated Identity

**Decision date:** 2026-08-24

**Status:** Accepted

**Decision:** The CH3 Scenario Agent canonical identity is a dedicated test
user authenticated through OAuth 2.0 device code with delegated Microsoft Graph
permissions. The Collector remains a separate app-only service principal using
OAuth 2.0 client credentials and Graph application permissions.

**Impact:** App-only service-principal execution is not an approved canonical
Scenario runtime. Existing app-only Scenario material is retained only as
candidate implementation evidence. Future Scenario execution, validation, audit
evidence, and permission design must use the delegated identity model defined in
`docs/design/ADR-CH3-AUTH-001.md`.

## ADR: Accept and Freeze the G10 Foundation

**Decision:** Accept the G10 Foundation and freeze its endpoint integration architecture.

**Completed milestones:** G10-001A user runtime wiring; G10-001B1 tenant binding hardening; G10-001B2 persistence dispatcher; G10-001B2-FIX1 event source enforcement; G10-001B2-FIX2 tenant boundary validation; and G10-001B2-FIX3 persistence security boundary.

**Accepted capabilities:** Graph runtime flow, trusted tenant handling, generic persistence dispatch, security validation boundary, event validation, and documentation governance.

**Architecture constraint:** Future endpoints must follow Graph Collector → Adapter → Registry → Persistence Dispatcher → Security Boundary → Writer → Database.

**Remaining technical debt:** Registry and SQL mapping duplication, no live PostgreSQL integration suite, rejection metrics/tracing, and retry recovery hardening.

**Impact:** New endpoint work must reuse the frozen flow and must not bypass the registry, dispatcher, security boundary, or writer layers.


## ADR: Temporarily Retain Current Persistence SQL Mapping

**Decision:** Keep current persistence SQL mapping temporarily.

**Context:** The G10-001B2 Terra review identified duplicated registry metadata and persistence SQL mapping.

**Reason:** The current implementation is stable and tested. An immediate refactor creates unnecessary regression risk.

**Alternative considered:** Immediate consolidation of registry and SQL mapping.

**Future direction:** Move toward a registry-authoritative persistence contract.

**Impact:** Track the duplicated metadata and mapping as technical debt until the future contract improvement is implemented and validated.
