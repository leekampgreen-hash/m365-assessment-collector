"""Auth configuration loading for the collector framework.

The collector's three required logical variables are:

    GRAPH_TENANT_ID
    GRAPH_CLIENT_ID
    GRAPH_CLIENT_SECRET

Loading is delegated to a small ``Source`` callable that returns a
``Mapping[str, str]``. The framework ships two source implementations:

- ``EnvSource`` -- reads from ``os.environ`` (the default in production).
- ``DictSource`` -- reads from an in-memory mapping (used by tests and
  by the ``--dry-run`` CLI path).

To remain compatible with the existing protected
``secrets/collector.env`` file without ever exposing its contents, a
file source is provided (``EnvFileSource``). It ONLY reads variable
values into a local mapping; it never logs them, never returns the full
file contents, and the framework never logs raw env contents.

Security:

- The config object stores the secret as an attribute on
  ``CollectorAuthConfig`` (see ``auth.py``); its ``repr`` is redacted.
- This module never logs a value, never prints a value, and never
  returns the source contents to callers beyond the three required keys.
- Error messages name missing variables, NEVER values.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Mapping, Optional

from .auth import CollectorAuthConfig


REQUIRED_VARS = ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")


class AuthConfigError(ValueError):
    """Raised when one or more required auth variables are missing.

    The message lists missing variable names, NEVER values.
    """


# --- Sources ------------------------------------------------------------


Source = Callable[[], Mapping[str, str]]


def env_source(env: Optional[Mapping[str, str]] = None) -> Source:
    """Build a source that reads from ``os.environ`` (or a caller mapping).

    The returned callable returns ONLY the three required keys (filtered
    out from the broader environment to avoid accidentally serializing
    unrelated variables).
    """
    backing = env if env is not None else os.environ

    def _load() -> Mapping[str, str]:
        return {key: backing.get(key, "") for key in REQUIRED_VARS}

    return _load


def dict_source(values: Mapping[str, str]) -> Source:
    """Build a source from an explicit mapping (used by tests and dry-run).

    Only the three required keys are returned. Other keys are ignored.
    """

    def _load() -> Mapping[str, str]:
        return {key: str(values.get(key, "")) for key in REQUIRED_VARS}

    return _load


def env_file_source(path) -> Source:
    """Build a source that reads a ``.env``-style file.

    The file format is one ``KEY=VALUE`` per line, with optional ``#``
    comments and optional single/double quotes around values. No
    variable expansion, no shell substitution.

    The file is read once at construction time, not per ``load()`` call,
    to avoid surprising behavior if the file is modified under the
    process. The raw file contents are not retained -- only the three
    required keys are kept on the resulting mapping.
    """
    file_path = Path(path)

    def _load() -> Mapping[str, str]:
        raw: dict = {}
        with file_path.open(encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                raw[key.strip()] = value.strip().strip("'\"")
        return {key: raw.get(key, "") for key in REQUIRED_VARS}

    return _load


# --- Loader -------------------------------------------------------------


def load_auth_config(source: Source) -> CollectorAuthConfig:
    """Load a ``CollectorAuthConfig`` from ``source``.

    Raises ``AuthConfigError`` listing missing variable names (never
    values). Raises ``TypeError`` if the source returns non-strings.
    """
    if source is None:
        raise AuthConfigError("Auth source is required")
    try:
        values = source()
    except FileNotFoundError as exc:
        raise AuthConfigError("Auth env file not found: {}".format(exc.filename or "?")) from None
    except OSError as exc:
        raise AuthConfigError("Auth env file could not be read: {}".format(type(exc).__name__)) from None

    missing = [key for key in REQUIRED_VARS if not values.get(key)]
    if missing:
        raise AuthConfigError("Missing required auth variables: " + ", ".join(missing))

    for key in REQUIRED_VARS:
        if not isinstance(values[key], str):
            raise AuthConfigError("Auth variable {} is not a string".format(key))

    return CollectorAuthConfig(
        tenant_id=values["GRAPH_TENANT_ID"],
        client_id=values["GRAPH_CLIENT_ID"],
        client_secret=values["GRAPH_CLIENT_SECRET"],
    )


__all__ = [
    "AuthConfigError",
    "REQUIRED_VARS",
    "Source",
    "dict_source",
    "env_file_source",
    "env_source",
    "load_auth_config",
]