"""
Unit Tests: Longitudinal Timeline Engine & Trend Calculations
"""

from services.timeline_service import (
    build_patient_timeline,
    compute_metric_trend,
    format_trend_summary,
    parse_safe_date,
)


def test_timeline_chronological_ordering():
    obs = [
        {"OBSERVATION_ID": 1, "TEST_NAME": "HbA1c", "VALUE_NUMERIC": 6.4, "UNIT": "%", "OBSERVED_AT": "2026-10-12", "FILE_NAME": "rep1.pdf"},
        {"OBSERVATION_ID": 2, "TEST_NAME": "HbA1c", "VALUE_NUMERIC": 6.8, "UNIT": "%", "OBSERVED_AT": "2026-11-08", "FILE_NAME": "rep2.pdf"},
    ]
    timeline = build_patient_timeline(obs)
    # Newest first
    assert timeline[0]["date_str"] == "2026-11-08"
    assert timeline[1]["date_str"] == "2026-10-12"


def test_timeline_same_day_secondary_sort():
    obs = [
        {"OBSERVATION_ID": 10, "TEST_NAME": "Glucose", "VALUE_NUMERIC": 110, "UNIT": "mg/dL", "OBSERVED_AT": "2026-10-12", "FILE_NAME": "rep1.pdf"},
        {"OBSERVATION_ID": 20, "TEST_NAME": "Glucose", "VALUE_NUMERIC": 105, "UNIT": "mg/dL", "OBSERVED_AT": "2026-10-12", "FILE_NAME": "rep2.pdf"},
    ]
    timeline = build_patient_timeline(obs)
    assert timeline[0]["observation_id"] == 20
    assert timeline[1]["observation_id"] == 10


def test_timeline_deduplication():
    obs = [
        {"OBSERVATION_ID": 1, "TEST_NAME": "HbA1c", "VALUE_NUMERIC": 6.4, "UNIT": "%", "OBSERVED_AT": "2026-10-12", "FILE_NAME": "rep1.pdf"},
        {"OBSERVATION_ID": 2, "TEST_NAME": "HbA1c", "VALUE_NUMERIC": 6.4, "UNIT": "%", "OBSERVED_AT": "2026-10-12", "FILE_NAME": "rep1.pdf"},
    ]
    timeline = build_patient_timeline(obs)
    assert len(timeline) == 1  # Duplicate identical signature deduplicated


def test_metric_trend_calculations():
    obs = [
        {"OBSERVATION_ID": 1, "TEST_CODE": "HBA1C", "TEST_NAME": "HbA1c", "VALUE_NUMERIC": 6.4, "UNIT": "%", "OBSERVED_AT": "2026-10-12", "FILE_NAME": "rep1.pdf"},
        {"OBSERVATION_ID": 2, "TEST_CODE": "HBA1C", "TEST_NAME": "HbA1c", "VALUE_NUMERIC": 6.8, "UNIT": "%", "OBSERVED_AT": "2026-11-08", "FILE_NAME": "rep2.pdf"},
    ]
    trend = compute_metric_trend(obs, "HBA1C")
    assert trend["count"] == 2
    assert trend["first_value"] == 6.4
    assert trend["latest_value"] == 6.8
    assert trend["absolute_change"] == 0.4
    assert trend["percentage_change"] == 6.25


def test_zero_baseline_handling():
    obs = [
        {"OBSERVATION_ID": 1, "TEST_CODE": "PROTEIN", "TEST_NAME": "Protein", "VALUE_NUMERIC": 0.0, "UNIT": "mg/dL", "OBSERVED_AT": "2026-10-12"},
        {"OBSERVATION_ID": 2, "TEST_CODE": "PROTEIN", "TEST_NAME": "Protein", "VALUE_NUMERIC": 15.0, "UNIT": "mg/dL", "OBSERVED_AT": "2026-11-08"},
    ]
    trend = compute_metric_trend(obs, "PROTEIN")
    assert trend["is_zero_baseline"] is True
    assert trend["percentage_change"] is None  # Undefined division by zero avoided
    summary = format_trend_summary(trend)
    assert "Undefined (baseline measurement was 0.0)" in summary

