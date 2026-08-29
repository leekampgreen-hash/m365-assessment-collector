# G08-D1 — Guarded Live Interactive Sign-in Executor

## Purpose

G08-D1 introduces the **first LIVE-capable executor** for the
Scenario Agent. It implements a guarded, action-restricted live
boundary that supports exactly one action today:

    ActionType.INTERACTIVE_SIGNIN

The executor is implemented in
`agents/scenario/live_executor.py` and the supporting auth
abstractions live in `agents/scenario/auth/`. The implementation is
covered by an **offline-only** test suite under `tests/scenario/live/`.
This task does **not** perform a real device-code login; the live
acceptance step is a separate G08-D2 task so the implementation and
review boundary stays clean.

## Why AUTH is the first live scenario

The only enabled scenario in the current catalog is
`SCN-AUTH-001` (operator-driven test user sign-in, observability
classification `DIRECTLY_OBSERVABLE` via G01-006). The scenario is
uniquely well suited as the **first live step** for three reasons:

1. **Zero permission expansion.** It only requires the existing
   `User.Read` baseline delegated scope. No `Mail.Send`,
   `Calendars.ReadWrite`, `Files.ReadWrite`, `ChannelMessage.Send`,
   or `Group.ReadWrite.All` is requested. No new consent grant is
   required.
2. **No programmatic Graph write.** The value of the scenario is
   that the resulting sign-in event is collected by G01-006
   (sign-in logs) attributable to the test user. There is no mail
   sent, no calendar event created, no file created. The blast
   radius of an accidental run is bounded to a single sign-in event
   attributed to the test user.
3. **Strong attribution.** The device-code flow produces a single
   sign-in event whose `event_time` can be correlated to the
   scenario's `started_at` / `completed_at` window. It is the most
   directly observable scenario in the initial catalog.

Selecting AUTH as the first live step lets us validate the entire
live boundary (executor wiring, transport injection, actor
verification, correlation, failure classification, evidence redaction)
without any write capability and without any new permission grant.

## Zero permission expansion

The live executor's permission contract is **the closed union of the
allowlisted actions' declared delegated permissions** today:

    INTERACTIVE_SIGNIN → User.Read

`LiveScenarioExecutor.declared_permissions` returns exactly
`("User.Read",)`. There is no code path in the live executor that
requests `Mail.Send`, `Calendars.ReadWrite`, `Files.ReadWrite`,
`ChannelMessage.Send`, or any other delegated scope. The
Scenario Agent app registration is **not** modified by this task.

## User.Read baseline only (pinned)

`LiveScenarioConfig.delegated_scopes` is **pinned** to exactly
`("User.Read",)`. The constructor validates the value and raises
`ValueError` for anything else: an empty scope set, any extra scope
(`Mail.Send`, `Calendars.ReadWrite`, `Files.ReadWrite`, wildcards,
arbitrary values), duplicates, or variants (no whitespace stripping,
no case folding -- `user.read` is not normalized into acceptance).
The validated value is stored as the immutable tuple
`LIVE_REQUIRED_DELEGATED_SCOPES`.

The same validation runs again at the live execution boundary inside
`LiveScenarioExecutor.execute(...)` (dataclass fields are mutable
after construction). A config mutated post-construction produces a
controlled BLOCKED result classified
`LIVE_CONFIGURATION_INVALID` **before** any network or auth
operation can start. The device-code request form never includes a
`client_secret`, `username`, or `password`. The flow is the
public-client device-code grant only.

## Device-code delegated flow

`DeviceCodeFlow` performs the public-client OAuth 2.0 device-code
grant against the Microsoft identity platform:

1. `POST /oauth2/v2.0/devicecode` for the tenant, with
   `client_id=<scenario_app_client_id>` and `scope=User.Read`
   (the pinned live scope; no additional scopes are possible). No
   client secret.
2. The response carries `user_code`, `verification_uri`,
   `expires_in`, and `interval` (and `device_code`, which is the
   confidential value used for polling; it is held privately by the
   flow and is never returned to the operator).
3. The operator sees only the safe fields (`user_code`,
   `verification_uri`, `expires_in`, `interval`, and the human
   message). The prompt class
   `agents.scenario.auth.DeviceCodePrompt` exposes those fields
   only; the `device_code` is not on the prompt.
4. `POST /oauth2/v2.0/token` with
   `grant_type=urn:ietf:params:oauth:grant-type:device_code` is
   polled until the user completes sign-in, declines, the code
   expires, or the configured timeout elapses.

The confidential `device_code` lives only in a private,
repr-excluded attribute of the flow while polling requires it.
`DeviceCodeFlow.run(...)` clears that state in a `finally` block, so
it never outlives a terminal outcome: success, declined,
timeout/expiry, token error, or transport failure.

