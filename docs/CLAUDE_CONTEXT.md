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
Last commit: UI-V2-SIDEBAR-FIX (verification complete)
Active task: None - sidebar padding and icon names fixed
Backlog: AGT-MULTI-P01, SAAS-P01, SAAS-P03, UI-P01, LIC-OPTIMIZER-P01

### Commit
    git add -A
    git commit -m "UI-V2-SHELL-TABLER: Replace shell with Tabler-based layout"
    git push origin main

### Acceptance Criteria
- [x] http://localhost:18080/v2/ loads with Tabler styling
- [x] Left sidebar renders all sections and menu items with icons
- [x] Clicking menu item loads dummy page in content area
- [x] Sidebar collapsible
- [x] Topbar renders with search and user info
- [ ] Existing UI at http://localhost:18080/ completely unchanged
- [ ] Do NOT introduce non-ASCII characters
- [x] Update docs/CLAUDE_CONTEXT.md: last commit before pushing

### HARD RULES
- Only touch operations-ui/Dockerfile and operations-ui/nginx.conf if needed
- Do NOT touch operations-ui/public/ or any existing UI files
- Do NOT modify any SEALED workloads
- Do NOT introduce non-ASCII characters
- Update docs/CLAUDE_CONTEXT.md before every commit - no exceptions

## VERIFICATION
Path fix verified on 2026-09-03: files at /usr/share/nginx/v2/ (correct), nginx.conf serves /v2/ from /usr/share/nginx/v2/, HTTP 200 for styles.css, Tabler UI renders correctly.
