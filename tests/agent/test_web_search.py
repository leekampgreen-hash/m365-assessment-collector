from unittest.mock import patch

from agent import orchestrator


def test_is_m365_scoped_keywords():
    assert orchestrator.is_m365_scoped("How does Conditional Access work?")
    assert orchestrator.is_m365_scoped("What is the Microsoft Security Score?")


def test_is_m365_scoped_unrelated():
    assert not orchestrator.is_m365_scoped("What is the weather in Jakarta?")


def test_out_of_scope_live_message_skips_openai():
    with patch.dict(orchestrator.config.__dict__, {"AGENT_MODE": "live"}), patch("openai.OpenAI") as openai:
        result = orchestrator.chat("What is the weather in Jakarta?")
    openai.assert_not_called()
    assert result["tools_used"] == []
    assert "only assist with Microsoft 365" in result["reply"]


def test_knowledge_fallback_context_is_available():
    from agent.knowledge.loader import knowledge_base

    context = knowledge_base.get_context_for_prompt(["mfa", "coverage"])
    assert context
    assert "mfa" in context.casefold()
