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
**Status:** PASS  
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
