# Model Selection Guide
# Guide for choosing the right model per task type.
# Purpose: cost efficiency without sacrificing quality.

## Core Principle

```
A capable model with a short prompt beats a cheap model with a fat prompt.
A fat prompt is a signal that the model lacks capability — not a solution to it.
```

---

## Tiers and Roles

### Tier 1 — Supervisor (Claude at claude.ai)
**When to use:**
- Review worker output
- Scope and direction decisions
- Blockers that require complex reasoning
- Reading and interpreting evidence files
- Planning the next task

**Budget:** Conserve — 1 session = 1 topic or 1 review.
Do not use Claude for code execution or running tests.

---

### Tier 2 — Coding Worker (opencode + selected model)

| Task Type | Recommended Model | Reason |
|---|---|---|
| Write/edit Python code | **Devstral Medium** | Mistral coding agent — less scope drift |
| Focused pytest fixture | **Devstral Medium** | Same |
| Error analysis / RCA | **DeepSeek V3.x** | Strong reasoning, low cost |
| Initial draft / exploration | **Luna (GPT 5.6 Luna)** | Cheap, sufficient for drafts |
| Draft review / light reasoning | **Qwen 3.7 Plus** | Better reasoning than Luna, similar price |
| Long-context tasks | **Kimi K2.7 / Gemini 3.x** | Large context window |

---

### Tier 3 — Cheap Worker (draft and exploration only)

Use only for:
- Early exploration where output will be reviewed before use
- Tasks whose output does not go directly to production
- Boilerplate generation that will be manually edited

Models: **Luna**, **Muse Spark 1.1**, **North Mini Code**

---

## Decision Flow

```
New task arrives
    │
    ├─ Needs a decision or output review?
    │   └─ → Claude (Supervisor)
    │
    ├─ Write/edit production code?
    │   └─ → Devstral Medium (worker)
    │
    ├─ Error analysis / RCA?
    │   └─ → DeepSeek V3.x (worker)
    │
    ├─ Initial draft / exploration?
    │   └─ → Luna or Muse (cheap worker)
    │
    └─ Unsure?
        └─ → Ask Claude before executing
```

---

## Cost Controls

### Always do:
- Set a **daily spend cap** at your provider (never skip this)
- Set a **max tokens per request** limit in your opencode config
- Test with 1 small task before running a new model on a large task

### Signs the worker model needs replacing:
- Drifts off-scope more than twice in a single task
- Output does not follow the existing repo structure
- Prompt keeps growing just to repeat the same rules

### Signs a task scope is too large:
- Prompt has more than 15 sections
- DO NOT list has more than 10 items
- Worker needs to read more than 5 evidence files at once

→ Break the task into 3–4 sections, execute gate by gate.

---

## Provider Notes

The current provider uses custom model names (Luna, Terra, Muse, etc.).
The true underlying model identity is not 100% verified. Implications:

- Output consistency may change between sessions
- If a model suddenly seems smarter or dumber, the provider may have swapped
  the backend model
- Keep benchmark results per model name for future reference

For production-critical tasks: prefer a model already proven on a similar task
over an untested model, regardless of advertised capability.
