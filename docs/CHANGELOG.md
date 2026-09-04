# Changelog

## Technical Debt Elimination & Foundation Security Certification (TD-001 through TD-008)

- **TD-001 & TD-002: Registry Retention Metadata Drift & Closed Vocabulary Enforcement**: Reconciled all endpoint retention classes in `collectors/workloads/registry.py` (aligning G01-005, G01-006, G01-013, and G01-014 to authoritative schema retention class `LONG`). Enforced closed retention vocabulary `('SHORT', 'STANDARD', 'LONG', 'REFERENCE')` and fail-closed runtime validation via `validate_registry()`. Added comprehensive unit tests in `tests/workloads/test_registry.py`.
- **TD-005: Bounded Rejection Metrics & Secret-Scrubbed Tracing**: Created `collectors/core/rejections.py` with typed rejection models (`RejectionCategory`, `RejectionReason`, `RejectionSeverity`), automated sensitive-token redactor (`[REDACTED]`), and Prometheus-style `RejectionTracker` metrics (`records_rejected_total`). Integrated structured rejection tracking into `CollectionResult` and data normalization pipelines while strictly preserving fail-closed validation. Covered by 18 unit tests in `tests/core/test_rejections.py`.
- **TD-006: Retry Recovery Hardening & Operational Observability**: Formalized failure permanence classification in `collectors/core/errors.py` distinguishing `RETRYABLE` from `PERMANENT`. Hardened `RetryPolicy` in `collectors/core/retry.py` with bounded backoff, jitter, and strict ceiling (`max_retry_after_seconds = 60s`). Created `RecoveryEvidence` tracking attempts, recovery status, and actionable operator recommendations (`RETRY_RUN`, `CHECK_GRAPH_PERMISSION`, etc.). Added agentic analytics service `collectors/core/operations_analytics.py`. Covered by 19 unit tests in `tests/core/test_retry_hardening.py`.
- **TD-003: Empirical Live Microsoft Graph Integration Validation**: Built and executed `scripts/validate_live_graph.py` inside the container against live tenant `2ac16e52-2259-4c0f-b02b-c6a04e5246d6` across 4 representative endpoints (Users, Subscribed SKUs, Sign-in Logs, Conditional Access Policies). Verified 100% PASS on projection, pagination, secret scrubbing, and token lifecycle. Documented in `docs/evidence/TD-003-LIVE-GRAPH-VALIDATION-REPORT.md`.
- **TD-004: Empirical Live PostgreSQL Runtime Validation**: Built and executed `scripts/validate_live_postgres.py` against live PostgreSQL 16 under least-privilege `graph_agent_runtime`. Validated 7/7 test suites covering schema existence, table schemas, check constraints, transaction atomicity, upsert conflict handling, and event replay idempotency. Documented in `docs/evidence/TD-004-LIVE-POSTGRESQL-VALIDATION-REPORT.md`.
- **TD-007: Controlled Validation Environment Certification**: Established and certified three-tier boundary separation (Local Development, Controlled Validation Environment, Production) with isolated Docker Compose stacks, runtime secret injection, and strict credential exclusion. Documented in `docs/evidence/TD-007-CONTROLLED-VALIDATION-REPORT.md`.
- **TD-008: Foundation Security Certification**: Fully resolved all limitations from CH-2.5 using empirical live evidence from TD-003, TD-004, and TD-007. Elevated security posture from `PASS WITH LIMITATIONS` to **FULL PASS - UNRESTRICTED PRODUCTION READINESS**. Documented in `docs/evidence/TD-008-FOUNDATION-SECURITY-CERTIFICATION.md`.
- **Complete Test Suite Verification**: All 1,400 pytest suite items pass with 100% success rate.

## Collector Standardization & Operations Modernization (Phases 1-5)

