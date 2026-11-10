"""
Unit Tests: Pydantic Validation Models
"""

import pytest
from pydantic import ValidationError
from ingestion.validation import ExtractedObservation, ReviewDecision


def test_extracted_observation_valid():
    obs = ExtractedObservation(
        test_name="Glycated Hemoglobin",
        test_code="hba1c",
        value_numeric=6.4,
        unit="%",
        reference_low=4.0,
        reference_high=5.6,
        observed_at="2026-10-12",
        source_page=1,
        source_snippet="HbA1c: 6.4%",
        confidence=0.96,
    )
    assert obs.test_code == "HBA1C"  # Normalized to uppercase
    assert obs.value_numeric == 6.4
    assert obs.needs_review is False


def test_confidence_bounds_enforced():
    with pytest.raises(ValidationError):
        ExtractedObservation(test_name="Test", confidence=1.5)
    with pytest.raises(ValidationError):
        ExtractedObservation(test_name="Test", confidence=-0.1)


def test_missing_unit_flags_review():
    obs = ExtractedObservation(
        test_name="Total Cholesterol",
        value_numeric=195.0,
        unit=None,
        observed_at="2026-10-12",
    )
    assert obs.needs_review is True
    assert any("Unit" in r for r in obs.review_reasons)


def test_review_decision_validation():
    decision = ReviewDecision(
        observation_id=10,
        action="APPROVED",
        corrected_value_numeric=6.5,
        corrected_unit="%",
        corrected_date="2026-10-15",
        corrected_test_code="hba1c",
        reviewed_by="DR_REVIEWER",
    )
    assert decision.action == "APPROVED"
    assert decision.corrected_value_numeric == 6.5
    assert decision.corrected_test_code == "HBA1C"
    assert decision.corrected_date == "2026-10-15"


def test_review_decision_invalid_date():
    with pytest.raises(ValidationError):
        ReviewDecision(
            observation_id=10,
            action="APPROVED",
            corrected_date="not-a-date",
        )

