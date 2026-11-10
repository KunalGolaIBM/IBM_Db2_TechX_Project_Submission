"""
Unit Tests: Clinical Date Parsing & Validation
"""

from ingestion.validation import ExtractedObservation
from services.timeline_service import parse_safe_date
from datetime import datetime


def test_missing_date_flags_review():
    obs = ExtractedObservation(test_name="Glucose", value_numeric=105, unit="mg/dL", observed_at=None)
    assert obs.needs_review is True
    assert any("Date" in r for r in obs.review_reasons)


def test_future_date_suppressed():
    obs = ExtractedObservation(test_name="Glucose", value_numeric=105, unit="mg/dL", observed_at="2099-01-01")
    assert obs.observed_at is None
    assert obs.needs_review is True


def test_alternate_date_formats_normalized():
    obs = ExtractedObservation(test_name="Glucose", value_numeric=105, unit="mg/dL", observed_at="15/10/2026")
    assert obs.observed_at == "2026-10-15"


def test_safe_date_parser():
    dt, s = parse_safe_date("2026-11-08")
    assert s == "2026-11-08"
    assert dt == datetime(2026, 11, 8, 0, 0)

    # Invalid string fallback
    dt_bad, s_bad = parse_safe_date("invalid-date")
    assert dt_bad == datetime.min

