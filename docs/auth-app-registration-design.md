# Authentication & App Registration Design

> **Task:** G04-001 — Authentication & App Registration Design
> **Mode:** DESIGN / DOCUMENTATION ONLY
> **Baseline:** G01 API Inventory (19 PASS), G02 Permission Matrix, G03 Data Catalog
> **Scope:** Defines the authoritative authentication and Microsoft Entra application-registration design for the Graph Agentic Collector project.
> **Out of scope for G04-001:** Source-code implementation, Entra ID modifications, secret material handling, G04-002 / G05 kickoff.

---

## 0. Architecture Baseline

The project intentionally separates two security principals. They MUST NOT be collapsed into one broad "super-agent". Each principal has a distinct identity, a distinct permission model, a distinct authentication flow, and a distinct responsibility boundary.

**CH3 authority:** Per `docs/design/ADR-CH3-AUTH-001.md`, the delegated
dedicated-test-user model is the canonical and approved Scenario Agent identity.
Scenario has no app-only implementation or client-secret configuration. The
Collector app-only model remains separate and is not a substitute for Scenario
Agent user attribution.

| Principal | Logical name (DEV) | Identity type | Auth flow | Purpose |
|---|---|---|---|---|
| **Graph Collector App** | `graph-agent-collector-dev` | App-only (service principal) | OAuth 2.0 client credentials | Unattended, read-focused Graph collection |
| **Scenario Agent App** | `graph-agent-scenario-dev` | Delegated user context | OAuth 2.0 device code (DEV) | Controlled test-user scenario execution |

These are two **separate** Microsoft Entra application registrations. They share
no client ID, secret, certificate, admin-consent grant, configuration source,
runtime secret mount, or audit attribution. The Scenario public-client
configuration contains only its tenant and client IDs; a dedicated test user's
interactive sign-in is its credential.

This design preserves the documented G02 finding that `Organization.Read.All` was **not** present in the Collector runtime token at discovery time, yet the Organization endpoint returned HTTP 200. That behavior is reproduced in this design as a "documented vs observed" classification — it is **not** used as justification to add the permission.

---

## 1. Security Principal Responsibilities

### 1.1 Graph Collector App

- App-only identity (service principal with application permissions only).
- Unattended collector execution (no interactive user, no user prompt).
- Read-focused Microsoft Graph access across the 19 endpoints catalogued in `docs/api-inventory.md` and the data catalog rows in `docs/data-catalog.md`.
- No user impersonation under any circumstance.
- No scenario-generation actions (Collector never writes, creates, updates, deletes, invites, or provisions).
- Least-privilege application permissions only (see Section 3).
- Credentials stored outside source code and outside this document (see Section 6).

### 1.2 Scenario Agent App

- Delegated user identity (signed-in user context required for every Graph call).
- Controlled scenario / test actions only.
- Dedicated test users only (see Section 5).
- No collector-wide application permissions baseline (see Section 4).
- User context must remain attributable in Microsoft 365 unified audit log, Entra sign-in log, and activity records.
- No production-user automation in the DEV design.
- Interactive (device-code) authentication during DEV is acceptable; production-equivalent authentication is out of scope for G04-001 and must be reviewed separately.

### 1.3 Responsibility Matrix

| Responsibility | Graph Collector App | Scenario Agent App |
|---|:---:|:---:|
| Unattended batch collection | ✓ | ✗ |
| Read-only / read-focused Graph access | ✓ | ✓ (per scenario) |
| Application permissions baseline | ✓ | ✗ |
| Delegated user context | ✗ | ✓ |
| User impersonation | ✗ | ✗ (only dedicated test users) |
| Scenario / test actions | ✗ | ✓ |
| Write / mutation Graph calls | ✗ | ✗ in DEV baseline (added per approved testcase only) |
| Audit / sign-in attribution to a user | N/A (app-only) | ✓ (required) |
| Production-realistic credential posture | future-only (see §6) | future-only |
| Credential storage outside repo | ✓ | ✓ |

---

## 2. Authentication Flows

### 2.1 Collector — OAuth 2.0 Client Credentials

Conceptual flow:

