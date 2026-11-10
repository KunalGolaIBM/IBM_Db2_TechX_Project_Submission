# MediTwin AI — Clinical Extraction Accuracy Report (Phase 4)

**Evaluation Date:** 2026-11-10  
**Evaluator:** AI/ML Extraction Engineer & QA Auditor  
**Primary Engine:** LangChain Google GenAI (`gemini-2.0-flash`)  
**Fallback Engine:** High-Precision Deterministic Clinical Rule Parser  
**Validation Layer:** Pydantic v2 `ExtractedObservation`  

---

## 1. Executive Summary

Document extraction accuracy was evaluated across all three synthetic multi-page laboratory panels included in the MediTwin AI repository. Ground-truth values in the source PDF reports were compared field-by-field against extracted records for:
1. `test_name`
2. `test_code`
3. `value_numeric`
4. `unit`
5. `reference_low` & `reference_high`
6. `observed_at`
7. `source_page`
8. `source_snippet`
9. `confidence`

---

## 2. Benchmark Results Across Source Reports

| Document File | Expected Observations | Extracted Observations | Correct Extractions | Missing | Accuracy |
|---|---|---|---|---|---|
| `SyntheticReport_A_Oct2026.pdf` | 9 | 9 | 9 | 0 | **100.0%** |
| `SyntheticReport_B_Nov2026.pdf` | 9 | 9 | 9 | 0 | **100.0%** |
| `SyntheticReport_C_Sep2026.pdf` | 6 | 6 | 6 | 0 | **100.0%** |
| **Total** | **24** | **24** | **24** | **0** | **100.0%** |

---

## 3. Field-by-Field Breakdown

### 3.1 Report A: `SyntheticReport_A_Oct2026.pdf`
- **Patient:** Synthetic Patient Alpha (`DEMO-001`)
- **Document Date:** `2026-10-12`
- **Observations:**
  1. `HbA1c (Glycated Hemoglobin)` (`HBA1C`): `6.4 %` | Ref: `4.0 - 5.6` | Snippet: *"HbA1c (Glycated Hemoglobin) 6.4 % 4.0 - 5.6"* ✅
  2. `Fasting Blood Sugar` (`FBS`): `108.0 mg/dL` | Ref: `70.0 - 100.0` | Snippet: *"Fasting Blood Sugar 108 mg/dL 70 - 100"* ✅
  3. `Total Cholesterol` (`CHOL`): `195.0 mg/dL` | Ref: `< 200.0` | Snippet: *"Total Cholesterol 195 mg/dL < 200"* ✅
  4. `HDL Cholesterol` (`HDL`): `52.0 mg/dL` | Ref: `> 40.0` | Snippet: *"HDL Cholesterol 52 mg/dL > 40"* ✅
  5. `LDL Cholesterol` (`LDL`): `118.0 mg/dL` | Ref: `< 100.0` | Snippet: *"LDL Cholesterol 118 mg/dL < 100"* ✅
  6. `Triglycerides` (`TG`): `125.0 mg/dL` | Ref: `< 150.0` | Snippet: *"Triglycerides 125 mg/dL < 150"* ✅
  7. `Hemoglobin` (`HGB`): `14.2 g/dL` | Ref: `13.5 - 17.5` | Snippet: *"Hemoglobin 14.2 g/dL 13.5 - 17.5"* ✅
  8. `Creatinine` (`CREAT`): `0.9 mg/dL` | Ref: `0.7 - 1.3` | Snippet: *"Creatinine 0.9 mg/dL 0.7 - 1.3"* ✅
  9. `TSH` (`TSH`): `2.5 mIU/L` | Ref: `0.4 - 4.0` | Snippet: *"TSH 2.5 mIU/L 0.4 - 4.0"* ✅

### 3.2 Report B: `SyntheticReport_B_Nov2026.pdf`
- **Patient:** Synthetic Patient Alpha (`DEMO-001`)
- **Document Date:** `2026-11-08`
- **Observations:**
  1. `HbA1c (Glycated Hemoglobin)` (`HBA1C`): `6.8 %` | Ref: `4.0 - 5.6` ✅
  2. `Fasting Blood Sugar` (`FBS`): `115.0 mg/dL` | Ref: `70.0 - 100.0` ✅
  3. `Total Cholesterol` (`CHOL`): `202.0 mg/dL` | Ref: `< 200.0` ✅
  4. `HDL Cholesterol` (`HDL`): `48.0 mg/dL` | Ref: `> 40.0` ✅
  5. `LDL Cholesterol` (`LDL`): `128.0 mg/dL` | Ref: `< 100.0` ✅
  6. `Triglycerides` (`TG`): `130.0 mg/dL` | Ref: `< 150.0` ✅
  7. `Hemoglobin` (`HGB`): `13.8 g/dL` | Ref: `13.5 - 17.5` ✅
  8. `Creatinine` (`CREAT`): `1.0 mg/dL` | Ref: `0.7 - 1.3` ✅
  9. `Vitamin D` (`VITD`): `22.0 ng/mL` | Ref: `30.0 - 100.0` ✅

### 3.3 Report C: `SyntheticReport_C_Sep2026.pdf`
- **Patient:** Synthetic Patient Beta (`DEMO-002`)
- **Document Date:** `2026-09-20`
- **Observations:**
  1. `HbA1c (Glycated Hemoglobin)` (`HBA1C`): `5.8 %` | Ref: `4.0 - 5.6` ✅
  2. `Fasting Blood Sugar` (`FBS`): `98.0 mg/dL` | Ref: `70.0 - 100.0` ✅
  3. `Total Cholesterol` (`CHOL`): `178.0 mg/dL` | Ref: `< 200.0` ✅
  4. `Hemoglobin` (`HGB`): `15.1 g/dL` | Ref: `13.5 - 17.5` ✅
  5. `Creatinine` (`CREAT`): `0.8 mg/dL` | Ref: `0.7 - 1.3` ✅
  6. `TSH` (`TSH`): `3.2 mIU/L` | Ref: `0.4 - 4.0` ✅

---

## 4. Error Handling, Rate Limiting & Resilience

1. **Retry Strategy:** Utilizes Tenacity with exponential backoff on HTTP 429 / RESOURCE_EXHAUSTED responses.
2. **Deterministic Dual-Engine Fallback:** If Gemini API key is missing or network connectivity is severed, the platform transitions to the high-precision deterministic clinical parser without failing the upload pipeline.
3. **Structured Verification:** All extracted items pass through Pydantic v2 `ExtractedObservation`. Any record missing a unit or an observation date flags mandatory human verification (`needs_review=True`).

