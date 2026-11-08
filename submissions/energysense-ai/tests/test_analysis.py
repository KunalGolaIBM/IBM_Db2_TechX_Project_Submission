from src.analysis import analyse_window, diagnose, recommend


def _baseline_rows(count=12):
    return [
        {
            "irms_a": 1.50 + (i % 2) * 0.01,
            "vrms_v": 230.0 + (i % 2) * 0.2,
            "apparent_power_va": 345.0 + (i % 2) * 1.0,
            "runtime_s": 3600 + i,
            "temperature_c": 40.0 + (i % 2) * 0.1,
            "vibration_rms": 0.20 + (i % 2) * 0.001,
            "telemetry_id": str(i),
        }
        for i in range(count)
    ]


def test_high_current_deviation_is_flagged():
    history = _baseline_rows(10)
    current = {
        "irms_a": 2.5, "vrms_v": 230.0, "apparent_power_va": 575.0,
        "runtime_s": 3600, "temperature_c": 40.0, "vibration_rms": 0.2,
        "telemetry_id": "latest",
    }
    report = analyse_window(current, history)
    assert report["anomaly_detected"] is True
    assert "irms_a" in {flag["feature"] for flag in report["flags"]}
    assert "current" in diagnose(report, current).lower()
    assert "verify" in recommend(report, current).lower()


def test_low_voltage_and_low_current_deviations_are_flagged():
    history = _baseline_rows(10)
    current = {
        "irms_a": 0.4, "vrms_v": 170.0, "apparent_power_va": 68.0,
        "runtime_s": 3600, "temperature_c": 40.0, "vibration_rms": 0.2,
        "telemetry_id": "low-reading",
    }
    report = analyse_window(current, history)
    features = {flag["feature"] for flag in report["flags"]}
    assert {"irms_a", "vrms_v"}.issubset(features)
    assert all(flag["direction"] == "below" for flag in report["flags"] if flag["feature"] in {"irms_a", "vrms_v"})
    assert "lower" in diagnose(report, current).lower()


def test_no_anomaly_with_stable_current():
    history = [{"irms_a": 1.5 + i * 0.001, "telemetry_id": str(i)} for i in range(10)]
    current = {"irms_a": 1.505, "telemetry_id": "latest"}
    report = analyse_window(current, history)
    assert report["anomaly_detected"] is False
    assert report["anomaly_score"] == 0.0


def test_current_row_is_not_used_in_its_own_baseline():
    history = _baseline_rows(10)
    current = {**history[-1], "irms_a": 2.5}
    report = analyse_window(current, history + [current])
    assert report["history_samples"] == 10
    assert report["anomaly_detected"] is True


def test_incomplete_history_does_not_claim_baseline_ready():
    report = analyse_window({"irms_a": 2.0}, [{"irms_a": 1.0}, {"irms_a": 1.1}])
    assert report["baseline_ready"] is False
    assert report["anomaly_detected"] is False


def test_non_finite_history_values_are_ignored():
    history = [{"irms_a": float("nan"), "telemetry_id": str(i)} for i in range(6)]
    report = analyse_window({"irms_a": 1.0}, history)
    assert "irms_a" not in report["baseline"]
    assert report["baseline_ready"] is False
    assert report["anomaly_detected"] is False
