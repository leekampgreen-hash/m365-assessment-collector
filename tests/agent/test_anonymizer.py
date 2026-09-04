import pytest
from agent.anonymizer import Anonymizer, session_store


def test_anonymize_value_and_deanonymize():
    anon = Anonymizer()
    token1 = anon.anonymize_value("MOD Administrator")
    token2 = anon.anonymize_value("Isaiah Langer")
    token1_again = anon.anonymize_value("MOD Administrator")

    assert token1 == "USER_A"
    assert token2 == "USER_B"
    assert token1_again == "USER_A"
    assert anon.deanonymize(f"Audit {token1} and {token2}") == "Audit MOD Administrator and Isaiah Langer"


def test_anonymize_data_nested():
    anon = Anonymizer()
    payload = [
        {"display_name": "MOD Administrator", "score": 90},
        {"display_name": "Lidia Holloway", "score": 85},
    ]
    anonymized = anon.anonymize_data(payload)
    assert anonymized[0]["display_name"] == "USER_A"
    assert anonymized[1]["display_name"] == "USER_B"
    assert anonymized[0]["score"] == 90


def test_anonymize_text_exact_and_case_insensitive():
    anon = Anonymizer()
    anon.anonymize_value("MOD Administrator")
    anon.anonymize_value("Isaiah Langer")

    query1 = "Audit user MOD Administrator: explain why this user is marked high risk."
    assert anon.anonymize_text(query1) == "Audit user USER_A: explain why this user is marked high risk."

    query2 = "Audit user mod administrator: please investigate."
    assert anon.anonymize_text(query2) == "Audit user USER_A: please investigate."

    query3 = "Check isaiah langer signins."
    assert anon.anonymize_text(query3) == "Check USER_B signins."


def test_anonymize_text_word_boundary_and_symbols():
    anon = Anonymizer()
    anon.anonymize_value("Lee")
    anon.anonymize_value("Brian Johnson (TAILSPIN)")

    # "Lee" should not be replaced inside "Fleet"
    text1 = "Fleet management for Lee"
    assert anon.anonymize_text(text1) == "Fleet management for USER_A"

    # Name with symbols should be matched properly
    text2 = "Audit user Brian Johnson (TAILSPIN): explain"
    assert anon.anonymize_text(text2) == "Audit user USER_B: explain"


def test_session_store_lifecycle():
    sid = session_store.create()
    assert sid is not None
    session = session_store.get(sid)
    assert session is not None
    assert "anonymizer" in session
    assert "history" in session

    session_store.append_history(sid, "user", "Hello")
    session_store.append_history(sid, "assistant", "Hi there")
    assert len(session["history"]) == 2