- **Phase 1: Scheduler & CLI Flag Standardization**: Resolved argument mismatch bugs between `collectors/scheduler.py` and `collectors/run_collector.py` (`--defender-devices` vs `--defender-summary`, `--entra-stale-devices`, `intune_compliance_policies`, `intune_mobile_apps`, `onedrive_audit`) with backward-compatibility aliases.
- **Phase 2: SSOT API Inventory Registration**: Fully registered all 12 specialized script collectors into `config/api_inventory.json` (`OD-AUDIT`, `SP-A01`, `SP-SITES`, `INTUNE-001` through `004`, `ENTRA-GUESTS`, `ENTRA-AUTH`, `ENTRA-STALE`, `ENTRA-PIM`, `DEF-DEV`) with explicit schema fields (`collector_type: "specialized"`, `module`, `function`, `cli_flag`, `table`, `permission`, and `documented_permissions`), bringing total registered endpoints to 45 SSOT specs. Added deduplication guards to prevent double-counting.
- **Phase 3: Unified Collector Runner & Checkpoint Synchronization**: Introduced unified `--collector <ID_OR_NAME>` CLI runner in `collectors/run_collector.py` supporting standard codes (`G01-001`, `OD-AUDIT`), specialized keys, short slugs, security rules, and batch-2 sources. Reconciled database checkpoint timestamps in `control.collector_checkpoint` and modernized `GET /api/admin/collector/status` with dual-key resolution and `slug` delivery.
- **Phase 4: Operations Admin UI & Scheduler Modernization**: Enhanced `operations-ui/public/admin.html` with real-time collector search bar, workload domain filter dropdown (Entra, Intune, Defender, Purview, SharePoint, OneDrive, Usage), quick-action Copy CLI Command button, and manual refresh. Refactored scheduler dispatch loop to route all jobs via unified runner. Published comprehensive reference catalog in `docs/COLLECTORS_REFERENCE.md`.
- **Phase 5: On-Demand Execution, Metric Cards & Inspector Modal**: Added authenticated `POST /api/admin/collector/trigger` endpoint with subprocess execution and safety timeout. Added 4 top-level collector health summary metric cards (Total Registered, Healthy <24h, Stale >24h, Pending/Inactive), inline row-level and modal "Run Now" buttons with live spinner, and an interactive Collector Inspector modal detailing workload, permissions, GMT+7 checkpoints, and copyable commands.

## Architecture & Test Suite Resilience (TD-009 & TD-010)

- **TD-009: Workload Registry vs Specialized Collector Invariant Alignment**: Formalized `collector_type: str = "declarative" | "specialized"` in `EndpointSpec` typed model and inventory loader. Aligned invariant assertions in `tests/workloads/test_registry.py` and `tests/architecture/test_security_wiring.py` so specialized script collectors are cleanly distinguished from declarative adapters.
- **TD-010: Test Environment Dependencies & Namespace Shadowing**: Removed empty package file `tests/agent/__init__.py` that shadowed the root `agent` package during test discovery. Installed missing test runtime packages (`pytest`, `openai`, `psycopg3`, `pyotp`). Resolved DB connection mock in `test_operations_api.py` to adhere to standard cursor context manager protocols. All 1,360 test suite items now pass with 0 errors.
- **Backlog Governance**: Sealed `LIC-OPTIMIZER-P01` in `docs/progress/backlog.md` and updated `docs/TECHNICAL_DEBT.md` with resolved status for TD-009 and TD-010.

## Operations UI: License FinOps Command Center & Identities Reclamation Redesign

