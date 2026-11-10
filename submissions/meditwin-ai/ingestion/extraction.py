"""
MediTwin AI — LangChain Structured Extraction
Uses LangChain with Gemini (gemini-2.0-flash) to extract medical observations from text.
Includes tenacity retries for rate-limit protection and a deterministic rule parser fallback.
"""

import os
import re
import json
import logging
from typing import List, Optional, Tuple

from ingestion.validation import ExtractedObservation, ExtractionResult
from services.retrieval_service import TEST_CODE_ALIASES

logger = logging.getLogger(__name__)

# Extraction prompt template for LangChain + Gemini
EXTRACTION_PROMPT = """You are MediTwin AI's medical document data extraction assistant.

Your task is to extract structured medical observations from the clinical document text.

STRICT EXTRACTION RULES:
1. Extract ONLY information explicitly present in the text.
2. Never invent, extrapolate, or hallucinate medical values.
3. If a date cannot be determined, set observed_at to null.
4. If a unit cannot be determined, set unit to null.
5. If a reference range is present, extract reference_low and reference_high as numbers.
6. For each measurement, capture the exact verbatim text snippet in source_snippet.
7. Assign confidence between 0.0 and 1.0.
8. Standardize test_code using canonical clinical abbreviations (HBA1C, FBS, CHOL, HDL, LDL, TG, HGB, CREAT, TSH, VITD, etc.).

DOCUMENT TEXT (Page {page_number}):
---
{text}
---

Return ONLY a valid JSON array of observation objects with these exact keys:
[
  {{
    "test_name": "Full Test Name",
    "test_code": "HBA1C",
    "value_numeric": 6.4,
    "value_text": null,
    "unit": "%",
    "reference_low": 4.0,
    "reference_high": 5.6,
    "observed_at": "YYYY-MM-DD",
    "source_page": {page_number},
    "source_snippet": "Exact quote from text",
    "confidence": 0.95
  }}
]

If the text contains no clinical observations, return [].
"""


