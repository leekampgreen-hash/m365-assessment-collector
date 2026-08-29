"""Offline tests for the Graph ``/me`` identity validator."""
from __future__ import annotations

import unittest

from agents.scenario.auth import (
    ExpectedActor,
    GraphMeError,
    GraphMeValidator,
    TokenTransportResponse,
)
from agents.scenario.auth.transports import FakeGraphTransport


def _validator(expected, transport=None):
    transport = transport or FakeGraphTransport().request
    return GraphMeValidator(transport=transport, expected=expected)


class IdentityMatchTests(unittest.TestCase):
    def test_match_on_object_id(self):
        expected = ExpectedActor(object_id="abc-123")
        transport = FakeGraphTransport(me_object_id="abc-123", me_user_principal_name="u@e.test")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        identity = v.validate("TOKEN")
        self.assertEqual(identity.object_id, "abc-123")
        self.assertEqual(identity.user_principal_name, "u@e.test")

    def test_match_on_upn(self):
        expected = ExpectedActor(user_principal_name="u@e.test")
        transport = FakeGraphTransport(me_object_id="abc", me_user_principal_name="u@e.test")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        identity = v.validate("TOKEN")
        self.assertEqual(identity.user_principal_name, "u@e.test")

    def test_match_on_both(self):
        expected = ExpectedActor(object_id="abc", user_principal_name="u@e.test")
        transport = FakeGraphTransport(me_object_id="abc", me_user_principal_name="u@e.test")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        v.validate("TOKEN")

    def test_mismatch_on_object_id(self):
        expected = ExpectedActor(object_id="abc", user_principal_name="u@e.test")
        transport = FakeGraphTransport(me_object_id="xxx", me_user_principal_name="u@e.test")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        with self.assertRaises(GraphMeError) as ctx:
            v.validate("TOKEN")
        self.assertEqual(ctx.exception.classification, "ACTOR_IDENTITY_MISMATCH")

    def test_mismatch_on_upn(self):
        expected = ExpectedActor(object_id="abc", user_principal_name="u@e.test")
        transport = FakeGraphTransport(me_object_id="abc", me_user_principal_name="other@e.test")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        with self.assertRaises(GraphMeError) as ctx:
            v.validate("TOKEN")
        self.assertEqual(ctx.exception.classification, "ACTOR_IDENTITY_MISMATCH")


class IdentityFailureTests(unittest.TestCase):
    def test_http_error(self):
        expected = ExpectedActor(object_id="abc")
        transport = FakeGraphTransport()
        transport.me_error = TokenTransportResponse(
            status=401,
            body={"error": "invalid_token"},
            is_error=True,
        )
        v = GraphMeValidator(transport=transport.request, expected=expected)
        with self.assertRaises(GraphMeError) as ctx:
            v.validate("TOKEN")
        self.assertEqual(ctx.exception.classification, "GRAPH_ME_VALIDATION_FAILED")

    def test_transport_exception(self):
        expected = ExpectedActor(object_id="abc")
        transport = FakeGraphTransport()
        transport.me_exception = OSError("boom")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        with self.assertRaises(GraphMeError) as ctx:
            v.validate("TOKEN")
        self.assertEqual(ctx.exception.classification, "GRAPH_ME_VALIDATION_FAILED")

    def test_missing_id(self):
        expected = ExpectedActor(object_id="abc")
        transport = FakeGraphTransport()
        transport.me_error = TokenTransportResponse(
            status=200, body={"userPrincipalName": "u@e.test"}, is_error=False
        )
        # The fake's body is ignored when me_error is set, so unset it.
        transport.me_error = None

        class NoIdTransport:
            def __init__(self, inner):
                self._inner = inner

            def __call__(self, token, url):
                # Return a body that lacks an id field.
                return TokenTransportResponse(
                    status=200,
                    body={"userPrincipalName": "u@e.test", "displayName": "X"},
                    is_error=False,
                )

        v = GraphMeValidator(transport=NoIdTransport(None), expected=expected)
        with self.assertRaises(GraphMeError) as ctx:
            v.validate("TOKEN")
        self.assertEqual(ctx.exception.classification, "GRAPH_ME_VALIDATION_FAILED")

    def test_empty_token(self):
        expected = ExpectedActor(object_id="abc")
        v = _validator(expected)
        with self.assertRaises(GraphMeError):
            v.validate("")

    def test_non_string_token(self):
        expected = ExpectedActor(object_id="abc")
        v = _validator(expected)
        with self.assertRaises(GraphMeError):
            v.validate(None)  # type: ignore[arg-type]

    def test_validator_rejects_empty_expected(self):
        with self.assertRaises(ValueError):
            GraphMeValidator(transport=FakeGraphTransport().request, expected=ExpectedActor())


class IdentitySafetyTests(unittest.TestCase):
    def test_token_not_in_exception_message(self):
        expected = ExpectedActor(object_id="abc")
        transport = FakeGraphTransport()
        transport.me_exception = OSError("boom")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        try:
            v.validate("SUPER-SECRET-TOKEN-VALUE")
        except GraphMeError as e:
            self.assertNotIn("SUPER-SECRET-TOKEN-VALUE", e.message)
            self.assertNotIn("SUPER-SECRET-TOKEN-VALUE", str(e))
        else:
            self.fail("expected GraphMeError")

    def test_token_not_in_identity(self):
        expected = ExpectedActor(object_id="abc")
        transport = FakeGraphTransport(me_object_id="abc")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        identity = v.validate("SUPER-SECRET-TOKEN-VALUE")
        # identity never echoes the access token.
        for field in ("object_id", "user_principal_name", "display_name"):
            self.assertNotIn("SUPER-SECRET-TOKEN-VALUE", getattr(identity, field))
        self.assertNotIn("SUPER-SECRET-TOKEN-VALUE", repr(identity))
        self.assertNotIn("SUPER-SECRET-TOKEN-VALUE", repr(identity.to_dict()))

    def test_me_call_records_token_but_repr_redacts(self):
        # The transport call records the token; tests that depend on
        # the recording must redact manually. This test exists to
        # document the seam.
        expected = ExpectedActor(object_id="abc")
        transport = FakeGraphTransport(me_object_id="abc")
        v = GraphMeValidator(transport=transport.request, expected=expected)
        v.validate("AAA")
        self.assertEqual(len(transport.me_calls), 1)
        token_arg, url_arg = transport.me_calls[0]
        self.assertEqual(token_arg, "AAA")
        self.assertIn("graph.microsoft.com", url_arg)

    def test_fake_graph_transport_repr_redacts_all_token_bearing_fields(self):
        error_token = "ERROR-BODY-ACCESS-TOKEN"
        exception_token = "EXCEPTION-TEXT-ACCESS-TOKEN"
        call_token = "RECORDED-CALL-ACCESS-TOKEN"
        transport = FakeGraphTransport(
            me_error=TokenTransportResponse(
                status=401,
                body={"access_token": error_token},
                is_error=True,
            ),
            me_exception=OSError("request failed: {0}".format(exception_token)),
        )
        transport.me_calls.append((call_token, "https://graph.microsoft.com/v1.0/me"))

        representation = repr(transport)

        self.assertNotIn(error_token, representation)
        self.assertNotIn(exception_token, representation)
        self.assertNotIn(call_token, representation)


if __name__ == "__main__":
    unittest.main()
