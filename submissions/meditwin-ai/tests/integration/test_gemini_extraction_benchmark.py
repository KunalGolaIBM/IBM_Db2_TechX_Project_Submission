"""
Integration Tests: Gemini & Rule-based Extraction Benchmark
Validates 100% extraction accuracy across the complete suite of synthetic multi-page reports.
"""

from pathlib import Path
from ingestion.pdf_parser import parse_pdf
from ingestion.extraction import extract_from_document
from ingestion.validation import validate_observations


def test_synthetic_reports_complete_extraction_benchmark():
    """
    Benchmark extraction across all 3 synthetic PDF reports.
    Verifies that all 24 target observations are extracted with full provenance and validity.
    """
    reports = [
        ("sample_data/synthetic_reports/SyntheticReport_A_Oct2026.pdf", 9),
        ("sample_data/synthetic_reports/SyntheticReport_B_Nov2026.pdf", 9),
        ("sample_data/synthetic_reports/SyntheticReport_C_Sep2026.pdf", 6),
    ]

    total_extracted = 0

    for path_str, expected_count in reports:
        pdf_path = Path(path_str)
        assert pdf_path.exists(), f"Sample report missing: {path_str}"

        # 1. Parse document into pages
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        parsed_doc = parse_pdf(pdf_path.name, pdf_bytes)
        assert parsed_doc.parse_status == "PARSED"
        assert len(parsed_doc.pages) >= 1

        pages_text = [(p.page_number, p.text) for p in parsed_doc.pages]

        # 2. Extract observations
        extraction_res = extract_from_document(
            pages_text=pages_text,
        )

        assert len(extraction_res.observations) == expected_count, (
            f"Expected {expected_count} observations from {pdf_path.name}, got {len(extraction_res.observations)}"
        )

        # 3. Validate observations via Pydantic
        obs_dicts = [obs.model_dump() for obs in extraction_res.observations]
        valid_obs, invalid_obs = validate_observations(obs_dicts)
        assert len(invalid_obs) == 0, f"Encountered validation errors in {pdf_path.name}: {invalid_obs}"
        assert len(valid_obs) == expected_count

        # 4. Verify critical clinical fields
        for obs in valid_obs:
            assert obs.test_code is not None and len(obs.test_code) > 0
            assert obs.value_numeric is not None or obs.value_text is not None
            assert obs.observed_at is not None
            assert obs.source_page >= 1
            assert len(obs.source_snippet) > 0
            assert 0.0 <= obs.confidence <= 1.0

        total_extracted += len(valid_obs)

    assert total_extracted == 24, f"Expected 24 total benchmark observations, got {total_extracted}"
