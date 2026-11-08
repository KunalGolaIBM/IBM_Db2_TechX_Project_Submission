import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src import api
from src.api import TelemetryIn
from src.store import SQLiteStore


@pytest.fixture()
def client(tmp_path, monkeypatch):
    store = SQLiteStore(str(tmp_path / "api.db"))
    monkeypatch.setattr(api, "get_store", lambda: store)
    return TestClient(api.app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database_backend"] == "sqlite"


def test_telemetry_ingestion_and_history_endpoint(client):
    response = client.post("/api/v1/telemetry", json={
        "equipment_id": "ES-API", "appliance_id": "fan-api", "vrms_v": 230.0,
        "irms_a": 0.8, "apparent_power_va": 184.0, "runtime_s": 300,
        "source": "wokwi_simulated", "recorded_at": "2026-11-08T12:00:00+05:30",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stored"] is True
    assert body["telemetry"]["recorded_at"] == "2026-11-08T06:30:00+00:00"
    history = client.get("/api/v1/telemetry/fan-api").json()["items"]
    assert len(history) == 1
    assert history[0]["source"] == "wokwi_simulated"


def test_telemetry_rejects_out_of_range_and_extra_fields(client):
    bad_range = client.post("/api/v1/telemetry", json={
        "equipment_id": "ES-1", "appliance_id": "pump", "vrms_v": 900,
    })
    extra = client.post("/api/v1/telemetry", json={
        "equipment_id": "ES-1", "appliance_id": "pump", "vrms_v": 230, "relay_command": "OFF",
    })
    assert bad_range.status_code == 422
    assert extra.status_code == 422


def test_telemetry_rejects_blank_ids_no_measurements_and_bad_time(client):
    blank_id = client.post("/api/v1/telemetry", json={
        "equipment_id": "  ", "appliance_id": "pump", "irms_a": 0.1,
    })
    no_measurement = client.post("/api/v1/telemetry", json={
        "equipment_id": "ES-1", "appliance_id": "pump",
    })
    bad_time = client.post("/api/v1/telemetry", json={
        "equipment_id": "ES-1", "appliance_id": "pump", "irms_a": 0.1, "recorded_at": "yesterday",
    })
    assert blank_id.status_code == 422
    assert no_measurement.status_code == 422
    assert bad_time.status_code == 422


def test_event_list_limit_validation(client):
    assert client.get("/api/v1/events?limit=0").status_code == 422
    assert client.get("/api/v1/events?limit=500").status_code == 200


def test_telemetry_model_rejects_non_finite_measurement():
    with pytest.raises(ValidationError):
        TelemetryIn.model_validate({
            "equipment_id": "ES-1", "appliance_id": "pump", "irms_a": float("nan"),
        })


def test_device_status_returns_latest_record_without_claiming_online_state(client):
    client.post("/api/v1/telemetry", json={
        "equipment_id": "ES-STATUS", "appliance_id": "pump-status", "vrms_v": 229.0,
        "irms_a": 1.1, "relay_state": "ON", "source": "synthetic",
    })
    response = client.get("/api/v1/devices/pump-status/status")
    assert response.status_code == 200
    body = response.json()
    assert body["has_readings"] is True
    assert body["reported_relay_state"] == "ON"
    assert body["source"] == "synthetic"
    assert "online" not in body


def test_device_status_returns_empty_for_unknown_appliance(client):
    response = client.get("/api/v1/devices/unknown/status")
    assert response.status_code == 200
    assert response.json() == {
        "appliance_id": "unknown", "has_readings": False, "latest": None,
    }
