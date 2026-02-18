"""
SecureFlow AI — Redaction Engine.
Replaces detected entities with reversible tokens (or XXX masks) and handles restoration.
"""

from __future__ import annotations
from app.models.schemas import DetectedEntity


def redact(
    text: str,
    entities: list[DetectedEntity],
    mode: str = "token",
) -> tuple[str, dict[str, str]]:
    """
    Replace detected entities in *text*.

    Args:
        text:     Original text.
        entities: List of detected entities with start/end positions.
        mode:     "token" → reversible `[REDACTED_TYPE_N]` tokens (default).
                  "xxx"   → fixed `XXX` replacement (non-reversible).

    Returns:
        (sanitized_text, token_map) — token_map is empty when mode="xxx".
    """
    if mode == "xxx":
        return _redact_xxx(text, entities)
    return _redact_token(text, entities)


def _redact_token(
    text: str, entities: list[DetectedEntity]
) -> tuple[str, dict[str, str]]:
    """Reversible redaction with `[REDACTED_TYPE_N]` tokens."""
    token_map: dict[str, str] = {}
    counters: dict[str, int] = {}

    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)

    for entity in sorted_entities:
        entity_type = entity.type.upper()
        counters[entity_type] = counters.get(entity_type, 0) + 1
        token = f"[REDACTED_{entity_type}_{counters[entity_type]}]"

        token_map[token] = entity.text
        text = text[:entity.start] + token + text[entity.end:]

    return text, token_map


def _redact_xxx(
    text: str, entities: list[DetectedEntity]
) -> tuple[str, dict[str, str]]:
    """Non-reversible redaction — replaces every entity with 'XXX'."""
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)

    for entity in sorted_entities:
        text = text[:entity.start] + "XXX" + text[entity.end:]

    return text, {}


def restore(text: str, token_map: dict[str, str]) -> str:
    """
    Replace `[REDACTED_*]` tokens in text with their originals from token_map.

    Args:
        text:      Text containing redaction tokens.
        token_map: Mapping of tokens → original values.

    Returns:
        Restored text with originals reinjected.
    """
    for token, original in token_map.items():
        text = text.replace(token, original)
    return text
