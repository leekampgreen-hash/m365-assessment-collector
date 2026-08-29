# CH3-AUTH-EXEC-001: Scenario App-Only Runtime Candidate (Superseded)

> **Architecture status:** Superseded by `CH3-AUTH-BOUNDARY-001`. Per
> `docs/design/ADR-CH3-AUTH-001.md`, canonical Scenario Agent execution uses a
> dedicated test user, OAuth 2.0 device-code authentication, and delegated
> Microsoft Graph permissions. The app-only candidate implementation described
> below has been removed and must not be restored.

## Scope

This evidence records a removed candidate that formerly provided the Scenario
Agent with an OAuth 2.0 `client_credentials` runtime path. It is retained as a
historical record only.

This evidence does not approve, authorize, or establish an app-only Scenario
identity. It must not be used as the basis for future canonical Scenario
execution or permission grants.

## Removed Runtime Flow

The former Scenario app-only provider, coordinator, and secret-source interface
were removed. Scenario configuration is now represented by an explicit
delegated-user identity contract that cannot hold a client secret or Collector
identity. Device-code execution is intentionally not implemented by this
boundary-hardening task.

## Boundary Controls

The Scenario Compose service does not mount `./secrets`; only the Collector
service can access Collector credentials. The Scenario identity contract
accepts only `scenario_delegated_user` and its safe authentication context
rejects a Collector app-only identity type.

## Security Properties

- The Scenario runtime has no credential provider, secret source, or
  client-credentials grant.
- No Entra mutation, credential creation, permission change, or token storage
  is implemented.
- The context has no access-token field and uses `repr=False`.
- Authentication errors omit secret values, response bodies, tokens, and
  authorization headers.
- Adapter results retain operation metadata only, never raw Graph payloads.
- Graph access remains limited to the existing fixed `GET /users` and
  `GET /groups` adapter transport contract.

## Validation

The historical checks below validated the removed candidate implementation.
They do not validate the approved delegated Scenario Agent architecture.

- `python3 -m unittest tests.scenario.test_app_only_auth_execution tests.scenario.test_read_focused_adapter`
  passed: 12 tests.
- `python3 -m compileall -q agents/scenario tests/scenario` passed.
- `docker compose config` passed.
- `python3 -m unittest discover -s tests -p 'test*.py'` passed: 631 tests.
