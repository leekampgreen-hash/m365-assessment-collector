# Security Production Orchestration

Run a registered Security rule through the collector's app-only production
stack:

```bash
python -m collectors.run_collector --security-rule M365-ENTRA-CA-ENFORCEMENT-001 --granted-graph-permissions Policy.Read.All
```

The command resolves capabilities from persisted `core.subscribed_sku.service_plans`
before requesting a token or constructing a Graph collector. `--granted-graph-permissions`
is an explicit deployment declaration of app permissions granted to the collector
identity; it is not inferred from Graph errors.

## CH8 license-aware production seal

**Status:** SEALED / PASS  
**Task:** `CH8-LICENSE-AWARE-SECURITY-PIPELINE-SEAL-001`

This is acceptance documentation only. It does not trigger collection, evaluation,
or persistence.

### Capability and authentication contract

- The high-tier E5/P2 development tenant defines the supported feature superset;
  customer entitlement defines the executed subset.
- `NOT_ENTITLED` is `SKIP_NOT_LICENSED`: zero Graph reads, no evaluation, and no
  finding. `UNKNOWN`, `PERMISSION_REQUIRED`, and `SOURCE_UNAVAILABLE` remain
  distinct states and are never relabelled as `NOT_LICENSED`.
- Security collection uses app-only `client_credentials` authentication with
  `Policy.Read.All`. Delegated auth, device code, Scenario Agent auth, and
  interactive actions are outside this pipeline.
- The generic Security orchestrator gates before token/Graph construction, keeps
  Collector lifecycle separate from Security observation/evaluation/current
  projection persistence, and retries persistence without recollecting Graph.
- Security status and severity are deterministic. AI does not determine finding
  status, severity, or evidence. No Graph writes or auto-remediation exist.

### Accepted Rule #7 live proof

`M365-ENTRA-CA-ENFORCEMENT-001`: `ENTRA_P1=ENTITLED`, gate `COLLECT`, lower-tier
`NOT_ENTITLED` contract `PASS`; app-only Graph `G01-011`, HTTP `200`, one page.
Lifecycle: collection run `8`, endpoint run `13`, endpoint `PASS`, collection
`SUCCESS`, error classification `PASS`, stale `RUNNING=0`. Observation, evaluation,
current projection, retry idempotency, and duplicate-row checks passed; no second
Graph collection occurred.

Aggregate: **3 Conditional Access policies, 0 enabled, 2 report-only, 1 disabled**.
The deterministic finding is `OPEN`, `MEDIUM`, scoped to
`CONDITIONAL_ACCESS_ENFORCEMENT_PRESENCE_ONLY`: **No Conditional Access policy is
actively enforced.** This does not prove MFA absence, MFA user/admin/all-user
coverage, authentication strength, Identity Protection coverage, Security Defaults
state, or overall tenant authentication posture. Those require separate deterministic
evidence.

### Current seven-rule Security snapshot

| Rule | Category | State | Severity | Required capability | Acceptance |
| --- | --- | --- | --- | --- | --- |
| `M365-SP-EXT-001` | SharePoint / OneDrive External Sharing | `OPEN` | `MEDIUM` | None recorded | Offline: PASS |
| `M365-ENTRA-CONSENT-001` | Application Security / User Consent | `NOT_EVALUATED` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-RISKY-CONSENT-001` | Application Security / Risky Application Consent | `NOT_EVALUATED` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-GUEST-001` | External Collaboration / Guest Invitations | `OPEN` | `MEDIUM` | None recorded | Offline: PASS |
| `M365-ENTRA-GUEST-ACCESS-001` | External Collaboration / Guest Directory Access | `PASS` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-GA-001` | Privileged Access / Global Administrators | `OPEN` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-CA-ENFORCEMENT-001` | Authentication / Conditional Access | `OPEN` | `MEDIUM` | `ENTRA_P1` | Live: PASS |

Persisted Security evaluations: **7**. Accepted product evidence: summary HTTP
`200`, findings HTTP `200`, Rule #7 detail HTTP `200`, dashboard generic rendering
`PASS`. Accepted full regression baseline: **684 PASS**.

### Seal accounting

```text
Graph_reads: 0
Graph_writes: 0
DB_writes: 0
DB_schema_changed: NO
Entra_changed: NO
Scenario_changed: NO
Intune_touched: NO
```
