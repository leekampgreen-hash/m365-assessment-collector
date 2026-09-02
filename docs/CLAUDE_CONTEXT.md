# Claude Session Context
# Paste this file at the start of every new Claude session.
# Update the ACTIVE TASK section each time you begin a new task.

## Project
**m365-assessment-collector** — Read-only SaaS M365 operations dashboard.
Collects data from Microsoft Graph API and Management Activity API,
persists to PostgreSQL, served via Operations API and browser UI.

## Repo
- Server: `/opt/docker/graph-agent`
- GitHub: https://github.com/leekampgreen-hash/m365-assessment-collector
- Branch: `main`

## Stack
Python 3.13, PostgreSQL 16, Docker Compose, Microsoft Graph API,
Microsoft 365 Management Activity API, static HTML/JS UI.

## Navigation
- Progress index: `docs/PROJECT_PROGRESS.md`
- Active task and next steps: `docs/progress/current.md`
- Foundation / G01 / CH / STD-01–STD-15: `docs/progress/foundation.md`
- Workload progress: `docs/progress/exchange.md`, `docs/progress/onedrive.md`, `docs/progress/sharepoint.md`, `docs/progress/teams.md`, `docs/progress/license.md`
- Quick navigation and rules: `docs/FILE_MAP_QUICK.md`
- Full file ownership: `docs/PROJECT_FILE_MAP.md`
- Worker rules: `docs/WORKER_HANDOVER.md`
- Evidence: `docs/evidence/`

---

## SEALED — DO NOT REOPEN

| Workload | Status |
|---|---|
| OneDrive (OD-P01 through OD-P10) | **SEALED** |
| Exchange (EX-P03 through EX-P10) | **SEALED** |
| Migrations 001–020 | **LOCKED** |

May only be reopened for: a proven production regression, formally approved new scope,
or an independent blocking security/correctness finding.

---

## ALREADY PROVEN — DO NOT REPEAT

- Exchange: collector, persistence, analytics, API, UI capacity — ACCEPTED
- OneDrive: collector, persistence, audit, analytics, API, UI capacity — ACCEPTED
- SharePoint: basic collector + live acceptance — ACCEPTED (STD-07/08)
- License: inventory, mapping, live acceptance — ACCEPTED (STD-09/10/11)
- Cross-workload correlation — ACCEPTED (STD-12)
- Standard KPI engine — ACCEPTED (STD-13)
- Standard API — ACCEPTED (STD-14)
- Standard Dashboard — ACCEPTED (STD-15 series)
- Runtime parity check: `python scripts/check_runtime_parity.py`
- Test suite baseline: pytest inside container `graph-agent-collector-dev`

---

## ACTIVE TASK
<!-- Update this section each time you begin a new task -->

**ACTIVE TASK:** UI-BATCH-01 - Font hierarchy, anonymized token badges, Tailwind CDN fix
**Current phase:** UI fixes implemented; verification pending
**Blocker:** None
**Last commit:** 32b700b — DOCS-UPDATE
**Backlog:** ENTRA-P05, INT-P05, INT-P06, INFRA-P02
**Next planned:** Verify UI-BATCH-01, then continue backlog

**Deferred until STD-22 closes:**
- Entra security-posture expansion
- Identity Protection, PIM, advanced Conditional Access
- Purview, DLP, oversharing analytics
- Advanced license optimization, AI recommendations

---

## Key Commands

```bash
# Run test suite (inside container only — do NOT install pytest on host)
docker exec graph-agent-collector-dev pytest tests/ -x -q

# Runtime parity check
python scripts/check_runtime_parity.py

# Rebuild a single service
docker compose up -d --build --no-deps <service-name>

# Check container health
docker compose ps
```

## Production DB
- Host: `postgres:5432`
- Database: `graph_agent`
- Runtime role: `graph_agent_runtime`
- Active tenant: `tenant_id=2`
- Legitimate OneDrive audit rows: 3 (DO NOT touch)
- Synthetic residue: NONE
