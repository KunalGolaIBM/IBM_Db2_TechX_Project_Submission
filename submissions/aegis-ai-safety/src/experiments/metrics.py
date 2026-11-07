"""Evaluation metrics for AEGIS claim verification.

No benchmark values are embedded here. Every metric is computed from predictions
supplied at runtime.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean, median

LABELS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def classification_metrics(
    gold: list[str],
    predicted: list[str],
    labels: tuple[str, ...] = LABELS,
) -> dict:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted label lists must have equal length")
    if not gold:
        raise ValueError("at least one labelled example is required")

    confusion = {true: {pred: 0 for pred in labels} for true in labels}
    invalid = 0
    for true_label, predicted_label in zip(gold, predicted):
        if true_label not in confusion or predicted_label not in labels:
            invalid += 1
            continue
        confusion[true_label][predicted_label] += 1

    per_class = {}
    f1_scores = []
    precision_scores = []
    recall_scores = []
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in labels if other != label)
        false_negative = sum(confusion[label][other] for other in labels if other != label)
        precision = _safe_divide(true_positive, true_positive + false_positive)
        recall = _safe_divide(true_positive, true_positive + false_negative)
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        support = sum(confusion[label].values())
        per_class[label] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": support,
        }
        f1_scores.append(f1)
        precision_scores.append(precision)
        recall_scores.append(recall)

    total = sum(sum(row.values()) for row in confusion.values())
    correct = sum(confusion[label][label] for label in labels)
    false_positives = {
        "total": sum(
            confusion["INSUFFICIENT_EVIDENCE"][label] for label in labels if label != "INSUFFICIENT_EVIDENCE"
        ),
        "supported_when_nei": confusion["INSUFFICIENT_EVIDENCE"]["SUPPORTED"],
        "contradicted_when_nei": confusion["INSUFFICIENT_EVIDENCE"]["CONTRADICTED"],
    }
    return {
        "n": total,
        "invalid_records": invalid,
        "accuracy": round(_safe_divide(correct, total), 6),
        "macro_precision": round(mean(precision_scores), 6),
        "macro_recall": round(mean(recall_scores), 6),
        "macro_f1": round(mean(f1_scores), 6),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "false_positive_analysis": false_positives,
    }


def retrieval_recall_at_k(
    gold_doc_ids: dict[str, list[int] | tuple[int, ...]],
    retrieved_doc_ids: dict[str, list[int] | tuple[int, ...]],
    k: int = 10,
) -> dict:
    if k <= 0:
        raise ValueError("k must be positive")
    common = sorted(set(gold_doc_ids) & set(retrieved_doc_ids))
    if not common:
        raise ValueError("no overlapping claim ids between gold and retrieval predictions")
    hits = 0
    for claim_id in common:
        gold = set(int(value) for value in gold_doc_ids[claim_id])
        if not gold:
            continue
        retrieved = [int(value) for value in retrieved_doc_ids[claim_id][:k]]
        if gold & set(retrieved):
            hits += 1
    return {
        "k": k,
        "n": len(common),
        "recall": round(_safe_divide(hits, len(common)), 6),
        "hits": hits,
    }


def latency_stats(latencies_ms: list[float]) -> dict:
    if not latencies_ms:
        return {"n": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
    ordered = sorted(float(value) for value in latencies_ms)
    index = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
    return {
        "n": len(ordered),
        "mean_ms": round(mean(ordered), 3),
        "median_ms": round(median(ordered), 3),
        "p95_ms": round(ordered[index], 3),
    }


def false_positive_examples(
    claim_ids: list[str],
    gold: list[str],
    predicted: list[str],
    limit: int = 50,
) -> list[dict]:
    if not (len(claim_ids) == len(gold) == len(predicted)):
        raise ValueError("claim_ids, gold, and predicted must have equal length")
    examples = []
    for claim_id, true_label, predicted_label in zip(claim_ids, gold, predicted):
        if true_label == "INSUFFICIENT_EVIDENCE" and predicted_label in (
            "SUPPORTED",
            "CONTRADICTED",
        ):
            examples.append(
                {
                    "claim_id": claim_id,
                    "gold": true_label,
                    "predicted": predicted_label,
                }
            )
        if len(examples) >= limit:
            break
    return examples


def label_distribution(labels: list[str]) -> dict[str, int]:
    counts = Counter(labels)
    return {label: counts.get(label, 0) for label in LABELS}
