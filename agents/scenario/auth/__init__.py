"""Authentication abstractions for the live Scenario Agent executor.

This sub-package is the **only** place inside ``agents.scenario`` that
performs delegated OAuth 2.0 device-code flow and Graph ``/me``
identity verification. It is intentionally small and stdlib-only.

The boundaries enforced here are:

* The :class:`DeviceCodeFlow` only ever calls an injected transport
  (``device_code_transport`` and ``token_transport`` callables). The
  module never imports ``urllib`` at module load and never opens a
  socket on its own. Test code substitutes a fake transport.
* No token, refresh token, ``Authorization`` header, or client secret
  is ever returned to a caller. The token itself is held in an
  attribute on the dataclass and is the private property of a single
  execution; it must not be propagated into evidence.
* The :class:`GraphMeValidator` only ever calls an injected
  ``graph_transport`` callable. It raises structured
  :class:`LiveAuthError` subclasses when the response is malformed or
  when the identity does not match the expected actor.
* All exceptions are classified using the closed failure-model
  vocabulary declared in :mod:`agents.scenario.live_executor`.

This sub-package **does not** import anything from ``collectors`` or
``database``. It is safe to import from offline test code.
"""
from __future__ import annotations

from .device_code import (
    DeviceCodeError,
    DeviceCodeFlow,
    DeviceCodePrompt,
    DeviceCodeToken,
    _http_post_form,  # re-exported for test override
)
from .identity import (
    ExpectedActor,
    GraphMeError,
    GraphMeValidator,
    MeIdentity,
)
from .contracts import (
    IdentityType,
    ScenarioActorMetadata,
    ScenarioAuthenticationContext,
    ScenarioIdentityConfig,
)
from .delegated import (
    APPROVED_DELEGATED_SCOPES,
    DelegatedAuthenticationResult,
    DelegatedScenarioAuthenticationProvider,
    validate_approved_delegated_scopes,
)
from .transports import (
    DeviceCodeTransport,
    FakeDeviceCodeTransport,
    FakeGraphTransport,
    GRAPH_ME_URL,
    MicrosoftDeviceCodeHttpsTransport,
    TokenTransportResponse,
)

__all__ = [
    "DeviceCodeError",
    "DeviceCodeFlow",
    "DeviceCodePrompt",
    "DeviceCodeToken",
    "DeviceCodeTransport",
    "DelegatedAuthenticationResult",
    "DelegatedScenarioAuthenticationProvider",
    "ExpectedActor",
    "FakeDeviceCodeTransport",
    "FakeGraphTransport",
    "GRAPH_ME_URL",
    "GraphMeError",
    "GraphMeValidator",
    "IdentityType",
    "MeIdentity",
    "MicrosoftDeviceCodeHttpsTransport",
    "ScenarioAuthenticationContext",
    "ScenarioActorMetadata",
    "ScenarioIdentityConfig",
    "TokenTransportResponse",
    "APPROVED_DELEGATED_SCOPES",
    "_http_post_form",
    "validate_approved_delegated_scopes",
]
