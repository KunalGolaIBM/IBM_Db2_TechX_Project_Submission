"""Seed normal pump telemetry, then one intentionally unusual sample."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from .store import get_store
from .workflow import run_agent_workflow


def main() -> None:
    random.seed(12)
    store = get_store()
    base_time = datetime.now(timezone.utc) - timedelta(minutes=35)
    last = None
    for index in range(30):
        last = store.insert_telemetry({
            "equipment_id": "ES-01",
            "appliance_id": "pump-01",
            "appliance_name": "Pump 01",
            "vrms_v": round(random.normalvariate(230, 1.0), 2),
            "irms_a": round(random.normalvariate(1.60, 0.025), 3),
            "apparent_power_va": round(random.normalvariate(368, 6), 2),
            "runtime_s": 3600 + index * 60,
            "temperature_c": round(random.normalvariate(41, 0.5), 2),
            "vibration_rms": round(random.normalvariate(0.20, 0.01), 3),
            "relay_state": "ON",
            "source": "synthetic",
            "recorded_at": (base_time + timedelta(minutes=index)).isoformat(timespec="seconds"),
        })
    current = store.insert_telemetry({
        "equipment_id": "ES-01",
        "appliance_id": "pump-01",
        "appliance_name": "Pump 01",
        "vrms_v": 229.5,
        "irms_a": 2.45,
        "apparent_power_va": 562.0,
        "runtime_s": 5400,
        "temperature_c": 42.0,
        "vibration_rms": 0.22,
        "relay_state": "ON",
        "source": "synthetic",
    })
    result = run_agent_workflow(store, current)
    print("Demo telemetry loaded.")
    print(f"Anomaly detected: {result['anomaly']['anomaly_detected']}")
    print(f"Diagnosis: {result['diagnosis']}")
    print(f"Recommendation: {result['recommended_action']}")
    print("This is synthetic data for software demonstration, not physical sensor evidence.")


if __name__ == "__main__":
    main()