- **Command Center Layout**: Replaced fragmented and redundant cards with a unified 3-column Hero Command Center (`#license-command-center`) featuring Potential Annual Recovery ($/yr and $/mo run-rate), Cost Leakage Sources breakdown (Inactive Accounts, Zero Usage, Over-Licensed) with mini progress bars, and an Executive AI Advisory card with direct assistant consultation action.
- **Subscribed SKUs Real Efficiency**: Enhanced the SKU inventory table (`#licenses`) with friendly product names, monthly per-seat pricing, active vs idle seat allocation, visual Real Efficiency progress bars (good/warning/critical or Free Tier unmetered badge), and interactive click-to-filter drill-down functionality.
- **Identities Reclamation Pipeline (1 User = 1 Row)**: Redesigned the reclamation table (`#license-optimizer-table`) to eliminate duplicate rows by grouping multiple flags per identity into clean multi-badge tags (`Inactive`, `Zero Usage`, `Over-Licensed`, `Duplicate SKU`, `Guest Account`, `Blocked Account`). Added filter chips (`All Flagged`, `Inactive Accounts`, `Zero Usage`, `Over-Licensed`), instant client-side search, and per-user "Audit AI" actions.
- **Real Efficiency & Tag Contrast Fix**: Resolved text legibility issue in the Subscribed SKUs table where `.eff-critical` applied a solid opaque red background to text labels. Scoped fill backgrounds to `.efficiency-bar-fill` and styled `.efficiency-text` as subtle badges with high-contrast text (`#fca5a5` in dark mode, `#b91c1c` in light mode). Added `.text-success` utility and light-theme contrast rules for tags.
- **Docker Compose Port Binding**: Updated `operations-ui` host port binding in `docker-compose.yml` to `18080:80` for consistent accessibility across local interfaces and containers.

## API & Operations Optimization: Minimum-Impact Codebase Improvements

- **Cleaned Up Unreachable Security Handlers**: Removed dead handler `if` blocks in `api/operations.py` for `/api/security/admin-roles`, `/api/security/mfa-coverage`, `/api/security/ca-policies`, `/api/security/signin-summary`, and `/api/security/mfa-registration`, which were previously intercepted by the telemetry caching handler. Kept reachable handlers such as `/api/security/signin-risk`.
- **Exchange Capacity Performance Optimization**: Cached `self.exchange_capacity()` to a local variable `cap` inside `OperationsAnalyticsQueryService.exchange_adoption()` in `analytics/operations.py`, reducing redundant 4x computation calls.
- **Defensive Security Cache Route Guard**: Added a defensive `path not in methods` guard in `_load_cached_security()` in `api/operations.py` returning `{"status": "NOT_FOUND"}` instead of raising uncaught `KeyError`.
- **Honest KPI & Dynamic MFA Deltas**: Updated `hydrateKpiDeltas()` in `operations-ui/public/app.js` and placeholder badges in `operations-ui/public/index.html` to compute actual MFA coverage dynamically and display honest `Live` indicators instead of deceptive hardcoded percentages (`+2.1%`, `+1.5%`, `0% vs run`).
- **SKU Pricing Consolidation**: Removed the hardcoded `LICENSE_PRICES` dictionary from `api/operations.py`. Consolidated all license parking calculations to use centralized `config/sku_pricing.json` via `load_pricing()`, `get_sku_price()`, and `calculate_user_monthly_cost()`. Added `DESKLESSPACK` SKU to `config/sku_pricing.json` to ensure 100% price parity.

## Operations UI: Session Telemetry Caching & License Metrics Single Source of Truth

- Implemented session-scoped client caching in `operations-ui/public/app.js` using `sessionStorage` keyed by `session_id`, ensuring instant load (< 5ms) on page refresh and eliminating numeric flickering.
- Resolved conflicting hydration mutations: established `hydrateFinancialSummary()` as the single authority for License FinOps metrics and the sidebar savings badge (`#sidebar-savings-badge`, `#kpi-parking-savings`, `#fin-savings-sub`, `#fin-inactive-seats`).
- Removed duplicate financial DOM mutations from `hydrateKpiCards()` and aligned the static HTML badge placeholder in `operations-ui/public/index.html` to prevent display of conflicting fallback values.
- Integrated automatic cache invalidation on logout and manual force refresh via the "Refresh Data" control.

## CH8 Security Findings Foundation

