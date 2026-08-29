# Scenario Agent Framework (G08-A)

## Purpose

The Scenario Agent is the deterministic execution layer for controlled
Microsoft 365 test actions. It sits **below** any AI / LLM reasoning
and **above** the future live Microsoft Graph transport. Its job is to
turn a caller-supplied scenario request into a safe, evidence-only
execution plan, then drive a deterministic executor against that plan.

G08-A ships the **framework only**. It does **not**:

- perform any live Microsoft Graph write operation,
- modify Entra permissions or application registration,
- store, log, or accept passwords, tokens, refresh tokens, client
  secrets, or raw `Authorization` header values,
- introduce a live executor,
- start production scenario execution.

## Components

| Module | Responsibility |
|---|---|
| `agents.scenario.models` | Typed dataclasses: `ScenarioDefinition`, `ScenarioRequest`, `ScenarioPlan`, `ScenarioStep`, `ScenarioExecutionResult`, `ScenarioStepResult`, `ScenarioActor`. Closed status / risk / identity vocabularies. |
| `agents.scenario.actions` | Closed action vocabulary (`SEND_MAIL`, `CREATE_CALENDAR_EVENT`, `CREATE_FILE`, `UPDATE_FILE`, `CREATE_TEAMS_MESSAGE`, `CREATE_GROUP_CONTENT`, `NOOP_VALIDATION`), declared delegated permissions per action, allowed safe-parameter keys, and parameter sanitisation that drops `url`/`method`/`body` overrides. |
| `agents.scenario.actors` | `ScenarioActor` model carrying identifiers and an explicit allow-list of scenarios / workloads it may drive. Deterministic `actor_is_authorized` helper. |
| `agents.scenario.safety` | `evaluate_safety` gate and `ScenarioBlockedError`. Closed reason code vocabulary (`SCENARIO_UNKNOWN`, `SCENARIO_DISABLED`, `SCENARIO_DESTRUCTIVE_DISABLED`, `ACTION_UNSUPPORTED`, `ACTOR_MISSING`, `ACTOR_UNAUTHORIZED`, `RAW_TOKEN_INPUT_REJECTED`, `ARBITRARY_URL_INPUT_REJECTED`, `ARBITRARY_METHOD_INPUT_REJECTED`, `RAW_BODY_PASSTHROUGH_REJECTED`, `PERMISSIONS_UNDECLARED`). |
| `agents.scenario.registry` | `ScenarioRegistry` -- a deterministic `scenario_id` -> `ScenarioDefinition` map. Ships a built-in catalog covering each supported action type. Validates that every definition declares at least one required delegated permission. |
| `agents.scenario.executor` | `ScenarioActionExecutor` protocol and `DryRunScenarioExecutor`. The dry-run executor performs **zero network calls** and redacts token-shaped values from any parameter it touches. |
| `agents.scenario.engine` | `ScenarioAgent` orchestrator: `plan(...)`, `execute(...)`, `plan_and_execute(...)`. The engine does not import the Graph transport, never persists secrets, and never mutates caller input. |

All public symbols are re-exported from `agents.scenario`. The
package's `__all__` is the contract.

## Deterministic scenario execution model

A scenario is a closed, registry-bound pattern of actions. Callers
cannot invent new actions or override URL / method / body at request
time. The flow is:

```
ScenarioRequest           (caller input: scenario_id, actor, metadata)
        |
        v
ScenarioRegistry          (lookup; rejects unknown scenario_id)
        |
        v
ScenarioDefinition        (action_type, permissions, risk, enabled, ...)
        |
        v
evaluate_safety           (deterministic gate; raises ScenarioBlockedError)
        |
        v
ScenarioAgent.plan        (builds an immutable ScenarioPlan)
        |
        v
ScenarioAgent.execute     (drives the injected ScenarioActionExecutor)
        |
        v
ScenarioExecutionResult   (safe evidence only)
```

The model is **deterministic**. Given the same request and the same
registry, `plan()` produces a plan with identical content (modulo
freshly-generated `plan_id`, `execution_id`, and `correlation_id`
markers).

There are **no hidden retries**, **no network I/O**, **no AI calls**,
and **no caller-input mutation** in any layer of the framework.

## Separation of AI reasoning vs execution engine

