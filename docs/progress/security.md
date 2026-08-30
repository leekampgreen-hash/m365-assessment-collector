# Security Progress


## SEC-P07 Sign-in detail and combined risk scoring (PASS)

**Task:** `SEC-P07`
**Status:** `SEC-P07 PASS`

- Added per-user sign-in detail and combined risk scoring endpoints and agent tools.
- Responses expose display names only, with plain-language risk signals and score factors.


## SEC-P01 Sign-in risk API and tool (PASS)

**Task:** `SEC-P01`
**Status:** `SEC-P01 PASS`

- Added `GET /api/security/signin-risk` with tenant-scoped risky-user and risk-detection summaries.
- Added `get_signin_risk()` and mock/live agent registration.

## SEC-P02 MFA coverage API and tool (PASS)

**Task:** `SEC-P02`
**Status:** `SEC-P02 PASS`

- Added `GET /api/security/mfa-coverage` with MFA finding counts and pass rate.
- Added `get_mfa_coverage()` and explicit agent tool guidance.

## SEC-P03 Conditional-access API and tool (PASS)

**Task:** `SEC-P03`
**Status:** `SEC-P03 PASS`

- Added `GET /api/security/ca-policies` with tenant policy totals and states.
- Added `get_ca_policies()` and mock/live agent registration.
 - Existing nginx `/api/security/` proxy covers all three endpoints.

## SEC-P05 Sign-in logs collector (PASS)

**Task:** `SEC-P05`
**Status:** `SEC-P05 PASS`

- G01-006 sign-in collector persists to `core.signin_log` (51 rows).
- `/api/security/signin-summary` returns real data: 51 sign-ins and 15 failures.
- Verified the agent `get_signin_summary` tool is working.
- Expanded M365 scope keywords to include login and authentication terms.
- MFA invocation: `--security-rule M365-ENTRA-MFA-REG-001`.

## SEC-P04 Admin roles API and tool (PASS)

**Task:** `SEC-P04`
**Status:** `SEC-P04 PASS`

- Added `GET /api/security/admin-roles`.
- Risk classification: Global Admin → HIGH, privileged roles → MEDIUM.
- Auto-generated findings: Global Admin count > 3 triggers a HIGH finding.
- Registered `get_admin_roles` with mock keyword matching.
- Added the Entra `admin_roles` knowledge topic.
- Join key: `directory_role_assignment.role_definition_id = directory_role_definition.source_object_id`.
- Verified: 3 roles, 7 Global Administrator assignments, and correct HIGH findings.
 - 1,052 tests pass, with 1 pre-existing unrelated failure.

## SEC-P06 MFA registration per user API and tool (PASS)

**Task:** `SEC-P06`
**Status:** `SEC-P06 PASS`

- Added `GET /api/security/mfa-registration`.
- Data: 39 users, 2 registered, 37 unregistered (5% registration rate).
- Verified the `get_mfa_registration` agent tool.
- No email addresses or UPNs are exposed in the response.
- 303 tests pass, with 1 pre-existing migration-order failure.


