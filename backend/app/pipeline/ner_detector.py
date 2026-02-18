"""
SecureFlow AI — spaCy NER Detector.
Detects named entities (PERSON, ORG, GPE, DATE, etc.) using spaCy.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.models.schemas import DetectedEntity
from app.config import get_settings

logger = logging.getLogger(__name__)

# Lazy-loaded spaCy model
_nlp = None


def _load_model():
    """Load the spaCy model (lazy, one-time)."""
    global _nlp
    if _nlp is not None:
        return _nlp

    import spacy

    settings = get_settings()
    model_name = settings.spacy_model

    try:
        _nlp = spacy.load(model_name)
        logger.info(f"Loaded spaCy model: {model_name}")
    except OSError:
        # Fallback to small model if transformer model unavailable
        fallback = "en_core_web_sm"
        logger.warning(f"Model '{model_name}' not found, falling back to '{fallback}'")
        try:
            _nlp = spacy.load(fallback)
        except OSError:
            raise RuntimeError(
                f"No spaCy model available. Install one with: "
                f"python -m spacy download {fallback}"
            )

    return _nlp


# Mapping spaCy labels → our entity types + default risk
LABEL_MAP = {
    "PERSON":   ("PERSON",   "MEDIUM"),
    "ORG":      ("ORG",      "LOW"),
    "GPE":      ("LOCATION", "LOW"),
    "LOC":      ("LOCATION", "LOW"),
    "DATE":     ("DATE",     "LOW"),
    "NORP":     ("GROUP",    "LOW"),
    "FAC":      ("FACILITY", "LOW"),
    "EVENT":    ("EVENT",    "LOW"),
    "MONEY":    ("FINANCIAL","MEDIUM"),
    "CARDINAL": ("NUMBER",   "LOW"),
}


async def detect(text: str, sensitivity: str = "high") -> list[DetectedEntity]:
    """
    Run spaCy NER on text and return detected entities.

    Args:
        text:        Input text to scan.
        sensitivity: "high" | "medium" | "low" — controls which labels are included.

    Returns:
        List of DetectedEntity objects.
    """
    nlp = _load_model()
    doc = nlp(text)

    # Sensitivity filtering: higher sensitivity → more entity types included
    if sensitivity == "low":
        allowed_labels = {"PERSON"}
    elif sensitivity == "medium":
        allowed_labels = {"PERSON", "ORG", "GPE", "LOC", "DATE", "MONEY"}
    else:  # high
        allowed_labels = set(LABEL_MAP.keys())

    entities: list[DetectedEntity] = []

    for ent in doc.ents:
        if ent.label_ not in allowed_labels:
            continue

        mapped = LABEL_MAP.get(ent.label_, (ent.label_, "LOW"))

        entities.append(DetectedEntity(
            start=ent.start_char,
            end=ent.end_char,
            type=mapped[0],
            text=ent.text,
            risk=mapped[1],
            source="ner",
        ))

    logger.debug(f"NER detected {len(entities)} entities at sensitivity={sensitivity}")
    return entities
