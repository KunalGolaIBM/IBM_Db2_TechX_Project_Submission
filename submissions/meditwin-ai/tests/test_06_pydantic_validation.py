"""
Test Category 6: Pydantic Validation Test
Validates observation models, field types, bounds, and normalizations.
"""

import pytest
from pydantic import ValidationError
from ingestion.validation import ExtractedObservation


def test_valid_numeric_observation():
    """Verify valid observation instantiates correctly."""
    obs = ExtractedObservation(
        test_name="Glycated Hemoglobin",
        test_code="HBA1C",
        value_numeric=6.4,
        unit="%",
        reference_low=4.0,
        reference_high=5.6,
        observed_at="2026-10-12",
        source_page=1,
        source_snippet="HbA1c: 6.4 %",
        confidence=0.95
    )
    assert obs.test_name == "Glycated Hemoglobin"
    assert obs.test_code == "HBA1C"
    assert obs.value_numeric == 6.4
    assert obs.unit == "%"
    assert obs.confidence == 0.95
    assert obs.needs_review is False


def test_confidence_bounds_enforced():
    """Confidence must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        ExtractedObservation(test_name="HbA1c", confidence=1.5)
    with pytest.raises(ValidationError):
        ExtractedObservation(test_name="HbA1c", confidence=-0.1)


def test_test_code_normalization():
    """Test code should normalize to uppercase."""
    obs = ExtractedObservation(test_name="Fasting Glucose", test_code="fbs")
    assert obs.test_code == "FBS"

