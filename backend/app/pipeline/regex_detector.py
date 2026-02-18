"""
SecureFlow AI — Regex-Based PII Detector.
Matches patterns from data/regex_patterns.json against input text.
"""

from __future__ import annotations
import json
import re
import logging
from pathlib import Path

from app.models.schemas import DetectedEntity

logger = logging.getLogger(__name__)

# ── Load regex patterns from JSON ─────────────────────────────────

_patterns: list[dict] = []


def _load_patterns():
    """Load regex patterns from the JSON data file."""
    global _patterns
    if _patterns:
        return _patterns

    pattern_file = Path(__file__).resolve().parent.parent.parent / "data" / "regex_patterns.json"

    if not pattern_file.exists():
        logger.warning(f"Regex patterns file not found: {pattern_file}")
        return []

    with open(pattern_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    _patterns = data.get("patterns", [])
    logger.info(f"Loaded {len(_patterns)} regex patterns from {pattern_file.name}")
    return _patterns


# ── Risk-level filter based on sensitivity ────────────────────────

SENSITIVITY_RISK_MAP = {
    "low":    {"HIGH"},
    "medium": {"HIGH", "MEDIUM"},
    "high":   {"HIGH", "MEDIUM", "LOW"},
}


async def detect(text: str, sensitivity: str = "high") -> list[DetectedEntity]:
    """
    Scan text using regex patterns and return detected entities.

    Args:
        text:        Input text to scan.
        sensitivity: "high" | "medium" | "low".

    Returns:
        List of DetectedEntity objects.
    """
    patterns = _load_patterns()
    allowed_risks = SENSITIVITY_RISK_MAP.get(sensitivity, {"HIGH", "MEDIUM", "LOW"})

    entities: list[DetectedEntity] = []

    for rule in patterns:
        risk = rule.get("risk", "HIGH")
        if risk not in allowed_risks:
            continue

        # Skip context-dependent patterns (like generic bank account numbers)
        if rule.get("requires_context", False):
            continue

        try:
            compiled = re.compile(rule["pattern"])
        except re.error as e:
            logger.error(f"Invalid regex pattern '{rule['name']}': {e}")
            continue

        for match in compiled.finditer(text):
            entities.append(DetectedEntity(
                start=match.start(),
                end=match.end(),
                type=rule.get("label", rule.get("name", "UNKNOWN")).upper(),
                text=match.group(),
                risk=risk,
                source="regex",
            ))

    logger.debug(f"Regex detected {len(entities)} entities at sensitivity={sensitivity}")
    return entities
