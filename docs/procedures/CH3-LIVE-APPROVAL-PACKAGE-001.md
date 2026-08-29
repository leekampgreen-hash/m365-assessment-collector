# CH3-LIVE-APPROVAL-PACKAGE-001: Live Scenario Agent Approval Package

## Purpose

This document is the single source of truth for CH3 live acceptance readiness.
It records the approved status of the preceding security gates and defines the
bounded operator authorization required before the first controlled live
Scenario Agent validation.

This package does not authorize authentication, Microsoft Graph calls, Entra
changes, permission changes, credential creation, or live execution by itself.
Actual runtime values must remain outside source control, logs, prompts, and
evidence.

## Architecture Approval

**Reference**

ADR: `CH3-AUTH-001`

**Status**

`ACCEPTED`

**Identity Model**

**Scenario Agent:**

- Delegated user identity
- OAuth2 device code
- Delegated permission `User.Read`

**Collector:**

- App-only service principal
- Client credentials
- Application permissions

The Scenario Agent and Collector identities remain separate. The Collector
identity is not permitted for Scenario Agent live validation.

## Security Review Approval

**Record**

`CH3-SCENARIO-SECURITY-REVIEW-003`

**Status**

`APPROVED`

**Controls verified:**

- Identity boundary
- Token lifecycle
- Actor verification
- Evidence sanitization
- Live execution gate

## Security Remediation Approval

**Record**

`CH3-LIVE-SECURITY-REMEDIATION-002`

**Status**

`COMPLETED`

**Controls:**

- Token cleanup
- Evidence protection
- Device-code safety

## Storage Boundary Approval

**Record**

`CH3-LIVE-AUDIT-STORAGE-REVIEW-002`

**Status**

`APPROVED`

**Controls:**

- `ScenarioEvidenceBoundary`
- `ScenarioEvidenceWriter`
- Fixed persistence schema

## Operator Console Approval

**Record**

`CH3-LIVE-OPERATOR-CONSOLE-REVIEW-001`

**Status**

`APPROVED`

**Controls:**

- Transient prompt handling
- No challenge persistence
- No token exposure

## DEV Live Authorization Template

Complete this section outside source control for the specific approved run.
Do not record actual identity values, device codes, tokens, secrets, or
authentication artifacts in this document.

**Actor:** `<dedicated test user>`

**Execution Window:** `<approved window>`

**Scope:** `INTERACTIVE_SIGNIN ONLY`

**Graph Endpoint:** `GET /me`

**Restrictions:**

- No writes
- No permission changes
- No Entra mutation
- No Collector identity
- No client secret

## Runtime Preconditions

The following checklist must be verified by the operator using approved runtime
configuration. Values themselves must not be entered in this document.

- [ ] `SCENARIO_CLIENT_ID` available
- [ ] `SCENARIO_TENANT_ID` available
- [ ] Expected actor object ID available
- [ ] Expected actor UPN available
- [ ] `SCENARIO_CLIENT_SECRET` absent
- [ ] Collector credentials unavailable

## Final Gate

Live execution is prohibited until:

- Approval package exists
- Runtime values verified
- Operator authorization completed

## Offline Validation Record

This package is intended to be checked offline for document consistency and for
the absence of secrets, tokens, device codes, and forbidden Collector
credentials. No authentication, Microsoft Graph call, Entra mutation,
permission change, or live execution is part of this validation.
