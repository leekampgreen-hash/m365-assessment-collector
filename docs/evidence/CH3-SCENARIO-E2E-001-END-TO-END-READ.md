# CH3-SCENARIO-E2E-001 End-to-End Read

> **Architecture status:** The app-only execution path evaluated by this
> evidence is not an accepted canonical Scenario Agent path. Per
> `docs/design/ADR-CH3-AUTH-001.md`, future Scenario execution must use a
> dedicated test user authenticated through OAuth 2.0 device code with
> delegated Microsoft Graph permissions.

## Result

**STATUS: BLOCKED BEFORE AUTHENTICATION OR GRAPH DISPATCH**

This result concerns a requested app-only candidate path only. It is not a
blocker for, validation of, or authorization to implement canonical delegated
Scenario execution.

No token was acquired, no Microsoft Graph request was sent, and no Entra or
Collector operation occurred. The repository does not contain the required
client-credentials authentication provider or an execution coordinator that
connects an approved Scenario-only application identity to the bounded read
adapter.

The existing `ReadFocusedAdapter` is deliberately incompatible with the
requested app-only flow: its `AuthenticationContext` requires a delegated
`/me`-verified `MeIdentity` (`agents/scenario/adapters/read_focused_adapter.py:32-49`),
while `MicrosoftDeviceCodeHttpsTransport` only supplies device-code token
handling and fixed GET collection methods (`agents/scenario/auth/transports.py:115-216`).
The current `LiveScenarioExecutor` supports only `INTERACTIVE_SIGNIN` and pins
delegated `User.Read` (`agents/scenario/live_executor.py:1-71,148-154`); it
cannot run `USER_LIST` or `GROUP_LIST` with client credentials.

## Sanitized Evidence Records

```text
execution_id: ch3-scenario-e2e-001-20260824T133507Z
correlation_id: CH3-SCENARIO-E2E-001-20260824T133507Z
scenario_id: CH3-SCENARIO-E2E-001
operation: USER_LIST
timestamp: 2026-08-24T13:35:07Z
status: BLOCKED
object_count: 0
sanitized_result_summary: Blocked before token acquisition and adapter dispatch; no Graph request was made.

execution_id: ch3-scenario-e2e-001-20260824T133507Z
correlation_id: CH3-SCENARIO-E2E-001-20260824T133507Z
scenario_id: CH3-SCENARIO-E2E-001
operation: GROUP_LIST
timestamp: 2026-08-24T13:35:07Z
status: BLOCKED
object_count: 0
sanitized_result_summary: Blocked before token acquisition and adapter dispatch; no Graph request was made.
```

## Validation

| Check | Result |
| --- | --- |
| Targeted E2E adapter tests | PASS: `python3 -m unittest tests.scenario.test_read_focused_adapter` ran 6 tests. |
| Full unittest suite | PASS: `python3 -m unittest discover -s tests -p 'test_*.py'` ran 625 tests. |
| Compile check | PASS: `python3 -m compileall -q agents/scenario` exited 0. |
| Docker Compose validation | PASS: `docker compose config` exited 0. |

## Security Confirmation

- No Graph write method or endpoint was invoked.
- No Microsoft Graph `GET /users` or `GET /groups` request was invoked.
- No token, authorization header, secret, or raw Graph response was output or persisted.
- No Entra mutation, permission change, Collector interaction, or arbitrary endpoint execution occurred.
- The evidence records contain only the required fields and sanitized summaries.

## Next Safe Task

Reconcile or implement the canonical delegated Scenario Agent execution path in
accordance with `docs/design/ADR-CH3-AUTH-001.md`. It must authenticate a
dedicated test user through device code, use least-privileged delegated
permissions for an approved scenario, preserve user-attributable audit
evidence, avoid generic URLs or methods, and avoid token or raw-response
persistence. Add offline tests before requesting any live execution.
