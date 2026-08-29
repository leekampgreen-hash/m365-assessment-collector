# CH3-SCENARIO-LIVE-VALIDATION-001: Canonical Delegated Scenario Live Validation

## Purpose

This procedure defines the controlled, operator-approved validation of the
canonical Scenario Agent delegated flow. It is a runbook only. It does not
authorize implementation changes, Entra changes, permission grants, credential
creation, Collector changes, or live execution by default.

The Scenario Agent uses a delegated identity and OAuth 2.0 device-code flow.
The Collector remains a separate app-only component using `client_credentials`
and application permissions. This procedure must not use the Collector's
identity, token, permissions, or configuration.

## Preconditions

Confirm all of the following before seeking operator approval:

1. The Scenario App registration is available and is the dedicated Scenario
   Agent registration, not the Collector registration.
2. Approval for the required delegated permission exists. The current bounded
   validation contract is exactly `User.Read`; do not add or request scopes.
3. A dedicated test user is assigned and its expected object ID and UPN have
   been independently verified from the approved test-user record.
4. An authorized operator has approved this specific execution, including the
   expected actor, approved operation, and execution window.
5. The live execution gate is disabled by default and remains disabled until
   the operator enables it for this single approved run.
6. No Entra configuration, permission, credential, secret, Collector, or
   application code changes are part of the run.

Record the expected actor outside source control:

| Field | Required value |
| --- | --- |
| Object ID | Dedicated test user's immutable Entra object ID |
| UPN | Dedicated test user's current user principal name |

## Validation Flow

```text
Device Code Authentication
        |
        v
Delegated Token
        |
        v
/me Actor Verification
        |
        v
Approved Scenario Execution
        |
        v
Sanitized Evidence
```

1. Confirm the gate is OFF and all preconditions are recorded.
2. Obtain manual operator approval for one bounded execution.
3. Enable the gate only for the approved operator session and only for the
   approved execution window.
4. Present the device-code prompt to the dedicated test user. Do not capture
   or record device codes, tokens, headers, or browser artifacts.
5. Accept the delegated token only for mandatory `GET /me` actor verification.
6. Compare the returned actor object ID and UPN to the expected values. Both
   values must match when both are configured.
7. Execute only the approved bounded Scenario Agent operation after successful
   actor validation.
8. Emit sanitized evidence, disable the gate immediately, and review the
   evidence against this procedure.

## Actor Validation

Expected actor identity consists of the dedicated test user's:

* Object ID
* UPN

Rules:

* A mismatch in either configured identity field fails closed. Do not continue
  under a different authenticated account.
* A missing, blank, malformed, or unverifiable identity fails closed.
* Actor validation is mandatory after authentication and before approved
  scenario execution. There is no bypass path.
* The expected object ID and UPN are runtime inputs. Do not store actual test
  user identity values in source control or evidence beyond approved actor
  metadata handling.

## Allowed Operations

Only explicitly approved, bounded operations are permitted. Under the current
canonical Scenario Agent implementation, the live allowlist contains only
`INTERACTIVE_SIGNIN` using exactly the delegated `User.Read` scope.

The validation must not permit:

* Arbitrary endpoint selection
* Arbitrary HTTP method selection
* Write, update, delete, or other mutation operation
* Permission escalation, new consent, or scope expansion

The mandatory `/me` request is only an actor-verification control, not a
general-purpose Graph query capability.

## Evidence Policy

Sanitized evidence may contain only:

* `execution_id`
* `correlation_id`
* Approved actor metadata
* Timestamp
* Operation
* Status
* Response classification

Evidence must never contain:

* Access token
* Refresh token
* Authorization header
* Secrets, passwords, client secrets, or device codes
* Raw request or response payload

Use classifications and bounded metadata instead of raw responses. Sanitize
before persistence, display, export, or handoff. If a potentially sensitive
field is observed, stop immediately and treat the run as failed.

## Stop Conditions

Immediately stop the execution, disable the live gate, retain only sanitized
failure evidence, and escalate to the authorized operator if any of the
following occurs:

* Actor mismatch
* Unexpected permission or scope
* Unexpected endpoint
* Token or other secret leakage
* Mutation attempt

No retry, alternate account, endpoint substitution, or scope change is allowed
within the same approval.

## Operator Gate

Default: **OFF**

Enablement: manual operator approval only.

The operator approval must identify the expected actor, the exact bounded
operation, the execution window, and the approving operator. Enable the gate
only immediately before the approved run. Disable it immediately after a
success, failure, stop condition, timeout, or abandoned device-code prompt.

## Completion Criteria

A validation succeeds only when the gate was manually approved, the dedicated
test user completed device-code authentication, `/me` matched the configured
object ID and UPN, only the approved bounded operation ran, and the resulting
evidence passed the evidence policy.

This procedure intentionally performs no live call itself. A live run requires
separate operator approval and must follow the controls above.

## Offline Regression Checks

Before requesting an operator-approved live run, execute:

```bash
python3 -m unittest discover -s tests -p 'test*.py'
python3 -m compileall
docker compose config
```