- Added the deterministic Security Findings foundation (no Graph calls, no AI, no database writes, no remediation).
- Introduced explicit domain contracts in `security/models.py`: `SecurityRule`, `SecurityBaseline`, `SecurityObservation`, `SecurityFinding`, `EvidenceReference`, `Recommendation`, and the `SecurityFindingService` contract, with `PASS`/`OPEN`/`NOT_EVALUATED` status and `INFO`/`LOW`/`MEDIUM`/`HIGH`/`CRITICAL` severity.
- Enforced fail-safe semantics: `NO_EVIDENCE != SECURITY_GAP`; missing/ambiguous/unsupported/malformed evidence is `NOT_EVALUATED` and never `OPEN`.
- Defined the product baseline `m365-security-recommended-v1` (version `1.0.0`) in `security/baseline.py` with `formal_compliance_claim = False` (no CIS/NIST/Secure Score/regulatory claim).
- Implemented the first rule `M365-SP-EXT-001` (SharePoint / OneDrive External Sharing) in `security/rules/sp_ext_001.py` with explicit ordered canonical levels (`none`, `existing_guests`, `new_and_existing_guests`, `anyone`), deterministic PASS/OPEN/NOT_EVALUATED comparison, and deterministic severity/recommendation that advises but never executes remediation.
- Added `DeterministicSecurityFindingService` in `security/service.py` resolving baseline/rule, validating dependency, and performing the deterministic comparison; identical input yields a semantically identical, stable-id finding with no AI or network dependency.
- Added `tests/security/test_security_findings.py` covering compliant/stricter->PASS, violated->OPEN, unavailable/malformed/unsupported->NOT_EVALUATED, deterministic severity/recommendation, repeated-evaluation determinism, evidence preservation, sensitive-data exclusion, disabled-rule, and no-network/no-AI dependencies (26 tests).

## G01-012 Named Locations CURRENT Endpoint

- Reconciled the registry retention class from `STANDARD` to authoritative `REFERENCE` for the paginated `/v1.0/identity/conditionalAccess/namedLocations` endpoint.
- Reused the existing security-service adapter and retained only named-location identity and lifecycle metadata; IP ranges, countries and regions, unknown fields, credentials, tokens, authorization material, and raw Graph payload are excluded.
- Verified registry-controlled `CURRENT` dispatch to `core.named_location`, parameter-bound SQL, `(tenant_id, source_object_id)` conflict handling, `DO UPDATE` replay, trusted tenant validation, paginator fail-closed behavior, and transactional rollback without changing the writer, dispatcher, security boundary, or SQL mapping.
- Added focused normalization, field-boundary, malformed input/page, pagination, empty-result, registry, persistence, replay, tenant, and rollback coverage.

## G01-011 Conditional Access Policies CURRENT_WITH_SNAPSHOT Endpoint

- Implemented and verified the inventory-driven paginated `/v1.0/identity/conditionalAccess/policies` endpoint with application auth, `Policy.Read.All`, `$top=100`, and the approved metadata-only selection fields.
- Reused the security-service Conditional Access adapter and retained only policy identity, display name, state, created timestamp, and modified timestamp; policy bodies, credentials, tokens, authorization material, and unknown fields are excluded.
- Verified registry-controlled `CURRENT_WITH_SNAPSHOT` dispatch to `core.conditional_access_policy` and `core.conditional_access_policy_snapshot`, with retention reconciled from `STANDARD` to authoritative `REFERENCE`.
- Reused parameter-bound current upsert, run-scoped snapshot `DO NOTHING` replay, trusted tenant validation, paginator fail-closed behavior, and transactional rollback without adding a writer, migration, dispatcher, or architecture change.
- Added focused normalization, field-boundary, malformed input, pagination, empty-result, no-partial-write, registry, SQL, replay, tenant, and rollback coverage.

## G01-010 Administrative Units CURRENT Endpoint

- Implemented and verified the inventory-driven paginated `/v1.0/directory/administrativeUnits` endpoint with application auth, `AdministrativeUnit.Read.All`, and the approved Administrative Unit selection fields.
- Reused the directory Administrative Units adapter and retained only approved identifiers and metadata; unknown, credential, token, and authorization material are excluded.
- Verified registry-controlled `CURRENT` dispatch to `core.administrative_unit`, parameter-bound SQL, `(tenant_id, source_object_id)` conflict handling, `DO UPDATE` replay, tenant validation, and transactional rollback without changing the foundation pipeline.
- Added focused normalization, malformed payload, pagination, empty-result, malformed-nextLink, no-partial-write, and field-exclusion coverage.