```
Graph Collector App
  → POST to Microsoft identity platform token endpoint (tenant-specific authority)
      with grant_type=client_credentials, client_id, client_secret, scope=https://graph.microsoft.com/.default
  → receives app-only access token (no refresh token)
  → calls Microsoft Graph endpoints with that token
  → obtains a fresh token whenever the previous token is missing, expired, or invalid
```

Properties:

- **Authority:** tenant-specific Microsoft identity platform endpoint (e.g. `https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token`). The exact authority string is loaded at runtime from configuration — never embedded in source.
- **client_id:** the application (client) ID of the `graph-agent-collector-dev` registration.
- **client_secret:** loaded at runtime from an external environment file or secret mount (see §6). DEV-only secret.
- **scope:** `https://graph.microsoft.com/.default` (the `.default` scope for a Microsoft Graph v2.0 token request against an app registration that has Graph application permissions granted via admin consent).
- **No refresh token:** client credentials grants issue access tokens only; the Collector obtains a fresh token when required.
- **No user context:** tokens carry `oid`/`sub` of the service principal, not of any user.
- **No secrets in code or docs:** secrets are never written to this document, never committed, never logged, never passed to any AI prompt.

### 2.2 Scenario Agent — OAuth 2.0 Device Code (DEV)

Conceptual flow:

```
Scenario Agent
  → POST to /oauth2/v2.0/devicecode for the tenant
  → displays user_code + verification URL to the operator
  → dedicated test user authenticates at microsoft.com/devicelogin and approves
  → Scenario Agent polls /oauth2/v2.0/token with grant_type=urn:ietf:params:oauth:grant-type:device_code
  → receives delegated access token (and refresh token when `offline_access` scope is requested)
  → calls Microsoft Graph as that test user
  → refreshes the token when expired; re-authenticates interactively on invalid_grant / MFA / CA failures
```

Properties:

- **Delegated token / user context:** the access token carries the test user's identity. Every Graph call is attributable to that user in Entra sign-in logs and Microsoft 365 audit logs.
- **User vs admin consent:** individual-user delegated scopes that are not admin-restricted can be consented to by the signing-in user. Admin-restricted scopes (e.g. anything that reads directory-wide data on behalf of an app that has no admin grant) require an admin to grant tenant-wide admin consent before sign-in. Scenario Agent DEV baseline is limited to `User.Read` (individual scope); additional delegated scopes are added per approved testcase (§4).
- **Refresh tokens:** handled conceptually — stored in memory only for the duration of a scenario run, never written to disk, never logged, never committed, never pasted into prompts or documentation.
- **Interactive DEV use:** the device-code UX is acceptable for DEV because the operator and the test user can be co-located or can follow a documented handoff. Non-interactive flows for Scenario Agent are out of scope for G04-001.
- **Production authentication:** must be reviewed separately (interactive headless, ROPC, or a managed-identity-equivalent flow are candidates — none are designed or recommended in this document).

---

## 3. Collector Permission Model

The authority for the current Collector application permission set is `docs/permission-matrix.md`. The current runtime-confirmed baseline, derived from the discovery token (`discovery-state.json`) at the G01 final workflow state, is:

### 3.1 Confirmed Required (present in token at discovery; endpoints returned HTTP 200)

| Permission | Endpoints | Status |
|---|---|---|
| `User.Read.All` | G01-001 | CONFIRMED_REQUIRED |
| `Group.Read.All` | G01-002 | CONFIRMED_REQUIRED |
| `LicenseAssignment.Read.All` | G01-004 | CONFIRMED_REQUIRED |
| `AuditLog.Read.All` | G01-005, G01-006 | CONFIRMED_REQUIRED (shared) |
| `Application.Read.All` | G01-007, G01-008 | CONFIRMED_REQUIRED (shared) |
| `Device.Read.All` | G01-009 | CONFIRMED_REQUIRED |
| `AdministrativeUnit.Read.All` | G01-010 | CONFIRMED_REQUIRED |
| `Policy.Read.All` | G01-011, G01-012 | CONFIRMED_REQUIRED (shared) |
| `IdentityRiskyUser.Read.All` | G01-013 | CONFIRMED_REQUIRED |
| `IdentityRiskEvent.Read.All` | G01-014 | CONFIRMED_REQUIRED |
| `ServiceHealth.Read.All` | G01-015, G01-016 | CONFIRMED_REQUIRED (shared) |
| `ServiceMessage.Read.All` | G01-017 | CONFIRMED_REQUIRED |
| `RoleManagement.Read.Directory` | G01-018, G01-019 | CONFIRMED_REQUIRED (shared) |

