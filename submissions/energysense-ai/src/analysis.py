"""Appliance-specific anomaly scoring and explainable diagnostics."""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

FEATURES = ("irms_a", "vrms_v", "apparent_power_va", "temperature_c", "vibration_rms", "runtime_s")


def _finite_numeric(values: list[dict[str, Any]], feature: str) -> list[float]:
    result: list[float] = []
    for row in values:
        value = row.get(feature)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            result.append(number)
    return result


def analyse_window(current: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the latest sample with that appliance's history.

    Feature-level z-scores explain changes in either direction. Isolation Forest
    is attempted with at least 20 complete historical feature windows. These are
    anomaly indicators, not failure probabilities or certified protection limits.
    """
    prior = history[:-1] if history and history[-1].get("telemetry_id") == current.get("telemetry_id") else history
    flags: list[dict[str, Any]] = []
    baseline: dict[str, dict[str, float]] = {}
    usable_features: list[str] = []

    for feature in FEATURES:
        observed_value = current.get(feature)
        if observed_value is None:
            continue
        try:
            observed = float(observed_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(observed):
            continue
        values = _finite_numeric(prior, feature)
        if len(values) < 5:
            continue
        avg = mean(values)
        raw_std = pstdev(values) if len(values) > 1 else 0.0
        # Noise floor prevents a nearly constant simulated signal producing an
        # unbounded score from tiny numerical differences.
        effective_std = max(raw_std, abs(avg) * 0.03, 0.01)
        z_score = (observed - avg) / effective_std
        baseline[feature] = {
            "mean": round(avg, 4),
            "std": round(effective_std, 4),
            "z_score": round(z_score, 3),
            "samples": float(len(values)),
        }
        usable_features.append(feature)
        if abs(z_score) >= 3.0:
            flags.append({
                "feature": feature,
                "observed": round(observed, 4),
                "baseline_mean": round(avg, 4),
                "baseline_std": round(effective_std, 4),
                "z_score": round(z_score, 3),
                "direction": "above" if z_score > 0 else "below",
            })

    # Optional multivariate outlier detection. Only complete, finite windows are used.
    iforest_prediction: int | None = None
    iforest_score: float | None = None
    if len(prior) >= 20 and len(usable_features) >= 2:
        try:
            from sklearn.ensemble import IsolationForest

            matrix: list[list[float]] = []
            for row in prior:
                values = _finite_numeric([row], usable_features[0])
                if not values:
                    continue
                vector = [values[0]]
                for feature in usable_features[1:]:
                    feature_values = _finite_numeric([row], feature)
                    if not feature_values:
                        break
                    vector.append(feature_values[0])
                if len(vector) == len(usable_features):
                    matrix.append(vector)
            if len(matrix) >= 20:
                current_vector = [float(current[name]) for name in usable_features]
                model = IsolationForest(n_estimators=120, contamination="auto", random_state=42)
                model.fit(matrix)
                iforest_prediction = int(model.predict([current_vector])[0])
                iforest_score = round(float(model.decision_function([current_vector])[0]), 5)
        except (ImportError, ValueError, FloatingPointError):
            # Preserve the explainable baseline path when the optional model is unavailable.
            pass

    max_z = max((abs(flag["z_score"]) for flag in flags), default=0.0)
    forest_anomaly = iforest_prediction == -1
    detected = bool(flags) or forest_anomaly
    forest_component = max(0.0, -iforest_score) * 4 if iforest_score is not None else 0.0
    score = round(min(max(max_z / 6.0, forest_component), 1.0), 3) if detected else 0.0

    if flags:
        primary = max(flags, key=lambda item: abs(item["z_score"]))
        reason = (
            f"{primary['feature']} is {primary['direction']} its appliance baseline: "
            f"{primary['observed']} versus a mean of {primary['baseline_mean']} "
            f"(z={primary['z_score']})."
        )
    elif forest_anomaly:
        primary = None
        reason = "Isolation Forest found an unusual multivariate operating pattern; inspect the feature window and recent operating context."
    else:
        primary = None
        reason = "No feature crossed the appliance-baseline deviation rule and no multivariate outlier was detected."

    # Select a useful baseline feature for audit events even when only the
    # multivariate detector fired and no single feature crossed 3 sigma.
    if primary is None and forest_anomaly and baseline:
        selected = max(baseline, key=lambda name: abs(baseline[name]["z_score"]))
        primary = {
            "feature": selected,
            "observed": round(float(current[selected]), 4),
            "baseline_mean": baseline[selected]["mean"],
            "baseline_std": baseline[selected]["std"],
            "z_score": baseline[selected]["z_score"],
            "direction": "above" if baseline[selected]["z_score"] >= 0 else "below",
        }

    severity = "HIGH" if max_z >= 5.0 else ("MEDIUM" if detected else "INFO")
    return {
        "anomaly_detected": detected,
        "anomaly_score": score,
        "severity": severity,
        "flags": flags,
        "baseline": baseline,
        "primary_feature": primary["feature"] if primary else None,
        "primary_observed": primary["observed"] if primary else None,
        "primary_baseline_mean": primary["baseline_mean"] if primary else None,
        "primary_baseline_std": primary["baseline_std"] if primary else None,
        "explanation": reason,
        "method": "feature-level z-scores plus Isolation Forest when at least 20 complete history windows are available",
        "isolation_forest_prediction": iforest_prediction,
        "isolation_forest_decision_score": iforest_score,
        "history_samples": len(prior),
        "baseline_ready": bool(baseline),
    }


def diagnose(report: dict[str, Any], current: dict[str, Any]) -> str:
    if not report["anomaly_detected"]:
        return "No significant deviation was found against the available appliance baseline. Continue monitoring."
    descriptions = []
    for flag in report["flags"]:
        direction = "higher" if flag.get("direction") == "above" else "lower"
        feature = flag["feature"]
        if feature == "irms_a":
            descriptions.append(f"current draw is {direction} than this appliance's learned operating pattern")
        elif feature == "vrms_v":
            descriptions.append(f"voltage is {direction} than the appliance's baseline")
        elif feature == "temperature_c":
            descriptions.append(f"temperature is {direction} than the observed baseline")
        elif feature == "vibration_rms":
            descriptions.append(f"vibration is {direction} than the observed baseline")
        elif feature == "runtime_s":
            descriptions.append(f"runtime is {direction} than the observed baseline")
        elif feature == "apparent_power_va":
            descriptions.append(f"apparent power is {direction} than the observed baseline")
    if not descriptions:
        return (
            "The multivariate operating pattern differs from historical samples. "
            "Review the latest readings and operating context before assigning a cause."
        )
    return "Possible operating change: " + "; ".join(descriptions) + ". This is a diagnostic hypothesis, not proof of a component fault."


def recommend(report: dict[str, Any], current: dict[str, Any]) -> str:
    if not report["anomaly_detected"]:
        return "Continue logging normal operation and collect more samples before changing maintenance plans."
    features = {flag["feature"] for flag in report["flags"]}
    actions = []
    if "irms_a" in features or "apparent_power_va" in features:
        actions.append("verify appliance load, cable/connector condition and sensor calibration")
    if "temperature_c" in features:
        actions.append("inspect ventilation, cooling and bearing temperature under qualified supervision")
    if "vibration_rms" in features:
        actions.append("inspect mounting, alignment and rotating-part condition")
    if "vrms_v" in features:
        actions.append("verify voltage-sensor calibration and supply quality")
    if "runtime_s" in features:
        actions.append("check scheduling, operating cycle and unexpected continuous runtime")
    if not actions:
        actions.append("review the recent multivariate trend and inspect the equipment under qualified supervision")
    return "; ".join(actions) + ". Confirm findings with a qualified technician before maintenance or shutdown."
