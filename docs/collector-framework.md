# Collector Framework (G05-001 / G05-002)

## Purpose

The collector framework is a small, reusable Python package under
`collectors/core/` that future Microsoft Graph workload collectors
(G07: SharePoint, OneDrive, Exchange, Teams, etc.) will build on. It
contains:

- typed endpoint specifications and collection results,
- a Microsoft Graph HTTP transport abstraction,
- a `@odata.nextLink` paginator,
- a bounded retry policy that honors `Retry-After`,
- deterministic error classification,
- an inventory loader adapter over `config/api_inventory.json`,
- a `BaseCollector` orchestrator that ties the above together.

The framework does NOT:

- call Microsoft Graph during validation,
- modify Entra ID or any tenant object,
- add or grant permissions,
- store, log, or serialize tokens, client secrets, or
  `Authorization` header values,
- implement workload-specific collectors (those land in G07),
- implement the Scenario Agent logic,
- introduce a database design (that belongs to G06).

## Components

| Module | Responsibility |
|---|---|
| `collectors.core.models` | `EndpointSpec`, `CollectionResult`, helpers |
| `collectors.core.errors` | Deterministic HTTP / transport classification |
| `collectors.core.retry` | Bounded retry policy; honors `Retry-After` |
| `collectors.core.transport` | `GraphTransport`: GET, params, timeout, structured errors |
| `collectors.core.pagination` | `Paginator`: follows `@odata.nextLink` |
| `collectors.core.inventory` | `load_inventory`, `entry_to_spec`, `enabled_specs` |
| `collectors.core.collector` | `BaseCollector`: orchestrates one endpoint run |
| `collectors.core.auth` | App-only client-credentials token provider and structured auth errors |
| `collectors.core.config` | Process-environment and protected `.env` configuration sources |
| `collectors.core.results` | Safe result serialization and auth-failure result mapping |
| `collectors.core.runtime` | Inventory selection, authentication, transport, and collector execution |
| `collectors.run_collector` | Minimal command-line entry point |

## Token provider

`CollectorTokenProvider` implements the OAuth 2.0 client-credentials grant against the tenant-specific Microsoft identity platform v2 token endpoint. It requests only `https://graph.microsoft.com/.default`, applies a bounded timeout, and acquires a token lazily when `get_token()` is first called.

Tokens remain in process memory only. An unexpired token is reused; a token inside the configurable refresh-skew window is replaced before expiry. Failed acquisition clears the cache, and no persistent token cache is created. Token endpoint failures are classified as missing configuration, rejected client credentials, token HTTP/network failure, or malformed token response. Error text excludes response descriptions and credential material.

## Environment and configuration

The Collector requires these process variables:

- `GRAPH_TENANT_ID`
- `GRAPH_CLIENT_ID`
- `GRAPH_CLIENT_SECRET`

There are no default credentials. Missing-variable errors identify variable names but never values. Process environment is preferred. `env_file_source()` provides minimal compatibility with the protected `secrets/collector.env` file without logging, printing, or returning unrelated environment entries. The protected file is not modified.

## Runtime flow

`CollectorRuntime` loads and validates the endpoint inventory, resolves one endpoint, a supplied endpoint-ID set, or all enabled endpoints, builds the token provider and `GraphTransport`, and executes `BaseCollector` for each selected specification. Behavior remains data-driven through `EndpointSpec`; the runtime contains no workload-specific endpoint implementations and performs no database writes.

Authentication failures that prevent Graph traffic become structured `CollectionResult` objects. Graph HTTP 403 remains `PERMISSION_REQUIRED`, distinct from token-acquisition authentication failure.

## CLI and dry-run

The offline validation entry point is:

```console
python3 -m collectors.run_collector --endpoint G01-001 --dry-run
python3 -m collectors.run_collector --all --dry-run
python3 -m collectors.run_collector --all --inventory config/api_inventory.json --dry-run --json
```

`--endpoint`, `--endpoints`, and `--all` are mutually exclusive selections. `--inventory` overrides the inventory path. Dry-run loads and validates the inventory and authentication configuration and resolves the selection, but does not instantiate a live HTTP opener, request a token, or call Microsoft Graph. Output contains endpoint identifiers and validation status only; it never includes credential values or token-bearing headers. Live workload execution remains programmatic until a future workload supplies its HTTP integration.

