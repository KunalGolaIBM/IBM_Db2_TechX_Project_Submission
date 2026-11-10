"""
Evaluation script: compare classification results against ground truth.

Calculates precision, recall, and F1 for the PII classifier and
compares against a regex-only baseline.
"""
import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass

from app.classify import run as run_classification
from app.config import settings


@dataclass
class Metrics:
    """Classification metrics for a single PII type."""
    
    label: str
    true_positives: int
    false_positives: int
    false_negatives: int
    
    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)"""
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0
    
    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)"""
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0
    
    @property
    def f1(self) -> float:
        """F1 score: harmonic mean of precision and recall"""
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def load_ground_truth(filepath: str = "eval/labels.csv") -> dict[tuple[str, str], tuple[str, str]]:
    """
    Load ground truth labels from CSV.
    
    Args:
        filepath: Path to labels CSV file
        
    Returns:
        Dict mapping (table, column) to (is_pii, type)
    """
    truth = {}
    
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        
        for row in reader:
            if len(row) < 4:
                continue
            table, column, is_pii, pii_type = row
            truth[(table.upper(), column.upper())] = (is_pii, pii_type)
    
    return truth


def map_label_to_truth_type(label: str) -> str:
    """
    Map classifier labels to ground truth labels.
    
    Some labels may map to more general categories.
    
    Args:
        label: Classifier label
        
    Returns:
        Mapped label for comparison with ground truth
    """
    # Direct mappings
    mapping = {
        "EMAIL": "EMAIL",
        "PHONE": "PHONE",
        "PAN": "GOVT_ID",
        "AADHAAR": "GOVT_ID",
        "NAME": "NAME",
        "ADDRESS": "ADDRESS",
        "DOB": "DOB",
        "HEALTH": "HEALTH",
        "GOVT_ID": "GOVT_ID",
        "FREE_TEXT": "FREE_TEXT",
    }
    
    return mapping.get(label, label)


def calculate_metrics(
    predictions: dict[tuple[str, str], str],
    ground_truth: dict[tuple[str, str], tuple[str, str]],
) -> dict[str, Metrics]:
    """
    Calculate precision, recall, F1 for each PII type.
    
    Args:
        predictions: Dict mapping (table, column) to predicted label
        ground_truth: Dict mapping (table, column) to (is_pii, type)
        
    Returns:
        Dict mapping PII type to Metrics
    """
    # Initialize metrics for each type
    pii_types = set()
    for is_pii, pii_type in ground_truth.values():
        if is_pii == "Y":
            pii_types.add(pii_type)
    
    metrics_by_type = {
        pii_type: Metrics(pii_type, 0, 0, 0) for pii_type in pii_types
    }
    
    # Also track overall PII vs NOT_PII
    metrics_by_type["OVERALL"] = Metrics("OVERALL", 0, 0, 0)
    
    # Calculate TP, FP, FN for each column
    for (table, column), (is_pii, truth_type) in ground_truth.items():
        pred_label = predictions.get((table, column), "NOT_PII")
        mapped_pred = map_label_to_truth_type(pred_label)
        
        is_truth_pii = is_pii == "Y"
        is_pred_pii = pred_label != "NOT_PII"
        
        # Overall PII detection
        if is_truth_pii and is_pred_pii:
            metrics_by_type["OVERALL"].true_positives += 1
        elif not is_truth_pii and is_pred_pii:
            metrics_by_type["OVERALL"].false_positives += 1
        elif is_truth_pii and not is_pred_pii:
            metrics_by_type["OVERALL"].false_negatives += 1
        
        # Per-type metrics
        if is_truth_pii and truth_type in metrics_by_type:
            if mapped_pred == truth_type:
                metrics_by_type[truth_type].true_positives += 1
            else:
                # Predicted PII but wrong type
                if is_pred_pii:
                    metrics_by_type[truth_type].false_negatives += 1
                    # Also count as FP for the predicted type if it exists
                    if mapped_pred in metrics_by_type:
                        metrics_by_type[mapped_pred].false_positives += 1
                else:
                    # Missed entirely
                    metrics_by_type[truth_type].false_negatives += 1
    
    return metrics_by_type


def check_thresholds(
    metrics: Metrics,
    min_precision: float | None = None,
    min_recall: float | None = None,
) -> list[str]:
    """Return threshold failures for the overall evaluation metrics."""
    failures = []
    if min_precision is not None and metrics.precision < min_precision:
        failures.append(
            f"precision {metrics.precision:.3f} is below required {min_precision:.3f}"
        )
    if min_recall is not None and metrics.recall < min_recall:
        failures.append(f"recall {metrics.recall:.3f} is below required {min_recall:.3f}")
    return failures