## G01-009 Devices CURRENT Endpoint

- Implemented and verified the inventory-driven paginated `/v1.0/devices` endpoint with application auth, `Device.Read.All`, and the approved device selection fields.
- Reused the directory Devices adapter and retained only approved device identifiers and metadata; unknown, credential, token, and authorization material are excluded.
- Verified registry-controlled `CURRENT` dispatch to `core.device`, parameter-bound SQL, `(tenant_id, source_object_id)` conflict handling, `DO UPDATE` replay, tenant validation, and transactional rollback without changing the foundation pipeline.
- Added focused normalization, malformed payload, pagination, empty-result, no-partial-write, registry, persistence, replay, tenant, rollback, and field-exclusion coverage.

## G01-008 Service Principals CURRENT Endpoint

- Implemented and verified the inventory-driven paginated `/v1.0/servicePrincipals` endpoint with application auth, `Application.Read.All`, and the approved Service Principal selection fields.
- Reused the directory Service Principals adapter and retained only approved identifiers and metadata; credential, key, assignment, permission, token, secret, authorization, and unknown properties are excluded.
- Verified registry-controlled `CURRENT` dispatch to `core.service_principal`, parameter-bound SQL, `(tenant_id, source_object_id)` conflict handling, `DO UPDATE` replay, tenant validation, and transactional rollback without changing the foundation pipeline.
- Added focused normalization, malformed payload, pagination, empty-result, no-partial-write, registry, persistence, replay, tenant, rollback, and credential-exclusion coverage.

## G01-007 Applications CURRENT Endpoint

- Implemented and verified the inventory-driven paginated `/v1.0/applications` endpoint with application auth, `Application.Read.All`, and the approved application selection fields.
- Reused the directory Applications adapter and retained only approved identifiers and metadata; credential, key, authorization, token, and unknown properties are excluded.
- Verified registry-controlled `CURRENT` dispatch to `core.application`, parameter-bound SQL, `(tenant_id, source_object_id)` conflict handling, `DO UPDATE` replay, tenant validation, and transactional rollback without changing the foundation pipeline.
- Added focused normalization, malformed payload, pagination, empty-result, no-partial-write, registry, persistence, replay, tenant, and rollback coverage.

## G01-006 Sign-In Logs EVENT Endpoint

- Implemented and verified the inventory-driven paginated `/v1.0/auditLogs/signIns` endpoint with application auth, `AuditLog.Read.All`, and the approved sign-in selection fields.
- Reused the security-service adapter and normalized `createdDateTime`, user/app actors, client activity, nested status, and interactivity into `core.audit_event`; `SIGN_IN` is forced and sensitive/unknown fields are excluded.
- Corrected scalar numeric `status.errorCode` normalization while preserving fail-closed handling for malformed nested status values.
- Reused registry-controlled EVENT dispatch, the shared event writer, tenant boundary, `(tenant_id, event_source, source_object_id)` conflict key, `DO NOTHING` replay, and transactional rollback.
- Added focused pagination, empty-result, malformed-page, field-boundary, source-spoofing, replay, tenant, rollback, and credential-exclusion coverage.

## G01-005 Directory Audit EVENT Endpoint

- Verified the inventory-driven paginated `/v1.0/auditLogs/directoryAudits` endpoint with `AuditLog.Read.All` and approved Graph selection fields.
- Reused the existing security-service adapter, forcing `DIRECTORY_AUDIT`, rejecting missing/malformed records, and excluding unknown and credential fields.
- Hardened common pagination validation for malformed Graph collection envelopes while preserving `@odata.nextLink` traversal and fail-closed collection behavior.
- Verified registry-controlled `EVENT` dispatch to `core.audit_event`, the `(tenant_id, event_source, source_object_id)` conflict key, `DO NOTHING` replay, tenant/event-source protections, and transactional rollback without adding a writer, migration, or dispatcher redesign.
- Added focused endpoint handoff, field-boundary, malformed-response, replay, tenant-boundary, and rollback coverage.

