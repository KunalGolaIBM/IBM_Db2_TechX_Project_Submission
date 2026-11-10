"""Tests for evaluation quality gates."""

from eval.run_eval import Metrics, check_thresholds


def test_check_thresholds_passes_when_metrics_meet_requirements():
    metrics = Metrics("OVERALL", true_positives=19, false_positives=1, false_negatives=1)

    assert check_thresholds(metrics, min_precision=0.95, min_recall=0.95) == []


def test_check_thresholds_reports_each_failed_metric():
    metrics = Metrics("OVERALL", true_positives=8, false_positives=2, false_negatives=3)

    failures = check_thresholds(metrics, min_precision=0.9, min_recall=0.9)

    assert len(failures) == 2
    assert "precision" in failures[0]
    assert "recall" in failures[1]
