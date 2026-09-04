# UX Backlog

## AGT-UX01 — Executive Summary Panel

**Status:** PASS  
**Priority:** MEDIUM

**Description:**
Add a summary panel at the top of the dashboard showing actionable findings that require IT attention.

**Design:**
- Show max 5 most critical items
- Each item: severity icon + plain language description
- Data sources:
  - `/api/security/findings` (open findings)
  - `/api/security/mfa-coverage` (MFA pass rate)
  - `/api/security/admin-roles` (admin count findings)
  - `/api/security/ca-policies` (report-only policies)
- Color coding: red = HIGH, yellow = MEDIUM
- Click item → scroll to relevant dashboard section

**Verification:**
- 5 findings displayed from real DB data
- Plain language descriptions with color-coded severity
- API key injection via nginx envsubst

**Dependencies:**
- SEC-P04 admin roles API (complete)
- All existing security endpoints (complete)

**Example output:**
```text
⚠️ 3 items require your attention
🔴 7 Global Administrators — recommend max 3
🔴 MFA pass rate 0% — users unprotected
🟡 2 CA policies in report-only mode
```

## AGT-DEV01 — Agent Auto-Tester
**Status:** PASS (100% score)
**Priority:** LOW

**Description:**
Build an automated agent tester that generates random M365 questions
and verifies agent response quality.

**Requirements:**
- Generate diverse M365 questions (security, adoption, license, inactivity)
- Verify tools_used is not empty for in-scope questions
- Verify out-of-scope questions return rejection message
- Verify no raw rule IDs in response (regex check)
- Verify response is in plain language
- Report pass/fail per question with tools_used and reply preview
- Run as standalone script: `python scripts/test_agent.py`

**Dependencies:**
- All agent tools working (complete)
- Agent live mode (complete)

**Verification:**
- 30-question dataset and standalone evaluator added under `scripts/`
- Live score: 100% (30/30 questions)
- All categories pass: security, adoption, license, inactivity, general, out_of_scope
- No rule IDs or UUIDs detected in any response
- Results saved to `scripts/agent_test_results.json`

## INFRA-P02 — Scheduled Email Report
**Status:** SEALED
**Priority:** HIGH

**Description:**
Daily/weekly HTML email summary to IT admins.

**Design doc:**
docs/progress/infra_roadmap.md

**Dependencies:**
All security + license endpoints (complete)

## LIC-OPTIMIZER-P01 — License Optimizer Agent
**Status:** SEALED  
**Priority:** HIGH

**Description:**
AI agent and advisory pipeline that analyzes license parking report and generates specific reclaim recommendations with quantified cost savings. Fully solved and integrated into the License FinOps Command Center and Identities Reclamation Pipeline (`LIC-UX01` & `LIC-UX02`).

**Triggers:**
On-demand via chat or dedicated inline AI audit consultation buttons.

**Dependencies:**
LIC-P01 license parking report (complete), LIC-UX02 identities reclamation pipeline (complete)

## AGT-MULTI-P01 — Multi-tenant Architecture
**Status:** PLANNED
**Priority:** HIGH

**Description:**
Support multiple customer tenants — each with own credentials, data isolation, and API key.

**Dependencies:**
Full architecture redesign required.

## AGT-DEV01-UPDATE — Update Agent Test Questions
**Status:** SEALED  
**Priority:** MEDIUM

**Description:**
Updated `scripts/agent_test_questions.json` to 42 questions covering all 20 internal operational and security tools (including `get_license_parking`, `run_security_analysis`, `get_signin_detail`, `get_risk_score`, `get_admin_roles`, `get_mfa_registration`). Added test parametrization and mock tests across all 20 tools in `tests/agent/test_tools.py` and `tests/agent/test_orchestrator.py`. Hardened agent model routing to `kl/gpt-5.4` and verified 100% PASS across live question evaluation and unit tests.

## UI-P01 — UI Polish
**Status:** PLANNED
**Priority:** MEDIUM

**Description:**
Mobile responsive, loading states, error handling, usage cards icon centering fix.

## AGT-P11 — Web Fetch Cache Layer
**Status:** DEFERRED
**Priority:** LOW

**Blocker:**
DuckDuckGo blocked from container, Tavily API key needed.

## AGT-P12 — Research Integration
**Status:** DEFERRED
**Priority:** LOW

**Blocker:**
Depends on AGT-P11.

## SAAS-P01 — Customer Onboarding Flow
**Status:** PLANNED
**Priority:** MEDIUM

**Description:**
Self-service onboarding for new MSP customers — register tenant, generate API key, connect Graph API.

## SAAS-P02 — White Label
**Status:** PLANNED
**Priority:** LOW

**Description:**
MSP can rebrand dashboard with own logo and colors.

## SAAS-P03 — Rate Limiting
**Status:** PLANNED
**Priority:** MEDIUM

**Description:**
Protect API from abuse — per key rate limiting.

## DEF-P02 - Defender for Office 365
Status: SEALED

## DEF-P03 - Cloud Apps Discovery
Status: SEALED

## DLP-P01 - DLP Policy Violations
Status: SEALED

## DLP-P02 - Sensitivity Label Adoption
Status: SEALED

## ENTRA-P05 - Named Locations
Status: SEALED. Priority: MEDIUM. New collector + UI panel for Entra named locations inventory.

## INT-P05 - Compliance Policy Inventory
Status: SEALED. Priority: MEDIUM. New collector + UI panel for Intune compliance policy inventory.

## INT-P06 - App Deployment Status
Status: SEALED. Priority: MEDIUM. New collector + UI panel for Intune app deployment status.

## SEC-ANALYST-P05-FIX2 - Token Format [ANON:X]
Status: SEALED. Priority: HIGH. Fix token format display issue in Security Analyst agent output.

## UI-FONT-03 - Fix Section Heading Hierarchy
Status: SEALED. Priority: LOW. CSS only. Section headings too small - increase to 1.25rem font-weight 600. Labels stay 11px uppercase muted.

## TAILWIND-CDN-FIX - Tailwind CDN Warning
Status: SEALED. Priority: LOW. Fix Tailwind CDN warning in UI. CSS/config only.

