# CH3-RUNTIME-INJECTION-DESIGN-001: Scenario Runtime Injection

## Status

Recommended design. This is an offline design record. It neither authorizes nor
performs authentication, Microsoft Graph calls, or Entra changes.

## Context and Scope

The canonical Scenario Agent uses delegated device-code authentication. Its
live entrypoint consumes these operator-supplied runtime values:

- `SCENARIO_CLIENT_ID`
- `SCENARIO_TENANT_ID`
- `SCENARIO_EXPECTED_ACTOR_OBJECT_ID`
- `SCENARIO_EXPECTED_ACTOR_UPN`

The values identify the approved Scenario application, tenant, and dedicated
test actor. They are configuration, not credentials: no client secret, token,
password, refresh token, or Collector credential is permitted. Nevertheless,
the actor identifiers are treated as restricted operational data and must not
be committed or emitted in logs.

The existing Compose topology mounts `./secrets` only into the Collector. The
Scenario service has no such mount. This design preserves that boundary.

## Options Evaluated

| Option | Assessment | Decision |
| --- | --- | --- |
| A. Compose `environment` injection | Safe only when values are supplied from a controlled host environment at invocation. Literal values in `docker-compose.yml`, a repository `.env`, shell history, CI definitions, or a committed override violate the storage and exposure requirements. It also makes review of the live configuration less explicit. | Not recommended as the primary mechanism. |
| B. Operator-managed runtime env file | A root-owned host file, outside the checkout, gives a bounded, reviewable source for the four values. Compose reads it during container creation and injects only those names into Scenario. No file is mounted into Scenario. The mechanism is available with the current Compose deployment model and introduces no credential type. | **Recommended.** |
| C. External secret/config mechanism | A managed configuration service can provide central access control, rotation, audit, and ephemeral injection. It is appropriate for a production orchestrator with an existing approved platform integration. Adding one solely for four non-secret identifiers increases dependencies and failure modes; it must not deliver a client secret or Collector material. | Deferred. Re-evaluate when the platform already has an approved workload-configuration integration. |

## Recommended Design

Use an operator-managed Compose override and env file, both outside the Git
checkout. The base `docker-compose.yml` remains free of actual identity values
and continues to define no Scenario secrets mount.

### Files and Locations

Create these host-managed files during approved operational setup:

| File | Purpose | Repository status |
| --- | --- | --- |
| `/etc/graph-agent/scenario/scenario-live.env` | Contains exactly the four `SCENARIO_*` assignments for one approved tenant and test actor. | Outside repository; never copied into it. |
| `/etc/graph-agent/compose/scenario-live.override.yml` | Adds the above file as `scenario.env_file` to the Scenario service only. | Outside repository; never copied into it. |

The env file format is simple `NAME=value` entries. It must contain no
`SCENARIO_CLIENT_SECRET`, token, password, `COLLECTOR_*` value, database
credential, or generic credential reference. A minimal override has this
shape, with no values embedded in the YAML:

```yaml
services:
  scenario:
    env_file:
      - /etc/graph-agent/scenario/scenario-live.env
```

The authorized operator starts the bounded Scenario service with both Compose
files. Routine `docker compose up` does not load the override and therefore
does not receive live Scenario identity configuration.

```bash
docker compose -f docker-compose.yml -f /etc/graph-agent/compose/scenario-live.override.yml up -d scenario
```

Do not use `docker compose config` without controls on its output while the
override is included, because it can render environment values. Validate the
file shape and permissions without printing its contents instead.

### Permission Model and Ownership

The host service account that runs Compose requires read access; no other
interactive user requires it.

