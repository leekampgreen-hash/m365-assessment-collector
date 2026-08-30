import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from agent import tools


@pytest.mark.parametrize("name,args", [
    ("get_kpi", ()), ("get_summary", ()), ("get_data_quality", ()),
    ("get_capabilities", ()), ("get_adoption_exchange", ()),
    ("get_adoption_onedrive", ()), ("get_adoption_sharepoint", ()),
    ("get_inactivity", (30,)), ("get_license_utilization", ()),
    ("get_correlation_users", ()), ("get_signin_risk", ()),
    ("get_mfa_coverage", ()), ("get_ca_policies", ()),
])
def test_tools_return_dict(name, args):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({"ok": True}).encode()

    with patch("agent.tools.urlopen", return_value=Response()) as mock_open:
        assert isinstance(getattr(tools, name)(*args), dict)
        mock_open.assert_called_once()


def test_tool_error_on_http_error():
    error = HTTPError("url", 500, "error", {}, None)
    with patch("agent.tools.urlopen", side_effect=error), pytest.raises(tools.ToolError):
        tools.get_kpi()


def test_tool_error_on_unavailable_service():
    from urllib.error import URLError
    with patch("agent.tools.urlopen", side_effect=URLError("timeout")), pytest.raises(tools.ToolError, match="Service temporarily unavailable"):
        tools.get_kpi()
