"""
SecureFlow AI — BERT Risk Classifier.
Classifies detected entities as HIGH / MEDIUM / LOW risk using a fine-tuned BERT model.

NOTE: This module requires a trained model to be present at the configured path.
Without a trained model, it falls back to rule-based risk assignment.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.models.schemas import DetectedEntity
from app.config import get_settings

logger = logging.getLogger(__name__)

# Lazy-loaded model components
_model = None
_tokenizer = None
_model_loaded = False
_model_available = False

RISK_LABELS = ["HIGH", "MEDIUM", "LOW"]


def _load_model():
    """Attempt to load the fine-tuned BERT model."""
    global _model, _tokenizer, _model_loaded, _model_available
    if _model_loaded:
        return _model_available

    _model_loaded = True

    settings = get_settings()
    model_path = settings.bert_model_path

    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch

        _tokenizer = AutoTokenizer.from_pretrained(model_path)
        _model = AutoModelForSequenceClassification.from_pretrained(model_path)
        _model.eval()
        _model_available = True
        logger.info(f"BERT risk classifier loaded from {model_path}")

    except Exception as e:
        logger.warning(
            f"BERT model not available at '{model_path}': {e}. "
            f"Falling back to rule-based risk scoring."
        )
        _model_available = False

    return _model_available


# ── Rule-based fallback risk scoring ──────────────────────────────

HIGH_RISK_TYPES = {
    "AADHAAR", "PAN", "PASSPORT", "CREDIT_CARD", "DOB",
    "MEDICAL_RECORD", "ABHA", "VOTER_ID", "DRIVING_LICENCE",
    "SSN",  # kept for universal coverage
}
MEDIUM_RISK_TYPES = {
    "PERSON", "PHONE", "EMAIL", "FINANCIAL", "BANK_ACCOUNT",
    "IFSC", "UPI_ID", "GSTIN", "RATION_CARD",
}


def _rule_based_risk(entity: DetectedEntity) -> str:
    """Assign risk based on entity type when BERT is unavailable."""
    entity_type = entity.type.upper()
    if entity_type in HIGH_RISK_TYPES:
        return "HIGH"
    elif entity_type in MEDIUM_RISK_TYPES:
        return "MEDIUM"
    return "LOW"


# ── BERT inference ────────────────────────────────────────────────

def _predict_risk(text: str, context: str = "") -> tuple[str, float]:
    """
    Run BERT inference on a text snippet.

    Returns:
        (risk_label, confidence)
    """
    import torch

    input_text = f"{context} [SEP] {text}" if context else text
    inputs = _tokenizer(
        input_text,
        return_tensors="pt",
        truncation=True,
        max_length=128,
        padding=True,
    )

    with torch.no_grad():
        outputs = _model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]
        confidence, predicted = torch.max(probs, dim=0)

    return RISK_LABELS[predicted.item()], confidence.item()


async def classify_risk(
    entities: list[DetectedEntity],
    full_text: str = "",
) -> list[DetectedEntity]:
    """
    Classify risk level for each detected entity.
    Uses BERT if available, otherwise falls back to rule-based scoring.

    Args:
        entities:  List of detected entities.
        full_text: The original full text (for context).

    Returns:
        Updated entities with risk levels set.
    """
    settings = get_settings()
    model_available = _load_model()

    classified: list[DetectedEntity] = []

    for entity in entities:
        if model_available:
            # Extract context window around the entity
            ctx_start = max(0, entity.start - 50)
            ctx_end = min(len(full_text), entity.end + 50)
            context = full_text[ctx_start:ctx_end]

            risk, confidence = _predict_risk(entity.text, context)

            # Conservative: if confidence is low, default to HIGH
            if confidence < settings.bert_confidence_threshold:
                risk = "HIGH"

            entity.risk = risk
        else:
            entity.risk = _rule_based_risk(entity)

        classified.append(entity)

    logger.debug(f"Classified {len(classified)} entities (BERT={model_available})")
    return classified