These are 13 confirmed-required unique application permissions spanning all 19 endpoints except G01-003.

### 3.2 `Organization.Read.All` — Documented vs Observed (preserved)

| Attribute | Value |
|---|---|
| Endpoint | G01-003 (`/v1.0/organization`) |
| Documented permission | `Organization.Read.All` |
| Permission present in Collector token at discovery | **No** |
| Final HTTP status | **200** (1 page, 1 row) |
| Final classification | **PASS** |
| Permission status | **OBSERVED_WITHOUT_DOCUMENTED_ROLE** |

This design **explicitly preserves** that finding:

- `Organization.Read.All` is a documented Microsoft Graph application permission for the Organization endpoint.
- It was **not** present in the original Collector runtime permission set.
- The endpoint nevertheless returned HTTP 200 with required fields.
- It is classified here as **documented vs observed behavior**, not as a runtime-requirement gap.
- The design **does not recommend** granting `Organization.Read.All` merely to make the documentation look symmetric, and does not grant it in G04-001 (G04-001 makes no Entra changes).

If a future Gxx task observes that the Organization endpoint stops returning 200 without `Organization.Read.All`, that task must record the new evidence, classify it `CONFIRMED_REQUIRED`, and update both `docs/permission-matrix.md` and the Collector registration together.

### 3.3 Governing Principles for the Collector Permission Set

- Permissions are added **only** when (a) an endpoint demonstrates a confirmed runtime requirement, or (b) an approved design requirement exists in writing.
- No broad `Directory.Read.All` shortcut. `Directory.Read.All` would over-grant relative to the actual endpoint set; the per-endpoint least-privilege roles above are the maintained baseline.
- No write permissions for the Collector in this scope. Any future write permission requires a separately approved future scope (out of G04-001).
- No `Mail.Read`, `Calendars.Read`, `Files.Read`, `Notes.Read`, or other workload permissions that are not required by the G01 inventory and that would expand the data surface.
- Permission source for this design is `docs/permission-matrix.md` and `config/api_inventory.json`. Any drift between this design and those files must be resolved in favor of the matrix (the matrix is the authority) and recorded.

---

## 4. Scenario Agent Permission Model

### 4.1 Current Baseline

| Attribute | Value |
|---|---|
| Identity type | Public client (device-code capable) |
| Delegated permission baseline | `User.Read` |
| Application permission baseline | None |
| Consent posture | User-consent scope where possible; admin consent only when a required scope is admin-restricted |

`User.Read` is the only baseline delegated permission for the Scenario Agent in G04-001. It is required for any delegated Microsoft Graph session to function and to attribute activity to the signing-in test user.

### 4.2 Future Permission Expansion — Controlled Process

Scenario Agent permissions are **not** pre-granted in bulk. Each new permission is the result of an approved scenario testcase. The process is:

1. **Scenario requirement** — a specific testcase identifies the Graph operation needed (e.g. read a user's mailbox metadata, list a user's OneDrive root, create a calendar event).
2. **Operation mapping** — the exact Microsoft Graph operation, endpoint, and method are documented.
3. **Delegated permission identification** — the minimum delegated permission required for that operation, in its least-privileged form, is identified (prefer `*.Read` over `*.ReadWrite`; prefer user-scoped over directory-scoped).
4. **Privilege / risk assessment** — the privilege tier, blast radius, and audit-attribution implications are reviewed. Admin-restricted scopes trigger an explicit admin review.
5. **Admin review (if required)** — admin-restricted scopes are escalated and tenant-wide admin consent is requested only after explicit approval.
6. **Minimum-permission grant** — only the approved scope is added to the Scenario Agent registration. No "while we're here" extras.
7. **Execution** — the scenario runs against the dedicated test user; the registration's effective permission set is verified before each run.
8. **Validation** — resulting Graph data and audit/sign-in records are reviewed to confirm the scenario produced the expected attribution and side effects.
9. **Retention / removal** — temporary scenario permissions are removed after the testcase completes; durable permissions are retained only with a documented ongoing test justification.

