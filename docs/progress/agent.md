# Agent Progress

Agentic M365 Operational Assistant phases.

## AGT-P01 Agent tools (PASS)

**Task:** `AGT-P01`
**Status:** `AGT-P01 PASS`

- `agent/tools.py` provides 8 read-only tool functions for Operations Analytics.
- `ToolError` provides consistent internal API failure handling.
- The internal API caller retrieves JSON data from the Operations API over HTTP.

## AGT-P02 Agent orchestration (PASS)

**Task:** `AGT-P02`
**Status:** `AGT-P02 PASS`

- `agent/orchestrator.py` implements the ReAct orchestration pattern.
- Mock and live modes are selected through the `AGENT_MODE` environment variable.
- Mock mode uses the internal tools and returns tool results without calling OpenAI.

## AGT-P03 Chat API (PASS)

**Task:** `AGT-P03`
**Status:** `AGT-P03 PASS`

- `api/agent.py` validates chat payloads and delegates to the agent orchestrator.
- `POST /api/agent/chat` is registered in `api/operations.py`.
- The endpoint returns `reply` and `tools_used`, with real database data in mock mode.

## AGT-P04 Chat box UI (PASS)

**Task:** `AGT-P04`
**Status:** `AGT-P04 PASS`

- Floating chat panel with expand/collapse toggle (300px default, 520px expanded).
- Dark theme applied to the chat UI.
- Security guardrails reject prompt injection, SQL injection, and data export attempts.
- Violations return HTTP 400 `REJECTED` without disclosing the triggered rule.
- System prompt hardened against manipulation.

## AGT-P05 Live acceptance (PASS)

**Task:** `AGT-P05`
**Status:** `AGT-P05 PASS`

Live acceptance using OpenAI completed successfully. All 8 tests passed:

- TEST 1 Inactivity Q&A: PASS
- TEST 2 Adoption query: PASS (data unavailable in DB — correct behavior)
- TEST 3 License check: PASS
- TEST 4 Health summary: PASS
- TEST 5 Prompt injection: PASS (HTTP 400)
- TEST 6 SQL injection: PASS
- TEST 7 Data export attempt: PASS
- TEST 8 Tool selection: PASS

Evidence: AGT-P01 through AGT-P05 accepted; all 8 AGT-P05 tests pass.

## AGT-P06 Additional agent tools (PASS)

**Task:** `AGT-P06`
**Status:** `AGT-P06 PASS`

- Added `get_summary` for the Operations API summary endpoint.
- Added `get_data_quality` for Operations API data-quality status.
- Added `get_capabilities` for the system capabilities endpoint.
- `get_capabilities` requires an explicit system prompt instruction to trigger for capability questions.
 - Live acceptance passed for all three new tools.

## AGT-P07 Agent knowledge base (PASS)

**Task:** `AGT-P07`
**Status:** `AGT-P07 PASS`

- Added file-backed plain-language translations for security rules, Conditional Access states, M365 terminology, and prioritized recommendations.
- Added keyword-based context lookup with a concise prompt-size limit and module-level singleton loading.
- Integrated relevant knowledge context into live-mode agent system prompts.

## AGT-P09 Knowledge base restructure (PASS)

**Task:** `AGT-P09`
**Status:** `AGT-P09 PASS`

- Restructured the knowledge base into `core/` and `products/` directories.
- Added 6 product files: Exchange, SharePoint, OneDrive, Teams, Entra, and License.
- Added lazy product loading based on topic detection.
- Prepared the `cache/` directory for AGT-P11.
- 1,046 tests pass; 1 pre-existing failure remains in the unrelated security suite.

## AGT-P10 Research tool (PASS)

**Task:** `AGT-P10`
**Status:** `AGT-P10 PASS`

- Curated Microsoft Learn URLs added to all 6 product files.
- Research module simplified to a future-proof stub.
- `learn_more_url` injected into agent responses.
- 38 agent tests pass.
- Web fetch deferred to the future; AGT-P11 and AGT-P12 are on hold.

## AGT-P11 Web fetch cache (DEFERRED)

**Task:** `AGT-P11`
**Status:** `AGT-P11 DEFERRED`

- Cache layer structure is ready in `agent/knowledge/cache/`.
- Implementation deferred until web fetch is available.

## AGT-P12 Research integration (DEFERRED)

**Task:** `AGT-P12`
**Status:** `AGT-P12 DEFERRED`

- Integration deferred until AGT-P11 is complete.

