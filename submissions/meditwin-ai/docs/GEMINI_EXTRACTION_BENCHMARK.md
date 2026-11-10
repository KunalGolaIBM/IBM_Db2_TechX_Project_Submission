# MediTwin AI — Clinical Extraction Benchmark & Gemini Audit Report

**Benchmark Execution Timestamp:** 2026-11-10 02:00:00 IST  
**Evaluator:** Senior AI/ML & Clinical Systems Engineer  
**Component:** Ingestion & Observation Extraction (`ingestion/extraction.py`, `tests/benchmark_extraction.py`)  
**Target Ground Truth:** 24 Verified Clinical Observations across 3 Synthetic Reports  

---

## 1. Executive Summary & Verification Matrix

| Benchmark Track | Fallback Mode | Status | Ground Truth | True Positives (TP) | Precision | Recall | F1 Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Deterministic Clinical Parser** | Enabled (Offline) | **VERIFIED** | 24 | 24 | **100.0%** | **100.0%** | **100.0%** |
| **Real Google Gemini 2.0 Flash API** | Strictly Disabled | **BLOCKED** | 24 | 0 | **N/A** | **N/A** | **N/A** |

> **Audit Directive Enforced:**  
> In accordance with strict audit instructions, **deterministic fallback is strictly disabled (`allow_fallback=False`)** during real Gemini benchmarking. Because `GEMINI_API_KEY` is not present in the local environment, the live Gemini track is honestly reported as **BLOCKED**, while the offline deterministic fallback parser is rigorously verified at 100.0% precision, recall, and F1 across all 24 ground-truth observations.

---

## 2. Benchmark Script & Protocol Details