## G01-004 Subscribed SKUs CURRENT_WITH_SNAPSHOT Endpoint

- Verified the inventory-driven paginated Subscribed SKUs collection at `/v1.0/subscribedSkus` with `LicenseAssignment.Read.All`.
- Verified approved-field normalization, scalar `prepaidUnits` transformation, malformed/missing-ID rejection, unknown-field exclusion, and credential exclusion.
- Verified registry `CURRENT_WITH_SNAPSHOT` mapping to `core.subscribed_sku` and `core.subscribed_sku_snapshot`.
- Reused the existing dispatcher, security boundary, snapshot writer, conflict keys, transaction rollback, and replay behavior without adding a writer, migration, or dispatcher change.
- Added focused collector handoff and workload regression coverage.

## G01-003 Organization CURRENT Endpoint

- Verified the inventory-driven single-object Organization collection at `/v1.0/organization` using the existing Graph runtime and authentication flow.
- Added focused normalization and collector-to-workload handoff coverage for approved fields, malformed responses, missing identifiers, optional fields, tenant lineage, and credential exclusion.
- Verified `CURRENT` dispatch to `core.organization` and reuse of the existing tenant-keyed current writer with deterministic replay updates; no SQL architecture, migration, or new writer was added.

## G01-002-FIX2 Runtime Persistence Wiring

- Wired production CLI execution to open the configured PostgreSQL runtime connection and inject the canonical `CollectionWriter` with `dispatch_persistence` into `CollectorRuntime`.
- Preserved the dispatcher, security boundary, existing SQL writers, and transaction handling.
- Added CLI wiring, dispatcher/writer handoff, missing-dependency failure, dry-run, and trusted-tenant regression coverage.

## G01-002-FIX1 Runtime Tenant Wiring

- Wired the production collector CLI to inject a trusted tenant resolver into `RuntimeOptions`.
- Require the positive internal tenant surrogate from `GRAPH_TENANT_DB_ID`; missing and malformed values fail closed.
- Preserved dry-run behavior and the existing runtime lineage and persistence tenant-boundary checks.

## G01-002 Groups CURRENT Endpoint

- Implemented and verified the inventory-driven paginated Groups collection using the existing Graph runtime and authentication flow.
- Verified Groups normalization, lineage propagation, credential exclusion, registry `CURRENT` dispatch, and reuse of the existing `core."group"` current writer.

## G10-001B2-FIX3 Persistence Boundary Hardening

- Validated populated tenant IDs in every public mode-specific persistence handler before SQL execution.
- Made `CollectionWriter` validate endpoint and registry mode alignment before `BEGIN`, including injected writer flows.
- Made dispatcher batch validation complete before writer invocation, preventing partial writes when a later record is invalid.
- Preserved closed SQL maps, parameter binding, idempotency, transaction handling, and event-source validation.

## G10-001B2-FIX2 Tenant Boundary Hardening

- Added pre-persistence validation that trusted runtime and normalized row tenant IDs exist, are positive integers, and match.
- Rejected tenant-boundary failures before transaction start, writer invocation, or SQL execution, preserving existing handlers, parameter binding, idempotency, transactions, dispatch, and event-source validation.
- Added focused persistence tests for acceptance, missing and mismatched tenants, and no-writer/no-SQL behavior.


## G10-001B2 Persistence Dispatcher / G10-001B2-FIX1 Event Control

- Documented completion of the canonical persistence dispatcher for all 19 G01 endpoints.
- Recorded mode-specific current, reference, event, snapshot, and history routing with deterministic conflict handling.
- Recorded event-control safeguards for endpoint allowlisting, registered `event_source` validation, required-column checks, and rejection before SQL execution.
- Recorded parameter binding, closed destination maps, transaction rollback, and credential-free dispatch boundaries as security evidence.
- Recorded offline registry, workload integration, persistence core, and event-control test coverage plus remaining live-integration and observability debt.
