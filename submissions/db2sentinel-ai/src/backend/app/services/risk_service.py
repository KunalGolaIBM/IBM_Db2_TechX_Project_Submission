from typing import Dict, Any, List

class RiskScoringEngine:
    """
    Explainable, deterministic mathematical risk scoring engine.
    Computes a transparent 0-100 score based on four weighted factors:
      - Behavior Deviation: 30%
      - Privilege Sensitivity: 25%
      - Data Access Anomaly: 25%
      - Authentication Anomalies: 20%
    """
    WEIGHT_BEHAVIOR = 0.30
    WEIGHT_PRIVILEGE = 0.25
    WEIGHT_VOLUME = 0.25
    WEIGHT_AUTH = 0.20

    @classmethod
    def calculate_score(
        cls,
        behavior_dev: float = 0.0,
        privilege_sens: float = 0.0,
        volume_anomaly: float = 0.0,
        auth_anomaly: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculates the weighted risk score and returns transparent factor breakdowns.
        All input factor scores must be normalized between 0.0 and 100.0.
        """
        b_score = min(max(behavior_dev, 0.0), 100.0)
        p_score = min(max(privilege_sens, 0.0), 100.0)
        v_score = min(max(volume_anomaly, 0.0), 100.0)
        a_score = min(max(auth_anomaly, 0.0), 100.0)

        total_score = (
            (b_score * cls.WEIGHT_BEHAVIOR) +
            (p_score * cls.WEIGHT_PRIVILEGE) +
            (v_score * cls.WEIGHT_VOLUME) +
            (a_score * cls.WEIGHT_AUTH)
        )
        total_score = round(min(max(total_score, 0.0), 100.0), 1)

        if total_score >= 75.0:
            severity = "CRITICAL"
        elif total_score >= 50.0:
            severity = "HIGH"
        elif total_score >= 25.0:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return {
            "risk_score": total_score,
            "severity": severity,
            "formula": "0.30 * Behavior + 0.25 * Privilege + 0.25 * Volume + 0.20 * Auth",
            "breakdown": {
                "behavior_deviation": {"raw": b_score, "weighted": round(b_score * cls.WEIGHT_BEHAVIOR, 2)},
                "privilege_sensitivity": {"raw": p_score, "weighted": round(p_score * cls.WEIGHT_PRIVILEGE, 2)},
                "volume_anomaly": {"raw": v_score, "weighted": round(v_score * cls.WEIGHT_VOLUME, 2)},
                "auth_anomaly": {"raw": a_score, "weighted": round(a_score * cls.WEIGHT_AUTH, 2)}
            }
        }
