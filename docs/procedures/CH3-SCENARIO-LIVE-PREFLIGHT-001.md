# CH3-SCENARIO-LIVE-PREFLIGHT-001: Scenario Live Validation Readiness

## Purpose

This document records the offline readiness checks required before
`CH3-SCENARIO-LIVE-VALIDATION-001`. It does not authorize authentication, a
Microsoft Graph call, Entra changes, permission changes, or Collector identity
usage. Runtime identity values remain operator-provided inputs and must not be
recorded in this document.

## 1. Architecture Approval Status

| Field | Status or model |
| --- | --- |
| ADR | `CH3-AUTH-001` |
| Status | Accepted |
| Scenario Agent identity | Delegated user identity |
| Scenario Agent authentication | Device code authentication |
| Scenario Agent permission | Delegated permission |
| Collector identity | App-only service principal |
| Collector authentication | Client credentials |

The Scenario Agent and Collector identities, credentials, permissions, and
audit boundaries are separate. The Collector identity is not permitted for
Scenario Agent live validation.

## 2. Security Approval Status

Completed controls:

- Token lifecycle remediation
- Device-code sanitization
- Evidence boundary
- Storage boundary
- Persistence writer

References:

- `CH3-SCENARIO-SECURITY-REVIEW-003`
- `CH3-LIVE-SECURITY-REMEDIATION-002`
- `CH3-LIVE-AUDIT-STORAGE-REVIEW-002`

## 3. Required Live Configuration Checklist

The following values must be supplied through the approved runtime
configuration for the specific, operator-approved run. Actual values must not
be stored in this document, source control, logs, prompts, or evidence.

Required:

- `SCENARIO_CLIENT_ID`
- `SCENARIO_TENANT_ID`
- `SCENARIO_EXPECTED_ACTOR_OBJECT_ID`
- `SCENARIO_EXPECTED_ACTOR_UPN`

Must not exist in the Scenario Agent runtime configuration:

- `SCENARIO_CLIENT_SECRET`
- Collector credential reference

## 4. Live Execution Scope

Allowed:

- `INTERACTIVE_SIGNIN`

Expected Graph operation:

- `GET /me`

Not allowed:

- Graph writes
- Permission changes
- Entra mutations
- Collector identity usage

The `GET /me` operation is limited to actor verification. It is not a
general-purpose Graph query capability.

## 5. Operator Approval Checklist

Before live run:

- [ ] Approved test user selected
- [ ] Execution window approved
- [ ] Scenario app verified
- [ ] Expected actor verified
- [ ] Live gate enabled explicitly
- [ ] Evidence review planned

The live gate must remain disabled unless and until the authorized operator
approves the specific bounded run.

## 6. Stop Conditions

Stop immediately, disable the live gate, and retain only sanitized failure
evidence if any of the following occurs:

- Missing runtime config
- Actor mismatch
- Unexpected permissions
- Token leakage
- Evidence leakage
- Collector identity detected

No alternate account, retry, scope change, permission change, or endpoint
substitution is allowed after a stop condition within the same approval.

## Offline Readiness Validation

This readiness package was checked offline for:

- Document consistency with `CH3-AUTH-001` and
  `CH3-SCENARIO-LIVE-VALIDATION-001`
- Completeness of the required and prohibited configuration checklist
- Absence of secret values, token values, device codes, and Collector
  credential references

No authentication, Microsoft Graph call, Entra mutation, permission change, or
Collector credential access is part of this validation.
