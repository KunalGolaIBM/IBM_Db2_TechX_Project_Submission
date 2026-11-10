"""
Test Category 7: Invalid Date Handling Test
Verifies that unparseable or out-of-range dates trigger review and do not silently corrupt records.
"""

from ingestion.validation import ExtractedObservation


def test_missing_date_flags_review():
    """Observations without an observation date must trigger review."""
    obs = ExtractedObservation(
        test_name="HbA1c",
        value_numeric=6.4,
        unit="%",
        observed_at=None
    )
    assert obs.needs_review is True
    assert any("Date" in r for r in obs.review_reasons)


def test_invalid_date_format_converted_or_flagged():
    """Unrecognized date formats should result in None and trigger review."""
    obs = ExtractedObservation(
        test_name="Glucose",
        value_numeric=110,
        unit="mg/dL",
        observed_at="not-a-real-date"
    )
    assert obs.observed_at is None
    assert obs.needs_review is True


def test_future_impossible_date_flagged():
    """Dates far in the future (> 2030) are suppressed and flagged."""
    obs = ExtractedObservation(
        test_name="Glucose",
        value_numeric=110,
        unit="mg/dL",
        observed_at="2099-01-01"
    )
    assert obs.observed_at is None
    assert obs.needs_review is True


def test_alternate_valid_date_format_parsed():
    """Common alternative date formats (e.g. DD/MM/YYYY) are parsed into YYYY-MM-DD."""
    obs = ExtractedObservation(
        test_name="Glucose",
        value_numeric=110,
        unit="mg/dL",
        observed_at="15/10/2026"
    )
    assert obs.observed_at == "2026-10-15"