The flow is implemented as a **pure state machine**. It performs no
I/O of its own. The caller injects a request transport and a poll
transport; production wiring will use `urllib`-based HTTP calls,
offline tests use
`agents.scenario.auth.transports.FakeDeviceCodeTransport`. No
network code runs unless the caller wires a real transport.

## Token lifecycle

The bearer token exists only transiently inside
`DelegatedScenarioAuthenticationProvider.authenticate()`. The provider
uses it for mandatory actor verification, then clears it in a `finally`
block before authentication returns, including when authentication or
verification fails.

`LiveScenarioExecutor` never receives, stores, or wipes bearer tokens.
The authentication result and live execution evidence contain only safe
authentication metadata and contain no token material. The token is:

* **never** written to disk,
* **never** stored in `ScenarioExecutionResult` or
  `ScenarioStepResult`,
* **never** echoed in `__repr__`, exception messages, or
  evidence labels.

The `DeviceCodeToken.__repr__` returns
`"DeviceCodeToken(access_token=<redacted>, ...)"`. The
`DeviceCodePrompt` does not carry the access token, the refresh
token, the `device_code`, or the `Authorization` header.

## Actor verification (mandatory)

After a successful device-code flow, the
`GET https://graph.microsoft.com/v1.0/me` using the transient access
token and matches the response against the expected identity before
returning authentication metadata. Matching is performed by the
`GraphMeValidator` class. There is no successful live path that skips
actor verification, and the executor never receives the token.

The expected actor is supplied at construction time as an
`ExpectedActor(object_id=..., user_principal_name=...)`. Both
fields are optional but at least one verifiable field must be
supplied (an object ID, a UPN, or both; blank or whitespace-only
values do not count). When both are supplied, both must match
(defence in depth). When only one is supplied, only that field is
compared. The expected actor is runtime-supplied identity; it is
never hard-coded into scenario configs, catalog definitions, or any
file under version control.

If a usable expected actor is missing or empty, the executor fails
closed with a BLOCKED result classified
`LIVE_CONFIGURATION_INVALID` **before** authentication or any
network operation starts (no device-code request, no poll, no
`/me`). A successful live execution without actor verification is
impossible by construction, and the former
`actor_verification_skipped` evidence label no longer exists.

If the authenticated identity does not match the expected actor,
the executor emits a controlled `ACTOR_IDENTITY_MISMATCH`
failure. The executor does **not** silently execute under another
user. Malformed `/me` data (missing `id`, non-object body) fails
closed with `GRAPH_ME_VALIDATION_FAILED`.

## Explicit `allow_live` gate

`LiveScenarioExecutor(allow_live=False)` is the default. When
`allow_live` is `False`, every call to `execute(...)` returns a
`BLOCKED` step result with the closed error code
`LIVE_EXECUTION_DISABLED`. The executor is safe to instantiate in
tests or in upstream code paths that should never perform a live
action; nothing runs by accident.

Production wiring requires an explicit `allow_live=True` at
construction. With `allow_live=True` the constructor also requires:

* a `LiveScenarioConfig` with `scenario_app_client_id`,
  `scenario_app_tenant_id`, and `delegated_scopes` (default
  `User.Read`),
* a `device_code_request_transport`,
* a `device_code_poll_transport`,
* a `graph_me_transport`.

When any of these is missing the constructor raises `ValueError`
without performing any I/O.

## Action restriction

The live executor's allowlist is exactly one action:

    LIVE_SUPPORTED_ACTIONS = ("INTERACTIVE_SIGNIN",)

Every other `ActionType` in the closed framework vocabulary is
refused with `UNSUPPORTED_LIVE_ACTION`. The refused actions are:

* `SEND_MAIL`
* `CREATE_CALENDAR_EVENT`
* `UPDATE_CALENDAR_EVENT`
* `DELETE_CALENDAR_EVENT`
* `CREATE_FILE`
* `UPDATE_FILE`
* `DELETE_FILE`
* `CREATE_TEAMS_MESSAGE`
* `CREATE_GROUP_CONTENT`
* `NOOP_VALIDATION`

Unknown action types are also refused with `UNSUPPORTED_LIVE_ACTION`
(when `allow_live=True`) or `LIVE_EXECUTION_DISABLED` (when
`allow_live=False`). The live executor does **not** accept an
arbitrary Graph URL, an arbitrary HTTP method, or an arbitrary
body. The action vocabulary remains the closed vocabulary
introduced in G08-A.

## G01-006 expected observation

`SCN-AUTH-001` is `DIRECTLY_OBSERVABLE` via G01-006 (sign-in
logs). The live executor's evidence explicitly records
`expected_observable_endpoint:G01-006` so downstream consumers of
the result can confirm the expected observation site.