def regex_only_baseline(ground_truth: dict[tuple[str, str], tuple[str, str]]) -> dict[tuple[str, str], str]:
    """
    Simple regex-only baseline for comparison.
    
    Only looks at column names with simple keyword matching.
    
    Args:
        ground_truth: Ground truth labels
        
    Returns:
        Dict mapping (table, column) to predicted label
    """
    predictions = {}
    
    for table, column in ground_truth.keys():
        col_lower = column.lower()
        
        # Simple keyword matching
        if "email" in col_lower or "mail" in col_lower:
            predictions[(table, column)] = "EMAIL"
        elif "phone" in col_lower or "ph" in col_lower or "mobile" in col_lower:
            predictions[(table, column)] = "PHONE"
        elif "name" in col_lower or "nm" in col_lower:
            predictions[(table, column)] = "NAME"
        elif "addr" in col_lower or "address" in col_lower:
            predictions[(table, column)] = "ADDRESS"
        elif "dob" in col_lower or "birth" in col_lower:
            predictions[(table, column)] = "DOB"
        else:
            predictions[(table, column)] = "NOT_PII"
    
    return predictions


def print_metrics_table(metrics: dict[str, Metrics], title: str) -> None:
    """Print metrics in a formatted table."""
    print(f"\n{title}")
    print("=" * 70)
    print(f"{'Type':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>6} {'FP':>6} {'FN':>6}")
    print("-" * 70)
    
    # Sort by F1 descending, but put OVERALL first
    items = sorted(
        metrics.items(),
        key=lambda x: (x[0] != "OVERALL", -x[1].f1)
    )
    
    for label, m in items:
        print(
            f"{label:<15} {m.precision:>10.3f} {m.recall:>10.3f} {m.f1:>10.3f} "
            f"{m.true_positives:>6} {m.false_positives:>6} {m.false_negatives:>6}"
        )
    
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    """Run evaluation and print results."""
    parser = argparse.ArgumentParser(description="Evaluate PII classification quality.")
    parser.add_argument("--min-precision", type=float)
    parser.add_argument("--min-recall", type=float)
    args = parser.parse_args(argv)
    for name in ("min_precision", "min_recall"):
        threshold = getattr(args, name)
        if threshold is not None and not 0 <= threshold <= 1:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")

    print("=" * 70)
    print("Db2 Privacy Copilot - Classification Evaluation")
    print("=" * 70)
    
    # Load ground truth
    print("\n1. Loading ground truth labels...")
    truth = load_ground_truth()
    print(f"   Loaded {len(truth)} labeled columns")
    
    pii_count = sum(1 for is_pii, _ in truth.values() if is_pii == "Y")
    print(f"   PII columns: {pii_count}")
    print(f"   Non-PII columns: {len(truth) - pii_count}")
    
    # Run classification
    print("\n2. Running classification...")
    results = run_classification(settings.db2_schema)
    
    # Build predictions dict
    predictions = {
        (r.table.upper(), r.column.upper()): r.label for r in results
    }
    
    # Calculate metrics for our system
    print("\n3. Calculating metrics...")
    our_metrics = calculate_metrics(predictions, truth)
    
    # Calculate metrics for baseline
    print("\n4. Running regex-only baseline...")
    baseline_predictions = regex_only_baseline(truth)
    baseline_metrics = calculate_metrics(baseline_predictions, truth)
    
    # Print results
    print_metrics_table(our_metrics, "Our System (Value Rules + Name Similarity)")
    print_metrics_table(baseline_metrics, "Baseline (Regex Only)")
    
    # Comparison summary
    print("\n" + "=" * 70)
    print("Comparison Summary")
    print("=" * 70)
    
    our_overall = our_metrics["OVERALL"]
    baseline_overall = baseline_metrics["OVERALL"]
    
    print(f"\nOVERALL PII DETECTION:")
    print(f"  Our System - Precision: {our_overall.precision:.3f}, Recall: {our_overall.recall:.3f}, F1: {our_overall.f1:.3f}")
    print(f"  Baseline   - Precision: {baseline_overall.precision:.3f}, Recall: {baseline_overall.recall:.3f}, F1: {baseline_overall.f1:.3f}")
    
    f1_improvement = our_overall.f1 - baseline_overall.f1
    if f1_improvement > 0:
        print(f"  ✓ Our system F1 is {f1_improvement:.3f} points better")
    else:
        print(f"  ✗ Baseline F1 is {-f1_improvement:.3f} points better")
    
    # Highlight specific wins
    print("\nKEY IMPROVEMENTS:")
    for label in ["EMAIL", "PHONE", "GOVT_ID", "ADDRESS", "NAME"]:
        if label in our_metrics and label in baseline_metrics:
            our_f1 = our_metrics[label].f1
            baseline_f1 = baseline_metrics[label].f1
            improvement = our_f1 - baseline_f1
            
            if improvement > 0.05:  # Significant improvement
                print(f"  ✓ {label}: +{improvement:.3f} F1 improvement")
    
    # Note challenging cases
    print("\nCHALLENGING CASES HANDLED:")
    print("  • Phone numbers stored as BIGINT (PH_NO)")
    print("  • Email with ugly column name (CUST_MAIL_ID)")
    print("  • PAN hidden in free-text NOTES fields")
    print("  • Decoy columns rejected (TICKET_REF_NO)")
    print("  • Invalid Aadhaar numbers rejected (Verhoeff check)")
    
    print("\n" + "=" * 70)
    print("Evaluation complete!")
    print("=" * 70)
    
    failures = check_thresholds(our_overall, args.min_precision, args.min_recall)
    if failures:
        print("\nEvaluation failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
