"""
Test Category 11: Timeline Ordering Test
Validates chronological ordering, earliest/latest detection, and deterministic difference computation.
"""

from services.timeline_service import build_patient_timeline, compute_metric_trend


def test_timeline_chronological_ordering():
    """Verify observations are ordered chronologically."""
    observations = [
        {
            "OBSERVATION_ID": 10,
            "TEST_NAME": "HbA1c",
            "TEST_CODE": "HBA1C",
            "VALUE_NUMERIC": 6.8,
            "UNIT": "%",
            "OBSERVED_AT": "2026-11-08",
            "FILE_NAME": "report_nov.pdf",
            "SOURCE_PAGE": 1,
            "SOURCE_SNIPPET": "HbA1c: 6.8%",
        },
        {
            "OBSERVATION_ID": 5,
            "TEST_NAME": "HbA1c",
            "TEST_CODE": "HBA1C",
            "VALUE_NUMERIC": 6.4,
            "UNIT": "%",
            "OBSERVED_AT": "2026-10-12",
            "FILE_NAME": "report_oct.pdf",
            "SOURCE_PAGE": 1,
            "SOURCE_SNIPPET": "HbA1c: 6.4%",
        },
    ]

    # Timeline view orders newest first
    timeline = build_patient_timeline(observations)
    assert timeline[0]["date_str"] == "2026-11-08"
    assert timeline[1]["date_str"] == "2026-10-12"


def test_metric_trend_calculation():
    """Verify deterministic change calculation: first, latest, absolute, percentage."""
    observations = [
        {
            "OBSERVATION_ID": 1,
            "TEST_NAME": "HbA1c",
            "TEST_CODE": "HBA1C",
            "VALUE_NUMERIC": 6.4,
            "UNIT": "%",
            "OBSERVED_AT": "2026-10-12",
            "FILE_NAME": "report_a.pdf"
        },
        {
            "OBSERVATION_ID": 2,
            "TEST_NAME": "HbA1c",
            "TEST_CODE": "HBA1C",
            "VALUE_NUMERIC": 6.8,
            "UNIT": "%",
            "OBSERVED_AT": "2026-11-08",
            "FILE_NAME": "report_b.pdf"
        }
    ]

    trend = compute_metric_trend(observations, "HBA1C")
    assert trend["count"] == 2
    assert trend["first_value"] == 6.4
    assert trend["latest_value"] == 6.8
    assert trend["absolute_change"] == 0.4
    assert trend["percentage_change"] == 6.25
    assert trend["first_source"] == "report_a.pdf"
    assert trend["latest_source"] == "report_b.pdf"