## Correlation: GA-SCENARIO-* is plan-side only

The framework's correlation marker
`correlation_prefix(execution_id)` produces values of the form
`GA-SCENARIO-<execution_id>`. The marker is recorded on the plan
and on the result. The live executor propagates it into the
step's evidence labels.

**The marker is NOT embedded in the actual Microsoft sign-in
event.** Microsoft identity platform's sign-in event schema does
not accept a custom correlation token; the platform records its
own `appId`, `appDisplayName`, `correlationId`, and `conditionalAccessPolicies`
fields. We do **not** claim that `GA-SCENARIO-*` appears inside
the upstream sign-in event.

Instead, the executor's evidence records the correlation by:

* the **scenario execution_id**,
* the **actor identity** (logical alias + authenticated object id),
* the **authentication completion timestamp** (`completed_at`),
* the **expected observable endpoint** (`G01-006`),
* an explicit `scenario_correlation:plan_correlation_only` label
  that documents the above distinction.

A downstream consumer correlates a `ScenarioExecutionResult` to an
observed G01-006 row by:

* matching `actor_id` (logical alias) to the `userPrincipalName`
  recorded by G01-006 (via a configured `actor_id → upn` map that
  is **not** part of the executor's persisted state),
* matching the `completed_at` timestamp to the sign-in
  `event_time` (within the configured window),
* matching the `appId` to the Scenario Agent app's application id
  (this is a separate, runtime-only lookup).

This correlation is documented in evidence labels, not enforced by
the executor.

## No token persistence / no Authorization in evidence

The executor does not have any field, method, or attribute
named `save_token`, `write_token`, `cache_token`, `persist_to`,
or similar. The dataclass is dataclass-validated at construction
and exposes only the action-allowlist properties. The token is
owned transiently by `DelegatedScenarioAuthenticationProvider` during
`authenticate()` and is cleared before that method returns.

`ScenarioExecutionResult`, `ScenarioStepResult`, and
`ScenarioStepResult.to_dict()` never include the access token,
the refresh token, the `device_code`, the `Authorization` header,
the bearer scheme, or the client secret. The `to_dict()`
representation is exercised by the test
`test_authorization_never_appears_in_result_to_dict`.

## Failure model

`LiveScenarioExecutor` classifies every failure using a closed
vocabulary. The vocabulary is exposed as
`agents.scenario.LIVE_FAILURE_CLASSIFICATIONS`:

| Classification | Triggered when |
|---|---|
| `LIVE_EXECUTION_DISABLED` | The executor was constructed with `allow_live=False`; nothing runs. |
| `UNSUPPORTED_LIVE_ACTION` | The step's action type is not in the live allowlist. |
| `LIVE_CONFIGURATION_INVALID` | Pre-flight configuration validation failed at the execution boundary: the delegated scopes are not exactly `("User.Read",)`, or no usable expected actor (at least one verifiable identity field) is configured. Refused before any network or auth operation starts. At the config construction boundary the same violations raise `ValueError`. |
| `AUTH_DEVICE_CODE_ERROR` | The device-code request failed (transport error, HTTP error, malformed body, missing fields, missing `device_code`). |
| `AUTH_TIMEOUT` | The configured flow timeout elapsed before sign-in completed, or the device code expired. |
| `AUTH_DECLINED` | The user declined the device-code prompt (`authorization_declined`). |
| `AUTH_TOKEN_ERROR` | The token endpoint returned a non-recoverable error (`invalid_grant`, `invalid_client`, missing `access_token`, invalid `expires_in`, transport error on the poll endpoint). |
| `ACTOR_IDENTITY_MISMATCH` | The `GET /me` response did not match the expected actor. |
| `GRAPH_ME_VALIDATION_FAILED` | The `GET /me` request itself failed (transport error, HTTP error, malformed body, missing `id`). |

Sensitive upstream error bodies are **never** included in
exception messages or evidence labels. Only the deterministic
classification is propagated.

## Network abstraction / testability

The live executor and the auth subpackage perform **no I/O** on
their own. The only place any of these modules opens a socket is
in the `_http_post_form` runtime seam in
`agents.scenario.auth.device_code`, which is a stub that raises
`DeviceCodeError("AUTH_DEVICE_CODE_ERROR", ...)` if it is
called without a transport override. Production wiring will
replace this stub with an `urllib`-based transport; offline
tests inject `FakeDeviceCodeTransport` and
`FakeGraphTransport` instead. The fakes are the only objects
test code touches.

The full offline test path is verified to make zero
`urllib.request.urlopen` calls and zero `socket.socket` calls
(`test_no_real_network_call` /
`test_no_real_network_call_on_failure` in
`tests/scenario/live/test_live_executor.py`).

## G08-D2 live acceptance still required

This task ends with the implementation and the offline tests. The
actual controlled device-code login against the real
`graph-agent-scenario-dev` app registration is a **separate
acceptance step (G08-D2)**. G08-D2 will:

* confirm the device-code flow against the real Microsoft
  identity platform,
* confirm the `/me` identity check against the real Microsoft
  Graph endpoint,
* confirm a single observed row in G01-006 (sign-ins) correlated
  to the test user,
* confirm the live executor's evidence labels and the
  collector-side correlation process,
* confirm the actor verification failure path against a real
  second test user.

Until G08-D2 passes, the live executor is **not** wired into any
production entrypoint. No operator-run script, no
`plan_and_execute(...)` call path, no CLI, and no scheduled job
constructs the live executor. The only thing that has changed in
G08-D1 is the addition of the `LiveScenarioExecutor` class and
its offline tests.

## Test coverage

G08-D1F hardening adds focused negative suites on top of the
original 83 offline tests, all under `tests/scenario/live/`:

| File | Coverage |
|---|---|
| `_helpers.py` | Shared plan / actor factory (synthetic identities only); module-graph import-safety tests (no `collectors.*`, no `agents.discovery.*`, no top-level `urllib.request` import in the live modules). |
| `test_live_gate.py` | `allow_live` default is `False`; disabled executor blocks every action; action allowlist refuses every action except `INTERACTIVE_SIGNIN`; construction-time validation of the live executor (`allow_live=True` requires config and transports); `DryRunScenarioExecutor` semantics unchanged. |
| `test_device_code.py` | Successful flow returns a safe prompt + token; pending flow correctly waits and completes; declines / expirations / invalid grants / invalid clients are classified deterministically; the flow does not accept a client secret, username, or password; the request form is `client_id` + `scope` only. |
| `test_identity.py` | Match on object id / UPN / both; mismatch blocks; HTTP / transport / missing-id failures; expected actor must declare at least one of `object_id` / `user_principal_name`; token never appears in identity `repr` or exception messages. |
| `test_live_executor.py` | End-to-end fake login success with mandatory actor verification; missing expected actor fails closed before any network/auth operation; actor mismatch / declined / timeout / token error / device-code error classifications; token never appears in `result.repr` / `evidence_labels` / `to_dict()`; `Authorization` never appears in evidence; provider-owned token is cleared during authentication; no file-persistence path; no real network call (the test patches `urllib.request.urlopen` and `socket.socket`). |
| `test_scope_hardening.py` | G08-D1F Finding 1: exactly `User.Read` accepted end to end; empty / extra (`Mail.Send`, `Calendars.ReadWrite`) / arbitrary / variant (case and whitespace) / duplicate scopes rejected at the config boundary and re-validated at the execution boundary (`LIVE_CONFIGURATION_INVALID`) before any network or auth operation starts. |
| `test_actor_hardening.py` | G08-D1F Finding 2: missing / empty / whitespace-only expected actors rejected before authentication starts; object-ID-only and UPN-only actors accepted; matching `/me` succeeds; second account yields `ACTOR_IDENTITY_MISMATCH`; malformed `/me` fails closed; verification cannot be skipped (structural proof that `actor_verification_skipped` no longer exists). |
| `test_device_code_cleanup.py` | G08-D1F Finding 3: private device-code state cleared after success, decline, timeout/expiry, token error, and transport/error terminal paths; state still present while polling requires it (not cleared prematurely); a rerun performs a fresh request instead of resurrecting state. |
| `test_public_surface.py` | Public surface (`LIVE_FAILURE_CLASSIFICATIONS`, `LIVE_SUPPORTED_ACTIONS`, `LIVE_REQUIRED_DELEGATED_SCOPES`, `LiveScenarioExecutor`, `LiveScenarioConfig`, error-code constants) is exposed from `agents.scenario` and is identical to the module surface; auth subpackage imports cleanly. |

## Combined regression

* G08-D1 (incl. D1F hardening): 131 tests, all offline.
* G08-C integration: 76 tests (unchanged).
* G08-A framework: 111 tests (unchanged).
* G08-B catalog: 57 tests (unchanged).

The hardened suites pass in the offline test harness. The
implementation boundary is preserved: the live executor never
imports anything from `collectors.*`, `agents.discovery.*`, or
the production transport layer.

## Related documents

* `docs/g08-scenario-agent-framework.md` -- G08-A framework.
* `docs/g08-scenario-catalog.md` -- G08-B catalog.
* `docs/g08-scenario-integration.md` -- G08-C integration.
* `docs/g08-scenario-permission-matrix.md` -- permission pack
  matrix and `User.Read` baseline.
* `docs/auth-app-registration-design.md` -- Scenario Agent
  device-code flow design.
