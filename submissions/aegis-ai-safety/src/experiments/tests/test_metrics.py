"""Tests for evaluation utilities. Synthetic labels only, not benchmark results."""

from __future__ import annotations

import pytest

from experiments.metrics import (
    classification_metrics,
    false_positive_examples,
    latency_stats,
    retrieval_recall_at_k,
)


def test_macro_f1_perfect_predictions():
    labels = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
    metrics = classification_metrics(labels, labels)
    assert metrics["macro_f1"] == 1.0
    assert metrics["macro_precision"] == 1.0
    assert metrics["macro_recall"] == 1.0
    assert metrics["accuracy"] == 1.0
    assert metrics["false_positive_analysis"]["total"] == 0


def test_confusion_matrix_counts():
    gold = ["SUPPORTED", "SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
    predicted = ["SUPPORTED", "CONTRADICTED", "CONTRADICTED", "CONTRADICTED"]
    metrics = classification_metrics(gold, predicted)
    assert metrics["confusion_matrix"]["SUPPORTED"]["CONTRADICTED"] == 1
    assert metrics["confusion_matrix"]["INSUFFICIENT_EVIDENCE"]["CONTRADICTED"] == 1
    assert metrics["false_positive_analysis"]["contradicted_when_nei"] == 1
    assert metrics["per_class"]["CONTRADICTED"]["support"] == 1


def test_retrieval_recall_at_k():
    gold = {"a": [1, 2], "b": [5]}
    retrieved = {"a": [9, 1, 2], "b": [7, 8]}
    assert retrieval_recall_at_k(gold, retrieved, k=1)["recall"] == 0.0
    assert retrieval_recall_at_k(gold, retrieved, k=2)["recall"] == 0.5
    assert retrieval_recall_at_k(gold, retrieved, k=5)["recall"] == 0.5


def test_latency_stats_and_empty_input():
    stats = latency_stats([100, 200, 300, 400])
    assert stats["n"] == 4
    assert stats["median_ms"] == 250
    assert latency_stats([])["mean_ms"] is None


def test_false_positive_examples_only_nei_gold():
    examples = false_positive_examples(
        ["1", "2", "3"],
        ["INSUFFICIENT_EVIDENCE", "SUPPORTED", "INSUFFICIENT_EVIDENCE"],
        ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"],
    )
    assert examples == [{"claim_id": "1", "gold": "INSUFFICIENT_EVIDENCE", "predicted": "SUPPORTED"}]


def test_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        classification_metrics(["SUPPORTED"], ["SUPPORTED", "CONTRADICTED"])
