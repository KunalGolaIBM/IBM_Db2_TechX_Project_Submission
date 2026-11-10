import pytest
from src.backend.app.database import db_manager
from src.backend.app.services.detection_service import DetectionEngine

def test_detection_engine_rules():
    """Validates that deterministic rules identify brute force, sensitive access, and recon."""
    db_manager.reset_demo_data()
    db_manager.seed_demo_data()

    engine = DetectionEngine(db_manager)
    alerts = engine.run_detection()

    assert len(alerts) > 0
    alert_names = [a["alert_name"] for a in alerts]

    # Verify key rules fired
    assert any("Brute Force" in name for name in alert_names)
    assert any("Sensitive Table" in name for name in alert_names)
    assert any("Privileged Catalog" in name for name in alert_names)
