from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from urllib.request import Request

from collectors.core.models import EndpointSpec
from collectors.core.transport import GraphTransport
from collectors.run_collector import collect_and_persist_sharepoint_settings


SYNTHETIC_TENANT_ID = 555020


class Response:
    status = 200
    headers = {}

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _connect(user, password):
    import psycopg

    return psycopg.connect(
        host=os.environ.get("PGHOST", "postgres"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "graph_agent"),
        user=user,
        password=password,
    )


def _runtime_password():
    path = Path("/run/secrets/graph_agent_runtime_password")
    if not path.exists():
        raise unittest.SkipTest("production database credentials are unavailable")
    return path.read_text(encoding="utf-8").strip()


def _bootstrap_password():
    value = os.environ.get("SP_P05_BOOTSTRAP_PASSWORD", "")
    if not value:
        raise unittest.SkipTest("SP_P05_BOOTSTRAP_PASSWORD unavailable")
    return value


class SharePointTenantSettingsProductionPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = _connect("graph_agent_bootstrap", _bootstrap_password())
        cls.bootstrap.autocommit = True
        cursor = cls.bootstrap.cursor()
        cursor.execute(
            "INSERT INTO core.tenant (tenant_id, entra_tenant_id, display_label, enabled, retention_class) "
            "VALUES (%s, %s, %s, TRUE, 'REFERENCE') ON CONFLICT (tenant_id) DO NOTHING",
            (SYNTHETIC_TENANT_ID, "synthetic-555020", "SP-P05 synthetic tenant"),
        )

    @classmethod
    def tearDownClass(cls):
        cursor = cls.bootstrap.cursor()
        cursor.execute("DELETE FROM core.sharepoint_tenant_settings WHERE tenant_id = %s", (SYNTHETIC_TENANT_ID,))
        cursor.execute("DELETE FROM control.collection_run WHERE tenant_id = %s", (SYNTHETIC_TENANT_ID,))
        cursor.execute("DELETE FROM core.tenant WHERE tenant_id = %s", (SYNTHETIC_TENANT_ID,))
        cursor.execute("SELECT count(*) FROM core.sharepoint_tenant_settings WHERE tenant_id = %s", (SYNTHETIC_TENANT_ID,))
        if cursor.fetchone()[0] != 0:
            raise AssertionError("synthetic SharePoint tenant settings residue remains")
        cls.bootstrap.close()

    def test_fake_transport_reaches_real_postgresql_persistence(self):
        payload = {
            "sharingCapability": "externalUserAndGuestSharing",
            "defaultSharingLinkType": "view",
            "externalUserExpirationRequired": True,
            "externalUserExpirationInDays": 30,
            "fileAnonymousLinkType": "view",
            "folderAnonymousLinkType": "edit",
            "requireAnonymousLinksExpireInDays": 90,
            "allowGuestUserSharing": True,
        }
        calls = []

        def opener(request: Request, timeout=None):
            calls.append(request.full_url)
            return Response(payload)

        connection = _connect("graph_agent_runtime", _runtime_password())
        self.addCleanup(connection.close)
        spec = EndpointSpec(
            endpoint_id="G01-020",
            name="SharePoint Tenant Settings",
            path="/v1.0/admin/sharepoint/settings",
            workload="SharePoint Tenant Settings",
            pagination=False,
        )
        result = collect_and_persist_sharepoint_settings(
            tenant_id=SYNTHETIC_TENANT_ID,
            transport=GraphTransport(lambda: "fake-token", url_open=opener),
            connection=connection,
            spec=spec,
        )

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.persisted_rows, 1)
        self.assertEqual(len(calls), 1)
        cursor = self.bootstrap.cursor()
        cursor.execute(
            "SELECT sharing_capability, default_sharing_link_type, external_user_expiration_required, "
            "external_user_expiration_in_days, file_anonymous_link_type, folder_anonymous_link_type, "
            "require_anonymous_links_expire_in_days, allow_guest_user_sharing "
            "FROM core.sharepoint_tenant_settings WHERE tenant_id = %s",
            (SYNTHETIC_TENANT_ID,),
        )
        self.assertEqual(
            cursor.fetchone(),
            ("externalUserAndGuestSharing", "view", True, 30, "view", "edit", 90, True),
        )


if __name__ == "__main__":
    unittest.main()
