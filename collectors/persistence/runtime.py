"""Production-edge PostgreSQL connection setup.

The persistence core remains database-driver agnostic. This module only loads
the protected runtime connection settings and creates a DB-API connection for
the CLI boundary.
"""
from __future__ import annotations

import os
from pathlib import Path


DEFAULT_ENV_FILE = Path("secrets/graph-agent-postgres-runtime.env")
DEFAULT_PASSWORD_FILE = Path("/run/secrets/graph_agent_runtime_password")
_CONNECTION_KEYS = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGSSLMODE")


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def open_database_connection(
    *,
    env_file: Path = DEFAULT_ENV_FILE,
    password_file: Path = DEFAULT_PASSWORD_FILE,
):
    """Create the production DB-API connection without exposing credentials."""
    try:
        env_file_exists = env_file.exists()
    except PermissionError:
        # The workspace fallback may be intentionally unreadable in production.
        env_file_exists = False
    values = _read_env_file(env_file) if env_file_exists else {}
    params = {key: os.environ.get(key, values.get(key, "")) for key in _CONNECTION_KEYS}
    password = os.environ.get("PGPASSWORD", "")
    if not password and password_file.exists():
        password = password_file.read_text(encoding="utf-8").strip()
    params["password"] = password
    missing = [key for key in ("PGHOST", "PGDATABASE", "PGUSER") if not params[key]]
    if missing:
        raise RuntimeError("missing database runtime configuration: " + ", ".join(missing))
    try:
        import psycopg
    except ImportError:
        raise RuntimeError("PostgreSQL driver is unavailable") from None
    try:
        connection_args = {
            "host": params["PGHOST"],
            "port": params["PGPORT"],
            "dbname": params["PGDATABASE"],
            "user": params["PGUSER"],
            "sslmode": params["PGSSLMODE"],
            "password": params["password"],
        }
        return psycopg.connect(**{key: value for key, value in connection_args.items() if value})
    except Exception as exc:
        raise RuntimeError("database connection failed: " + type(exc).__name__) from None
