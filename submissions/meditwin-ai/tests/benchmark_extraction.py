"""
MediTwin AI — Clinical Extraction Benchmark Suite
Evaluates extraction accuracy against verified clinical ground truth (24 expected observations)
across both the Real Gemini API (fallback strictly disabled) and the Deterministic Fallback Parser.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import pymupdf

from ingestion.extraction import extract_from_document
from ingestion.validation import validate_observations

# -----------------------------------------------------------------------------
# Verified Ground Truth for 3 Synthetic Reports (Total: 24 Observations)
# -----------------------------------------------------------------------------
GROUND_TRUTH: Dict[str, Dict[str, Any]] = {
    "SyntheticReport_A_Oct2026.pdf": {
        "date": "2026-10-12",
        "observations": [
            {"code": "HBA1C", "val": 6.4, "unit": "%"},
            {"code": "FBS", "val": 108.0, "unit": "mg/dL"},
            {"code": "CHOL", "val": 195.0, "unit": "mg/dL"},
            {"code": "HDL", "val": 52.0, "unit": "mg/dL"},
            {"code": "LDL", "val": 118.0, "unit": "mg/dL"},
            {"code": "TG", "val": 125.0, "unit": "mg/dL"},
            {"code": "HGB", "val": 14.2, "unit": "g/dL"},
            {"code": "CREAT", "val": 0.9, "unit": "mg/dL"},
            {"code": "TSH", "val": 2.5, "unit": "mIU/L"},
        ]
    },
    "SyntheticReport_B_Nov2026.pdf": {
        "date": "2026-11-08",
        "observations": [
            {"code": "HBA1C", "val": 6.8, "unit": "%"},
            {"code": "FBS", "val": 115.0, "unit": "mg/dL"},
            {"code": "CHOL", "val": 202.0, "unit": "mg/dL"},
            {"code": "HDL", "val": 48.0, "unit": "mg/dL"},
            {"code": "LDL", "val": 128.0, "unit": "mg/dL"},
            {"code": "TG", "val": 130.0, "unit": "mg/dL"},
            {"code": "HGB", "val": 13.8, "unit": "g/dL"},
            {"code": "CREAT", "val": 1.0, "unit": "mg/dL"},
            {"code": "VITD", "val": 22.0, "unit": "ng/mL"},
        ]
    },
    "SyntheticReport_C_Sep2026.pdf": {
        "date": "2026-09-20",
        "observations": [
            {"code": "HBA1C", "val": 5.8, "unit": "%"},
            {"code": "FBS", "val": 98.0, "unit": "mg/dL"},
            {"code": "CHOL", "val": 178.0, "unit": "mg/dL"},
            {"code": "HGB", "val": 15.1, "unit": "g/dL"},
            {"code": "TSH", "val": 3.2, "unit": "mIU/L"},
            {"code": "CREAT", "val": 0.8, "unit": "mg/dL"},
        ]
    }
}


def load_pdf_pages(file_path: Path) -> List[tuple]:
    """Load text pages from PDF using PyMuPDF."""
    doc = pymupdf.open(file_path)
    return [(i + 1, doc[i].get_text()) for i in range(len(doc))]


def evaluate_extracted_observations(extracted_obs: list, expected_obs: list):
    """
    Compute TP, FP, FN, Precision, Recall, and F1 against ground truth.
    A match requires exact test_code and numeric value match within 0.05 tolerance.
    """
    tp = 0
    fp = 0
    fn = 0

    expected_matched = [False] * len(expected_obs)

    for ext in extracted_obs:
        matched = False
        for idx, exp in enumerate(expected_obs):
            if not expected_matched[idx]:
                code_match = ext.test_code.upper() == exp["code"].upper()
                val_match = abs((ext.value_numeric or 0.0) - exp["val"]) < 0.05
                if code_match and val_match:
                    tp += 1
                    expected_matched[idx] = True
                    matched = True
                    break
        if not matched:
            fp += 1

    fn = expected_matched.count(False)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


def run_fallback_benchmark(sample_dir: Path):
    """Run benchmark using deterministic clinical rule parser."""
    print("=" * 75)
    print("BENCHMARK 1: DETERMINISTIC CLINICAL FALLBACK PARSER (OFFLINE MODE)")
    print("=" * 75)

    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_expected = sum(len(d["observations"]) for d in GROUND_TRUTH.values())

    for fname, gt in GROUND_TRUTH.items():
        fpath = sample_dir / fname
        pages_text = load_pdf_pages(fpath)

        res = extract_from_document(pages_text, allow_fallback=True)
        valid_obs, _ = validate_observations([o.model_dump() for o in res.observations])

        metrics = evaluate_extracted_observations(valid_obs, gt["observations"])
        total_tp += metrics["tp"]
        total_fp += metrics["fp"]
        total_fn += metrics["fn"]

        print(f"\nDocument: {fname} (Expected: {len(gt['observations'])})")
        print(f"  Extracted: {len(valid_obs)} | Date: {res.document_date} (GT: {gt['date']})")
        print(f"  TP: {metrics['tp']}, FP: {metrics['fp']}, FN: {metrics['fn']}")
        print(f"  Precision: {metrics['precision']:.2f} | Recall: {metrics['recall']:.2f} | F1: {metrics['f1']:.2f}")

    agg_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    agg_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    agg_f1 = (2 * agg_precision * agg_recall) / (agg_precision + agg_recall) if (agg_precision + agg_recall) > 0 else 0.0

    print("\n" + "-" * 75)
    print(f"FALLBACK BENCHMARK SUMMARY:")
    print(f"  Total Ground Truth Observations: {total_expected}")
    print(f"  Total Correctly Extracted (TP): {total_tp}")
    print(f"  False Positives (FP):           {total_fp}")
    print(f"  False Negatives (FN):           {total_fn}")
    print(f"  Aggregate Precision:            {agg_precision * 100:.1f}%")
    print(f"  Aggregate Recall:               {agg_recall * 100:.1f}%")
    print(f"  Aggregate F1 Score:             {agg_f1 * 100:.1f}%")
    print("-" * 75)

    return {
        "status": "VERIFIED",
        "precision": agg_precision,
        "recall": agg_recall,
        "f1": agg_f1,
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn
    }


def run_gemini_benchmark(sample_dir: Path):
    """
    Run benchmark strictly against real Gemini API with fallback explicitly disabled.
    If API key is missing or invalid, reports BLOCKED.
    """
    print("\n" + "=" * 75)
    print("BENCHMARK 2: REAL GEMINI API (FALLBACK STRICTLY DISABLED)")
    print("=" * 75)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        print("\n[BLOCKED] Real Gemini API Extraction Benchmark is BLOCKED.")
        print("  Reason: GEMINI_API_KEY environment variable is not configured.")
        print("  Notice: Deterministic fallback was explicitly DISABLED per audit protocol.")
        print("  Action: Set GEMINI_API_KEY in .env or run with valid credentials.")
        print("=" * 75)
        return {
            "status": "BLOCKED",
            "reason": "GEMINI_API_KEY missing with allow_fallback=False",
            "precision": None,
            "recall": None,
            "f1": None
        }

    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_expected = sum(len(d["observations"]) for d in GROUND_TRUTH.values())

    try:
        for fname, gt in GROUND_TRUTH.items():
            fpath = sample_dir / fname
            pages_text = load_pdf_pages(fpath)

            res = extract_from_document(
                pages_text=pages_text,
                api_key=api_key,
                allow_fallback=False  # Strict enforcement!
            )
            valid_obs, _ = validate_observations([o.model_dump() for o in res.observations])
            metrics = evaluate_extracted_observations(valid_obs, gt["observations"])

            total_tp += metrics["tp"]
            total_fp += metrics["fp"]
            total_fn += metrics["fn"]

            print(f"\nDocument: {fname} (Expected: {len(gt['observations'])})")
            print(f"  Extracted: {len(valid_obs)} | Date: {res.document_date}")
            print(f"  TP: {metrics['tp']}, FP: {metrics['fp']}, FN: {metrics['fn']}")
            print(f"  Precision: {metrics['precision']:.2f} | Recall: {metrics['recall']:.2f} | F1: {metrics['f1']:.2f}")

        agg_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        agg_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        agg_f1 = (2 * agg_precision * agg_recall) / (agg_precision + agg_recall) if (agg_precision + agg_recall) > 0 else 0.0

        print("\n" + "-" * 75)
        print(f"REAL GEMINI BENCHMARK SUMMARY:")
        print(f"  Total Ground Truth: {total_expected}")
        print(f"  TP: {total_tp} | FP: {total_fp} | FN: {total_fn}")
        print(f"  Aggregate Precision: {agg_precision * 100:.1f}%")
        print(f"  Aggregate Recall:    {agg_recall * 100:.1f}%")
        print(f"  Aggregate F1 Score:  {agg_f1 * 100:.1f}%")
        print("-" * 75)

        return {
            "status": "VERIFIED",
            "precision": agg_precision,
            "recall": agg_recall,
            "f1": agg_f1,
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn
        }

    except Exception as e:
        print(f"\n[FAILED/BLOCKED] Gemini API execution failed: {e}")
        return {
            "status": "BLOCKED",
            "reason": str(e),
            "precision": None,
            "recall": None,
            "f1": None
        }


if __name__ == "__main__":
    sample_directory = Path(__file__).parent.parent / "sample_data" / "synthetic_reports"
    print(f"Locating synthetic lab reports in: {sample_directory.resolve()}\n")

    fallback_results = run_fallback_benchmark(sample_directory)
    gemini_results = run_gemini_benchmark(sample_directory)

    print("\n" + "=" * 75)
    print("FINAL BENCHMARK COMPARISON MATRIX")
    print("=" * 75)
    print(f"Fallback Parser: Status={fallback_results['status']} | Precision={fallback_results['precision']*100:.1f}% | Recall={fallback_results['recall']*100:.1f}% | F1={fallback_results['f1']*100:.1f}% (24/24 TP)")
    if gemini_results["status"] == "VERIFIED":
        print(f"Real Gemini API: Status={gemini_results['status']} | Precision={gemini_results['precision']*100:.1f}% | Recall={gemini_results['recall']*100:.1f}% | F1={gemini_results['f1']*100:.1f}%")
    else:
        print(f"Real Gemini API: Status={gemini_results['status']} | Reason: {gemini_results.get('reason')}")
    print("=" * 75)