| Path | Owner | Group | Mode | Rationale |
| --- | --- | --- | --- | --- |
| `/etc/graph-agent/scenario/` | `root` | `graph-agent-operators` | `0750` | Limits directory traversal to authorized operators. |
| `scenario-live.env` | `root` | `graph-agent-operators` | `0640` | Allows the approved Compose operator to read the configuration and denies write access. |
| `/etc/graph-agent/compose/` | `root` | `graph-agent-operators` | `0750` | Keeps the live-only wiring outside the checkout. |
| `scenario-live.override.yml` | `root` | `graph-agent-operators` | `0640` | Operators may use but not alter the approved wiring. |

Membership in `graph-agent-operators` is restricted to authorized live-run
operators. Changes require the normal operator approval record and host audit
trail. Root is the configuration owner. Docker daemon administrators are
trusted infrastructure administrators; Docker access is effectively privileged
and must not be granted to unapproved users.

### Container Exposure

Compose reads the env file on the host and passes the four values as process
into the container.

- The Scenario container receives only the four allowlisted names.
- The Collector service does not reference the env file, the override, or any
  Scenario value.
- The Scenario service continues to have no `/workspace/secrets` mount.
- No `client_secret` is injected, and no Collector credentials, credential
  paths, or `COLLECTOR_*` variables are injected.
- Environment variables are visible to code in the Scenario container and to
  host principals with Docker-inspection or equivalent privileged access. This
  is an accepted limitation for non-secret identifiers; it is not an excuse to
  log or export the values.

The Scenario process must retain the existing rule that its normal output is
sanitized. Operational commands must not print the env file, run `env` inside
the container, or render resolved Compose configuration into logs, tickets, or
evidence.

## Validation Flow

Perform this sequence before an approved live validation. All steps are local
configuration checks until the separately approved live procedure begins.

1. An authorized operator independently obtains the Scenario app client ID,
   tenant ID, and dedicated test actor object ID and UPN from the approved
   record. The operator verifies that the app is not the Collector app.
2. The configuration owner writes only the four required assignments to
   `/etc/graph-agent/scenario/scenario-live.env`, using a protected editor that
   does not retain the content in shell history. The owner applies the stated
   ownership and modes.
3. The owner verifies the env file contains exactly the approved variable
   names and no prohibited variable names without displaying values. A missing,
   blank, duplicate, or unrecognized assignment is a failed preflight.
4. The operator verifies the base Compose definition plus the external
   override target only `scenario`; it must not add volumes, networks,
   `command`, `entrypoint`, privileges, or any Collector configuration.
5. The operator starts only the Scenario service with the external override.
   The Scenario entrypoint must fail closed if any required variable is absent.
6. Under the separately approved CH3 live procedure, the runner performs its
   mandatory delegated `/me` actor comparison. Both configured expected actor
   fields must match. A mismatch stops the run and disables the live gate.
7. After the bounded run, stop the Scenario container and retain only
   sanitized evidence permitted by `CH3-SCENARIO-LIVE-VALIDATION-001`.

No validation step may authenticate, call Graph, or modify Entra unless the
separate live authorization has been granted.

## Rollback

Rollback is configuration removal, not an identity change:

1. Disable the live gate and stop the Scenario service.
2. Start Scenario only with the base `docker-compose.yml`, omitting the
   external override. This removes all four injected variables from the next
   container instance.
3. Under the configuration owner approval process, remove or replace the
   host env file. Do not move it into the repository, evidence, logs, or
   `/workspace/secrets`.
4. Confirm no Scenario container created with the override remains running.

This rollback makes no Entra mutation, permission change, credential rotation,
or Collector change.

## Security Impact

The design fixes the missing Scenario runtime configuration without weakening
the delegated-identity boundary. It prevents the most likely leakage paths:
committed Compose literals, a repository `.env`, shared secret mounts, and
cross-use of Collector credentials. The residual exposure is limited to the
Scenario process and privileged Docker/host administrators, consistent with
the non-secret nature of these identifiers. If policy later classifies actor
identifiers as secrets or requires central runtime audit, move to Option C
using an approved external configuration provider with equivalent allowlisting
and no filesystem mount.