The Scenario Agent **does not** receive Collector-wide application permissions. Mixing scenario permissions into the Collector registration — or Collector permissions into the Scenario Agent registration — purely for convenience is forbidden (see §9).

---

## 5. Test Identity Boundary

The Scenario Agent operates **only** against dedicated test identities. This is a non-negotiable boundary in the DEV design.

Requirements:

- **Dedicated test users.** A pool of test-user identities is reserved exclusively for scenario execution. Test users are identifiable as test users (display name convention / UPN convention) and are not shared with production work.
- **Licensed for workloads required by scenarios.** A test user holds the licenses needed for the operations its scenarios perform (e.g. an Exchange Online license for mailbox scenarios, a SharePoint license for site scenarios).
- **No administrator accounts for ordinary scenarios.** Global Administrator, Privileged Role Administrator, and similar privileged directory roles are not used as routine test identities. A scenario that legitimately needs an admin role must (a) be explicitly approved and (b) use a dedicated admin test identity, not a shared human admin account.
- **No normal employee accounts.** Real employee identities, contractor identities, or any account tied to a real person's day-to-day work are excluded from the test pool.
- **Attributable activity.** Every scenario run records the test user identity used (UPN / object id). This enables audit reconstruction: a scenario event in Entra sign-in logs or in the M365 unified audit log must be traceable to a specific test user identity, not to a shared or anonymous context.
- **Scenario execution records the identity used.** The scenario evidence must record which test identity performed each scenario action.

This document does **not** copy or reproduce passwords, tokens, MFA factors, device-bound credentials, FIDO keys, certificate-thumbprint authentication material, or any other authentication method. Those artifacts remain in the secrets store and in operator workflow, never in this design.

---

## 6. Credential Management

### 6.1 DEV Design

**Collector (`graph-agent-collector-dev`):**

- A client secret is **allowed** in DEV (lowest-friction option for an unattended service-principal scenario during development).
- The secret is loaded at runtime from an external environment file or a secret mount that is mounted into the Collector process at start.
- The secret file / mount is **never** committed to Git.
- The secret file / mount is **never** emitted to logs (no `print`, no `logging.info`, no exception traceback).
- The secret value is **never** included in agent prompts, AI tool evidence, scratchpads, or repository documentation (including this file).
- The Collector process treats the secret as opaque bytes from the loader and passes it directly to the token endpoint.

**Scenario Agent (`graph-agent-scenario-dev`):**

- Public-client device-code flow — there is **no client secret** for the Scenario Agent itself in DEV. The "credential" the operator supplies is the test user's interactive authentication at `microsoft.com/devicelogin`.
- Delegated access tokens and refresh tokens are **not** committed, documented, logged, or pasted anywhere. They live in the Scenario Agent process memory for the duration of a scenario run.
- The Scenario Agent does not persist tokens across runs in DEV baseline.

### 6.2 Future Production Recommendation (DESIGN ONLY)

The following are **design recommendations**, not implementations in G04-001:

- Prefer **certificate-based credentials** or **workload identity / managed identity** over client secrets where the architecture and platform permit.
- A documented **credential rotation procedure** must exist for any credential type in use.
- DEV and PROD use **separate** registrations, separate credentials, and separate consent grants.
- Secret material in PROD must use a managed secret store (Azure Key Vault or equivalent) with audit, rotation, and access-policy controls.
- DEV secrets must never be reused in PROD.

---

## 7. Environment Separation

Logical separation recommended:

| Environment | Collector registration | Scenario Agent registration | Notes |
|---|---|---|---|
| **DEV** | `graph-agent-collector-dev` | `graph-agent-scenario-dev` | Active in G04 scope; secrets loaded from external secret source |
| **Future PROD** | separate Collector registration (not yet created) | separate Scenario Agent registration if scenario functionality exists in PROD | Independent credentials, independent consent, independent audit trail |

Rules:

- DEV and PROD credentials are independent.
- No DEV secret/token is reused in PROD.
- No DEV admin consent grant is reused in PROD.
- PROD registrations are **not** created in G04-001 (this task makes no Entra modifications).

---

## 8. Trust Boundaries

The following trust boundaries are recognized in the design. Each boundary has a clear owner and a clear prohibition on what crosses it from the outside inward into a sensitive context.

