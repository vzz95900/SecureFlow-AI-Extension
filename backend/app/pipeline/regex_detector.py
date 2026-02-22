"""
SecureFlow AI — Regex-Based PII Detector.
Matches patterns from data/regex_patterns.json against input text.
Includes priority-based overlap resolution to prevent misclassification.
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

# Priority for overlap resolution: lower number = higher priority
# If not specified in the JSON, patterns default to priority 50
_DEFAULT_PRIORITY = 50


def _resolve_overlaps(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """
    Resolve overlapping matches from multiple regex patterns.

    When two matches overlap, keep the one with:
      1. Lower priority number (higher importance — e.g., PHONE=5 beats AADHAAR=10)
      2. Longer span (more specific match)
      3. Higher risk level
    """
    if not entities:
        return []

    risk_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    # Sort by start, then by priority (ascending), then by span length (descending)
    entities.sort(key=lambda e: (
        e.start,
        getattr(e, '_priority', _DEFAULT_PRIORITY),
        -(e.end - e.start),
        -risk_order.get(e.risk, 0),
    ))

    resolved: list[DetectedEntity] = []
    last_end = -1

    for entity in entities:
        if entity.start >= last_end:
            resolved.append(entity)
            last_end = entity.end
        else:
            # Overlap detected — the earlier entity was already added and
            # has higher priority (or was longer / higher risk), so skip this one.
            logger.debug(
                f"Overlap resolved: kept previous, skipped {entity.type}={entity.text!r}"
            )

    return resolved


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

    # Sort patterns by priority (most important first)
    sorted_patterns = sorted(patterns, key=lambda r: r.get("priority", _DEFAULT_PRIORITY))

    for rule in sorted_patterns:
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
            entity = DetectedEntity(
                start=match.start(),
                end=match.end(),
                type=rule.get("label", rule.get("name", "UNKNOWN")).upper(),
                text=match.group(),
                risk=risk,
                source="regex",
            )
            # Attach priority as internal attribute for overlap resolution
            entity._priority = rule.get("priority", _DEFAULT_PRIORITY)
            entities.append(entity)

    # Resolve overlapping detections (e.g., same digits matched as PHONE and AADHAAR)
    resolved = _resolve_overlaps(entities)

    logger.debug(
        f"Regex detected {len(entities)} raw matches, "
        f"resolved to {len(resolved)} entities at sensitivity={sensitivity}"
    )
    return resolved
