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

## Active Task
Planning next sprint

## Next Steps

1. INFRA-P02 — Scheduled email report (designed, ready to implement)
2. Multi-tenant architecture design
3. UI polish — mobile responsive, loading states
4. AGT-P11/P12 — Web fetch + research integration (blocked, defer)
5. Security Analyst Agent (future)
6. License Optimizer Agent (future)


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