| Boundary | Owner | Inside the boundary | Outside the boundary | What MUST NOT cross inward |
|---|---|---|---|---|
| Microsoft Entra ID | Microsoft | Identity store, app registrations, consent, conditional access, sign-in log | The collector / scenario agent / operator / AI tooling | Tenant admin credentials to the operator side; tenant data to AI tooling |
| Microsoft Graph | Microsoft | Graph API surface, audit, activity log | The collector / scenario agent | Production user data to AI tooling; raw payloads to AI prompts |
| Graph Collector App | Project | Reads via application permissions only | Operator host / container, AI tooling | Nothing — the Collector is the consumer, not a producer of credentials to other systems |
| Scenario Agent App | Project | Delegated Graph actions as test users | Operator host / container, AI tooling | Production user context; real user data |
| Project host / container | Project | Process boundary for the Collector and the Scenario Agent | Developer workstation, CI runner, AI tooling | Secret files mounted into the container; tokens held by the process |
| Secrets storage | Project | Client secrets, future certificates, future Key Vault references | Source code, documentation, AI prompts | The secret **value** to source, docs, or AI prompts; the secret **reference** may exist in env-var-name form in operator runbooks only |
| Database / storage layer | Project | Collected Graph data, scenario evidence | The Collector process boundary | Raw Graph payloads beyond the data-catalog fields; secrets |
| External AI / model / router services | Third party | Reasoning, planning, summarization | The project process boundary | **Client secrets, access tokens, refresh tokens, passwords, production credentials, or any authentication material** |

Concrete rules for the external AI/model/router boundary:

- AI tooling MUST NOT receive client secrets, access tokens, refresh tokens, passwords, certificate private keys, or any production credential.
- Agent prompts use only the metadata / configuration needed for reasoning (endpoint path, documented permission class, result classification, evidence filename) — never authentication material.
- Evidence written by an AI-assisted workflow is reviewed for credential leakage before commit.

---

## 9. Authorization Governance

Permission changes — application or delegated, for either registration — must be governed. Each change must record:

- **Business / test purpose** — why this permission is being added.
- **Endpoint / operation mapping** — which Graph endpoint or operation is the permission for.
- **Permission type** — Application (Collector) or Delegated (Scenario Agent). Application permissions must never be added to the Scenario Agent, and Collector-wide application permissions must never be added to the Scenario Agent.
- **Least-privilege justification** — why this exact scope is the minimum necessary.
- **Approval requirement** — who approved (operator, tenant admin, project owner) and where the approval is recorded.
- **Validation evidence** — proof that the endpoint returned the expected success response and that audit / sign-in records reflect the expected attribution.

Additional rules:

- Collector and Scenario Agent permissions are **never** mixed merely for convenience.
- A new application permission is **never** added in bulk. If the Collector ever needs a write permission, that addition is a separately approved future scope.
- A new delegated permission for the Scenario Agent is **never** added in bulk. Each is tied to a specific approved testcase (see §4.2).
- `Directory.Read.All` and similar broad directory-wide scopes remain excluded unless an explicit, evidence-backed exception is approved.

---

## 10. Failure / Security Conditions (Conceptual Handling)

This section describes the **expected** classification of common failure responses, not a retry implementation. Retry logic, backoff, and alerting are out of scope for G04-001.