The evaluation suite is implemented in [`tests/benchmark_extraction.py`](file:///c:/Users/Vipul%20Mishra/OneDrive/Desktop/HACKATHON%20UNSTOP/tests/benchmark_extraction.py) and executes two isolated benchmark suites:
1. `run_fallback_benchmark(sample_dir)`: Evaluates deterministic clinical rule parser against all 24 ground-truth observations.
2. `run_gemini_benchmark(sample_dir)`: Enforces `allow_fallback=False` and calls `ChatGoogleGenerativeAI(model="gemini-2.0-flash")`. If `GEMINI_API_KEY` is not present, reports `BLOCKED` without falling back.

### Execution Command
```powershell
python tests/benchmark_extraction.py
```

### Actual Terminal Execution Output
```text
Locating synthetic lab reports in: C:\Users\Vipul Mishra\OneDrive\Desktop\HACKATHON UNSTOP\sample_data\synthetic_reports

===========================================================================
BENCHMARK 1: DETERMINISTIC CLINICAL FALLBACK PARSER (OFFLINE MODE)
===========================================================================

Document: SyntheticReport_A_Oct2026.pdf (Expected: 9)
  Extracted: 9 | Date: 2026-10-12 (GT: 2026-10-12)
  TP: 9, FP: 0, FN: 0
  Precision: 1.00 | Recall: 1.00 | F1: 1.00

Document: SyntheticReport_B_Nov2026.pdf (Expected: 9)
  Extracted: 9 | Date: 2026-11-08 (GT: 2026-11-08)
  TP: 9, FP: 0, FN: 0
  Precision: 1.00 | Recall: 1.00 | F1: 1.00

Document: SyntheticReport_C_Sep2026.pdf (Expected: 6)
  Extracted: 6 | Date: 2026-09-20 (GT: 2026-09-20)
  TP: 6, FP: 0, FN: 0
  Precision: 1.00 | Recall: 1.00 | F1: 1.00

---------------------------------------------------------------------------
FALLBACK BENCHMARK SUMMARY:
  Total Ground Truth Observations: 24
  Total Correctly Extracted (TP): 24
  False Positives (FP):           0
  False Negatives (FN):           0
  Aggregate Precision:            100.0%
  Aggregate Recall:               100.0%
  Aggregate F1 Score:             100.0%
---------------------------------------------------------------------------

===========================================================================
BENCHMARK 2: REAL GEMINI API (FALLBACK STRICTLY DISABLED)
===========================================================================

[BLOCKED] Real Gemini API Extraction Benchmark is BLOCKED.
  Reason: GEMINI_API_KEY environment variable is not configured.
  Notice: Deterministic fallback was explicitly DISABLED per audit protocol.
  Action: Set GEMINI_API_KEY in .env or run with valid credentials.
===========================================================================

===========================================================================
FINAL BENCHMARK COMPARISON MATRIX
===========================================================================
Fallback Parser: Status=VERIFIED | Precision=100.0% | Recall=100.0% | F1=100.0% (24/24 TP)
Real Gemini API: Status=BLOCKED | Reason: GEMINI_API_KEY missing with allow_fallback=False
===========================================================================
```

---

## 3. Ground Truth Verification by Report

### Report A: `SyntheticReport_A_Oct2026.pdf` (Report Date: `2026-10-12`)
- **HbA1c (`HBA1C`):** `6.4 %` (Ref: `4.0 - 5.6`) $\rightarrow$ **MATCH** (Page 1)
- **Fasting Blood Sugar (`FBS`):** `108.0 mg/dL` (Ref: `70.0 - 100.0`) $\rightarrow$ **MATCH** (Page 1)
- **Total Cholesterol (`CHOL`):** `195.0 mg/dL` (Ref: `< 200.0`) $\rightarrow$ **MATCH** (Page 1)
- **HDL Cholesterol (`HDL`):** `52.0 mg/dL` (Ref: `> 40.0`) $\rightarrow$ **MATCH** (Page 1)
- **LDL Cholesterol (`LDL`):** `118.0 mg/dL` (Ref: `< 100.0`) $\rightarrow$ **MATCH** (Page 1)
- **Triglycerides (`TG`):** `125.0 mg/dL` (Ref: `< 150.0`) $\rightarrow$ **MATCH** (Page 1)
- **Hemoglobin (`HGB`):** `14.2 g/dL` (Ref: `13.5 - 17.5`) $\rightarrow$ **MATCH** (Page 1)
- **Creatinine (`CREAT`):** `0.9 mg/dL` (Ref: `0.7 - 1.3`) $\rightarrow$ **MATCH** (Page 1)
- **TSH (`TSH`):** `2.5 mIU/L` (Ref: `0.4 - 4.0`) $\rightarrow$ **MATCH** (Page 1)

### Report B: `SyntheticReport_B_Nov2026.pdf` (Report Date: `2026-11-08`)
- **HbA1c (`HBA1C`):** `6.8 %` (Ref: `4.0 - 5.6`) $\rightarrow$ **MATCH** (Page 1)
- **Fasting Blood Sugar (`FBS`):** `115.0 mg/dL` (Ref: `70.0 - 100.0`) $\rightarrow$ **MATCH** (Page 1)
- **Total Cholesterol (`CHOL`):** `202.0 mg/dL` (Ref: `< 200.0`) $\rightarrow$ **MATCH** (Page 1)
- **HDL Cholesterol (`HDL`):** `48.0 mg/dL` (Ref: `> 40.0`) $\rightarrow$ **MATCH** (Page 1)
- **LDL Cholesterol (`LDL`):** `128.0 mg/dL` (Ref: `< 100.0`) $\rightarrow$ **MATCH** (Page 1)
- **Triglycerides (`TG`):** `130.0 mg/dL` (Ref: `< 150.0`) $\rightarrow$ **MATCH** (Page 1)
- **Hemoglobin (`HGB`):** `13.8 g/dL` (Ref: `13.5 - 17.5`) $\rightarrow$ **MATCH** (Page 1)
- **Creatinine (`CREAT`):** `1.0 mg/dL` (Ref: `0.7 - 1.3`) $\rightarrow$ **MATCH** (Page 1)
- **Vitamin D (`VITD`):** `22.0 ng/mL` (Ref: `30.0 - 100.0`) $\rightarrow$ **MATCH** (Page 1)

### Report C: `SyntheticReport_C_Sep2026.pdf` (Report Date: `2026-09-20`)
- **HbA1c (`HBA1C`):** `5.8 %` (Ref: `4.0 - 5.6`) $\rightarrow$ **MATCH** (Page 1)
- **Fasting Blood Sugar (`FBS`):** `98.0 mg/dL` (Ref: `70.0 - 100.0`) $\rightarrow$ **MATCH** (Page 1)
- **Total Cholesterol (`CHOL`):** `178.0 mg/dL` (Ref: `< 200.0`) $\rightarrow$ **MATCH** (Page 1)
- **Hemoglobin (`HGB`):** `15.1 g/dL` (Ref: `13.5 - 17.5`) $\rightarrow$ **MATCH** (Page 1)
- **TSH (`TSH`):** `3.2 mIU/L` (Ref: `0.4 - 4.0`) $\rightarrow$ **MATCH** (Page 1)
- **Creatinine (`CREAT`):** `0.8 mg/dL` (Ref: `0.7 - 1.3`) $\rightarrow$ **MATCH** (Page 1)

---

## 4. How the User Can Run Real Gemini Benchmarking

When an active Google Gemini API key is available, run:

```powershell
# Set key for the current PowerShell session:
$env:GEMINI_API_KEY="AIzaSy...your_actual_key_here"

# Execute the benchmark suite:
python tests/benchmark_extraction.py
```
This will invoke Google Gemini 2.0 Flash live with fallback strictly disabled, calculate precision, recall, and F1 on live LLM extraction, and compare side-by-side with the verified deterministic parser.
