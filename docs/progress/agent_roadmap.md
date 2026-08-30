# Agent Roadmap

## Agents in Production

### Agent 1 — M365 Assistant (LIVE)
- Role: Primary user-facing chat agent
- Model: kl/claude-sonnet-4-6 via KryptonLab
- Interface: Floating chat panel in dashboard
- Tools: 14 operational + security tools
- Knowledge: 4 core files + 6 product files
- Scope: M365 operational Q&A, security findings, license, adoption

## Agents Planned

### Agent 2 — Research Agent (STUB — AGT-P10)
- Role: Fetch and summarize Microsoft official documentation
- Trigger: Called by M365 Assistant when internal knowledge insufficient
- Source: learn.microsoft.com, docs.microsoft.com only
- Status: Stub exists in agent/research.py, web fetch deferred
- Blocker: Network fetch from agent container — pending solution

### Agent 3 — Security Analyst Agent (FUTURE)
- Role: Deep security posture analysis, risk scoring, automated reports
- Trigger: Scheduled or on-demand security review
- Scope: Cross-workload risk correlation, MFA gaps, CA policy gaps,
         risky user trends, privileged role monitoring
- Dependencies: Sign-in logs collector, MFA registration collector
- Status: Not started — pending SEC-P04+ completion

### Agent 4 — License Optimizer Agent (FUTURE)
- Role: License cost optimization recommendations
- Trigger: On-demand or monthly scheduled review
- Scope: Unused licenses, over-provisioned SKUs, 
         license-to-activity correlation, renewal recommendations
- Dependencies: Full license utilization data, user activity correlation
- Status: Not started — pending license data completeness

## Interaction Pattern
User → M365 Assistant → Research Agent (fallback)
M365 Assistant → Security Analyst (future escalation)
M365 Assistant → License Optimizer (future escalation)

## Rules
- User message never leaves the system to external search engines
- All external fetch done by Research Agent only (not M365 Assistant)
- Security Analyst and License Optimizer are read-only — no write actions
- Each agent has strict scope boundaries — cannot answer outside its domain
