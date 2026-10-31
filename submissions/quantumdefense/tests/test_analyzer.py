import os
import sys
import math

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import pytest
from analyzer import analyze_network_activity


def test_normal_network_activity():
    result = analyze_network_activity(1, 12, 0)

    assert result["anomaly_detected"] is False
    assert result["method"] == "Isolation Forest"
    assert math.isfinite(result["anomaly_score"])


def test_unusual_network_activity():
    result = analyze_network_activity(100, 500, 50)

    assert result["anomaly_detected"] is True
    assert result["method"] == "Isolation Forest"
    assert math.isfinite(result["anomaly_score"])


def test_negative_input():
    with pytest.raises(ValueError):
        analyze_network_activity(-1, 10, 0)


def test_invalid_input():
    with pytest.raises(ValueError):
        analyze_network_activity("invalid", 10, 0)
