from agent.knowledge.loader import KnowledgeBase, knowledge_base


def test_knowledge_base_loads_all_files():
    assert set(knowledge_base._data) == {"rules", "ca_states", "terms", "recommendations"}
    assert all(knowledge_base._data.values())


def test_known_rule_info():
    info = knowledge_base.get_rule_info("M365-ENTRA-MFA-REG-001")
    assert info["risk_level"] == "HIGH"


def test_known_ca_state_info():
    assert knowledge_base.get_ca_state_info("disabled")["risk"] == "HIGH"


def test_known_term_info():
    assert knowledge_base.get_term_info("mfa")["full_name"] == "Multi-factor authentication"


def test_context_relevant():
    assert knowledge_base.get_context_for_prompt(["multi-factor", "authentication"])


def test_context_irrelevant():
    assert knowledge_base.get_context_for_prompt(["unrelated", "zxqvterm"]) == ""


def test_invalid_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(KnowledgeBase, "_load", staticmethod(lambda path: {} if "rules" not in str(path) else {"bad": {}}))
    try:
        KnowledgeBase()
    except ValueError:
        pass
    else:
        raise AssertionError("expected schema validation failure")
