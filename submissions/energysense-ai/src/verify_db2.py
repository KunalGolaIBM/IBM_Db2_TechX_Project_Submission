"""Run a real Db2 read/write smoke test against the configured instance.

This command inserts one clearly labelled synthetic verification row and one
INFO event. It never touches hardware or changes relay state.
"""
from __future__ import annotations

import json
import uuid

from .config import get_settings
from .store import get_store


def main() -> None:
    settings = get_settings()
    settings.validate()
    if settings.db_backend != "db2":
        raise SystemExit("Set DB_BACKEND=db2 in .env before running this live Db2 smoke test.")

    store = get_store()
    suffix = uuid.uuid4().hex[:8]
    equipment_id = f"ES-VERIFY-{suffix}"
    appliance_id = f"db2-verify-{suffix}"
    store.insert_telemetry({
        "equipment_id": equipment_id,
        "appliance_id": appliance_id,
        "appliance_name": "Db2 Connectivity Verification (Synthetic)",
        "vrms_v": 230.0,
        "irms_a": 0.1,
        "apparent_power_va": 23.0,
        "runtime_s": 1.0,
        "relay_state": "UNKNOWN",
        "source": "synthetic",
    })
    store.insert_event({
        "equipment_id": equipment_id,
        "appliance_id": appliance_id,
        "severity": "INFO",
        "anomaly_score": 0.0,
        "feature_name": "db2_connectivity_smoke_test",
        "observed_value": 1.0,
        "baseline_mean": 1.0,
        "baseline_std": 0.0,
        "explanation": "Synthetic event created by the Db2 read/write verification command.",
        "recommended_action": "No action; this is a connectivity verification record.",
    })
    readings = store.recent_telemetry(appliance_id, limit=5)
    events = store.list_events(appliance_id=appliance_id, limit=5)
    if len(readings) != 1 or len(events) != 1:
        raise SystemExit("Db2 write/read verification failed: the verification records were not returned.")
    print(json.dumps({
        "status": "passed",
        "backend": store.backend,
        "telemetry_read_back": len(readings),
        "event_read_back": len(events),
        "synthetic_appliance_id": appliance_id,
        "note": "This command writes test rows to the configured Db2 database; remove them after verification if desired.",
    }, indent=2))


if __name__ == "__main__":
    main()
