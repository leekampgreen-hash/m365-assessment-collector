# M365 Assessment Collector

## PROJECT OVERVIEW

M365 Assessment Collector — Read-only SaaS M365 operations dashboard with AI-powered operations assistant.

## FEATURES

### Dashboard

- Dark theme operations dashboard
- Executive Summary Panel with top security findings
- KPI cards: licensed users, mailbox risk, license attention
- Usage overview: Email, OneDrive, SharePoint adoption
- License entitlements with utilization status

### M365 Assistant (AI Agent)

- Natural language Q&A about tenant health
- 19 tools covering operations, security, license, adoption
- Knowledge base with Microsoft Learn references
- Security guardrails: prompt injection, SQL injection, data export protection
- Plain language responses — no technical jargon
- Bahasa Indonesia support (multilingual)

### Security Coverage (Entra P1)

- Risky user detection
- MFA coverage and per-user registration status
- Conditional Access policy inventory
- Admin role inventory with risk classification
- Sign-in analytics: failed logins, legacy auth, country breakdown
- Combined user risk scoring (CRITICAL/HIGH/MEDIUM/LOW)

### Infrastructure

- Automated scheduled collection (phase-ordered)
- API Key authentication
- PostgreSQL persistence with 90-day event retention

## STACK

Python 3.13, PostgreSQL 16, Docker Compose, Microsoft Graph API, KryptonLab AI (claude-sonnet-4-6), nginx, APScheduler.

## ARCHITECTURE

```text
Browser → nginx → Operations API → PostgreSQL
                  ↓
            M365 Assistant (AI Agent)
                  ↓
            KryptonLab (claude-sonnet-4-6)

Microsoft Graph API → Scheduler → PostgreSQL
```

## QUICK START

### Prerequisites

- Docker
- Docker Compose
- Microsoft Entra App Registration

### Steps

1. Clone the repository.
2. Copy `secrets/collector.env.example` to `secrets/collector.env`.
3. Fill in `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, and `GRAPH_CLIENT_SECRET`.
4. Copy `.env.example` to `.env`, then fill in `API_KEY` and `KRYPTONLAB_API_KEY`.
5. Start the services:

   ```bash
   docker compose up -d
   ```

6. Open http://localhost:18080.

## REQUIRED GRAPH API PERMISSIONS

The Microsoft Entra app registration requires these application permissions:

- `Directory.Read.All`
- `AuditLog.Read.All`
- `Reports.Read.All`
- `Policy.Read.All`
- `RoleManagement.Read.Directory`
- `IdentityRiskyUser.Read.All`

## DEVELOPMENT

Run tests:

```bash
docker exec graph-agent-collector-dev pytest tests/ -x -q
```

Run the agent tester:

```bash
docker exec graph-agent-operations-api-dev python /tmp/test_agent.py
```

Check the scheduler:

```bash
docker compose logs scheduler --tail=20
```

## PROJECT STATUS

See [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md) for detailed progress tracking.
