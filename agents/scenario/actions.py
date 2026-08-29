"""Controlled action vocabulary for the Scenario Agent.

Every action the framework can plan is enumerated in
:data:`SUPPORTED_ACTION_TYPES`. Anything else is rejected at the safety
gate; an untrusted caller cannot introduce a new action type, an
arbitrary Graph URL, an arbitrary HTTP method, or a raw body
passthrough.

This module contains NO Microsoft Graph transport import and NO
network code. Action types are pure identifiers with declared
delegated permissions and a small list of allowed safe parameters.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# Closed action vocabulary
# ---------------------------------------------------------------------------

ACTION_SEND_MAIL = "SEND_MAIL"
ACTION_CREATE_CALENDAR_EVENT = "CREATE_CALENDAR_EVENT"
ACTION_UPDATE_CALENDAR_EVENT = "UPDATE_CALENDAR_EVENT"
ACTION_DELETE_CALENDAR_EVENT = "DELETE_CALENDAR_EVENT"
ACTION_CREATE_FILE = "CREATE_FILE"
ACTION_UPDATE_FILE = "UPDATE_FILE"
ACTION_DELETE_FILE = "DELETE_FILE"
ACTION_CREATE_TEAMS_MESSAGE = "CREATE_TEAMS_MESSAGE"
ACTION_CREATE_GROUP_CONTENT = "CREATE_GROUP_CONTENT"
ACTION_NOOP_VALIDATION = "NOOP_VALIDATION"
ACTION_INTERACTIVE_SIGNIN = "INTERACTIVE_SIGNIN"

SUPPORTED_ACTION_TYPES: Tuple[str, ...] = (
    ACTION_SEND_MAIL,
    ACTION_CREATE_CALENDAR_EVENT,
    ACTION_UPDATE_CALENDAR_EVENT,
    ACTION_DELETE_CALENDAR_EVENT,
    ACTION_CREATE_FILE,
    ACTION_UPDATE_FILE,
    ACTION_DELETE_FILE,
    ACTION_CREATE_TEAMS_MESSAGE,
    ACTION_CREATE_GROUP_CONTENT,
    ACTION_NOOP_VALIDATION,
    ACTION_INTERACTIVE_SIGNIN,
)


# ---------------------------------------------------------------------------
# Action parameter schema
# ---------------------------------------------------------------------------


_ACTION_PARAMETER_KEYS: Dict[str, Tuple[str, ...]] = {
    ACTION_SEND_MAIL: (
        "subject",
        "body_preview",
        "to_recipients_count",
    ),
    ACTION_CREATE_CALENDAR_EVENT: (
        "subject",
        "duration_minutes",
        "attendees_count",
    ),
    ACTION_UPDATE_CALENDAR_EVENT: (
        "subject",
        "duration_minutes",
        "attendees_count",
    ),
    ACTION_DELETE_CALENDAR_EVENT: (
        "subject",
    ),
    ACTION_CREATE_FILE: (
        "drive_kind",
        "file_name_prefix",
        "content_size_bytes",
    ),
    ACTION_UPDATE_FILE: (
        "drive_kind",
        "file_name_prefix",
        "new_content_size_bytes",
    ),
    ACTION_DELETE_FILE: (
        "drive_kind",
        "file_name_prefix",
    ),
    ACTION_CREATE_TEAMS_MESSAGE: (
        "team_kind",
        "channel_kind",
        "body_preview",
    ),
    ACTION_CREATE_GROUP_CONTENT: (
        "group_kind",
        "post_subject",
        "body_preview",
    ),
    ACTION_NOOP_VALIDATION: (),
    ACTION_INTERACTIVE_SIGNIN: (),
}


_ACTION_PERMISSIONS: Dict[str, Tuple[str, ...]] = {
    ACTION_SEND_MAIL: ("Mail.Send",),
    ACTION_CREATE_CALENDAR_EVENT: ("Calendars.ReadWrite",),
    ACTION_UPDATE_CALENDAR_EVENT: ("Calendars.ReadWrite",),
    ACTION_DELETE_CALENDAR_EVENT: ("Calendars.ReadWrite",),
    ACTION_CREATE_FILE: ("Files.ReadWrite",),
    ACTION_UPDATE_FILE: ("Files.ReadWrite",),
    ACTION_DELETE_FILE: ("Files.ReadWrite",),
    ACTION_CREATE_TEAMS_MESSAGE: ("ChannelMessage.Send",),
    ACTION_CREATE_GROUP_CONTENT: ("Group.ReadWrite.All",),
    ACTION_NOOP_VALIDATION: (),
    ACTION_INTERACTIVE_SIGNIN: ("User.Read",),
}


_ACTION_DESCRIPTIONS: Dict[str, str] = {
    ACTION_SEND_MAIL: "Send a controlled test email from the actor.",
    ACTION_CREATE_CALENDAR_EVENT: "Create a controlled calendar event for the actor.",
    ACTION_UPDATE_CALENDAR_EVENT: "Update a controlled calendar event previously created by the framework.",
    ACTION_DELETE_CALENDAR_EVENT: "Delete a controlled calendar event previously created by the framework.",
    ACTION_CREATE_FILE: "Create a controlled test file in a known drive.",
    ACTION_UPDATE_FILE: "Update a controlled test file with new content.",
    ACTION_DELETE_FILE: "Delete a controlled test file previously created by the framework.",
    ACTION_CREATE_TEAMS_MESSAGE: "Post a controlled test message in a Teams channel.",
    ACTION_CREATE_GROUP_CONTENT: "Create a controlled post in a test group.",
    ACTION_NOOP_VALIDATION: "Perform a validation-only step that performs no Graph action.",
    ACTION_INTERACTIVE_SIGNIN: "Operator-driven interactive sign-in observation; performs no Microsoft Graph write.",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_supported_action_type(action_type: str) -> bool:
    """Return ``True`` if ``action_type`` is in the closed vocabulary."""
    return action_type in SUPPORTED_ACTION_TYPES


def declared_permissions_for(action_type: str) -> List[str]:
    """Return the declared delegated permissions for an action type.

    Unknown action types return an empty list. The safety gate is
    responsible for rejecting unknown action types -- this helper is
    intentionally non-raising so the engine can compute a stable
    declaration.
    """
    return list(_ACTION_PERMISSIONS.get(action_type, ()))


def allowed_parameter_keys(action_type: str) -> Tuple[str, ...]:
    """Return the closed set of safe parameter keys for an action type."""
    return _ACTION_PARAMETER_KEYS.get(action_type, ())


def describe_action_type(action_type: str) -> str:
    """Return a human-readable description for a known action type."""
    return _ACTION_DESCRIPTIONS.get(action_type, "")


def sanitize_action_parameters(
    action_type: str,
    parameters: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Return a copy of ``parameters`` filtered to the allowed keys.

    The Scenario Agent never accepts arbitrary URL, ``method``, or
    ``body`` overrides from callers. Any of those keys present in the
    input are dropped silently, which is observable to callers via
    the safe parameter set on the produced step.
    """
    if not parameters:
        return {}
    allowed = set(allowed_parameter_keys(action_type))
    sanitized: Dict[str, Any] = {}
    for key, value in parameters.items():
        if key in allowed:
            sanitized[key] = value
    return sanitized


__all__ = [
    "ACTION_CREATE_CALENDAR_EVENT",
    "ACTION_CREATE_FILE",
    "ACTION_CREATE_GROUP_CONTENT",
    "ACTION_CREATE_TEAMS_MESSAGE",
    "ACTION_DELETE_CALENDAR_EVENT",
    "ACTION_DELETE_FILE",
    "ACTION_INTERACTIVE_SIGNIN",
    "ACTION_NOOP_VALIDATION",
    "ACTION_SEND_MAIL",
    "ACTION_UPDATE_CALENDAR_EVENT",
    "ACTION_UPDATE_FILE",
    "SUPPORTED_ACTION_TYPES",
    "allowed_parameter_keys",
    "declared_permissions_for",
    "describe_action_type",
    "is_supported_action_type",
    "sanitize_action_parameters",
]