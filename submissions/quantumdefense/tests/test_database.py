import os
import sys

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import database


def test_database_initialization():
    database.initialize_database()


def test_save_and_retrieve_event():
    database.initialize_database()

    event = {
        "event_type": "brute_force",
        "source_ip": "192.168.1.20",
        "severity": "High",
        "description": "Test security event"
    }

    event_id = database.save_event(event)

    events = database.get_events()

    assert event_id is not None
    assert any(item["id"] == event_id for item in events)


def test_save_and_retrieve_alert():
    database.initialize_database()

    event = {
        "event_type": "sql_injection",
        "source_ip": "192.168.1.30",
        "severity": "Critical",
        "description": "Test SQL injection"
    }

    event_id = database.save_event(event)

    database.save_alert(event_id, "Test security alert")

    alerts = database.get_alerts()

    assert any(item["event_id"] == event_id for item in alerts)


def test_save_and_retrieve_ml_result():
    database.initialize_database()

    event = {
        "event_type": "port_scan",
        "source_ip": "192.168.1.40",
        "severity": "Medium",
        "description": "Test ML analysis"
    }

    event_id = database.save_event(event)

    result = {
        "anomaly_detected": True,
        "anomaly_score": -0.08,
        "method": "Isolation Forest"
    }

    database.save_ml_result(event_id, result)

    results = database.get_ml_results()

    assert any(item["event_id"] == event_id for item in results)
