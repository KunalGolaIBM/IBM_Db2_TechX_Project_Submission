import pytest
from src.backend.app.api.health import health_check, db2_status
from src.backend.app.api.dashboard import get_dashboard_summary
from src.backend.app.api.demo import generate_demo_events, run_demo_detection, reset_demo
from src.backend.app.api.events import list_events, get_event
from src.backend.app.api.alerts import list_alerts
from src.backend.app.api.incidents import list_incidents
from src.backend.app.api.approvals import list_approvals

def test_api_health():
    """Validates health check endpoint returns proper service metadata."""
    res = health_check()
    assert res["status"] in ("healthy", "degraded")
    assert "service" in res
    assert "database_mode" in res

def test_api_db2_status():
    """Validates Db2 diagnostics endpoint."""
    res = db2_status()
    assert "active_mode" in res
    assert res["connected"] is True

def test_api_dashboard_summary():
    """Validates dashboard metrics endpoint."""
    res = get_dashboard_summary()
    assert "metrics" in res
    assert "severity_distribution" in res
    assert "database_status" in res

def test_api_demo_lifecycle():
    """Validates demo event generation, detection, and reset endpoints."""
    # 1. Reset demo
    r_reset = reset_demo()
    assert "reset successfully" in r_reset["message"]

    # 2. Generate events
    r_gen = generate_demo_events()
    assert r_gen["events_count"] > 0

    # 3. Run detection
    r_det = run_demo_detection()
    assert r_det["alerts_created"] > 0

    # 4. Verify events and alerts
    evts = list_events()
    assert evts["count"] > 0
    alrts = list_alerts()
    assert alrts["count"] > 0
