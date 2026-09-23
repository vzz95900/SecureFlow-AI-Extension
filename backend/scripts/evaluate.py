"""
SecureFlow AI — Entity-Level Evaluation Benchmark.

Computes precision, recall, and F1 per entity type using exact-match
and partial-match evaluation on a labeled test set.

Usage:
    cd backend
    python scripts/evaluate.py --dataset data/eval_set_300.json --verbose --report
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Normalize text for matching (strip, lowercase, collapse whitespace)."""
    return " ".join(text.strip().lower().split())


def _texts_match(predicted: str, expected: str) -> bool:
    """Check if predicted text matches expected (exact after normalization)."""
    return _normalize(predicted) == _normalize(expected)


def _texts_overlap(pred_text: str, exp_text: str, full_text: str) -> bool:
    """Check if predicted and expected texts overlap in the original string."""
    p = _normalize(pred_text)
    e = _normalize(exp_text)
    return p in e or e in p


async def evaluate(dataset_path: str, threshold: float = 0.08, verbose: bool = False):
    """
    Run the sanitization pipeline on test prompts and compute P/R/F1.

    Uses entity-level evaluation:
    - True Positive: expected entity matched by a detection (same type + text overlap)
    - False Negative: expected entity NOT matched by any detection
    - False Positive: detected entity NOT matching any expected entity
    """
    from app.pipeline.orchestrator import detect_all

    # ── Load dataset ──────────────────────────────────────────
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    logger.info(f"Loaded {len(dataset)} test cases from {dataset_path}")

    # ── Per-type counters ─────────────────────────────────────
    tp_by_type = defaultdict(int)   # true positives
    fp_by_type = defaultdict(int)   # false positives
    fn_by_type = defaultdict(int)   # false negatives

    # Map of NER output types → expected types for type matching
    TYPE_ALIASES = {
        "LOCATION": "LOCATION", "GPE": "LOCATION",
        "NUMBER": "NUMBER", "CARDINAL": "NUMBER",
    }

    all_types = set()

    # ── Run pipeline on each test case ────────────────────────
    for i, case in enumerate(dataset):
        text = case["text"]
        expected = case.get("expected_pii", [])

        # Run detection
        entities, risk_level, summary = await detect_all(text, sensitivity="high")

        # Track expected types
        for e in expected:
            all_types.add(e["type"])

        # Build matched sets
        matched_expected = set()   # indices of matched expected
        matched_predicted = set()  # indices of matched predicted

        # Match predicted → expected
        for pi, pred in enumerate(entities):
            pred_type = TYPE_ALIASES.get(pred.type, pred.type)

            for ei, exp in enumerate(expected):
                if ei in matched_expected:
                    continue
                exp_type = TYPE_ALIASES.get(exp["type"], exp["type"])

                if pred_type == exp_type and _texts_overlap(pred.text, exp["text"], text):
                    matched_expected.add(ei)
                    matched_predicted.add(pi)
                    tp_by_type[exp["type"]] += 1
                    break

        # False negatives: expected but not matched
        for ei, exp in enumerate(expected):
            if ei not in matched_expected:
                fn_by_type[exp["type"]] += 1
                if verbose:
                    logger.warning(
                        f"  FN [{exp['type']}] '{exp['text']}' — case #{i+1}"
                    )

        # False positives: predicted but not matched to any expected
        for pi, pred in enumerate(entities):
            if pi not in matched_predicted:
                pred_type = TYPE_ALIASES.get(pred.type, pred.type)
                fp_by_type[pred_type] += 1
                if verbose:
                    logger.info(
                        f"  FP [{pred_type}] '{pred.text}' — case #{i+1}"
                    )

    # ── Compute metrics ───────────────────────────────────────
    all_types.update(tp_by_type.keys())
    all_types.update(fp_by_type.keys())
    all_types.update(fn_by_type.keys())

    per_type_metrics = {}
    for t in sorted(all_types):
        tp = tp_by_type[t]
        fp = fp_by_type[t]
        fn = fn_by_type[t]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_type_metrics[t] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }

    # Micro-averaged
    total_tp = sum(tp_by_type.values())
    total_fp = sum(fp_by_type.values())
    total_fn = sum(fn_by_type.values())
    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    # Macro-averaged
    type_count = len(per_type_metrics)
    macro_p = sum(m["precision"] for m in per_type_metrics.values()) / type_count if type_count else 0
    macro_r = sum(m["recall"] for m in per_type_metrics.values()) / type_count if type_count else 0
    macro_f1 = sum(m["f1"] for m in per_type_metrics.values()) / type_count if type_count else 0

    passed = micro_r >= (1 - threshold)  # e.g., 92%+ recall

    # ── Report ────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 78)
    logger.info("  SecureFlow AI — Entity-Level Evaluation Results")
    logger.info("=" * 78)
    logger.info(f"  Dataset          : {dataset_path}")
    logger.info(f"  Test cases       : {len(dataset)}")
    neg = sum(1 for c in dataset if not c.get("expected_pii"))
    logger.info(f"  Negative cases   : {neg}")
    logger.info(f"  Total expected   : {total_tp + total_fn}")
    logger.info(f"  Total predicted  : {total_tp + total_fp}")
    logger.info("-" * 78)
    logger.info(f"  {'Type':<20} {'Prec':>7} {'Rec':>7} {'F1':>7} {'TP':>5} {'FP':>5} {'FN':>5} {'Sup':>5}")
    logger.info("  " + "-" * 70)

    for t in sorted(per_type_metrics.keys()):
        m = per_type_metrics[t]
        logger.info(
            f"  {t:<20} {m['precision']:>7.1%} {m['recall']:>7.1%} "
            f"{m['f1']:>7.1%} {m['tp']:>5} {m['fp']:>5} {m['fn']:>5} {m['support']:>5}"
        )

    logger.info("  " + "-" * 70)
    logger.info(
        f"  {'MICRO-AVG':<20} {micro_p:>7.1%} {micro_r:>7.1%} "
        f"{micro_f1:>7.1%} {total_tp:>5} {total_fp:>5} {total_fn:>5} {total_tp+total_fn:>5}"
    )
    logger.info(
        f"  {'MACRO-AVG':<20} {macro_p:>7.1%} {macro_r:>7.1%} "
        f"{macro_f1:>7.1%}"
    )
    logger.info("=" * 78)
    logger.info(f"  Result : {'✅ PASS' if passed else '❌ FAIL'} (recall threshold ≥ {1-threshold:.0%})")
    logger.info("=" * 78)

    return {
        "dataset": dataset_path,
        "num_examples": len(dataset),
        "num_negative": neg,
        "total_expected": total_tp + total_fn,
        "total_predicted": total_tp + total_fp,
        "per_type": per_type_metrics,
        "micro": {"precision": round(micro_p, 4), "recall": round(micro_r, 4), "f1": round(micro_f1, 4)},
        "macro": {"precision": round(macro_p, 4), "recall": round(macro_r, 4), "f1": round(macro_f1, 4)},
        "passed": passed,
    }


def main():
    parser = argparse.ArgumentParser(description="Run entity-level evaluation benchmark")
    parser.add_argument("--dataset", required=True, help="Path to eval dataset (JSON)")
    parser.add_argument("--threshold", type=float, default=0.08, help="Max acceptable miss rate")
    parser.add_argument("--report", action="store_true", help="Save JSON report")
    parser.add_argument("--verbose", action="store_true", help="Show individual FN/FP")

    args = parser.parse_args()

    results = asyncio.run(evaluate(
        dataset_path=args.dataset,
        threshold=args.threshold,
        verbose=args.verbose,
    ))

    if args.report:
        report_path = Path(args.dataset).parent / "eval_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info(f"\nReport saved to {report_path}")

    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
