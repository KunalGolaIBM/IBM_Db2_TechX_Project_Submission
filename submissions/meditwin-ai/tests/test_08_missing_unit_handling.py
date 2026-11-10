"""
Test Category 8: Missing Unit Handling Test
Ensures numeric measurements without units trigger review rather than guessing units.
"""

from ingestion.validation import ExtractedObservation


def test_missing_unit_on_numeric_measurement():
    """A numeric measurement without a unit must trigger mandatory review."""
    obs = ExtractedObservation(
        test_name="Total Cholesterol",
        value_numeric=195.0,
        unit=None,
        observed_at="2026-10-12"
    )
    assert obs.needs_review is True
    assert any("Unit" in r for r in obs.review_reasons)


def test_empty_string_unit_normalized_and_flagged():
    """An empty or whitespace unit must be treated as missing and flagged."""
    obs = ExtractedObservation(
        test_name="Blood Sugar",
        value_numeric=105.0,
        unit="   ",
        observed_at="2026-10-12"
    )
    assert obs.unit is None
    assert obs.needs_review is True