Agentic / LLM reasoning happens **above** this framework. A future
planner layer is expected to translate a high-level goal (for example
"create a calendar meeting as test user") into a
`ScenarioRequest(scenario_id="scenario.calendar.create_test_event",
actor=...)` call. The framework then guarantees the request is
validated, planned, and executed through a closed vocabulary. The
framework itself never invokes any LLM and never accepts a natural
language prompt.

This separation keeps the execution path auditable, reproducible, and
free of untrusted inputs.

## Test-user boundary

Every scenario declares an `identity_requirement` (one of
`NOT_REQUIRED`, `OPTIONAL`, `REQUIRED`). Scenarios with
`REQUIRED` are blocked at the safety gate when no actor is supplied.

The `ScenarioActor` carries **only identifiers**:

- `actor_id` (logical alias; required),
- `user_principal_name` (optional; supplied externally),
- `object_id` (optional),
- `allowed_scenario_ids` (optional allow-list),
- `allowed_workloads` (optional allow-list),
- `enabled` (boolean).

The actor NEVER carries a password, token, refresh token, client
secret, or `Authorization` header. The framework's `FORBIDDEN_ACTOR_FIELDS`
constant enumerates the credential-shaped names a future caller must
not try to attach to an actor. Even when constructing an actor
out-of-band, the safety gate never reads such fields.

Authorization is checked twice:

1. At the safety gate against the actor's `enabled`, `allowed_scenario_ids`,
   and `allowed_workloads` lists.
2. At execute time, by verifying that the actor supplied to
   `execute(plan, actor=...)` matches the `actor_id` recorded on the
   plan. A mismatch raises `ScenarioBlockedError`.

## Permission declaration

Every `ScenarioDefinition` declares
`required_delegated_permissions`. The safety gate rejects scenarios
that declare no permissions, and the registry itself refuses to
register such scenarios at construction time.

For each action type, the action module additionally exposes
`declared_permissions_for(action_type)` so the plan and execution
result carry the canonical, action-shaped permission declaration. A
scenario that mixes two action types inherits the union of those
permissions.

The framework never grants or modifies permissions. It only records
what is required.

## Safety gate

The gate is deterministic and pure: same input, same outcome, no I/O.
Its reason codes form a closed vocabulary; tests assert against the
codes rather than message text.

| Reason code | Triggered when |
|---|---|
| `SCENARIO_UNKNOWN` | The `scenario_id` is not in the registry. |
| `SCENARIO_DISABLED` | The scenario exists but `enabled=False`. |
| `SCENARIO_DESTRUCTIVE_DISABLED` | `destructive=True` and the agent was not constructed with `allow_destructive=True`. |
| `ACTION_UNSUPPORTED` | The scenario references an action type outside the closed vocabulary. |
| `PERMISSIONS_UNDECLARED` | The scenario declares no required delegated permissions. |
| `ACTOR_MISSING` | A `REQUIRED` scenario is requested without an actor. |
| `ACTOR_UNAUTHORIZED` | The actor is disabled, or its allow-lists exclude the scenario. |
| `RAW_TOKEN_INPUT_REJECTED` | Caller metadata contains a key that looks like a token field or a value that begins with `Bearer ` / `Basic `. |
| `ARBITRARY_URL_INPUT_REJECTED` | Caller metadata tries to smuggle a `url` / `endpoint` / `path` key. |
| `ARBITRARY_METHOD_INPUT_REJECTED` | Caller metadata tries to smuggle a `method` / `http_method` key. |
| `RAW_BODY_PASSTHROUGH_REJECTED` | Caller metadata tries to smuggle a `body` / `raw_body` / `payload` key. |

Destructive scenarios ship disabled and require explicit opt-in to
the engine. Cleanup-required scenarios carry a `cleanup_required`
flag and an optional `cleanup_scenario_id`.

## Correlation marker

Every plan and execution result carries a stable correlation id of
the form `GA-SCENARIO-<execution_id>`. The id is generated by
`correlation_prefix(execution_id)` in `agents.scenario.models` and is
the single hook future collectors can use to prove that observed
Microsoft 365 telemetry corresponds to a specific scenario action.

The framework exposes the marker on `ScenarioPlan.correlation_id`
and `ScenarioExecutionResult.correlation_id`. The same marker appears
inside per-step evidence labels produced by `DryRunScenarioExecutor`
(`correlation:<id>`).

G08-A does **not** insert the marker into Microsoft 365 artifacts. A
future live executor will be responsible for embedding it into
subjects, file names, and post bodies so collectors can match on it.

