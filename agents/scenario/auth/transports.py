"""Transport protocols, fixed Microsoft HTTPS transports, and test fakes.

This module is shared between the device-code flow and the ``/me``
identity validator. It defines:

* :class:`TokenTransportResponse` -- the closed shape returned by any
  token transport. The shape is JSON-object-shaped so it can carry
  either a real Microsoft identity platform response or a fake.
* :class:`DeviceCodeRequestTransport` -- a protocol describing a
  callable that issues a device-code request and returns the body.
* :class:`DeviceCodePollTransport` -- a protocol describing a callable
  that polls the token endpoint and returns the body.
* :class:`GraphMeTransport` -- a protocol describing a callable that
  performs a ``GET /me`` against the chosen endpoint.
* :class:`FakeDeviceCodeTransport` -- a deterministic, programmable
  fake that offline tests use. The fake records all calls; it never
  opens a socket. The fake can be configured to return a successful
  payload, an ``authorization_pending`` payload, an
  ``authorization_declined`` payload, an ``expired_token`` payload,
  an ``invalid_grant`` payload, or an HTTP error. The fake is the
  only thing test code injects to make a device-code flow observable.
* :class:`FakeGraphTransport` -- the matching fake for ``/me``. The
  fake returns a configured object-id, UPN, and display name, or a
  controlled HTTP / network error.

The fake is the **only** way the live executor makes outbound
requests during a test. Real network code lives outside this package
and is wired by the future integration layer; this task is offline
tests only.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# Transport response shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenTransportResponse:
    """Closed shape returned by any device-code / token transport.

    The shape is intentionally narrow: status, parsed body, and a
    boolean indicating whether the body is a Microsoft identity
    platform "error" body. The transport layer is responsible for
    deciding what counts as an error; this dataclass just carries the
    outcome.

    The transport MUST NOT include an ``access_token`` or
    ``refresh_token`` value in the parsed body when the request
    failed. The live executor inspects ``body`` only for classification
    purposes and never echoes the value back.
    """

    status: int
    body: Mapping[str, Any] = field(default_factory=dict)
    is_error: bool = False

    def oauth_error_code(self) -> Optional[str]:
        """Return the OAuth ``error`` field value when present."""
        if not self.is_error:
            return None
        value = self.body.get("error")
        return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# Transport protocols
# ---------------------------------------------------------------------------


# A device-code request returns the user_code, verification_uri, and
# the device_code used for polling. The transport is the only thing
# that knows the actual host.
DeviceCodeRequestTransport = Callable[[Mapping[str, str]], TokenTransportResponse]
DeviceCodePollTransport = Callable[[Mapping[str, str]], TokenTransportResponse]
GraphMeTransport = Callable[[str, str], TokenTransportResponse]


class DeviceCodeTransport(Protocol):
    """Abstract device-code endpoint transport used by Scenario auth.

    Implementations expose only the device-code request and device-code grant
    poll operations. It intentionally has no client-credentials operation.
    """

    def request_device_code(self, form: Mapping[str, str]) -> TokenTransportResponse: ...

    def poll_token(self, form: Mapping[str, str]) -> TokenTransportResponse: ...


# These are the complete production endpoint allowlist.  The identity
# endpoints are derived only from a validated tenant object ID; Graph /me is
# fixed.  No caller can supply a URL, method, or arbitrary request body.
MICROSOFT_LOGIN_HOST = "login.microsoftonline.com"
GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"
GRAPH_USERS_URL = "https://graph.microsoft.com/v1.0/users"
GRAPH_GROUPS_URL = "https://graph.microsoft.com/v1.0/groups"


def _open_without_redirects(request, timeout_seconds: float):
    """Open one fixed request without allowing urllib redirect handling."""
    from urllib.request import HTTPRedirectHandler, build_opener

    class NoRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, request, file_pointer, code, message, headers, new_url):
            return None

    return build_opener(NoRedirectHandler()).open(request, timeout=timeout_seconds)


def _validate_tenant_id(tenant_id: str) -> str:
    """Return a canonical tenant object ID or fail before opening a socket."""
    if not isinstance(tenant_id, str):
        raise ValueError("tenant_id must be a tenant object ID string")
    try:
        return str(uuid.UUID(tenant_id))
    except (AttributeError, ValueError) as error:
        raise ValueError("tenant_id must be a valid tenant object ID") from error


@dataclass(frozen=True)
class MicrosoftDeviceCodeHttpsTransport:
    """Minimal fixed-endpoint HTTPS transport for the device-code flow.

    This transport exposes only the three requests required by
    ``SCN-AUTH-001``: device-code POST, token POST, and Graph ``GET /me``.
    It deliberately has no generic URL/method/body execution API.
    """

    tenant_id: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _validate_tenant_id(self.tenant_id))
        if float(self.timeout_seconds) <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def device_code_endpoint(self) -> str:
        return "https://{0}/{1}/oauth2/v2.0/devicecode".format(
            MICROSOFT_LOGIN_HOST, self.tenant_id
        )

    @property
    def token_endpoint(self) -> str:
        return "https://{0}/{1}/oauth2/v2.0/token".format(
            MICROSOFT_LOGIN_HOST, self.tenant_id
        )

    @property
    def allowed_endpoints(self) -> Tuple[str, str, str]:
        """Return the original device-code and ``/me`` endpoint contract.

        Collection reads use the separate fixed-operation methods below;
        they are intentionally not exposed through this legacy auth tuple.
        """
        return (self.device_code_endpoint, self.token_endpoint, GRAPH_ME_URL)

    def request_device_code(self, form: Mapping[str, str]) -> TokenTransportResponse:
        """POST the fixed device-code endpoint with its fixed form shape."""
        return self._post_form(
            self.device_code_endpoint, form, required_keys=("client_id", "scope")
        )

    def poll_token(self, form: Mapping[str, str]) -> TokenTransportResponse:
        """POST the fixed token endpoint with the device-code grant only."""
        return self._post_form(
            self.token_endpoint,
            form,
            required_keys=("client_id", "grant_type", "device_code"),
        )

    def get_me(self, access_token: str, url: str) -> TokenTransportResponse:
        """GET the sole permitted Graph endpoint; reject every URL variant."""
        if url != GRAPH_ME_URL:
            raise ValueError("Graph endpoint is not allowlisted")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("access token must be a non-empty string")
        from urllib.error import HTTPError, URLError
        from urllib.request import Request

        request = Request(
            GRAPH_ME_URL,
            headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
            method="GET",
        )
        try:
            with _open_without_redirects(request, float(self.timeout_seconds)) as response:
                return _response_from_http(response.getcode(), response.read())
        except HTTPError as error:
            return _response_from_http(error.code, error.read())
        except (URLError, OSError) as error:
            raise OSError("Graph /me HTTPS request failed") from error

    def get_users(self, access_token: str) -> TokenTransportResponse:
        """GET the fixed ``/users`` endpoint; no URL or method is caller-controlled."""
        return self._get_graph_collection(GRAPH_USERS_URL, access_token)

    def get_groups(self, access_token: str) -> TokenTransportResponse:
        """GET the fixed ``/groups`` endpoint; no URL or method is caller-controlled."""
        return self._get_graph_collection(GRAPH_GROUPS_URL, access_token)

    def _get_graph_collection(self, endpoint: str, access_token: str) -> TokenTransportResponse:
        if endpoint not in (GRAPH_USERS_URL, GRAPH_GROUPS_URL):
            raise ValueError("Graph collection endpoint is not allowlisted")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("access token must be a non-empty string")
        from urllib.error import HTTPError, URLError
        from urllib.request import Request

        request = Request(
            endpoint,
            headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
            method="GET",
        )
        try:
            with _open_without_redirects(request, float(self.timeout_seconds)) as response:
                return _response_from_http(response.getcode(), response.read())
        except HTTPError as error:
            return _response_from_http(error.code, error.read())
        except (URLError, OSError) as error:
            raise OSError("Graph collection HTTPS request failed") from error

    def _post_form(
        self,
        endpoint: str,
        form: Mapping[str, str],
        *,
        required_keys: Tuple[str, ...],
    ) -> TokenTransportResponse:
        if endpoint not in self.allowed_endpoints[:2]:
            raise ValueError("identity endpoint is not allowlisted")
        if set(form) != set(required_keys):
            raise ValueError("OAuth form has an unsupported shape")
        if any(not isinstance(form[key], str) or not form[key] for key in required_keys):
            raise ValueError("OAuth form values must be non-empty strings")
        from urllib.error import HTTPError, URLError
        from urllib.request import Request

        request = Request(
            endpoint,
            data=encode_form_body(form),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            method="POST",
        )
        try:
            with _open_without_redirects(request, float(self.timeout_seconds)) as response:
                return _response_from_http(response.getcode(), response.read())
        except HTTPError as error:
            return _response_from_http(error.code, error.read())
        except (URLError, OSError) as error:
            raise OSError("Microsoft identity HTTPS request failed") from error


def _response_from_http(status: int, raw_body: bytes) -> TokenTransportResponse:
    """Parse a JSON object without exposing raw response text in errors."""
    if 300 <= int(status) < 400:
        return TokenTransportResponse(status=int(status), body={}, is_error=True)
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    return TokenTransportResponse(status=int(status), body=body, is_error=int(status) >= 400)


# ---------------------------------------------------------------------------
# Fake device-code transport
# ---------------------------------------------------------------------------


@dataclass
class FakeDeviceCodeTransport:
    """Programmable, deterministic fake for the device-code flow.

    The fake is the only object a test injects to drive the
    :class:`DeviceCodeFlow`. The fake:

    * records every call (``request_calls``, ``poll_calls``),
    * returns a configurable response for the next ``request`` call,
    * returns a configurable sequence of responses for ``poll`` calls.

    Use :meth:`queue_poll_response` to script a multi-step poll: the
    first call returns ``authorization_pending`` and the second returns
    the access token. Use :meth:`queue_request_error` to script an
    upstream HTTP error.

    The fake never opens a socket. It is safe for offline tests.
    """

    # Configurable response for the initial device-code POST.
    request_response: TokenTransportResponse = field(
        default_factory=lambda: TokenTransportResponse(
            status=200,
            body={
                "device_code": "fake-device-code",
                "user_code": "FAKE-USER-CODE",
                "verification_uri": "https://microsoft.com/devicelogin",
                "expires_in": 900,
                "interval": 5,
                "message": "To sign in, use a web browser to open the page "
                "https://microsoft.com/devicelogin and enter the code "
                "FAKE-USER-CODE to authenticate.",
            },
            is_error=False,
        )
    )

    # Sequence of poll responses. If the queue is empty the fake
    # returns the value of ``poll_response`` (a single value).
    poll_response: TokenTransportResponse = field(
        default_factory=lambda: TokenTransportResponse(
            status=200,
            body={
                "access_token": "fake-access-token-DO-NOT-LEAK",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "User.Read",
            },
            is_error=False,
        )
    )

    # Optional scripted sequence of poll responses (consumed FIFO).
    _poll_queue: List[TokenTransportResponse] = field(default_factory=list)

    # Recorded calls.
    request_calls: List[Mapping[str, Any]] = field(default_factory=list)
    poll_calls: List[Mapping[str, Any]] = field(default_factory=list)

    # Scripted failure flags.
    request_error: Optional[Exception] = None
    poll_error: Optional[Exception] = None

    # ---- configuration helpers ---------------------------------------

    def queue_poll_response(self, response: TokenTransportResponse) -> None:
        """Append a poll response to the scripted sequence."""
        self._poll_queue.append(response)

    def queue_request_error(self, error: Exception) -> None:
        """Force the next request call to raise ``error``."""
        self.request_error = error

    def queue_poll_error(self, error: Exception) -> None:
        """Force the next poll call to raise ``error``."""
        self.poll_error = error

    def reset(self) -> None:
        """Drop recorded calls and scripted responses (preserves
        configuration)."""
        self.request_calls.clear()
        self.poll_calls.clear()
        self._poll_queue.clear()
        self.request_error = None
        self.poll_error = None

    # ---- transport callables -----------------------------------------

    def request(self, form: Mapping[str, str]) -> TokenTransportResponse:
        """Pretend to POST the device-code request to Entra."""
        self.request_calls.append(dict(form))
        if self.request_error is not None:
            error = self.request_error
            self.request_error = None
            raise error
        return self.request_response

    def request_device_code(self, form: Mapping[str, str]) -> TokenTransportResponse:
        """Implement the production DeviceCodeTransport request surface."""
        return self.request(form)

    def poll(self, form: Mapping[str, str]) -> TokenTransportResponse:
        """Pretend to POST the token poll request to Entra."""
        self.poll_calls.append(dict(form))
        if self.poll_error is not None:
            error = self.poll_error
            self.poll_error = None
            raise error
        if self._poll_queue:
            return self._poll_queue.pop(0)
        return self.poll_response

    def poll_token(self, form: Mapping[str, str]) -> TokenTransportResponse:
        """Implement the production DeviceCodeTransport polling surface."""
        return self.poll(form)


# ---------------------------------------------------------------------------
# Fake Graph /me transport
# ---------------------------------------------------------------------------


@dataclass
class FakeGraphTransport:
    """Programmable, deterministic fake for ``GET /me`` validation.

    The fake is the only object a test injects to drive the
    :class:`GraphMeValidator`. The fake records every call and returns
    a configurable object-id, UPN, and display name. The fake can be
    configured to return an HTTP error or to raise a network error.
    """

    # Configurable success body.
    me_object_id: str = "00000000-0000-0000-0000-000000000001"
    me_user_principal_name: str = "fake-user@example.test"
    me_display_name: str = "Fake Test User"

    # Optional scripted error.
    me_error: Optional[TokenTransportResponse] = field(default=None, repr=False)
    me_exception: Optional[Exception] = field(default=None, repr=False)

    # Recorded calls: list of (token, url) pairs (token is redacted in repr).
    me_calls: List[Tuple[str, str]] = field(default_factory=list, repr=False)

    def request(self, token: str, url: str) -> TokenTransportResponse:
        """Pretend to GET ``url`` with ``token`` as the bearer."""
        self.me_calls.append((token, url))
        if self.me_exception is not None:
            error = self.me_exception
            self.me_exception = None
            raise error
        if self.me_error is not None:
            return self.me_error
        body = {
            "id": self.me_object_id,
            "userPrincipalName": self.me_user_principal_name,
            "displayName": self.me_display_name,
        }
        return TokenTransportResponse(status=200, body=body, is_error=False)

    def reset(self) -> None:
        """Drop recorded calls (preserves configuration)."""
        self.me_calls.clear()


# ---------------------------------------------------------------------------
# Helper: form-encoded body emitter (used by real transports)
# ---------------------------------------------------------------------------


def encode_form_body(form: Mapping[str, str]) -> bytes:
    """Encode a form mapping as ``application/x-www-form-urlencoded``.

    This helper is a thin wrapper around ``urllib.parse.urlencode``
    that returns bytes. It is the body the real transport would send.
    Tests use it to assert the outgoing form content.
    """
    from urllib.parse import urlencode

    return urlencode(dict(form)).encode("ascii")


def safe_body_dumps(body: Mapping[str, Any]) -> str:
    """Serialize a parsed body to JSON without echoing credentials.

    The helper exists so future structured-log calls can capture the
    shape of a token-endpoint response without leaking the
    ``access_token`` field. It is a defence-in-depth measure: callers
    must still avoid including the body in evidence.
    """
    scrubbed: Dict[str, Any] = {}
    for key, value in body.items():
        if key in ("access_token", "refresh_token", "id_token"):
            scrubbed[key] = "<redacted>"
        else:
            scrubbed[key] = value
    return json.dumps(scrubbed, sort_keys=True)


__all__ = [
    "DeviceCodePollTransport",
    "DeviceCodeRequestTransport",
    "FakeDeviceCodeTransport",
    "FakeGraphTransport",
    "GraphMeTransport",
    "GRAPH_GROUPS_URL",
    "GRAPH_ME_URL",
    "GRAPH_USERS_URL",
    "MICROSOFT_LOGIN_HOST",
    "MicrosoftDeviceCodeHttpsTransport",
    "TokenTransportResponse",
    "encode_form_body",
    "safe_body_dumps",
]
