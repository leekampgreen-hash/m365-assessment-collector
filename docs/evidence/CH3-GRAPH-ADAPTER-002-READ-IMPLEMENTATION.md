# CH3-GRAPH-ADAPTER-002 Read Implementation

## Scope

Implemented the Scenario Agent's real, read-focused Microsoft Graph adapter
path. The adapter exposes only the fixed operations `USER_LIST` and
`GROUP_LIST`, backed by `GET /users` and `GET /groups` respectively.

## Runtime Controls

Each execution requires all of the following before a transport call:

- A registered `OperationType` from the closed operation registry.
- An `AuthenticationContext` containing a non-empty ephemeral access token and
  a verified `MeIdentity` from the Scenario Agent's mandatory `/me` identity
  validation boundary.
- An `AuthorizationContext` that explicitly authorizes the requested
  operation.
- A `PolicyChecker` decision of exactly `ALLOW` for the requested operation.
- A non-empty Scenario Agent correlation identifier.

The adapter does not accept an endpoint, URL, HTTP method, request body, or
headers from its caller. It dispatches only to the fixed-operation transport
methods `get_users` and `get_groups`. The production HTTPS transport binds
those methods to the exact Graph endpoints and the `GET` method, with redirect
following disabled.

## Persistable Evidence

The only response-derived result is `OperationMetadata`:

- operation
- timestamp (UTC)
- status
- object count
- correlation id

Access tokens, headers, raw Graph payloads, secrets, and identity response
fields are not part of `OperationMetadata` and are not persisted by this path.
The access token is accepted only through the ephemeral authenticated context
and is supplied directly to the fixed transport call.

## Verification

Completed successfully:

```text
python3 -m unittest tests.scenario.test_read_focused_adapter
Ran 6 tests ... OK

python3 -m compileall -q agents/scenario
exit 0

docker compose config
exit 0
```

The focused tests cover successful mocked user and group reads, unsupported
operation rejection, missing policy approval rejection, missing authentication
context rejection, and token/raw-payload exclusion from result metadata.

The full test command was also run:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

It executed 625 tests and reported three existing failures in
`tests/scenario/live/test_d2_operator_entrypoint.py`. Those tests attempted a
live socket connection and their mocked request transport was not reached.
The adapter work initially exposed and then restored the legacy
`allowed_endpoints` tuple contract; the remaining three failures are outside
the adapter path.

## Explicit Non-Changes

- No Graph write operation was added.
- No HTTP `POST`, `PATCH`, `PUT`, or `DELETE` Graph operation was added.
- No delegated permissions were added or changed.
- No Entra configuration was changed.
- No collector code was changed.
- No token persistence or raw Graph response persistence was added.