| Condition | Typical indicator | Classification | Conceptual response |
|---|---|---|---|
| `invalid_client` | OAuth token endpoint returns 400 with `invalid_client` | **Authentication failure** — client_id not recognized, app not found, or platform-side issue. For a credential scenario this is typically the wrong client_id or a misconfigured app registration; for a confidential-client scenario it can also be a wrong / rotated secret. | Fail loudly; do not retry with the same credential. Operator must verify the Collector app registration and credential. |
| Invalid / expired client secret | Token endpoint returns 400 with `invalid_client` or `invalid_grant` specific to credential failure | **Authentication failure** | Fail loudly. Rotate the secret via the documented procedure; never log the secret value. |
| Invalid / expired access token | Graph returns 401 with `invalid_token` / `ExpiredToken` / `AuthenticationMissing` | **Authentication failure** | Obtain a fresh token (client_credentials for Collector; refresh-token flow or re-auth for Scenario Agent) and retry the call exactly once. If still failing, surface as authentication failure. |
| Insufficient privileges / HTTP 403 | Graph returns 403 with `Authorization_RequestDenied` / `insufficient privileges` | **Authorization failure**, not authentication failure | Surface; classify the operation as `PERMISSION_REQUIRED` (mirrors the G01 taxonomy); do not silently add permissions. |
| Consent missing | Token endpoint returns `invalid_grant` with `consent_required` or Graph returns 403 with admin-consent-required descriptor | **Authorization / configuration failure** | Operator/admin must grant the required consent; the system must not auto-consent in the design baseline. |
| User authentication failure (device code) | Device-code polling returns `authorization_pending`, `authorization_declined`, `expired_token`, or `invalid_grant` due to MFA / Conditional Access | **Authentication failure** for that user | Re-prompt with a fresh device code or escalate to operator; record which test user failed and why. |
| Conditional Access blocking delegated login | Token endpoint or downstream Graph returns 401/403 with CA-policy descriptor | **Authentication / authorization failure** (policy decision) | Surface; do not bypass CA. Configuration (named location, compliant device, MFA factor) is owned by tenant admin. |
| Throttling | Graph returns 429 (`throttledRequest`, `tooManyRequests`) | **NOT an authentication failure** | Respect `Retry-After`; defer. Throttling is rate-limit telemetry, not a credential or permission issue. |
| Network / transport error | Connection reset, DNS failure, TLS error | **Transient infrastructure** | Retry with backoff per platform guidance. Not an authentication or authorization condition. |

In all conditions above, no secret value, token value, or refresh-token value is written to logs, prompts, or evidence.

---

## 11. Architecture Decisions (ADRs)

### ADR-G04-01 — Separate Collector and Scenario Agent application registrations

- **Decision.** The project uses two distinct Microsoft Entra app registrations: `graph-agent-collector-dev` for unattended collection and `graph-agent-scenario-dev` for controlled test-user activity. They are not merged.
- **Rationale.** The two principals have fundamentally different identity types (app-only vs delegated user), different audit-attribution requirements, and different trust profiles. Collapsing them into a single "super-agent" would require granting the same registration both broad application permissions and delegated user actions, which violates least privilege, obscures audit attribution, and makes revocation / rotation harder.
- **Consequence.** Two registrations to create, govern, and rotate. Consent grants are duplicated where a permission is needed by both (rare; usually the Collector has its own read-only app permissions and the Scenario Agent has its own narrow delegated scopes). Operator workflow must select the right registration per task.

### ADR-G04-02 — Collector uses application permissions and OAuth 2.0 client credentials

- **Decision.** The Collector authenticates as itself (app-only) using the client credentials grant.
- **Rationale.** Unattended batch collection has no interactive user. Client credentials is the only Microsoft identity platform flow that issues tokens without a user. The Collector does not impersonate any user and does not need delegated user context.
- **Consequence.** The Collector registration holds application permissions only and never holds delegated permissions. Tokens carry the service principal identity, not a user. Audit records for Collector activity in Entra sign-in logs are attributable to the service principal, not to a user.

### ADR-G04-03 — Scenario Agent uses delegated permissions and dedicated test users

- **Decision.** The Scenario Agent authenticates interactively (device-code in DEV) as a dedicated test user and acts under that user's delegated context.
- **Rationale.** Scenario execution must be attributable to a specific user identity so that audit / sign-in / activity records can be reconstructed. The Scenario Agent must not gain application permissions; doing so would let it bypass user-context attribution for write-side or read-side actions. Dedicated test users (not admins, not real employees) bound scenario activity to testable, attributable identities.
- **Consequence.** Scenarios run interactively in DEV. Each scenario records which test user was used. Refresh tokens are scoped to the scenario run. Scenario permissions are added per testcase, not in bulk (see §4.2). Production-equivalent non-interactive flows are a separate design.

### ADR-G04-04 — Least privilege; no Directory.Read.All shortcut

- **Decision.** The Collector holds 13 confirmed-required unique application permissions mapped to specific endpoints, none of them `Directory.Read.All`. New permissions are added only on confirmed runtime requirement or approved design requirement.
- **Rationale.** `Directory.Read.All` is a directory-wide role that subsumes several of the per-endpoint roles actually needed; granting it would violate least privilege and expand the blast radius of a compromised Collector credential. The per-endpoint mapping in `docs/permission-matrix.md` is the authority.
- **Consequence.** Permission maintenance is per-endpoint, which is more work but auditable. The Collector registration is the minimum viable set; an operator reviewing it can see exactly which endpoint each role supports. Any future "we can't find which permission this needs" question is resolved by re-running the endpoint against an expanded-permission probe and recording evidence, not by granting `Directory.Read.All` as a shortcut.

