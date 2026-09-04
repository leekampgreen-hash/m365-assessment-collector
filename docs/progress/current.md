# Current Progress

## Completed Recently

- AGT-P01 to P03: Agent core + API endpoint — SEALED
- AGT-P04: Chat UI + dark theme — SEALED
- AGT-P05: Live acceptance test — SEALED
- AGT-P06: 3 additional tools (`get_summary`, `get_data_quality`, `get_capabilities`) — SEALED
- AGT-P07: Knowledge base — SEALED
- AGT-P08: KryptonLab provider switch (`kl/claude-sonnet-4-6`) — SEALED
- AGT-P09: Knowledge base restructure (`core/` + `products/`) — SEALED
- AGT-P10: Research tool stub + Microsoft Learn URLs — SEALED
- AGT-TD01: Tech debt cleanup (19 fixes) — SEALED
- AGT-UX01: Executive Summary Panel — SEALED
- AGT-DEV01: Agent auto-tester 100% score — SEALED
- SEC-P01: Risky users + risk detections — SEALED
- SEC-P02: MFA coverage — SEALED
- SEC-P03: CA Policy inventory — SEALED
- SEC-P04: Admin role inventory — SEALED
- SEC-P05: Sign-in logs analytics — SEALED
- SEC-P06: MFA registration per user — SEALED
- SEC-P07: Sign-in detail + combined risk scoring — SEALED
- SEC-ANALYST-P01: Security Analyst Agent — PASS
- INFRA-P01: Scheduled collector (phase-ordered) — SEALED
- AUTH-P01: API Key authentication — SEALED
- LIC-P01: License Parking Report — PASS
- AUTH-METHODS-FIX: Methods breakdown grid layout + top method card overflow - SEALED
- BATCH-2: DEF-P02 (Defender for Office 365), DEF-P03 (Cloud Apps Discovery), DLP-P01 (DLP policy violations), DLP-P02 (Sensitivity label adoption) - SEALED
- BATCH-3: ENTRA-P05 (Named locations), INT-P05 (Compliance policy inventory), INT-P06 (App deployment status) - SEALED
- UI-BATCH-01: Font hierarchy, token format badge, Tailwind CDN fix - SEALED
- INFRA-P02: Scheduled email report - SEALED
- API-CLEANUP-01: Dead code removal, exchange capacity caching, defensive security guard, dynamic KPI deltas, SKU pricing consolidation - SEALED
- LIC-UX02: License FinOps Command Center & Identities Reclamation Redesign - SEALED
- LIC-OPTIMIZER-P01: License optimizer advisory & reclamation recommendations (integrated in LIC-UX01/02) - SEALED
- COLLECTOR-STD-P01-P05: Collector Standardization Phases 1-5 (CLI flags, SSOT inventory with 45 collectors, Unified Runner `--collector`, Admin UI search & filter, on-demand trigger API, 4 metric cards, inspector modal, and reference catalog) - SEALED
- TD-009 & TD-010: Workload registry invariant alignment & test dependency / package shadowing resolution (100% test suite pass) - SEALED

## Active Task
Technical debt backlog reduction (TD-001/TD-002 retention metadata alignment) and next sprint planning

## Next Steps

1. TD-001/TD-002 - Registry retention metadata alignment for G01-005, 006, 013, 014
2. AGT-MULTI-P01 - Multi-tenant architecture design
3. SAAS-P01 - Customer onboarding flow
4. SAAS-P03 - Rate limiting
5. UI-P01 - UI polish (mobile responsive, loading states)
6. AGT-DEV01-UPDATE - Update agent test questions


## Available API Endpoints

From `api/operations.py`:

- `GET /health`
- `GET /api/operations/correlation/users`
- `GET /api/operations/kpi`
- `GET /api/operations/summary`
- `GET /api/operations/onedrive/high-value-audit?limit={limit}`
- `GET /api/operations/sharepoint/audit-summary?limit={limit}`
- `GET /api/operations/sharepoint/orphaned-sites`
- `GET /api/operations/sharepoint/external-sharing`
- `GET /api/operations/sharepoint/tenant-settings`
- `GET /api/operations/license/expiry`
- `GET /api/operations/teams/activity-summary`
- `GET /api/operations/inactivity?days={30|60|90}`
- `GET /api/operations/adoption/exchange`
- `GET /api/operations/adoption/onedrive`
- `GET /api/operations/adoption/sharepoint`
- `GET /api/operations/adoption/sharepoint/sites`
- `GET /api/operations/license-utilization`
- `GET /api/license/parking-report`
- `GET /api/operations/data-quality`
- `GET /api/security/summary`
- `GET /api/security/findings?status={status}&severity={severity}`
- `GET /api/security/findings/{finding_id}`
- `GET /api/security/data-quality`
- `GET /api/security/signin-risk`
- `GET /api/security/mfa-coverage`
- `GET /api/security/mfa-registration`
- `GET /api/security/ca-policies`
- `GET /api/capabilities`

## Navigation

- Index: `docs/PROJECT_PROGRESS.md`
- Foundation: `docs/progress/foundation.md`
- Workload files: `docs/progress/{exchange,onedrive,sharepoint,teams,license}.md`
