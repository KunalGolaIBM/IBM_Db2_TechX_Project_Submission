"""Auditable specialist pipeline: monitor -> detect -> diagnose -> recommend -> persist."""
from __future__ import annotations

from typing import Any

from .analysis import analyse_window, diagnose, recommend
from .store import utc_now


def run_agent_workflow(store, current: dict[str, Any]) -> dict[str, Any]:
    # These deterministic stages are the always-available analytics path. The
    # optional LangChain LLM agent adds read-only tool use for natural-language review.
    history = store.recent_telemetry(current["appliance_id"], limit=120)
    report = analyse_window(current, history)
    diagnosis = diagnose(report, current)
    action = recommend(report, current)

    result = {
        "equipment_id": current["equipment_id"],
        "appliance_id": current["appliance_id"],
        "anomaly": report,
        "diagnosis": diagnosis,
        "recommended_action": action,
        "workflow_trace": [
            {"stage": "monitor", "result": f"Retrieved {report['history_samples']} historical samples"},
            {"stage": "detect", "result": report["method"]},
            {"stage": "diagnose", "result": "Generated a cautious, measurement-grounded hypothesis"},
            {"stage": "recommend", "result": "Produced advisory inspection guidance"},
            {"stage": "supervise", "result": "Persisted an auditable event when an anomaly was detected" if report["anomaly_detected"] else "No event required"},
        ],
        "decision_engine": "deterministic baseline analytics; optional LangChain tool-calling assistant",
        "created_at": utc_now(),
        "safety_boundary": "AI is advisory only. Only the local ESP32 threshold logic may command the relay.",
    }
    if report["anomaly_detected"]:
        store.insert_event({
            "equipment_id": current["equipment_id"],
            "appliance_id": current["appliance_id"],
            "severity": report["severity"],
            "anomaly_score": report["anomaly_score"],
            "feature_name": report.get("primary_feature") or "multivariate_pattern",
            "observed_value": report.get("primary_observed"),
            "baseline_mean": report.get("primary_baseline_mean"),
            "baseline_std": report.get("primary_baseline_std"),
            "explanation": diagnosis,
            "recommended_action": action,
        })
    return result