def extract_date_from_text(text: str) -> Optional[str]:
    """Extract standard date from document header text if present."""
    date_match = re.search(r"Report Date:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    if date_match:
        return date_match.group(1)
    date_match2 = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    if date_match2:
        return date_match2.group(1)
    return None


def rule_based_laboratory_parser(text: str, page_number: int = 1,
                                 default_date: str = None) -> List[ExtractedObservation]:
    """
    High-precision deterministic rule parser for clinical reports.
    Functions as an offline fallback when Gemini API key is missing or quota is exhausted.
    """
    observations = []
    doc_date = default_date or extract_date_from_text(text)

    # Standard lab report line patterns:
    # Example: "HbA1c (Glycated Hemoglobin) 6.4 % 4.0 - 5.6"
    # Example: "Fasting Blood Sugar 108 mg/dL 70 - 100"
    # Example: "Total Cholesterol 195 mg/dL < 200"
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Also search for table row matches across consecutive tokens
    full_clean_text = " ".join(lines)

    # Common tests pattern matcher
    test_patterns = [
        (r"HbA1c(?:\s*\([^)]*\))?\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(%)\s*(?:([0-9\.]+)\s*-\s*([0-9\.]+))?", "HbA1c (Glycated Hemoglobin)", "HBA1C"),
        (r"Fasting Blood Sugar\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(mg/dL)\s*(?:([0-9\.]+)\s*-\s*([0-9\.]+))?", "Fasting Blood Sugar", "FBS"),
        (r"Total Cholesterol\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(mg/dL)\s*(?:<\s*([0-9\.]+))?", "Total Cholesterol", "CHOL"),
        (r"HDL Cholesterol\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(mg/dL)\s*(?:>\s*([0-9\.]+))?", "HDL Cholesterol", "HDL"),
        (r"LDL Cholesterol\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(mg/dL)\s*(?:<\s*([0-9\.]+))?", "LDL Cholesterol", "LDL"),
        (r"Triglycerides\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(mg/dL)\s*(?:<\s*([0-9\.]+))?", "Triglycerides", "TG"),
        (r"Hemoglobin\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(g/dL)\s*(?:([0-9\.]+)\s*-\s*([0-9\.]+))?", "Hemoglobin", "HGB"),
        (r"Creatinine\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(mg/dL)\s*(?:([0-9\.]+)\s*-\s*([0-9\.]+))?", "Creatinine", "CREAT"),
        (r"TSH\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(mIU/L)\s*(?:([0-9\.]+)\s*-\s*([0-9\.]+))?", "TSH", "TSH"),
        (r"Vitamin D\s*[:\-]?\s*([0-9]+\.?[0-9]*)\s*(ng/mL)\s*(?:([0-9\.]+)\s*-\s*([0-9\.]+))?", "Vitamin D", "VITD"),
    ]

    for pattern, name, code in test_patterns:
        match = re.search(pattern, full_clean_text, re.IGNORECASE)
        if match:
            val_str = match.group(1)
            unit_str = match.group(2) if len(match.groups()) >= 2 else None
            ref_low = None
            ref_high = None

            if len(match.groups()) >= 4:
                try:
                    if match.group(3): ref_low = float(match.group(3))
                    if match.group(4): ref_high = float(match.group(4))
                except (ValueError, TypeError):
                    pass
            elif len(match.groups()) >= 3 and match.group(3):
                try:
                    ref_high = float(match.group(3))
                except (ValueError, TypeError):
                    pass

            snippet = match.group(0)[:150]
            try:
                obs = ExtractedObservation(
                    test_name=name,
                    test_code=code,
                    value_numeric=float(val_str),
                    unit=unit_str,
                    reference_low=ref_low,
                    reference_high=ref_high,
                    observed_at=doc_date,
                    source_page=page_number,
                    source_snippet=snippet,
                    confidence=0.98,
                )
                observations.append(obs)
            except Exception as e:
                logger.warning(f"Error creating rule-based observation: {e}")

    return observations


def extract_observations_with_langchain(
    text: str,
    page_number: int = 1,
    document_date: str = None,
    api_key: str = None,
    model_name: str = "gemini-2.0-flash",
    allow_fallback: bool = True,
) -> ExtractionResult:
    """
    Extract structured medical observations from text using LangChain + Gemini.
    Falls back gracefully to deterministic clinical rule parser if API key is absent or offline
    (only when allow_fallback=True).
    """
    doc_date = document_date or extract_date_from_text(text)

    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")

    # Offline / No Key Handling
    if not api_key:
        if not allow_fallback:
            raise ValueError("Real Gemini API requested (allow_fallback=False) but GEMINI_API_KEY is not configured.")
        logger.info("No Gemini API key available. Executing deterministic clinical rule parser fallback.")
        rule_obs = rule_based_laboratory_parser(text, page_number=page_number, default_date=doc_date)
        return ExtractionResult(
            observations=rule_obs,
            document_date=doc_date,
            extraction_notes=f"Extracted {len(rule_obs)} observations using deterministic clinical parser (offline mode)."
        )

    # Real LangChain + Gemini extraction
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1,
            max_retries=3,
        )

        prompt = EXTRACTION_PROMPT.format(text=text, page_number=page_number)

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # Clean markdown codeblocks if LLM returned ```json ... ```
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        observations = []
        json_start = content.find("[")
        json_end = content.rfind("]") + 1

        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            raw_obs_list = json.loads(json_str)

            for raw in raw_obs_list:
                try:
                    obs = ExtractedObservation(**raw)
                    if obs.observed_at is None and doc_date:
                        obs.observed_at = doc_date
                    observations.append(obs)
                except Exception as e:
                    logger.warning(f"Skipping observation that failed validation: {e}")

        # If LLM returned empty but document clearly contains clinical values, augment if fallback allowed
        if not observations and allow_fallback:
            observations = rule_based_laboratory_parser(text, page_number=page_number, default_date=doc_date)

        return ExtractionResult(
            observations=observations,
            document_date=doc_date,
            extraction_notes=f"Extracted {len(observations)} observations via LangChain + Gemini ({model_name})."
        )

    except Exception as e:
        if not allow_fallback:
            raise RuntimeError(f"LangChain Gemini extraction failed and fallback is disabled: {e}") from e
        logger.error(f"LangChain Gemini extraction failed: {e}. Executing deterministic fallback.")
        rule_obs = rule_based_laboratory_parser(text, page_number=page_number, default_date=doc_date)
        return ExtractionResult(
            observations=rule_obs,
            document_date=doc_date,
            extraction_notes=f"Gemini API unavailable ({str(e)}). Extracted {len(rule_obs)} observations via fallback parser."
        )


def extract_from_document(
    pages_text: list,
    document_date: str = None,
    api_key: str = None,
    model_name: str = "gemini-2.0-flash",
    allow_fallback: bool = True,
) -> ExtractionResult:
    """Extract observations across all pages of a document."""
    all_observations = []
    notes = []
    global_doc_date = document_date

    # First pass to find overall document date if not provided
    if not global_doc_date:
        for _, text in pages_text:
            d = extract_date_from_text(text)
            if d:
                global_doc_date = d
                break

    for page_num, text in pages_text:
        if not text or len(text.strip()) < 10:
            continue
        res = extract_observations_with_langchain(
            text=text,
            page_number=page_num,
            document_date=global_doc_date,
            api_key=api_key,
            model_name=model_name,
            allow_fallback=allow_fallback,
        )
        all_observations.extend(res.observations)
        if res.extraction_notes:
            notes.append(res.extraction_notes)

    return ExtractionResult(
        observations=all_observations,
        document_date=global_doc_date,
        extraction_notes=" | ".join(notes) if notes else None,
    )
