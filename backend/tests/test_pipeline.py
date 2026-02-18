"""
Tests for the redaction engine and token map.
"""
import pytest
from app.pipeline.redactor import redact, restore
from app.models.schemas import DetectedEntity
from app.utils.token_map import TokenMapManager


def test_redact_single_entity():
    text = "My name is John Doe and I live here."
    entities = [
        DetectedEntity(start=11, end=19, type="PERSON", text="John Doe", risk="MEDIUM", source="ner")
    ]
    sanitized, token_map = redact(text, entities)
    assert "John Doe" not in sanitized
    assert "[REDACTED_PERSON_1]" in sanitized
    assert token_map["[REDACTED_PERSON_1]"] == "John Doe"


def test_redact_multiple_entities():
    text = "John Doe, SSN 123-45-6789, email john@test.com"
    entities = [
        DetectedEntity(start=0, end=8, type="PERSON", text="John Doe", risk="MEDIUM", source="ner"),
        DetectedEntity(start=14, end=25, type="SSN", text="123-45-6789", risk="HIGH", source="regex"),
        DetectedEntity(start=33, end=46, type="EMAIL", text="john@test.com", risk="MEDIUM", source="regex"),
    ]
    sanitized, token_map = redact(text, entities)
    assert "John Doe" not in sanitized
    assert "123-45-6789" not in sanitized
    assert "john@test.com" not in sanitized
    assert len(token_map) == 3


def test_restore_text():
    token_map = {
        "[REDACTED_PERSON_1]": "John Doe",
        "[REDACTED_SSN_1]": "123-45-6789",
    }
    sanitized = "Hello [REDACTED_PERSON_1], your SSN [REDACTED_SSN_1] is safe."
    restored = restore(sanitized, token_map)
    assert "John Doe" in restored
    assert "123-45-6789" in restored
    assert "[REDACTED_" not in restored


def test_restore_empty_map():
    text = "No tokens here."
    restored = restore(text, {})
    assert restored == text


def test_token_map_manager_lifecycle():
    manager = TokenMapManager()
    sid = manager.create_session()
    assert sid

    manager.store(sid, "[REDACTED_NAME_1]", "Alice")
    assert manager.get_original(sid, "[REDACTED_NAME_1]") == "Alice"

    full_map = manager.get_map(sid)
    assert full_map["[REDACTED_NAME_1]"] == "Alice"

    manager.delete_session(sid)
    assert manager.get_map(sid) == {}
