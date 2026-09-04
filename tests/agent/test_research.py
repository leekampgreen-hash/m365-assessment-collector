from unittest.mock import patch
from urllib.error import URLError

from agent import research


def test_get_curated_urls_matches_topics_and_limits_results():
    urls = research.get_curated_urls("MFA guidance", ["mfa"])
    assert len(urls) == 2
    assert all(url.startswith("https://learn.microsoft.com/") for url in urls)


def test_get_curated_urls_returns_flat_max_three():
    urls = research.get_curated_urls("MFA and conditional access", ["mfa", "conditional_access"])
    assert len(urls) == 3
    assert len(set(urls)) == len(urls)


def test_fetch_page_content_rejects_non_microsoft_domains():
    with patch("agent.research.urlopen") as open_url:
        assert research.fetch_page_content("https://example.com/page") == ""
    open_url.assert_not_called()


def test_extract_intent_strips_pii():
    intent = research.extract_intent("What is John's MFA status? Contact john@example.com from 192.168.1.5", [])
    assert "john" not in intent.casefold()
    assert "john@example.com" not in intent
    assert "192.168.1.5" not in intent
    assert "MFA" in intent


def test_research_fetches_curated_pages():
    body = b"<main><h1>MFA guidance</h1><p>Use multifactor authentication.</p></main>"
    with patch("agent.research.urlopen") as open_url:
        open_url.return_value.__enter__.return_value.read.return_value = body
        result = research.research("MFA best practices")
    assert "learn.microsoft.com" in result
    assert "multifactor authentication" in result


def test_research_returns_empty_on_network_error(tmp_path):
    with patch("agent.research._CACHE_DIR", tmp_path), patch("agent.research.urlopen", side_effect=URLError("offline")):
        assert research.research("MFA best practices") == ""
