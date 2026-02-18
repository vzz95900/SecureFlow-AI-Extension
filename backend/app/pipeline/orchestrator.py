"""
SecureFlow AI — Pipeline Orchestrator.
Runs all detectors, merges results, classifies risk, and produces final entity list.
"""

from __future__ import annotations
import logging
from collections import defaultdict

from app.models.schemas import DetectedEntity, EntitySummaryItem
from app.pipeline import ner_detector, regex_detector, bert_classifier

logger = logging.getLogger(__name__)


def _merge_and_deduplicate(
    *entity_lists: list[DetectedEntity],
) -> list[DetectedEntity]:
    """
    Merge entity lists from multiple detectors and deduplicate overlapping spans.
    When spans overlap, keep the longest match.
    """
    all_entities: list[DetectedEntity] = []
    for el in entity_lists:
        all_entities.extend(el)

    if not all_entities:
        return []

    # Sort by start position, then by span length descending (longest first)
    all_entities.sort(key=lambda e: (e.start, -(e.end - e.start)))

    merged: list[DetectedEntity] = []
    last_end = -1

    for entity in all_entities:
        if entity.start >= last_end:
            # No overlap → keep this entity
            merged.append(entity)
            last_end = entity.end
        # else: skip overlapping shorter span

    return merged


def _compute_overall_risk(entities: list[DetectedEntity]) -> str:
    """Compute the overall risk level (worst-case across all entities)."""
    if not entities:
        return "LOW"

    risk_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    max_risk = max(risk_order.get(e.risk, 1) for e in entities)

    for label, level in risk_order.items():
        if level == max_risk:
            return label

    return "LOW"


def _build_summary(entities: list[DetectedEntity]) -> list[EntitySummaryItem]:
    """Build a summary breakdown by entity type."""
    counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "risk": "LOW"})
    risk_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    for entity in entities:
        bucket = counts[entity.type]
        bucket["count"] += 1
        # Keep the highest risk seen for this type
        if risk_order.get(entity.risk, 1) > risk_order.get(bucket["risk"], 1):
            bucket["risk"] = entity.risk

    return [
        EntitySummaryItem(type=type_name, count=info["count"], risk=info["risk"])
        for type_name, info in sorted(counts.items())
    ]


async def detect_all(
    text: str,
    sensitivity: str = "high",
) -> tuple[list[DetectedEntity], str, list[EntitySummaryItem]]:
    """
    Run the full detection pipeline: NER → Regex → Merge → BERT Classify.

    Args:
        text:        Input text to scan.
        sensitivity: "high" | "medium" | "low".

    Returns:
        (entities, overall_risk_level, entity_summary)
    """
    # Step 1: Run NER and Regex detectors concurrently
    ner_entities = await ner_detector.detect(text, sensitivity)
    regex_entities = await regex_detector.detect(text, sensitivity)

    logger.info(
        f"Detection results: NER={len(ner_entities)}, Regex={len(regex_entities)}"
    )

    # Step 2: Merge & deduplicate
    merged = _merge_and_deduplicate(ner_entities, regex_entities)

    # Step 3: Classify risk via BERT (or rule-based fallback)
    classified = await bert_classifier.classify_risk(merged, text)

    # Step 4: Compute overall risk and summary
    overall_risk = _compute_overall_risk(classified)
    summary = _build_summary(classified)

    logger.info(
        f"Pipeline complete: {len(classified)} entities, risk={overall_risk}"
    )

    return classified, overall_risk, summary
