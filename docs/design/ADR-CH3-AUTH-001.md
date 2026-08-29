# ADR-CH3-AUTH-001: Scenario Agent Canonical Identity

## Status

Accepted - 2026-08-24

## Problem Statement

CH3 documentation contained an identity conflict. The original Scenario Agent
design uses a dedicated test user, device-code authentication, and delegated
Microsoft Graph permissions. A later implemented candidate instead uses an
app-only service principal and the OAuth 2.0 client-credentials flow. These
models have materially different identity attribution, authorization, and audit
properties and cannot both be canonical.

## Decision

The canonical CH3 Scenario Agent identity is a **delegated user identity**.

The Scenario Agent authenticates a dedicated test user through OAuth 2.0 device
code authentication and uses the resulting delegated Microsoft Graph token for
scenario execution. Delegated permissions are selected per approved scenario
test case and remain least-privileged.

The Collector remains a separate app-only workload. It authenticates its
service principal through OAuth 2.0 client credentials and uses Microsoft Graph
application permissions for unattended, read-focused collection.

## Rejected Alternative

The Scenario Agent must not use an app-only service principal as its canonical
identity. The app-only client-credentials implementation is a candidate
implementation only; it is not an approved canonical Scenario Agent runtime.

## Reasoning

A service principal attributes activity to an application identity. That is
appropriate for the unattended Collector, but it is different from
user-attributable scenario execution. CH3 scenarios require a traceable,
dedicated test-user actor so Entra sign-in logs, Microsoft 365 audit records,
and scenario evidence can be reconciled to the user who performed the action.

Using delegated identity also prevents Scenario Agent execution from inheriting
the Collector's broad application-permission model. The distinct identity and
permission types maintain least privilege and preserve the intended trust
boundary.

## Audit Model

- Each Scenario Agent run records its dedicated test-user identity and scenario
  correlation information.
- Scenario Graph activity is attributable to that user in relevant Entra
  sign-in logs and Microsoft 365 audit or activity records.
- Collector activity is attributed to its service principal, not to a user.
- Scenario and Collector evidence must identify the applicable identity type;
  service-principal records are not evidence of canonical Scenario execution.

## Security Controls

- Scenario Agent uses dedicated test users only; routine scenarios do not use
  employee or privileged administrator accounts.
- Scenario Agent uses delegated permissions only, added per approved test case.
- Scenario Agent does not receive Collector application permissions.
- Collector uses application permissions only for unattended read-focused work.
- The registrations, credentials, consent grants, token handling, and audit
  trails remain separate.
- Tokens, secrets, passwords, and authentication headers must not be committed
  to documentation, evidence, logs, or prompts.

## Separation of Responsibilities

| Component | Canonical identity | Authentication | Graph permission type | Purpose |
| --- | --- | --- | --- | --- |
| Scenario Agent | Dedicated test user | OAuth 2.0 device code | Delegated | Controlled, user-attributable scenario execution |
| Collector | Service principal | OAuth 2.0 client credentials | Application | Unattended, read-focused collection |

## Consequences

- Future CH3 Scenario Agent execution and validation must follow the delegated
  identity model.
- App-only Scenario evidence may be retained as candidate implementation
  evidence but must clearly state that it is not canonical or approved for
  Scenario execution.
- Any future change to this identity decision requires a new approved ADR and
  explicit reconciliation of audit, authorization, and security controls.
