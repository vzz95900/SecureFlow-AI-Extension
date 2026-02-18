"""
SecureFlow AI — Privacy Leakage Evaluation Benchmark.

Measures how well the pipeline detects and redacts PII from test prompts.

Usage:
    cd backend
    python scripts/evaluate.py --dataset data/eval_set.json --threshold 0.08 --report
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


async def evaluate(dataset_path: str, threshold: float = 0.08, verbose: bool = False):
    """
    Run the sanitization pipeline on test prompts and measure leakage.

    Dataset format (JSON):
    [
        {
            "text": "My name is Alice and my SSN is 123-45-6789",
            "expected_pii": [
                {"text": "Alice", "type": "PERSON"},
                {"text": "123-45-6789", "type": "SSN"}
            ]
        },
        ...
    ]
    """
    from app.pipeline.orchestrator import detect_all
    from app.pipeline.redactor import redact

    # ── Load dataset ──────────────────────────────────────────
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    logger.info(f"Loaded {len(dataset)} test cases from {dataset_path}")

    # ── Metrics ───────────────────────────────────────────────
    total_pii = 0
    detected_pii = 0
    missed_pii = 0
    false_positives = 0
    results_by_type = defaultdict(lambda: {"total": 0, "detected": 0, "missed": 0})

    # ── Run pipeline on each test case ────────────────────────
    for i, case in enumerate(dataset):
        text = case["text"]
        expected = case.get("expected_pii", [])

        # Run detection
        entities, risk_level, summary = await detect_all(text, sensitivity="high")

        # Redact
        sanitized, _ = redact(text, entities)

        # Check each expected PII
        for pii_item in expected:
            pii_text = pii_item["text"]
            pii_type = pii_item.get("type", "UNKNOWN")
            total_pii += 1
            results_by_type[pii_type]["total"] += 1

            if pii_text in sanitized:
                # PII leaked through!
                missed_pii += 1
                results_by_type[pii_type]["missed"] += 1
                if verbose:
                    logger.warning(
                        f"  LEAK [{pii_type}] '{pii_text}' — case #{i+1}"
                    )
            else:
                detected_pii += 1
                results_by_type[pii_type]["detected"] += 1

        # Count false positives (detected entities not in expected list)
        expected_texts = {p["text"].lower() for p in expected}
        for entity in entities:
            if entity.text.lower() not in expected_texts:
                false_positives += 1

    # ── Calculate metrics ─────────────────────────────────────
    leakage_rate = missed_pii / total_pii if total_pii > 0 else 0.0
    detection_rate = detected_pii / total_pii if total_pii > 0 else 1.0
    fp_rate = false_positives / (detected_pii + false_positives) if (detected_pii + false_positives) > 0 else 0.0

    passed = leakage_rate <= threshold

    # ── Report ────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("  SecureFlow AI — Privacy Leakage Benchmark Results")
    logger.info("=" * 60)
    logger.info(f"  Test cases       : {len(dataset)}")
    logger.info(f"  Total PII items  : {total_pii}")
    logger.info(f"  Detected         : {detected_pii}")
    logger.info(f"  Missed (leaked)  : {missed_pii}")
    logger.info(f"  False positives  : {false_positives}")
    logger.info("-" * 60)
    logger.info(f"  Detection rate   : {detection_rate:.1%}")
    logger.info(f"  Leakage rate     : {leakage_rate:.1%}  (threshold: ≤{threshold:.0%})")
    logger.info(f"  False positive   : {fp_rate:.1%}")
    logger.info("-" * 60)
    logger.info(f"  Result           : {'✅ PASS' if passed else '❌ FAIL'}")
    logger.info("=" * 60)

    # Per-type breakdown
    if results_by_type:
        logger.info("")
        logger.info("  Per-type breakdown:")
        logger.info(f"  {'Type':<20} {'Total':>6} {'Detected':>10} {'Missed':>8} {'Rate':>8}")
        logger.info("  " + "-" * 54)
        for pii_type in sorted(results_by_type.keys()):
            stats = results_by_type[pii_type]
            rate = stats["detected"] / stats["total"] if stats["total"] > 0 else 0
            logger.info(
                f"  {pii_type:<20} {stats['total']:>6} {stats['detected']:>10} "
                f"{stats['missed']:>8} {rate:>7.1%}"
            )

    return {
        "total_pii": total_pii,
        "detected": detected_pii,
        "missed": missed_pii,
        "false_positives": false_positives,
        "leakage_rate": leakage_rate,
        "detection_rate": detection_rate,
        "passed": passed,
    }


def main():
    parser = argparse.ArgumentParser(description="Run privacy leakage benchmark")
    parser.add_argument("--dataset", required=True, help="Path to eval dataset (JSON)")
    parser.add_argument("--threshold", type=float, default=0.08, help="Max acceptable leakage rate")
    parser.add_argument("--report", action="store_true", help="Show detailed report")
    parser.add_argument("--verbose", action="store_true", help="Show individual leaks")

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
