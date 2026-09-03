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
Last commit: 8fea6a1 - AGT-DEV01-FIX
Active task: AGT-DEV01-FIX2 - Fix test_agent.py container networking
Backlog: AGT-MULTI-P01, SAAS-P01, SAAS-P03, UI-P01, LIC-OPTIMIZER-P01

### Commit
    git add -A
    git commit -m "AGT-DEV01-FIX2: Fix test_agent.py container networking"
    git push origin main

### Acceptance Criteria
- [ ] docs/CLAUDE_CONTEXT.md contains all sections above verbatim
- [ ] Last commit shows 9d6748c — UI-BATCH-01
- [ ] Workflow section present
- [ ] Worker prompt format section present
- [ ] No code files touched
- [ ] Do NOT introduce non-ASCII characters

### HARD RULES
- Docs only — do NOT touch any code files
- Do NOT modify any SEALED workloads
- Do NOT introduce non-ASCII characters
