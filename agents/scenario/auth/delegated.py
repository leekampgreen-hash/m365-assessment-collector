"""Canonical delegated authentication provider for Scenario execution.

The provider is the sole Scenario boundary that combines OAuth device-code
authentication with mandatory Microsoft Graph ``/me`` actor verification. It
returns safe metadata only; OAuth tokens exist only inside ``authenticate``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .contracts import (
    ScenarioActorMetadata,
    ScenarioAuthenticationContext,
    ScenarioIdentityConfig,
)
from .device_code import DeviceCodeFlow, DeviceCodePrompt
from .identity import ExpectedActor, GraphMeValidator
from .transports import DeviceCodePollTransport, DeviceCodeRequestTransport, GraphMeTransport


APPROVED_DELEGATED_SCOPES: Tuple[str, ...] = ("User.Read",)


def validate_approved_delegated_scopes(scopes: object) -> Tuple[str, ...]:
    """Fail closed unless scopes exactly match the approved delegated set."""
    if not isinstance(scopes, (tuple, list)) or tuple(scopes) != APPROVED_DELEGATED_SCOPES:
        raise ValueError("delegated scopes must be exactly ('User.Read',)")
    return APPROVED_DELEGATED_SCOPES


@dataclass(frozen=True)
class DelegatedAuthenticationResult:
    """Persistable result of delegated authentication and actor verification.

    Device-code prompt material is delivered only to the transient operator
    callbacks. It must not cross this boundary into Scenario execution.
    """

    context: ScenarioAuthenticationContext


class DelegatedScenarioAuthenticationProvider:
    """Acquire a delegated token, verify its actor, then discard the token.

    No Scenario client secret, Collector credentials, refresh token, or
    authorization header is accepted or returned by this provider.
    """

    def __init__(
        self,
        *,
        identity_config: ScenarioIdentityConfig,
        expected_actor: ExpectedActor,
        correlation_id: str,
        delegated_scopes: Tuple[str, ...] = APPROVED_DELEGATED_SCOPES,
        device_code_request_transport: DeviceCodeRequestTransport,
        device_code_poll_transport: DeviceCodePollTransport,
        graph_me_transport: GraphMeTransport,
        prompt_callback: Optional[Callable[[DeviceCodePrompt], None]] = None,
        confirmation_callback: Optional[Callable[[DeviceCodePrompt], bool]] = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        epoch_clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(identity_config, ScenarioIdentityConfig):
            raise ValueError("identity_config must be a ScenarioIdentityConfig")
        if expected_actor is None or expected_actor.is_empty():
            raise ValueError("expected_actor must declare an object ID and/or UPN")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise ValueError("correlation_id is required")
        if device_code_request_transport is None or device_code_poll_transport is None or graph_me_transport is None:
            raise ValueError("device-code and Graph /me transports are required")
        self._config = identity_config
        self._expected_actor = expected_actor
        self._correlation_id = correlation_id
        self._scopes = validate_approved_delegated_scopes(delegated_scopes)
        self._request_transport = device_code_request_transport
        self._poll_transport = device_code_poll_transport
        self._graph_me_transport = graph_me_transport
        self._prompt_callback = prompt_callback
        self._confirmation_callback = confirmation_callback
        self._sleep = sleep
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._epoch_clock = epoch_clock

    def authenticate(self) -> DelegatedAuthenticationResult:
        """Perform device code and mandatory ``/me`` validation fail closed."""
        flow = DeviceCodeFlow(
            client_id=self._config.client_id,
            tenant_id=self._config.tenant_id,
            scopes=self._scopes,
            request_transport=self._request_transport,
            poll_transport=self._poll_transport,
            prompt_callback=self._prompt_callback,
            confirmation_callback=self._confirmation_callback,
            sleep=self._sleep,
            timeout_seconds=self._timeout_seconds,
            clock=self._clock,
        )
        token = flow.run()
        try:
            identity = GraphMeValidator(
                transport=self._graph_me_transport,
                expected=self._expected_actor,
            ).validate(token.access_token)
            context = ScenarioAuthenticationContext(
                authenticated=True,
                tenant_id=self._config.tenant_id,
                client_id=self._config.client_id,
                correlation_id=self._correlation_id,
                actor=ScenarioActorMetadata(
                    object_id=identity.object_id,
                    user_principal_name=identity.user_principal_name,
                    display_name=identity.display_name,
                ),
                expires_at_epoch=int(self._epoch_clock() + token.expires_in_seconds),
            )
            return DelegatedAuthenticationResult(context=context)
        finally:
            # The provider must not retain the only OAuth bearer token it sees.
            token.access_token = ""


__all__ = [
    "APPROVED_DELEGATED_SCOPES",
    "DelegatedAuthenticationResult",
    "DelegatedScenarioAuthenticationProvider",
    "validate_approved_delegated_scopes",
]
