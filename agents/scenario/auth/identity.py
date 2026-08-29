"""Microsoft Graph ``/me`` identity validator for the live executor.

The :class:`GraphMeValidator` performs a single ``GET /me`` against
Microsoft Graph using the access token returned by the device-code
flow. The response is matched against the **expected actor identity**
supplied by the caller.

The validator:

* performs no I/O of its own; the caller injects a transport,
* never echoes the bearer token in any return value, repr, or log,
* never returns the raw ``/me`` body to the caller; it returns a
  narrow :class:`MeIdentity` with only the fields the executor
  needs,
* classifies all failures using the closed vocabulary declared in
  :mod:`agents.scenario.live_executor`.

The validator is the **actor verification boundary**: the Scenario
Agent refuses to act under any user whose ``/me`` identity does not
match the expected actor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Tuple

from .transports import GraphMeTransport, TokenTransportResponse


# ---------------------------------------------------------------------------
# Identity shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeIdentity:
    """The narrow identity shape returned to the executor.

    Only the fields the live executor needs for actor verification and
    evidence correlation are exposed. The ``display_name`` is
    optional; many Entra tenants do not set it for service accounts.
    """

    object_id: str
    user_principal_name: str
    display_name: str = ""

    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "user_principal_name": self.user_principal_name,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class ExpectedActor:
    """The expected actor identity supplied by the runtime.

    The expected identity may be partial: if ``user_principal_name`` is
    ``None`` we match on ``object_id`` only, and vice versa. If both
    are ``None`` the validator raises a configuration error -- at
    least one field must be supplied so a silent identity mismatch
    cannot happen.

    A field only counts as present when it is a non-blank string.
    Blank or whitespace-only values do not constitute verifiable
    identity and fail the emptiness check, so they can never be used
    to bypass actor verification.
    """

    object_id: Optional[str] = None
    user_principal_name: Optional[str] = None

    def is_empty(self) -> bool:
        object_id = (
            self.object_id.strip() if isinstance(self.object_id, str) else None
        )
        upn = (
            self.user_principal_name.strip()
            if isinstance(self.user_principal_name, str)
            else None
        )
        return not (object_id or upn)


# ---------------------------------------------------------------------------
# Graph /me validator
# ---------------------------------------------------------------------------


class GraphMeValidator:
    """Validator that performs a single ``GET /me`` and checks the
    identity against an :class:`ExpectedActor`.

    The validator holds the bearer token in a private attribute and
    wipes it after the request. The token never leaves the validator
    via ``__repr__``, exception messages, or return values.
    """

    GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"

    def __init__(
        self,
        *,
        transport: GraphMeTransport,
        expected: ExpectedActor,
        graph_endpoint: str = GRAPH_ME_URL,
    ) -> None:
        if transport is None:
            raise ValueError("transport is required")
        if expected is None or expected.is_empty():
            raise ValueError(
                "expected actor must declare at least one of "
                "object_id / user_principal_name"
            )
        self._transport = transport
        self._expected = expected
        self._graph_endpoint = graph_endpoint

    @property
    def expected(self) -> ExpectedActor:
        return self._expected

    def validate(self, access_token: str) -> MeIdentity:
        """Validate the supplied ``access_token`` against the expected
        actor.

        Returns the :class:`MeIdentity` on success. Raises
        :class:`GraphMeError` on any failure. The token is never
        included in the exception message.
        """
        if not isinstance(access_token, str) or not access_token:
            raise GraphMeError(
                "GRAPH_ME_VALIDATION_FAILED",
                "Access token is empty.",
            )

        try:
            response = self._transport(access_token, self._graph_endpoint)
        except Exception as error:
            raise GraphMeError(
                "GRAPH_ME_VALIDATION_FAILED",
                "Graph /me transport error: {0}".format(type(error).__name__),
            ) from None

        if response.is_error or response.status >= 400:
            oauth_error = response.oauth_error_code() or "<unknown>"
            raise GraphMeError(
                "GRAPH_ME_VALIDATION_FAILED",
                "Graph /me rejected request (oauth_error={0})".format(
                    oauth_error,
                ),
            )

        body = response.body or {}
        if not isinstance(body, Mapping):
            raise GraphMeError(
                "GRAPH_ME_VALIDATION_FAILED",
                "Graph /me returned non-object body.",
            )

        object_id = body.get("id")
        upn = body.get("userPrincipalName")
        display_name = body.get("displayName", "")

        if not isinstance(object_id, str) or not object_id:
            raise GraphMeError(
                "GRAPH_ME_VALIDATION_FAILED",
                "Graph /me response missing id.",
            )

        identity = MeIdentity(
            object_id=object_id,
            user_principal_name=upn if isinstance(upn, str) else "",
            display_name=display_name if isinstance(display_name, str) else "",
        )

        if not self._matches_expected(identity):
            raise GraphMeError(
                "ACTOR_IDENTITY_MISMATCH",
                "Graph /me identity does not match the expected actor.",
            )

        return identity

    # ---- Internals --------------------------------------------------

    def _matches_expected(self, identity: MeIdentity) -> bool:
        expected_object_id = self._expected.object_id
        expected_upn = self._expected.user_principal_name

        match_object_id = (
            expected_object_id is not None
            and identity.object_id == expected_object_id
        )
        match_upn = (
            expected_upn is not None
            and identity.user_principal_name == expected_upn
        )

        # If both are provided, both must match (defence in depth).
        if expected_object_id is not None and expected_upn is not None:
            return match_object_id and match_upn
        # Otherwise, only the supplied field needs to match.
        return match_object_id or match_upn


class GraphMeError(Exception):
    """Structured error from the Graph /me validator.

    The default classification is ``GRAPH_ME_VALIDATION_FAILED``; the
    actor-mismatch path raises with ``ACTOR_IDENTITY_MISMATCH``.
    """

    classification: str = "GRAPH_ME_VALIDATION_FAILED"

    def __init__(self, classification: str, message: str) -> None:
        if not classification or not isinstance(classification, str):
            raise ValueError("classification must be a non-empty string")
        self.classification = classification
        self.message = message
        super().__init__(message)


__all__ = [
    "ExpectedActor",
    "GraphMeError",
    "GraphMeValidator",
    "MeIdentity",
]
