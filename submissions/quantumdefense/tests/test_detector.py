import os
import sys

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import pytest
import detector


def test_normal_activity():
    result = detector.analyze_event({
        "event_type": "normal_activity"
    })

    assert result["detected"] is False
    assert result["severity"] == "Low"


def test_brute_force_detection():
    result = detector.analyze_event({
        "event_type": "brute_force"
    })

    assert result["detected"] is True
    assert result["severity"] == "High"


def test_sql_injection_detection():
    result = detector.analyze_event({
        "event_type": "sql_injection"
    })

    assert result["detected"] is True
    assert result["severity"] == "Critical"


def test_missing_event_type():
    with pytest.raises(ValueError):
        detector.analyze_event({})


def test_invalid_ip_address():
    with pytest.raises(ValueError, match="Invalid source IP address"):
        detector.process_event({
            "event_type": "brute_force",
            "source_ip": "invalid-ip"
        })


def test_suspicious_event_creates_alert(monkeypatch):
    saved_events = []
    saved_alerts = []

    def fake_save_event(event):
        saved_events.append(event)
        return 101

    def fake_save_alert(event_id, message):
        saved_alerts.append((event_id, message))

    monkeypatch.setattr(detector, "save_event", fake_save_event)
    monkeypatch.setattr(detector, "save_alert", fake_save_alert)

    result = detector.process_event({
        "event_type": "brute_force",
        "source_ip": "192.168.1.10",
        "description": "Test brute-force activity"
    })

    assert result["event_id"] == 101
    assert result["detected"] is True
    assert len(saved_events) == 1
    assert len(saved_alerts) == 1
