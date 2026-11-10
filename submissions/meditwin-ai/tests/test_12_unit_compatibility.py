"""
Test Category 12: Unit Compatibility Test
Ensures measurements with conflicting units are never falsely compared directly.
"""

from services.timeline_service import compute_metric_trend


def test_incompatible_units_blocks_trend_calculation():
    """Conflicting units (e.g. mg/dL vs mmol/L) must not produce misleading mathematical differences."""
    observations = [
        {
            "OBSERVATION_ID": 1,
            "TEST_NAME": "Glucose",
            "TEST_CODE": "GLU",
            "VALUE_NUMERIC": 100.0,
            "UNIT": "mg/dL",
            "OBSERVED_AT": "2026-09-01",
            "FILE_NAME": "us_lab.pdf"
        },
        {
            "OBSERVATION_ID": 2,
            "TEST_NAME": "Glucose",
            "TEST_CODE": "GLU",
            "VALUE_NUMERIC": 5.5,
            "UNIT": "mmol/L",
            "OBSERVED_AT": "2026-10-01",
            "FILE_NAME": "uk_lab.pdf"
        }
    ]

    trend = compute_metric_trend(observations, "GLU")
    assert "incompatible units" in trend.get("message", "").lower()
    assert "absolute_change" not in trend

