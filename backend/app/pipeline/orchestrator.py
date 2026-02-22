"""
SecureFlow AI — Pipeline Orchestrator.
Runs all detectors, merges results, classifies risk, and produces final entity list.

Regex detections (AADHAAR, PAN, PHONE, etc.) ALWAYS override NER generic
labels (DATE, NUMBER, CARDINAL) when they overlap — even partially.
"""

from __future__ import annotations
import logging
from collections import defaultdict

from app.models.schemas import DetectedEntity, EntitySummaryItem
from app.pipeline import ner_detector, regex_detector, bert_classifier

logger = logging.getLogger(__name__)

# NER types that are generic and should yield to regex-specific detections
_NER_GENERIC_TYPES = {
    "DATE", "NUMBER", "CARDINAL", "ORDINAL", "QUANTITY",
    "EVENT", "FINANCIAL", "LOCATION", "GROUP", "FACILITY",
}


def _spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Return True if span [a_start, a_end) overlaps with [b_start, b_end)."""
    return a_start < b_end and b_start < a_end


def _filter_ner_against_regex(
    ner_entities: list[DetectedEntity],
    regex_entities: list[DetectedEntity],
) -> list[DetectedEntity]:
    """
    Remove NER entities whose spans overlap with any regex detection.

    This prevents spaCy's generic labels (DATE, CARDINAL) from overriding
    specific regex labels (AADHAAR, PAN, PHONE) even when spans differ slightly.
    """
    if not regex_entities:
        return ner_entities

    filtered: list[DetectedEntity] = []
    for ner_ent in ner_entities:
        # Check if any regex entity overlaps with this NER entity
        overlaps_regex = any(
            _spans_overlap(ner_ent.start, ner_ent.end, reg.start, reg.end)
            for reg in regex_entities
        )
        if overlaps_regex:
            logger.debug(
                f"Suppressed NER {ner_ent.type}={ner_ent.text!r} — "
                f"overlaps with regex detection"
            )
        else:
            filtered.append(ner_ent)

    dropped = len(ner_entities) - len(filtered)
    if dropped:
        logger.info(f"Filtered {dropped} NER entities that overlapped regex detections")

    return filtered


def _merge_and_deduplicate(
    *entity_lists: list[DetectedEntity],
) -> list[DetectedEntity]:
    """
    Merge entity lists and deduplicate overlapping spans.
    Keeps the longest match when spans overlap.
    """
    all_entities: list[DetectedEntity] = []
    for el in entity_lists:
        all_entities.extend(el)

    if not all_entities:
        return []

    risk_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    # Sort by start, then risk (highest first), then span length (longest first)
    all_entities.sort(key=lambda e: (
        e.start,
        -risk_order.get(e.risk, 0),
        -(e.end - e.start),
    ))

    merged: list[DetectedEntity] = []
    last_end = -1

    for entity in all_entities:
        if entity.start >= last_end:
            merged.append(entity)
            last_end = entity.end

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
    Run the full detection pipeline: NER → Regex → Filter → Merge → BERT Classify.

    Regex-specific detections (AADHAAR, PAN, PHONE, etc.) always take
    priority over NER generic labels (DATE, CARDINAL, etc.) on overlapping spans.
    """
    # Step 1: Run NER and Regex detectors
    ner_entities = await ner_detector.detect(text, sensitivity)
    regex_entities = await regex_detector.detect(text, sensitivity)

    logger.info(
        f"Detection results: NER={len(ner_entities)}, Regex={len(regex_entities)}"
    )

    # Step 2: Filter — remove NER entities that overlap with regex detections
    # This prevents spaCy's "DATE" from overriding regex's "AADHAAR"
    filtered_ner = _filter_ner_against_regex(ner_entities, regex_entities)

    # Step 3: Merge & deduplicate
    merged = _merge_and_deduplicate(filtered_ner, regex_entities)

    # Step 4: Classify risk via BERT (or rule-based fallback)
    classified = await bert_classifier.classify_risk(merged, text)

    # Step 5: Compute overall risk and summary
    overall_risk = _compute_overall_risk(classified)
    summary = _build_summary(classified)

    logger.info(
        f"Pipeline complete: {len(classified)} entities, risk={overall_risk}"
    )

    return classified, overall_risk, summary