## Configuration flow

```
config/api_inventory.json
        |
        v
inventory.load_inventory(path)
        |
        v
List[EndpointSpec]   <-- validated, dataclass-based, no credentials
        |
        v
enabled_specs(specs)   <-- filter on .enabled
        |
        v
BaseCollector(spec, transport).collect()
        |
        v
CollectionResult
```

The inventory file format is the same one the Discovery Agent already
uses. The framework wraps each entry in an `EndpointSpec` and validates
it defensively (required fields, types, `pagination` boolean,
`top` integer or null, `select` list of strings). Unknown fields are
ignored so the same file can drive G01 and G07 collectors.

## Request and pagination flow

For one `EndpointSpec`:

1. `BaseCollector._initial_url()` calls `transport.build_endpoint_url`
   to attach `$select` and `$top` to the path (or uses a full URL such
   as an `@odata.nextLink`).
2. `Paginator.run(url)` calls `transport.get_json(url)` for each page.
3. Each successful response's `value[]` is appended; rows are counted.
4. If the response carries an `@odata.nextLink`, the paginator uses it
   verbatim as the next URL.
5. When the response has no `@odata.nextLink`, pagination ends and the
   paginator reports `PASS`.

If the transport raises `GraphHttpError` or `GraphNetworkError`, the
paginator stops, records the status / classification, and returns.

## Error classification

| Status / condition | Classification | Retryable? |
|---|---|---|
| 2xx | `PASS` | no |
| 401 | `AUTH_FAILURE` | **no** |
| 403 | `PERMISSION_REQUIRED` | **no** |
| 429 | `THROTTLED` | yes (honors `Retry-After`) |
| any other non-2xx | `API_ERROR` | yes (transient 5xx) |
| transport / DNS / timeout / socket | `NETWORK_ERROR` | yes |

Classification rules live in `collectors/core/errors.py` and are
exercised by unit tests. 429 is **never** classified as
`AUTH_FAILURE`.

## Retry behavior

- `RetryPolicy(max_retries=N)` allows up to **N retries** beyond the
  initial attempt. With `max_retries=2` the policy performs at most
  three attempts in total before giving up.
- `AUTH_FAILURE` and `PERMISSION_REQUIRED` are never retried (they
  cannot resolve themselves by retrying).
- `THROTTLED` honors an integer `Retry-After` value when present;
  invalid `Retry-After` values are ignored.
- `RetryPolicy.sleep` is injectable so tests never sleep for real.

## Security boundaries

- The token is supplied to the transport through a callable
  (`token_provider`) that is invoked only at request time. The token is
  never stored on the transport or in any framework object.
- `Authorization` header values are never logged. The `GraphHttpError`
  class deliberately exposes only the safe `Retry-After` header.
- `CollectionResult` does not contain any credential field. Its
  serialization is verified by tests to contain no `Bearer`,
  `Authorization`, or token substrings.
- Authentication configuration is read only through filtered sources that return the three required `GRAPH_*` variables. Raw environment contents are never serialized.
- `secrets/collector.env` may be read by the minimal compatibility source, but is never modified, printed, logged, copied into evidence, or returned wholesale.
- Safe result serialization removes credential-shaped keys and rejects token-bearing text such as `Bearer` header values.
- Token endpoint response descriptions are not propagated because identity-platform descriptions may echo request metadata.

## Relationship to Discovery Agent

- The Discovery Agent (G01) keeps its existing implementation,
  classification rules, state file, evidence directory, and document
  generator untouched. G05-001 does not refactor G01.
- The classification strings defined by the framework
  (`PASS`, `AUTH_FAILURE`, `PERMISSION_REQUIRED`, `THROTTLED`,
  `API_ERROR`, `NETWORK_ERROR`) deliberately match the names the
  Discovery Agent already uses, so downstream state files remain
  forward-compatible.
- The `RetryPolicy` `should_retry` decisions preserve the existing
  semantics: auth and permission failures never loop; throttled
  endpoints respect `Retry-After`.

## What remains for future tasks

- **G06** — database schema and persistence for collected rows. The framework returns `CollectionResult` objects ready for persistence but does not itself write to a database.
- **G07** — actual SharePoint / OneDrive / Exchange / Teams collectors. They will consume this runtime and either reuse `config/api_inventory.json` or define a workload-specific inventory consumed by the same loader.