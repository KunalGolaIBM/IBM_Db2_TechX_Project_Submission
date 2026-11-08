import pytest

from src.store import SQLiteStore


def _reading(telemetry_id, recorded_at, current=1.2):
    return {
        "telemetry_id": telemetry_id,
        "equipment_id": "ES-TEST",
        "appliance_id": "pump-01",
        "appliance_name": "Test Pump",
        "vrms_v": 230.0,
        "irms_a": current,
        "apparent_power_va": 276.0,
        "runtime_s": 120.0,
        "source": "synthetic",
        "recorded_at": recorded_at,
    }


def test_sqlite_store_round_trip_and_chronological_order(tmp_path):
    store = SQLiteStore(str(tmp_path / "store.db"))
    store.insert_telemetry(_reading("id-2", "2026-11-08T10:02:00+00:00"))
    store.insert_telemetry(_reading("id-1", "2026-11-08T10:01:00+00:00"))
    rows = store.recent_telemetry("pump-01", limit=10)
    assert [row["telemetry_id"] for row in rows] == ["id-1", "id-2"]
    assert rows[0]["irms_a"] == pytest.approx(1.2)
    assert store.counts() == {"telemetry_count": 2, "event_count": 0}


def test_equipment_upsert_and_event_filter(tmp_path):
    store = SQLiteStore(str(tmp_path / "store.db"))
    store.upsert_equipment("ES-1", "First Name")
    store.upsert_equipment("ES-1", "Updated Name")
    store.insert_event({
        "equipment_id": "ES-1", "appliance_id": "pump-01", "severity": "MEDIUM",
        "anomaly_score": 0.65, "feature_name": "irms_a", "observed_value": 2.4,
        "baseline_mean": 1.5, "baseline_std": 0.05,
        "explanation": "Current exceeded baseline.", "recommended_action": "Check load.",
    })
    store.insert_event({
        "equipment_id": "ES-1", "appliance_id": "fan-01", "severity": "INFO",
        "anomaly_score": 0.0, "feature_name": None, "observed_value": None,
        "baseline_mean": None, "baseline_std": None,
        "explanation": "Normal.", "recommended_action": "Continue monitoring.",
    })
    assert len(store.list_events("pump-01")) == 1
    assert len(store.list_events()) == 2
    assert store.counts()["event_count"] == 2


def test_limits_are_bounded_and_minimum_one(tmp_path):
    store = SQLiteStore(str(tmp_path / "store.db"))
    for i in range(3):
        store.insert_telemetry(_reading(f"id-{i}", f"2026-11-08T10:0{i}:00+00:00"))
    assert len(store.recent_telemetry("pump-01", limit=0)) == 1
    assert len(store.recent_telemetry("pump-01", limit=9999)) == 3


def test_duplicate_telemetry_id_fails_without_partial_equipment_update(tmp_path):
    store = SQLiteStore(str(tmp_path / "store.db"))
    store.insert_telemetry(_reading("same-id", "2026-11-08T10:00:00+00:00"))
    with pytest.raises(Exception):
        store.insert_telemetry({**_reading("same-id", "2026-11-08T10:01:00+00:00"), "appliance_name": "Changed"})
    assert store.counts()["telemetry_count"] == 1


def test_event_requires_identity_and_severity(tmp_path):
    store = SQLiteStore(str(tmp_path / "store.db"))
    with pytest.raises(ValueError, match="Missing event fields"):
        store.insert_event({"equipment_id": "ES-1", "appliance_id": "pump-01"})
