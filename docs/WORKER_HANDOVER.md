# Worker Handover
# Read this file at the start of every task and every new session.
# Purpose: prevent scope drift, avoid re-doing proven work, and keep token usage efficient.

## Mandatory Steps Before Execution

1. Read `docs/WORKER_HANDOVER.md` (this file)
2. Read `docs/PROJECT_FILE_MAP.md` — all file ownership is here
3. Read `docs/PROJECT_PROGRESS.md` — current status of all phases
4. Confirm that every file path you intend to touch actually exists before editing
5. Do NOT broadly explore the repo — read only files relevant to the task

---

## Hard Rules

### DO NOT do the following without explicit instruction:
- Modify files outside the task scope
- Create evidence files (evidence is created by the supervisor)
- Reopen a SEALED workload
- Make live Microsoft API calls
- Mutate production tenant data
- Install pytest on the host — use container `graph-agent-collector-dev`
- Modify locked migrations (001–020)
- Auto-fix a real production defect — report it and STOP

### ALWAYS do the following:
- Confirm file paths before editing
- Run focused tests only — not full regression — unless explicitly instructed
- Report any defect found — do NOT auto-fix without instruction
- Report STOP if a blocker requires a human decision

---

## Sealed Workloads

| Workload | Sealed at | May reopen only if |
|---|---|---|
| OneDrive | OD-P10 | Proven production regression or approved new scope |
| Exchange | EX-P10 | Proven production regression or approved new scope |

---

## Test Environment

```bash
# Run tests inside the dev container
docker exec graph-agent-collector-dev pytest <test_path> -x -q

# DO NOT install pytest on the host
# DO NOT run broad regression unless explicitly instructed

# Runtime parity check (required after any production file change)
python scripts/check_runtime_parity.py
```

---

## Database

- Host: `postgres:5432`
- Database: `graph_agent`
- Runtime role: `graph_agent_runtime`
- Bootstrap role: for synthetic data cleanup only
- Active tenant: `tenant_id=2`
- **3 legitimate OneDrive audit rows: DO NOT touch**
- After every test run: verify `SYNTHETIC_RESIDUE = NONE`

---

## Result Report Format

Use this concise format — do NOT write verbose summaries:

```
TASK_ID:
RESULT: PASS / BLOCKED / FAIL
FILES_CHANGED:
TESTS: N/N PASS
BLOCKER: (if any)
SYNTHETIC_RESIDUE: NONE / <detail if any>
NEXT:
```

---

## Token Efficiency Rules

- Do NOT re-include proven baselines in your output — reference the evidence file only
- Do NOT produce verbose output unless explicitly requested
- For large tasks: complete one gate, report, then wait for confirmation before proceeding
- If uncertain between two approaches: STOP and ask — do not execute both

---

## Key Directory Map

```
collectors/          — Graph collection framework
  core/             — runtime, auth, HTTP, config
  workloads/        — registry, adapters, models
  persistence/      — DB transaction boundary
database/migrations/ — forward-only DDL (001-020 LOCKED)
tests/
  persistence/      — persistence unit tests
  workloads/        — workload unit tests
  integration/      — OneDrive audit production-path tests
  scenario/
    integration/    — cross-component integration tests
    live/           — environment-dependent (treat separately)
analytics/          — read-only analytics operations
api/                — Operations API
operations-ui/      — static dashboard (HTML/JS/CSS)
scripts/            — parity check tools
docs/               — all documentation and evidence
```
