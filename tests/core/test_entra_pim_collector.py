"""Unit tests for the entra_pim collector.

All tests are offline -- no live Graph traffic, no real database.
"""
import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock
from urllib.error import HTTPError

from collectors.core.transport import GraphHttpError, GraphTransport
from collectors.entra_pim import (
    REQUIRED_PERMISSION,
    _resolve_principal_names,
    collect_and_persist_entra_pim,
)


TENANT_ID = 42


def _make_url_open(responses):
    """Return a url_open callable backed by a sequence of payloads / HTTPErrors."""
    calls = iter(responses)

    def _url_open(request, timeout=30):
        item = next(calls)
        if isinstance(item, Exception):
            raise item

        class _Resp:
            status = 200
            headers = {}

            def read(self_):
                return json.dumps(item).encode()

            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

        return _Resp()

    return _url_open


def _make_transport(responses):
    return GraphTransport(lambda: "fake-token", url_open=_make_url_open(responses))


def _http_error(status, code="Forbidden", message="Access denied"):
    payload = json.dumps({"error": {"code": code, "message": message}}).encode()
    return HTTPError(
        url="https://graph.microsoft.com/test",
        code=status,
        msg="error",
        hdrs={},
        fp=BytesIO(payload),
    )


def _fake_connection():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cur


class RequiredPermissionTests(unittest.TestCase):
    def test_required_permission_constant(self):
        self.assertEqual(REQUIRED_PERMISSION, "RoleManagement.Read.Directory")


class ResolvePrincipalNamesTests(unittest.TestCase):
    def test_resolves_display_name(self):
        responses = [{"displayName": "Alice", "@odata.type": "#microsoft.graph.user"}]
        transport = _make_transport(responses)
        result = _resolve_principal_names(["pid-1"], transport)
        self.assertEqual(result, {"pid-1": "Alice"})

    def test_skips_on_403(self):
        transport = _make_transport([_http_error(403)])
        result = _resolve_principal_names(["pid-x"], transport)
        self.assertEqual(result, {})

    def test_skips_on_404(self):
        transport = _make_transport([_http_error(404, code="ResourceNotFound")])
        result = _resolve_principal_names(["pid-y"], transport)
        self.assertEqual(result, {})

    def test_skips_missing_display_name(self):
        transport = _make_transport([{"@odata.type": "#microsoft.graph.servicePrincipal"}])
        result = _resolve_principal_names(["pid-z"], transport)
        self.assertEqual(result, {})

    def test_empty_set(self):
        transport = _make_transport([])
        result = _resolve_principal_names(set(), transport)
        self.assertEqual(result, {})


class SuccessPathTests(unittest.TestCase):
    def _assignment(self, aid, pid, role_name):
        return {
            "id": aid,
            "principalId": pid,
            "startDateTime": None,
            "endDateTime": None,
            "roleDefinition": {"displayName": role_name},
        }

    def test_single_assignment_persisted(self):
        assignment_payload = {"value": [self._assignment("a1", "p1", "Global Reader")]}
        principal_payload = {"displayName": "Alice"}
        transport = _make_transport([assignment_payload, principal_payload])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertEqual(result["assignments_fetched"], 1)
        self.assertNotIn("skipped", result)
        self.assertTrue(conn.commit.called)
        row = cur.execute.call_args[0][1]
        self.assertEqual(row[0], "a1")
        self.assertEqual(row[1], TENANT_ID)
        self.assertEqual(row[2], "Alice")
        self.assertEqual(row[3], "Global Reader")
        self.assertEqual(row[4], "Assigned")

    def test_assignment_type_always_assigned(self):
        assignment_payload = {"value": [self._assignment("a2", "p2", "Reader")]}
        principal_payload = {"displayName": "Bob"}
        transport = _make_transport([assignment_payload, principal_payload])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        row = cur.execute.call_args[0][1]
        self.assertEqual(row[4], "Assigned")

    def test_paginates_through_next_link(self):
        page1 = {
            "value": [self._assignment("a1", "p1", "Reader")],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments?$skiptoken=abc",
        }
        page2 = {"value": [self._assignment("a2", "p2", "Writer")]}
        principal_p1 = {"displayName": "Bob"}
        principal_p2 = {"displayName": "Carol"}
        transport = _make_transport([page1, page2, principal_p1, principal_p2])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertEqual(result["assignments_fetched"], 2)
        self.assertEqual(cur.execute.call_count, 2)

    def test_empty_value_list(self):
        transport = _make_transport([{"value": []}])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertEqual(result["assignments_fetched"], 0)
        self.assertFalse(cur.execute.called)
        self.assertTrue(conn.commit.called)

    def test_missing_principal_stored_as_none(self):
        assignment_payload = {
            "value": [{
                "id": "a-null",
                "principalId": None,
                "startDateTime": None,
                "endDateTime": None,
                "roleDefinition": {"displayName": "Reader"},
            }]
        }
        transport = _make_transport([assignment_payload])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertEqual(result["assignments_fetched"], 1)
        row = cur.execute.call_args[0][1]
        self.assertIsNone(row[2])

    def test_unresolvable_principal_stored_as_none(self):
        assignment_payload = {"value": [self._assignment("a3", "p3", "Reader")]}
        principal_error = _http_error(403)
        transport = _make_transport([assignment_payload, principal_error])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertEqual(result["assignments_fetched"], 1)
        row = cur.execute.call_args[0][1]
        self.assertIsNone(row[2])

    def test_deduplicates_principal_lookup(self):
        assignment_payload = {
            "value": [
                self._assignment("a1", "p-shared", "Reader"),
                self._assignment("a2", "p-shared", "Writer"),
            ]
        }
        principal_payload = {"displayName": "Shared User"}
        transport = _make_transport([assignment_payload, principal_payload])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertEqual(result["assignments_fetched"], 2)
        self.assertEqual(cur.execute.call_count, 2)


class GracefulSkipTests(unittest.TestCase):
    def test_403_on_assignments_returns_skip(self):
        transport = _make_transport([_http_error(403)])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertTrue(result.get("skipped"))
        self.assertIn("403", result["skip_reason"])
        self.assertEqual(result["assignments_fetched"], 0)
        self.assertFalse(cur.execute.called)
        self.assertFalse(conn.commit.called)

    def test_404_on_assignments_returns_skip(self):
        transport = _make_transport([_http_error(404, code="ResourceNotFound")])
        conn, cur = _fake_connection()
        result = collect_and_persist_entra_pim(
            tenant_id=TENANT_ID, transport=transport, connection=conn
        )
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result["assignments_fetched"], 0)

    def test_500_propagates(self):
        transport = _make_transport([_http_error(500, code="InternalServerError")])
        conn, cur = _fake_connection()
        with self.assertRaises(GraphHttpError) as ctx:
            collect_and_persist_entra_pim(
                tenant_id=TENANT_ID, transport=transport, connection=conn
            )
        self.assertEqual(ctx.exception.status, 500)


if __name__ == "__main__":
    unittest.main()
