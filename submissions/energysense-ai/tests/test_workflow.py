from src.store import SQLiteStore
from src.workflow import run_agent_workflow


def test_workflow_records_anomaly_and_audit_trace(tmp_path):
    store = SQLiteStore(str(tmp_path / "workflow.db"))
    for i in range(10):
        store.insert_telemetry({
            "equipment_id": "ES-W", "appliance_id": "pump-workflow",
            "irms_a": 1.5 + (i % 2) * 0.01, "vrms_v": 230.0,
            "apparent_power_va": 345.0, "runtime_s": 600 + i,
            "temperature_c": 40.0, "vibration_rms": 0.2,
            "relay_state": "ON", "source": "synthetic",
        })
    current = store.insert_telemetry({
        "equipment_id": "ES-W", "appliance_id": "pump-workflow",
        "irms_a": 2.5, "vrms_v": 230.0, "apparent_power_va": 575.0,
        "runtime_s": 700, "temperature_c": 40.0, "vibration_rms": 0.2,
        "relay_state": "ON", "source": "synthetic",
    })
    result = run_agent_workflow(store, current)
    assert result["anomaly"]["anomaly_detected"] is True
    assert len(store.list_events("pump-workflow")) == 1
    assert [step["stage"] for step in result["workflow_trace"]] == ["monitor", "detect", "diagnose", "recommend", "supervise"]
    assert "local ESP32" in result["safety_boundary"]


def test_workflow_can_persist_multivariate_only_anomaly(monkeypatch, tmp_path):
    import src.workflow as workflow

    store = SQLiteStore(str(tmp_path / "iforest-only.db"))
    current = store.insert_telemetry({
        "equipment_id": "ES-M", "appliance_id": "pump-multi", "irms_a": 1.2,
        "vrms_v": 230, "source": "synthetic",
    })
    monkeypatch.setattr(workflow, "analyse_window", lambda *_: {
        "anomaly_detected": True, "anomaly_score": 0.42, "severity": "MEDIUM",
        "flags": [], "baseline": {}, "primary_feature": None,
        "primary_observed": None, "primary_baseline_mean": None,
        "primary_baseline_std": None, "explanation": "Multivariate outlier.",
        "method": "Isolation Forest", "history_samples": 30, "baseline_ready": True,
    })
    result = workflow.run_agent_workflow(store, current)
    events = store.list_events("pump-multi")
    assert result["anomaly"]["anomaly_detected"] is True
    assert len(events) == 1
    assert events[0]["feature_name"] == "multivariate_pattern"
    assert events[0]["observed_value"] is None
