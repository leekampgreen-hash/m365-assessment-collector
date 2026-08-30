# Current Progress

## Completed Recently

- SP-P03 to SP-P12: SharePoint workload SEALED
- TM-P01 to TM-P03: Teams collector + analytics PASS
- DA-P01 to DA-P03: Data audit + persistence fixes
- API-P01: Missing endpoints added
- OPT-P01: Token optimization (progress files split)
- AGT-P01 to AGT-P09: Agent tools, orchestration, chat API, chat box UI, additional tools, live acceptance, knowledge base, and knowledge base restructure PASS
- SEC-P01 to SEC-P07: Security risk, MFA coverage, conditional-access, admin-roles, sign-in logs, MFA registration, sign-in detail, and combined risk scoring APIs and agent tools PASS
- AGT-UX01: Executive Summary Panel PASS — 5 real DB findings displayed in plain language with color-coded severity and nginx envsubst API key injection
- AGT-DEV01: Agent Auto-Tester PASS — 30-question dataset and standalone evaluator added; live score pending execution against the operations API

## Agent Status

- AGT-P01: PASS
- AGT-P02: PASS
- AGT-P03: PASS
- AGT-P04: PASS
- AGT-P05: PASS
- AGT-P06: PASS
- AGT-P07: PASS
- AGT-P09: PASS
- AGT-P10: PASS
- AGT-P11: DEFERRED
- AGT-P12: DEFERRED
- SEC-P05: PASS
- SEC-P06: PASS
- AUTH-P01: PASS
- INFRA-P01: PASS

## Active Task
review and next planning session


## Next Steps

1. AGT-DEV01 Agent Auto-Tester
2. API Key auth UI (future SaaS)


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
