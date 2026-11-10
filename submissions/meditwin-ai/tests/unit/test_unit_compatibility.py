"""
Unit Tests: Unit Compatibility Verification
"""

from services.timeline_service import compute_metric_trend


def test_incompatible_units_detected_and_rejected():
    obs = [
        {"TEST_CODE": "GLU", "VALUE_NUMERIC": 100.0, "UNIT": "mg/dL", "OBSERVED_AT": "2026-09-01"},
        {"TEST_CODE": "GLU", "VALUE_NUMERIC": 5.5, "UNIT": "mmol/L", "OBSERVED_AT": "2026-10-01"},
    ]
    trend = compute_metric_trend(obs, "GLU")
    assert "Incompatible units detected" in trend.get("message", "")
    assert "absolute_change" not in trend


def test_compatible_normalized_units_allowed():
    obs = [
        {"TEST_CODE": "HBA1C", "VALUE_NUMERIC": 6.2, "UNIT": " % ", "OBSERVED_AT": "2026-09-01"},
        {"TEST_CODE": "HBA1C", "VALUE_NUMERIC": 6.5, "UNIT": "%", "OBSERVED_AT": "2026-10-01"},
    ]
    trend = compute_metric_trend(obs, "HBA1C")
    assert trend["count"] == 2
    assert trend["absolute_change"] == 0.3

