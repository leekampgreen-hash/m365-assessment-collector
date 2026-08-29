"""Offline tests for the controlled action vocabulary."""
from __future__ import annotations

import unittest

from agents.scenario.actions import (
    ACTION_CREATE_CALENDAR_EVENT,
    ACTION_CREATE_FILE,
    ACTION_CREATE_GROUP_CONTENT,
    ACTION_CREATE_TEAMS_MESSAGE,
    ACTION_DELETE_CALENDAR_EVENT,
    ACTION_DELETE_FILE,
    ACTION_INTERACTIVE_SIGNIN,
    ACTION_NOOP_VALIDATION,
    ACTION_SEND_MAIL,
    ACTION_UPDATE_CALENDAR_EVENT,
    ACTION_UPDATE_FILE,
    SUPPORTED_ACTION_TYPES,
    allowed_parameter_keys,
    declared_permissions_for,
    describe_action_type,
    is_supported_action_type,
    sanitize_action_parameters,
)


class ActionVocabularyTests(unittest.TestCase):
    def test_supported_action_types_are_documented(self):
        expected = {
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
        }
        self.assertEqual(set(SUPPORTED_ACTION_TYPES), expected)

    def test_is_supported_action_type_accepts_known(self):
        for action in SUPPORTED_ACTION_TYPES:
            self.assertTrue(is_supported_action_type(action))

    def test_is_supported_action_type_rejects_unknown(self):
        self.assertFalse(is_supported_action_type("DELETE_EVERYTHING"))
        self.assertFalse(is_supported_action_type(""))
        self.assertFalse(is_supported_action_type("send_mail"))  # case-sensitive

    def test_no_arbitrary_graph_url_action(self):
        # No action type allows raw URL execution.
        for action in SUPPORTED_ACTION_TYPES:
            keys = allowed_parameter_keys(action)
            self.assertNotIn("url", keys)
            self.assertNotIn("endpoint", keys)
            self.assertNotIn("method", keys)
            self.assertNotIn("body", keys)

    def test_describe_action_type_returns_string(self):
        for action in SUPPORTED_ACTION_TYPES:
            description = describe_action_type(action)
            self.assertIsInstance(description, str)
            self.assertNotEqual(description, "")


class PermissionsForActionTests(unittest.TestCase):
    def test_send_mail_declares_mail_send(self):
        self.assertIn("Mail.Send", declared_permissions_for(ACTION_SEND_MAIL))

    def test_create_calendar_event_declares_calendar_readwrite(self):
        self.assertIn(
            "Calendars.ReadWrite",
            declared_permissions_for(ACTION_CREATE_CALENDAR_EVENT),
        )

    def test_create_file_declares_files_readwrite(self):
        self.assertIn(
            "Files.ReadWrite",
            declared_permissions_for(ACTION_CREATE_FILE),
        )

    def test_update_file_declares_files_readwrite(self):
        self.assertIn(
            "Files.ReadWrite",
            declared_permissions_for(ACTION_UPDATE_FILE),
        )

    def test_create_teams_message_declares_channel_message_send(self):
        self.assertIn(
            "ChannelMessage.Send",
            declared_permissions_for(ACTION_CREATE_TEAMS_MESSAGE),
        )

    def test_create_group_content_declares_group_readwrite(self):
        self.assertIn(
            "Group.ReadWrite.All",
            declared_permissions_for(ACTION_CREATE_GROUP_CONTENT),
        )

    def test_unknown_action_returns_empty_permissions(self):
        self.assertEqual(declared_permissions_for("UNKNOWN_ACTION"), [])


class SanitizeParametersTests(unittest.TestCase):
    def test_allowed_keys_kept(self):
        sanitized = sanitize_action_parameters(
            ACTION_SEND_MAIL,
            {"subject": "hi", "body_preview": "preview"},
        )
        self.assertEqual(
            sanitized,
            {"subject": "hi", "body_preview": "preview"},
        )

    def test_arbitrary_url_key_dropped(self):
        sanitized = sanitize_action_parameters(
            ACTION_SEND_MAIL,
            {"subject": "hi", "url": "https://graph.microsoft.com/v1.0/me/sendMail"},
        )
        self.assertNotIn("url", sanitized)
        self.assertEqual(sanitized, {"subject": "hi"})

    def test_method_key_dropped(self):
        sanitized = sanitize_action_parameters(
            ACTION_SEND_MAIL,
            {"subject": "hi", "method": "POST"},
        )
        self.assertNotIn("method", sanitized)

    def test_body_key_dropped(self):
        sanitized = sanitize_action_parameters(
            ACTION_SEND_MAIL,
            {"subject": "hi", "body": "<raw body passthrough>"},
        )
        self.assertNotIn("body", sanitized)

    def test_empty_parameters_yield_empty_dict(self):
        self.assertEqual(sanitize_action_parameters(ACTION_SEND_MAIL, {}), {})
        self.assertEqual(sanitize_action_parameters(ACTION_SEND_MAIL, None), {})

    def test_token_like_key_dropped(self):
        # The sanitize function drops only the *forbidden transport*
        # keys; credential-shaped values are caught by the safety
        # gate, not here. ``token`` is not an allowed key, so it must
        # not appear in the sanitized result.
        sanitized = sanitize_action_parameters(
            ACTION_SEND_MAIL,
            {"subject": "hi", "token": "bearer abc"},
        )
        self.assertNotIn("token", sanitized)


if __name__ == "__main__":
    unittest.main()