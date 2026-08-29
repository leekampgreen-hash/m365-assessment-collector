# Task Prompt Template
# Use this template for all new tasks.
# Purpose: replace fat prompts (like OD-P05G) with a lean format.
# Target: < 500 tokens per prompt (vs 1500+ previously).

---

## Minimal Template

```
TASK_ID: <ID>
SESSION: NEW

FIRST:
Read docs/WORKER_HANDOVER.md
Read docs/PROJECT_FILE_MAP.md
Read docs/evidence/<previous-evidence>.md  ← baseline, do not repeat

OBJECTIVE:
<1-3 sentences — what must be achieved>

SCOPE:
<files or components that may be touched>

DO NOT:
<task-specific restrictions only>
See WORKER_HANDOVER.md for general rules — do not repeat them here.

GATES:
1. <first gate that must PASS>
2. <second gate>
3. <third gate>

STOP after each failing gate — do not proceed to the next.

RETURN:
TASK_ID:
RESULT: PASS / BLOCKED / FAIL
FILES_CHANGED:
TESTS: N/N
BLOCKER: (if any)
SYNTHETIC_RESIDUE:
NEXT:
```

---

## Example: Small Task (1 gate)

```
TASK_ID: STD-21A-RUNTIME-PARITY-001
SESSION: NEW

FIRST:
Read docs/WORKER_HANDOVER.md
Read docs/evidence/STD-20-CROSS-WORKLOAD-PRODUCTION-TEST-001.md

OBJECTIVE:
Verify runtime parity for all production modules after STD-20 changes.

SCOPE:
Run scripts/check_runtime_parity.py output only — no code changes.

DO NOT:
Modify any production files.
See WORKER_HANDOVER.md for general rules.

GATES:
1. Parity check — all modules MATCH.

RETURN:
TASK_ID: STD-21A-RUNTIME-PARITY-001
RESULT:
PARITY: MATCH / MISMATCH
MISMATCHED_FILES: (if any)
NEXT:
```

---

## Example: Medium Task (3 gates)

```
TASK_ID: STD-21-RUNTIME-HARDENING-001
SESSION: NEW

FIRST:
Read docs/WORKER_HANDOVER.md
Read docs/PROJECT_FILE_MAP.md
Read docs/evidence/STD-20-CROSS-WORKLOAD-PRODUCTION-TEST-001.md  ← baseline

OBJECTIVE:
Runtime hardening: parity check, focused regression, synthetic cleanup verification.

SCOPE:
- scripts/check_runtime_parity.py
- tests/scenario/integration/ (run only, no changes)
- Synthetic row cleanup if any exist

DO NOT:
- Make live Microsoft API calls
- Modify production source files
See WORKER_HANDOVER.md for general rules.

GATES:
1. Runtime parity — all modules MATCH
2. Focused integration tests PASS (not full regression)
3. SYNTHETIC_RESIDUE = NONE

STOP after each failing gate. Report and wait for instruction.

RETURN:
TASK_ID:
RESULT:
PARITY:
TESTS:
SYNTHETIC_RESIDUE:
BLOCKER:
NEXT:
```

---

## What Does NOT Belong in a Task Prompt

The following are already covered by `WORKER_HANDOVER.md` — do not repeat:

- ❌ Long generic DO NOT lists
- ❌ Re-explanation of locked baselines
- ❌ Rules about synthetic residue
- ❌ Rules about not installing pytest on host
- ❌ "NO NEW BUSINESS FEATURE / NO UX / NO ANALYTICS" etc.
- ❌ Full LOCKED ACCEPTED BASELINE sections

Just write: `"See WORKER_HANDOVER.md for general rules."`
