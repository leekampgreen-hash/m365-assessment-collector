# CH8 Security Findings Foundation

**Status:** PASS

**Task:** Build the deterministic Security Findings foundation for the Microsoft 365 Security & Operational Intelligence product. Foundation only — no Graph calls, no AI, no database writes, no remediation.

## Architecture

```
M365 configuration/activity
    -> normalized SecurityObservation
    -> deterministic baseline rule
    -> evaluation
    -> SecurityFinding (status, severity, risk, evidence, recommendation)
```

## Deliverables

| File | Purpose |
|------|---------|
| `security/models.py` | Domain contracts: `SecurityRule`, `SecurityBaseline`, `SecurityObservation`, `SecurityFinding`, `EvidenceReference`, `Recommendation`, `SecurityFindingService`. Finding status and severity enums. |
| `security/baseline.py` | Product baseline `m365-security-recommended-v1` version `1.0.0`. |
| `security/rules/sp_ext_001.py` | First rule `M365-SP-EXT-001` (SharePoint / OneDrive External Sharing) with deterministic comparison and content. |
| `security/service.py` | `DeterministicSecurityFindingService` — observation -> resolve baseline/rule -> validate dependency -> deterministic comparison -> finding. |
| `tests/security/test_security_findings.py` | CH8 test matrix (26 tests). |

## Fail-safe semantics

- valid evidence + baseline satisfied -> `PASS`
- valid evidence + baseline violated -> `OPEN`
- source unavailable / ambiguous / unsupported / malformed -> `NOT_EVALUATED`
- **`NO_EVIDENCE != SECURITY_GAP`**: missing evidence is `NOT_EVALUATED`, never `OPEN`.

## M365-SP-EXT-001 behavior

Canonical ordered external-sharing levels (strictest -> most permissive):
`none`, `existing_guests`, `new_and_existing_guests`, `anyone`.
Baseline expectation: `existing_guests`.

- actual equal/stricter than baseline -> `PASS`
- actual more permissive than baseline -> `OPEN`
- source unavailable -> `NOT_EVALUATED`
- unsupported value -> `NOT_EVALUATED`

Severity (`MEDIUM`) and the canonical recommendation are deterministic from the rule definition. The recommendation advises administrative remediation but never executes it.

## Baseline claims

This is a PRODUCT baseline. It does NOT claim CIS compliance, NIST certification, Microsoft Secure Score equivalence, or regulatory certification (`formal_compliance_claim = False`).

## Determinism / boundaries

- Same normalized input + same baseline/version produces a semantically identical result; `finding_id` is stable.
- No AI: gap decision, severity, evidence, and the canonical recommendation are all deterministic.
- No network and no AI dependency (only stdlib + local modules imported).
- `Graph_reads = 0`, `Graph_writes = 0`, `DB_writes = 0`, `DB_schema_changed = NO`.

## Validation

- Targeted security suite: 26 tests PASS.
- Full offline regression: 684 tests PASS (only pre-existing `scenario.live` interactive-auth/network prints, no failures).
- `python3 -m compileall security tests/security`: OK.

## License-aware Security production pipeline seal

**Task:** `CH8-LICENSE-AWARE-SECURITY-PIPELINE-SEAL-001`  
**Decision:** `LICENSE_AWARE_SECURITY_PIPELINE_SEAL: PASS`

This acceptance record documents the accepted live evidence without triggering
collection, evaluation, or persistence. No Graph call, database write, schema,
Entra, runtime, Scenario, Intune, new-rule, or Rule #8 change was performed.

### Closed architecture contract

- High-tier E5/P2 development capability is the supported superset; customer
  entitlement selects the executed subset.
- `NOT_ENTITLED -> SKIP_NOT_LICENSED` means zero Graph reads, no evaluation, and
  no false finding. `UNKNOWN`, `PERMISSION_REQUIRED`, and `SOURCE_UNAVAILABLE`
  remain distinct non-license states.
- Security uses app-only `client_credentials` with `Policy.Read.All`; Scenario
  Agent delegated/device-code authentication is isolated from Security collection.
- The generic orchestrator gates before token/Graph construction and separates
  Collector lifecycle persistence from Security observation, evaluation, and
  current projection persistence. Persistence retry reuses the observation.
- PASS/OPEN/severity and evidence are deterministic; AI does not determine them.
  The pipeline has no Graph writes or auto-remediation.

Architecture controls closed: capability gate, lower-tier execution contract,
app-only Security runtime, generic Security orchestrator, Collector lifecycle,
Security persistence, generic product surface, and Scenario Agent authentication
separation.

### Accepted live Rule #7 evidence

`M365-ENTRA-CA-ENFORCEMENT-001` was `ENTRA_P1: ENTITLED`, gate `COLLECT`, with
the lower-tier `NOT_ENTITLED` contract passing. App-only authentication used
`Policy.Read.All`; no delegated, device-code, Scenario Agent, or interactive action
was used. Graph evidence was `G01-011`, HTTP `200`, one page.

Lifecycle: collection run `8`, endpoint run `13`, endpoint `PASS`, collection
`SUCCESS`, error classification `PASS`, stale `RUNNING: 0`. Security observation,
evaluation, current projection, retry idempotency, and duplicate-row checks passed;
no second Graph collection occurred.

Aggregate: **3 total Conditional Access policies, 0 enabled, 2 report-only, and
1 disabled**. Finding: `OPEN`, `MEDIUM`, scope
`CONDITIONAL_ACCESS_ENFORCEMENT_PRESENCE_ONLY`. Accepted interpretation: **No
Conditional Access policy is actively enforced.** This does not prove MFA absence,
MFA user/admin/all-user coverage, authentication strength, Identity Protection
coverage, Security Defaults state, or overall tenant authentication posture. Each
requires separate deterministic evidence.

### Current seven-rule snapshot

| Rule | Category | State | Severity | Required capability | Acceptance |
| --- | --- | --- | --- | --- | --- |
| `M365-SP-EXT-001` | SharePoint / OneDrive External Sharing | `OPEN` | `MEDIUM` | None recorded | Offline: PASS |
| `M365-ENTRA-CONSENT-001` | Application Security / User Consent | `NOT_EVALUATED` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-RISKY-CONSENT-001` | Application Security / Risky Application Consent | `NOT_EVALUATED` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-GUEST-001` | External Collaboration / Guest Invitations | `OPEN` | `MEDIUM` | None recorded | Offline: PASS |
| `M365-ENTRA-GUEST-ACCESS-001` | External Collaboration / Guest Directory Access | `PASS` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-GA-001` | Privileged Access / Global Administrators | `OPEN` | `HIGH` | None recorded | Offline: PASS |
| `M365-ENTRA-CA-ENFORCEMENT-001` | Authentication / Conditional Access | `OPEN` | `MEDIUM` | `ENTRA_P1` | Live: PASS |

Persisted evaluations: **7**. Read-only product evidence: summary HTTP `200`,
findings HTTP `200`, Rule #7 detail HTTP `200`, dashboard generic rendering `PASS`.
Accepted full regression baseline: **684 PASS**.

```text
Graph_reads: 0
Graph_writes: 0
DB_writes: 0
DB_schema_changed: NO
Entra_changed: NO
Scenario_changed: NO
Intune_touched: NO
```