### ADR-G04-05 — DEV client secret is temporary; production credential mechanism reviewed separately

- **Decision.** DEV uses a client secret for the Collector for lowest-friction unattended execution. PROD will not use a long-lived shared secret if certificate-based or workload-identity alternatives are available.
- **Rationale.** A client secret in DEV is acceptable for early development. Production credentials require rotation, audit, and ideally keyless posture. Deferring the PROD credential decision keeps G04-001 focused on the design baseline and avoids committing to a credential mechanism that may not suit the eventual hosting platform.
- **Consequence.** The DEV secret must be rotated on the documented schedule and must not be reused in PROD. A future task must select the PROD credential mechanism (certificate, managed identity, Key Vault–backed secret) and document rotation. This design does not commit to a specific PROD mechanism.

### ADR-G04-06 — Secrets / tokens never enter AI prompts or repository documentation

- **Decision.** Client secrets, access tokens, refresh tokens, passwords, certificate private keys, and any other authentication material MUST NOT appear in this document, in commit messages, in AI agent prompts, in evidence files, in log lines, or in test fixtures.
- **Rationale.** Once a secret is committed or pasted into a prompt, it is effectively broadcast to whatever system retains that text — version control, AI training / context retention, logs, backups. Treat all authentication material as unprintable.
- **Consequence.** Operators and AI tooling must reference credentials by configuration name (e.g. `GRAPH_CLIENT_SECRET` env var) not by value. Evidence files must redact token-bearing headers. The project host / container / secrets store is the only place where secret values exist at rest.

---

## 12. Validation (Offline)

Verification performed offline against existing project artifacts. No Microsoft Graph calls, no Entra modifications, no source / config / state changes.

| Check | Result |
|---|---|
| Document created | ✓ — `docs/auth-app-registration-design.md` |
| Both application roles clearly separated | ✓ — see §0, §1 |
| Collector auth flow documented | ✓ — §2.1 (client credentials) |
| Scenario auth flow documented | ✓ — §2.2 (device code, delegated) |
| Application vs Delegated permission distinction correct | ✓ — §3 application-only, §4 delegated-only |
| Permission source matches `docs/permission-matrix.md` | ✓ — 13 unique confirmed-required permissions match the matrix exactly |
| `Organization.Read.All` exception preserved correctly | ✓ — §3.2 preserves OBSERVED_WITHOUT_DOCUMENTED_ROLE; no recommendation to add the permission |
| No invented write permissions | ✓ — none added for either registration |
| No secrets / tokens / passwords introduced | ✓ — document contains no client secret, token, JWT, tenant id, client id, GUID, UPN, or password |
| No Graph calls made | ✓ — design-only task |
| No source / config / state files modified | ✓ — only the new design document was written |
| G04-002 / G05 not started | ✓ — out of scope of this task |

---

## 13. Source Files Modified

- **Created:** `docs/auth-app-registration-design.md`
- **Modified:** none. `config/api_inventory.json`, `docs/api-inventory.md`, `docs/permission-matrix.md`, `docs/data-catalog.md`, `data/discovery/discovery-state.json`, and all other project artifacts are unchanged.

## 14. Unresolved Findings

- **G02 G01-003 (`Organization.Read.All`) documented-vs-observed behavior.** Preserved as `OBSERVED_WITHOUT_DOCUMENTED_ROLE`. Not "fixed" by granting the permission. If the endpoint later stops returning 200 without it, a future task must capture the new evidence and update the matrix and registration together.
- **Production credential mechanism for the Collector.** Deferred to a future task. Current DEV baseline is a client secret with external secret-source loading.
- **Production Scenario Agent authentication.** Deferred to a future task. Current DEV baseline is interactive device-code against dedicated test users.
- **Future write permissions for either registration.** Deferred. None are introduced by G04-001.

## 15. Blockers

None. The design is consistent with the existing G01/G02/G03 artifacts and the project baseline.
