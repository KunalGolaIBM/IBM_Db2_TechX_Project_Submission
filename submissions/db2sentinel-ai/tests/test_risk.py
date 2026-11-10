import pytest
from src.backend.app.services.risk_service import RiskScoringEngine

def test_risk_score_calculation():
    """Validates the transparent 4-factor weighted risk formula."""
    res = RiskScoringEngine.calculate_score(
        behavior_dev=85.0,
        privilege_sens=90.0,
        volume_anomaly=90.0,
        auth_anomaly=85.0
    )
    # Expected: 85*0.3 + 90*0.25 + 90*0.25 + 85*0.2 = 25.5 + 22.5 + 22.5 + 17.0 = 87.5
    assert res["risk_score"] == 87.5
    assert res["severity"] == "CRITICAL"
    assert "breakdown" in res
    assert res["breakdown"]["behavior_deviation"]["weighted"] == 25.5
    assert res["breakdown"]["privilege_sensitivity"]["weighted"] == 22.5
    assert res["breakdown"]["volume_anomaly"]["weighted"] == 22.5
    assert res["breakdown"]["auth_anomaly"]["weighted"] == 17.0

def test_risk_score_bounds():
    """Validates that scores clamp within [0, 100]."""
    res_low = RiskScoringEngine.calculate_score(0, 0, 0, 0)
    assert res_low["risk_score"] == 0.0
    assert res_low["severity"] == "LOW"

    res_high = RiskScoringEngine.calculate_score(150, 120, 200, 100)
    assert res_high["risk_score"] == 100.0
    assert res_high["severity"] == "CRITICAL"
