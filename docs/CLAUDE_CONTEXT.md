# Claude Session Context
# Paste this file at the start of every new Claude session.
# Claude will immediately understand the project, workflow, and format — no explanation needed.

## Project
m365-assessment-collector — Read-only SaaS M365 operations dashboard.
Collects data from Microsoft Graph API and Management Activity API,
persists to PostgreSQL, served via Operations API and browser UI.
Target customers: MSPs/CSPs managing Microsoft 365 tenants.

## Repo
Server: /opt/docker/graph-agent
GitHub: https://github.com/leekampgreen-hash/m365-assessment-collector
Branch: main

## Stack
Python 3.13, PostgreSQL 16, Docker Compose, Microsoft Graph API, Management Activity API, static HTML/JS UI.

## Workflow
Owner: makes all decisions, reviews results.
Claude: supervisor only — reads context, writes worker prompts, reviews output. Never implements code.
Worker: opencode + model kl/gpt-5.6-luna — executes all code and doc changes.
Claude quota is expensive (340k IDR/month) — be efficient, no unnecessary questions, no re-explaining.
Worker quota is cheap (20k IDR) — use worker for all implementation.

## Worker Prompt Format
Every worker prompt must be one single unbroken plain text block inside a code fence.
No markdown prose outside the block. No nested code fences inside the prompt.
Sections: Context, Fix or What to build, Rebuild and restart, Commit, Acceptance Criteria, HARD RULES.
Acceptance Criteria always includes:
- Update CLAUDE_CONTEXT.md: last commit, active task, backlog — before pushing
- Do NOT introduce non-ASCII characters
- pytest inside collector container: docker exec graph-agent-collector-dev pytest tests/ -x -q

## App Credentials
URL: http://localhost:18080
Email: admin@localhost
Password: c8xnvuVvxYzy-k155KrqZA

## SEALED — DO NOT REOPEN
OneDrive OD-P01 through OD-P10 — SEALED
Exchange EX-P03 through EX-P10 — SEALED
Migrations 001–020 — LOCKED

## Key Commands
docker exec graph-agent-collector-dev pytest tests/ -x -q
docker compose up -d --build --no-deps <service-name>
docker compose ps
python scripts/check_runtime_parity.py

## Production DB
Host: postgres:5432
Database: graph_agent
Runtime role: graph_agent_runtime
Active tenant: tenant_id=2
Legitimate OneDrive audit rows: 3 (DO NOT touch)
Synthetic residue: NONE

## ACTIVE TASK
UI-V2 rebuild + security_status integration
Last commit: a56d5d7 - API-USER-SECURITY-STATUS

Backlog (in order):
1. UI-V2-REBUILD-FINAL - Rebuild v2 UI cleanly (layout issues still unresolved)
2. UI-V2-SECURITY-STATUS - Add security_status badge + flags to User Intelligence table
3. UI-V2-SECURITY-PANEL - Build Security menu panels using createPaginatedTable()
4. UI-V2-PRODUCTIVITY-PANEL - Build Productivity menu panels
5. UI-V2-LICENSE-PANEL - Build License menu panels
6. AGT-MULTI-P01 - Multi-tenant architecture
7. SAAS-P01 - Customer onboarding flow

Known issues in UI-V2:
- Sidebar toggle button position and content expand not working correctly
- Layout has gaps and overlap issues
- Recommend full rebuild from clean Tabler starter before adding more features

API ready:
- GET /api/intelligence/users - 39 users, all attributes + security_status + security_score + security_flags
- security_status: CRITICAL/HIGH/MEDIUM/LOW/GOOD per CIS M365 v6.0.1 benchmark

### Commit
    git add -A
    git commit -m "DOCS-HANDOFF: Update context for session handoff"
    git push origin main

### Acceptance Criteria
- [ ] docs/CLAUDE_CONTEXT.md updated with correct last commit and backlog
- [ ] No code files touched
- [ ] Do NOT introduce non-ASCII characters
