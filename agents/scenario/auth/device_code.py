"""OAuth 2.0 device-code flow for the Scenario Agent.

The :class:`DeviceCodeFlow` performs the **public-client** delegated
device-code grant against the Microsoft identity platform. The flow is:

1. POST ``/oauth2/v2.0/devicecode`` to receive a ``user_code`` and
   ``verification_uri`` to display to the operator.
2. Poll ``/oauth2/v2.0/token`` with ``grant_type=urn:ietf:params:oauth:grant-type:device_code``
   until the user completes sign-in, declines, or the code expires.

The flow is implemented as a **pure** state machine. It performs no
network I/O of its own. The caller injects a transport (an instance of
:mod:`agents.scenario.auth.transports`). The transport is the only
place the flow ever talks to ``login.microsoftonline.com`` -- in
production. In tests, the caller injects
:class:`FakeDeviceCodeTransport` and no socket is ever opened.

The flow:

* never accepts a client secret,
* never accepts a username or password (no ROPC / no password grant),
* never writes the access token or refresh token to disk,
* never echoes the access token through ``__repr__`` or any string
  formatter,
* classifies failures using the closed vocabulary declared in
  :mod:`agents.scenario.live_executor`.

The :func:`_http_post_form` helper is exposed for the future
production transport; the offline test path does not use it. Tests
must not import it.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Tuple

from .transports import (
    DeviceCodePollTransport,
    DeviceCodeRequestTransport,
    TokenTransportResponse,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DeviceCodeError(Exception):
    """Base error for the device-code flow.

    Carries a deterministic ``classification`` so the live executor can
    map the failure into a closed evidence label. The default
    classification is ``AUTH_DEVICE_CODE_ERROR``.
    """

    classification: str = "AUTH_DEVICE_CODE_ERROR"

    def __init__(self, classification: str, message: str) -> None:
        if not classification or not isinstance(classification, str):
            raise ValueError("classification must be a non-empty string")
        self.classification = classification
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Prompt and token shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, repr=False)
class DeviceCodePrompt:
    """Transient operator-visible portion of a device-code response.

    The class intentionally does NOT carry the ``device_code`` (the
    confidential value used for polling). It is passed only to the prompt and
    confirmation callbacks during :meth:`DeviceCodeFlow.run`; it is never
    returned, serialized, or retained after those callbacks complete.
    """

    user_code: str
    verification_uri: str
    expires_in_seconds: int
    interval_seconds: int
    message: str

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return "DeviceCodePrompt(<transient authentication instructions>)"


@dataclass
class DeviceCodeToken:
    """The result of a successful device-code poll.

    The ``access_token`` is private to the executor. ``__repr__`` is
    redacted so that accidental ``str(...)`` calls do not leak the
    token. The ``object`` only lives as long as the executor needs it
    and is never persisted.
    """

    access_token: str
    expires_in_seconds: int
    token_type: str
    scope: str

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return (
            "DeviceCodeToken(access_token=<redacted>, "
            "expires_in_seconds={!r}, token_type={!r}, scope={!r})"
        ).format(self.expires_in_seconds, self.token_type, self.scope)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _http_post_form(
    url: str,
    form: Mapping[str, str],
    *,
    timeout: float = 30.0,
) -> TokenTransportResponse:
    """POST ``form`` to ``url`` and return a :class:`TokenTransportResponse`.

    This helper is the seam where the **real** Microsoft identity
    platform transport will live. The live executor wires this helper
    in production; offline tests wire a fake and never call it.

    The helper performs the request synchronously and returns the
    parsed body. The caller is responsible for never echoing the body
    in evidence.

    This function is intentionally a *runtime* seam: it is not called
    by the offline test path. It is exposed via the
    :mod:`agents.scenario.auth` package surface so the future
    production transport can be built on top of it without changing
    the public API.
    """
    # The real implementation would use ``urllib.request`` here. It
    # is intentionally stubbed in this task because this task is
    # offline-tests only. Tests must not call it.
    raise DeviceCodeError(
        "AUTH_DEVICE_CODE_ERROR",
        "Real device-code transport is not wired in this build (offline-only).",
    )


def _classify_poll_response(
    response: TokenTransportResponse,
) -> Tuple[bool, Optional[str]]:
    """Classify a poll response.

    Returns ``(is_pending, oauth_error)``. When the response is a
    Microsoft identity platform "pending" body, ``is_pending`` is
    ``True`` and the caller should sleep and re-poll. When the
    response is a terminal error, ``oauth_error`` is the ``error``
    field value (``authorization_declined``, ``expired_token``,
    ``invalid_grant``, ...). When the response carries an
    ``access_token`` the tuple is ``(False, None)``.

    The ``authorization_pending`` error code is the only error code
    that is non-terminal: it is reported by Microsoft identity
    platform while the user is still signing in. The function
    always returns ``(True, None)`` for that code, regardless of
    whether the caller supplied ``is_error=True`` on the response
    shape.
    """
    body = response.body or {}
    if not isinstance(body, Mapping):
        return False, None
    if "access_token" in body and not response.is_error:
        return False, None
    error_code = body.get("error")
    if error_code == "authorization_pending":
        return True, None
    if response.is_error or response.status >= 400:
        return False, error_code if isinstance(error_code, str) else None
    return False, None


def _is_terminal_error(oauth_error: Optional[str]) -> bool:
    """Return True if ``oauth_error`` is a terminal failure."""
    if not oauth_error:
        return False
    return oauth_error in {
        "authorization_declined",
        "expired_token",
        "invalid_grant",
        "invalid_client",
        "access_denied",
    }


# ---------------------------------------------------------------------------
# Device-code flow
# ---------------------------------------------------------------------------


@dataclass
class DeviceCodeFlow:
    """Pure state machine for the public-client device-code grant.

    Constructor arguments:

    * ``client_id`` -- the application (client) ID of the Scenario
      Agent app (``graph-agent-scenario-dev``). No client secret.
    * ``tenant_id`` -- the tenant ID. Used to build the device-code
      and token endpoints. No real endpoint is opened by this class;
      the value is forwarded to the injected transport.
    * ``scopes`` -- the delegated scopes to request. The Scenario
      Agent baseline is ``("User.Read",)``. The flow never requests
      more than the caller supplies.
    * ``request_transport`` -- a callable that issues the device-code
      request. Tests inject
      :class:`~agents.scenario.auth.transports.FakeDeviceCodeTransport`.
    * ``poll_transport`` -- a callable that polls the token endpoint.
    * ``sleep`` -- an injectable sleep function. Tests inject a fake
      to make the flow deterministic. ``time.sleep`` is the default
      for the future production path.
    * ``timeout_seconds`` -- the absolute time budget for the entire
      flow (request + poll). The flow stops polling once this budget
      is exceeded and raises :class:`DeviceCodeError` classified
      ``AUTH_TIMEOUT``.
    * ``clock`` -- an injectable monotonic clock used to enforce the
      timeout. ``time.monotonic`` is the default.

    Private state lifecycle: the confidential ``device_code`` received
    from the request step is held in a private attribute (never on
    the prompt, never in a repr) only while polling requires it.
    :meth:`run` clears it in a ``finally`` block, so the state is
    dropped as soon as the flow reaches **any** terminal outcome:
    success, declined, expiry/timeout, token error, or transport
    failure. The class performs no I/O of its own. All network
    interactions are forwarded to the injected transports.
    """

    client_id: str
    tenant_id: str
    scopes: Tuple[str, ...]
    request_transport: DeviceCodeRequestTransport
    poll_transport: DeviceCodePollTransport
    prompt_callback: Optional[Callable[[DeviceCodePrompt], None]] = field(
        default=None, repr=False
    )
    confirmation_callback: Optional[Callable[[DeviceCodePrompt], bool]] = field(
        default=None, repr=False
    )
    sleep: Callable[[float], None] = field(default=time.sleep)
    timeout_seconds: float = 300.0
    clock: Callable[[], float] = field(default=time.monotonic)

    # Private: the confidential device_code used for polling. It is
    # set by _request_device_code and MUST NOT outlive the terminal
    # outcome of run(); run() clears it in a finally block. It is
    # excluded from repr and equality so it can never leak through a
    # dataclass stringification.
    _device_code: Optional[str] = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    # ---- Public properties ------------------------------------------

    @property
    def device_code_endpoint(self) -> str:
        return (
            "https://login.microsoftonline.com/{0}/oauth2/v2.0/devicecode"
        ).format(self.tenant_id)

    @property
    def token_endpoint(self) -> str:
        return (
            "https://login.microsoftonline.com/{0}/oauth2/v2.0/token"
        ).format(self.tenant_id)

    @property
    def requested_scopes(self) -> Tuple[str, ...]:
        return tuple(self.scopes)

    # ---- Public API -------------------------------------------------

    def run(self) -> DeviceCodeToken:
        """Run the device-code flow and return only the private token.

        The prompt is delivered synchronously to transient operator callbacks
        and does not cross this method's return boundary. The token is private;
        the caller is responsible for not echoing it.

        The private ``device_code`` state is cleared in a ``finally``
        block so it never outlives a terminal outcome (success,
        declined, expiry/timeout, token error, or transport failure).
        """
        deadline = self.clock() + float(self.timeout_seconds)
        try:
            prompt = self._request_device_code()
            if self.prompt_callback is not None:
                self.prompt_callback(prompt)
            if self.confirmation_callback is not None:
                try:
                    confirmed = self.confirmation_callback(prompt)
                except KeyboardInterrupt:
                    raise DeviceCodeError(
                        "AUTH_DECLINED",
                        "Operator confirmation was interrupted; token polling was not started.",
                    ) from None
                except Exception:
                    raise DeviceCodeError(
                        "AUTH_DECLINED",
                        "Operator confirmation failed; token polling was not started.",
                    ) from None
                if confirmed is not True:
                    raise DeviceCodeError(
                        "AUTH_DECLINED",
                        "Operator confirmation was not accepted; token polling was not started.",
                    )
            interval = prompt.interval_seconds
            # The callbacks have completed; do not retain challenge material
            # while the remainder of the flow waits for a token.
            del prompt
            if self.clock() > deadline:
                raise DeviceCodeError(
                    "AUTH_TIMEOUT",
                    "Device-code expired before token polling was authorized.",
                )
            return self._poll_for_token(interval, deadline)
        finally:
            # Fail-safe cleanup: drop the confidential device-code
            # state on every terminal path. Polling no longer needs
            # the value once run() exits.
            self._clear_device_code_state()

    # ---- Internals --------------------------------------------------

    def _clear_device_code_state(self) -> None:
        """Drop the private device-code state from the flow.

        Best-effort secret hygiene: the string is immutable in
        CPython so the buffer cannot be zeroed, but dropping the
        reference makes the value eligible for garbage collection as
        soon as the flow reaches a terminal result.
        """
        self._device_code = None

    def _request_device_code(self) -> DeviceCodePrompt:
        try:
            response = self.request_transport({
                "client_id": self.client_id,
                "scope": " ".join(self.scopes),
            })
        except Exception as error:
            raise DeviceCodeError(
                "AUTH_DEVICE_CODE_ERROR",
                "Device-code request failed: {0}".format(type(error).__name__),
            ) from None

        if response.is_error or response.status >= 400:
            oauth_error = response.oauth_error_code() or "<unknown>"
            raise DeviceCodeError(
                "AUTH_DEVICE_CODE_ERROR",
                "Device-code endpoint rejected request (oauth_error={0})".format(
                    oauth_error,
                ),
            )

        body = response.body or {}
        if not isinstance(body, Mapping):
            raise DeviceCodeError(
                "AUTH_DEVICE_CODE_ERROR",
                "Device-code endpoint returned non-object body.",
            )

        try:
            user_code = str(body["user_code"])
            verification_uri = str(body["verification_uri"])
            expires_in = int(body.get("expires_in", 0))
            interval = int(body.get("interval", 5))
        except (KeyError, TypeError, ValueError):
            raise DeviceCodeError(
                "AUTH_DEVICE_CODE_ERROR",
                "Device-code response missing required fields.",
            )

        if expires_in <= 0 or interval <= 0:
            raise DeviceCodeError(
                "AUTH_DEVICE_CODE_ERROR",
                "Device-code response has invalid expires_in/interval.",
            )

        message = str(body.get("message", ""))

        # We intentionally do NOT keep ``device_code`` on the prompt.
        # It is the confidential value used for polling; it lives in a
        # private attribute of the flow.
        self._device_code = str(body.get("device_code", ""))
        if not self._device_code:
            raise DeviceCodeError(
                "AUTH_DEVICE_CODE_ERROR",
                "Device-code response missing device_code.",
            )

        return DeviceCodePrompt(
            user_code=user_code,
            verification_uri=verification_uri,
            expires_in_seconds=expires_in,
            interval_seconds=interval,
            message=message,
        )

    def _poll_for_token(
        self,
        interval: int,
        deadline: float,
    ) -> DeviceCodeToken:
        last_error: Optional[str] = None
        device_code = self._device_code or ""
        while True:
            if self.clock() > deadline:
                raise DeviceCodeError(
                    "AUTH_TIMEOUT",
                    "Device-code flow exceeded configured timeout "
                    "({0}s).".format(self.timeout_seconds),
                )
            try:
                response = self.poll_transport({
                    "grant_type": (
                        "urn:ietf:params:oauth:grant-type:device_code"
                    ),
                    "client_id": self.client_id,
                    "device_code": device_code,
                })
            except Exception as error:
                raise DeviceCodeError(
                    "AUTH_TOKEN_ERROR",
                    "Device-code poll failed: {0}".format(type(error).__name__),
                ) from None

            is_pending, oauth_error = _classify_poll_response(response)
            if is_pending:
                # Not yet complete. Sleep ``interval`` and re-poll.
                self.sleep(float(interval))
                continue

            if oauth_error:
                last_error = oauth_error
                if oauth_error == "authorization_declined":
                    raise DeviceCodeError(
                        "AUTH_DECLINED",
                        "Device-code sign-in was declined by the user.",
                    )
                if oauth_error == "expired_token":
                    raise DeviceCodeError(
                        "AUTH_TIMEOUT",
                        "Device-code expired before sign-in completed.",
                    )
                if oauth_error in {"invalid_grant", "invalid_client"}:
                    raise DeviceCodeError(
                        "AUTH_TOKEN_ERROR",
                        "Device-code poll rejected (oauth_error={0})".format(
                            oauth_error,
                        ),
                    )
                # Unknown but terminal error.
                raise DeviceCodeError(
                    "AUTH_TOKEN_ERROR",
                    "Device-code poll returned error (oauth_error={0})".format(
                        oauth_error,
                    ),
                )

            body = response.body or {}
            if not isinstance(body, Mapping):
                raise DeviceCodeError(
                    "AUTH_TOKEN_ERROR",
                    "Device-code poll returned non-object body.",
                )
            access_token = body.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise DeviceCodeError(
                    "AUTH_TOKEN_ERROR",
                    "Device-code poll response missing access_token.",
                )
            try:
                expires_in = int(body.get("expires_in", 0))
            except (TypeError, ValueError):
                raise DeviceCodeError(
                    "AUTH_TOKEN_ERROR",
                    "Device-code poll response missing valid expires_in.",
                ) from None
            if expires_in <= 0:
                raise DeviceCodeError(
                    "AUTH_TOKEN_ERROR",
                    "Device-code poll response missing valid expires_in.",
                )
            token_type = str(body.get("token_type", "Bearer"))
            scope = str(body.get("scope", " ".join(self.scopes)))
            return DeviceCodeToken(
                access_token=access_token,
                expires_in_seconds=expires_in,
                token_type=token_type,
                scope=scope,
            )


__all__ = [
    "DeviceCodeError",
    "DeviceCodeFlow",
    "DeviceCodePrompt",
    "DeviceCodeToken",
    "_http_post_form",
    "_classify_poll_response",
    "_is_terminal_error",
]
