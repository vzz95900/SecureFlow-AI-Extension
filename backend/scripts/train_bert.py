"""
SecureFlow AI — BERT Risk Classifier Training Script.

Fine-tunes a bert-base-uncased model for 3-class risk classification
(HIGH / MEDIUM / LOW) on labeled PII context snippets.

Usage:
    cd backend
    python scripts/train_bert.py --data data/training/risk_labels.jsonl --output models/bert_risk_classifier --epochs 5
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add parent dir to path so we can import app modules if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)


def load_dataset(filepath: str) -> tuple[list[str], list[int]]:
    """
    Load training data from a JSONL file.

    Each line: {"text": "...", "label": "HIGH"}
    Labels are mapped to: HIGH=0, MEDIUM=1, LOW=2
    """
    label_map = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    texts, labels = [], []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                text = record["text"]
                label_str = record["label"].upper()
                if label_str not in label_map:
                    logger.warning(f"Line {line_num}: unknown label '{label_str}', skipping")
                    continue
                texts.append(text)
                labels.append(label_map[label_str])
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Line {line_num}: parse error — {e}")

    logger.info(f"Loaded {len(texts)} samples from {filepath}")
    return texts, labels


def train(
    data_path: str,
    output_dir: str,
    model_name: str = "bert-base-uncased",
    epochs: int = 5,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    max_length: int = 128,
    val_split: float = 0.15,
):
    """Fine-tune BERT for risk classification."""

    try:
        import torch
        from transformers import (
            AutoTokenizer,
            AutoModelForSequenceClassification,
            Trainer,
            TrainingArguments,
        )
        from datasets import Dataset
        from sklearn.metrics import f1_score, precision_score, recall_score
        import numpy as np
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install with: pip install transformers torch datasets scikit-learn")
        sys.exit(1)

    # ── Load data ─────────────────────────────────────────────
    texts, labels = load_dataset(data_path)

    if len(texts) < 10:
        logger.error("Need at least 10 training samples. Exiting.")
        sys.exit(1)

    # ── Create HuggingFace Dataset ────────────────────────────
    dataset = Dataset.from_dict({"text": texts, "label": labels})
    split = dataset.train_test_split(test_size=val_split, seed=42, stratify_by_column="label")
    train_ds = split["train"]
    val_ds = split["test"]

    logger.info(f"Train: {len(train_ds)}, Validation: {len(val_ds)}")

    # ── Tokenizer ─────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )

    train_ds = train_ds.map(tokenize, batched=True)
    val_ds = val_ds.map(tokenize, batched=True)

    train_ds.set_format("torch", columns=["input_ids", "attention_mask", "label"])
    val_ds.set_format("torch", columns=["input_ids", "attention_mask", "label"])

    # ── Model ─────────────────────────────────────────────────
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=3,
        id2label={0: "HIGH", 1: "MEDIUM", 2: "LOW"},
        label2id={"HIGH": 0, "MEDIUM": 1, "LOW": 2},
    )

    # ── Metrics ───────────────────────────────────────────────
    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        return {
            "f1_macro": f1_score(labels, preds, average="macro"),
            "precision_macro": precision_score(labels, preds, average="macro", zero_division=0),
            "recall_macro": recall_score(labels, preds, average="macro", zero_division=0),
            "accuracy": (preds == labels).mean(),
        }

    # ── Training Arguments ────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=10,
        save_total_limit=2,
        report_to="none",
        fp16=torch.cuda.is_available(),
    )

    # ── Train ─────────────────────────────────────────────────
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    logger.info(f"Starting training: {epochs} epochs, batch_size={batch_size}, lr={learning_rate}")
    trainer.train()

    # ── Save best model ───────────────────────────────────────
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    logger.info(f"✅ Model saved to {output_dir}")

    # ── Final evaluation ──────────────────────────────────────
    metrics = trainer.evaluate()
    logger.info("Final validation metrics:")
    for k, v in metrics.items():
        logger.info(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train BERT risk classifier")
    parser.add_argument("--data", required=True, help="Path to training data (JSONL)")
    parser.add_argument("--output", default="models/bert_risk_classifier", help="Output directory")
    parser.add_argument("--model", default="bert-base-uncased", help="Base model name")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--max-length", type=int, default=128, help="Max token length")

    args = parser.parse_args()

    train(
        data_path=args.data,
        output_dir=args.output,
        model_name=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_length=args.max_length,
    )


if __name__ == "__main__":
    main()
