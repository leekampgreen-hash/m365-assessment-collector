# Graph Agent DEV PostgreSQL Runtime

The `postgres` Compose service is dedicated to this project. It uses the
`graph-agent-net` Docker network and the `graph-agent-postgres-data` named
volume; it publishes no host port and does not use the XDR database.

First initialization creates only `graph_agent`, its migration owner
`graph_agent_migrator`, and its runtime login `graph_agent_runtime`. No G06
schemas, tables, tenant data, or migrations are created or applied.

TLS is intentionally deferred for this DEV-only service because PostgreSQL is
reachable only on the isolated Docker network and has no public/host port.
`PGSSLMODE=disable` records this limitation explicitly. Production deployment
must enable and validate TLS before traffic leaves this internal boundary.

Passwords are Docker file secrets under `secrets/`, restricted to mode 600,
and are never committed or included in connection strings.