## Dry-run executor

`DryRunScenarioExecutor` is the only executor the framework ships in
G08-A. It:

- never imports `collectors.core.transport`,
- never makes a network call,
- returns deterministic `SUCCESS` step results,
- preserves `scenario_id`, `actor_id`, `correlation_id`, and `step_id`
  on every step result,
- redacts any value that resembles a bearer token, OpenAI-style
  `sk-...` key, or JWT prefix before propagating it inside evidence,
- includes `dry_run:<action_type>`, `scenario:<id>`,
  `actor:<id>`, `correlation:<id>`, and the safe parameter **keys**
  in `evidence_labels` (values are never echoed).

Test fixtures can substitute a custom executor by passing it to
`ScenarioAgent(registry, executor=...)`. The custom executor must
implement the `ScenarioActionExecutor` protocol:

```python
class ScenarioActionExecutor(Protocol):
    def execute(
        self,
        step: ScenarioStep,
        actor: Optional[ScenarioActor],
        plan: ScenarioPlan,
    ) -> ScenarioStepResult: ...
```

`ScenarioAgent.execute` collects step results, calculates a final
status (`SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `BLOCKED`), and stops
on the first non-`SUCCESS` step.

## Future live executor boundary

A future live executor will live alongside `DryRunScenarioExecutor`
and will be the **only** code in the framework allowed to call
Microsoft Graph. It will be subject to:

- inheriting the same `ScenarioActionExecutor` protocol,
- receiving the `actor` reference **only** at execute time (the actor
  never persists in results),
- embedding the plan's `correlation_id` into Microsoft 365 artifacts,
- returning `ScenarioStepResult` with safe evidence labels,
- never propagating raw `Authorization` headers or token strings
  into evidence,
- being constructed and wired by configuration outside the framework.

Until that executor exists, no Microsoft 365 write operation is
possible through `agents.scenario`.

## Security properties

- **No live Graph imports.** Importing `agents.scenario` does not
  transitively import any module under `collectors.core`.
- **No secret storage.** No class carries `password`, `token`,
  `access_token`, `refresh_token`, `client_secret`, `secret`, or
  `Authorization` fields.
- **No raw transport override.** `url`, `method`, `body`, and
  credential-shaped keys in caller metadata are rejected at the
  safety gate and never reach an action.
- **Caller input is not mutated.** `ScenarioAgent.plan` produces a
  plan from a `ScenarioRequest` without mutating the request.
- **Result serialization is safe.** `to_dict()` on every model never
  contains bearer-shaped strings, JWT prefixes, or `Authorization`
  header values. Tests assert against this property directly.
- **Destructive scenarios are off by default.** Destructive flags
  must be opted into at the `ScenarioAgent` constructor.
- **Disabled scenarios never run.** The gate rejects
  `enabled=False` entries deterministically.

## Relationship to other layers

- **G05 / G07 (Collector Framework and Workload Collectors).** The
  collector layer is app-only / read-focused. The Scenario Agent is
  delegated / test-user scoped. They share the test boundary (test
  Graph telemetry is collected by the collectors after a scenario
  runs) but the two layers never import one another.
- **G08-B (Scenario Catalog).** G08-B will own the JSON catalog at
  `config/scenarios/` and the actor / permission-pack metadata.
  G08-A does not depend on G08-B; the registry ships a small
  built-in catalog so the framework is self-contained.
- **Future live executor.** See "Future live executor boundary"
  above.

## Test coverage

G08-A adds 111 offline tests under `tests/scenario/framework/`:

- `test_models.py` -- typed models, closed vocabularies, correlation
  marker, serialization safety.
- `test_actions.py` -- closed action vocabulary, declared permissions
  per action, parameter sanitisation that drops transport overrides.
- `test_safety.py` -- safety gate reason codes, actor authorization,
  input hardening (token / URL / method / body rejection).
- `test_registry.py` -- built-in catalog shape, custom definitions,
  validation at construction.
- `test_executor.py` -- dry-run determinism, identifier preservation,
  redaction of token-shaped values, no Graph transport imports.
- `test_engine.py` -- plan / execute round-trip, status calculation,
  correlation marker propagation, request non-mutation, custom
  executor injection.
- `test_public_import.py` -- public surface smoke tests, no
  transitive Graph imports.

The full test suite (G05 / G06 / G07 / G08 catalog / G08-A) passes.