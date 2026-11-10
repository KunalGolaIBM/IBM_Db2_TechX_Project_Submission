"""Smoke tests for BLACKSTART AI FastAPI app (no live Db2 required)."""

import os

# Configure CORS before app import so Settings sees the production-style value.
os.environ.setdefault(
    "CORS_ORIGINS",
    "https://blackstart-ai-web.onrender.com,http://localhost:5173",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.orchestration.graph import analyze_grid  # noqa: E402

client = TestClient(app)


def test_root_banner():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "BLACKSTART AI"
    assert body["database"] == "IBM Db2"


def test_health_endpoint_for_render_checks():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["application"] == "BLACKSTART AI"
    assert body["version"]


def test_db2_status_is_honest():
    response = client.get("/api/v1/db2/status")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["connected"], bool)
    assert isinstance(body["message"], str) and body["message"]


def test_api_v1_prefix_retained():
    for path in ("/api/v1/health", "/api/v1/db2/status"):
        assert client.get(path).status_code == 200
    # Unprefixed variants must not silently exist
    assert client.get("/health").status_code == 404


def test_cors_allows_configured_frontend_origin():
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "https://blackstart-ai-web.onrender.com"},
    )
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://blackstart-ai-web.onrender.com"
    )


def test_cors_blocks_unconfigured_origin():
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None


def test_five_agents_execute_offline():
    """LangGraph pipeline runs without Db2 using a minimal grid snapshot."""
    grid = {
        "plants": [
            {
                "plant_id": 1,
                "plant_name": "Test Plant",
                "plant_type": "THERMAL",
                "capacity_mw": "100.00",
                "status": "ONLINE",
                "region": "NORTH",
            }
        ],
        "substations": [
            {
                "substation_id": 1,
                "substation_name": "Sub A",
                "voltage_kv": "400.00",
                "load_mw": "100.00",
                "status": "ONLINE",
                "region": "NORTH",
            },
            {
                "substation_id": 2,
                "substation_name": "Sub B",
                "voltage_kv": "220.00",
                "load_mw": "80.00",
                "status": "ONLINE",
                "region": "EAST",
            },
        ],
        "lines": [
            {
                "line_id": 1,
                "line_name": "A-B Link",
                "from_substation": 1,
                "to_substation": 2,
                "capacity_mw": "100.00",
                "current_load_mw": "95.00",
                "status": "ONLINE",
            }
        ],
        "incidents": [
            {
                "incident_id": 1,
                "incident_type": "OVERLOAD",
                "severity": "HIGH",
                "location": "Sub B",
                "description": "Test incident",
                "status": "OPEN",
                "detected_at": "2026-01-01T00:00:00",
            }
        ],
    }

    state = analyze_grid(grid)
    assert state["events"], "graph should emit AGENT_EVENT records"
    result = state["result"]

    assert result["system"] == "BLACKSTART AI"
    assert result["agents_executed"] == [
        "VOLT",
        "PULSE",
        "CASCADE",
        "GUARDIAN",
        "BLACKSTART",
    ]
    assert result["execution_mode"] == "ADVISORY_ONLY"
    assert result["data_source"] == "IBM Db2"
    assert set(result["findings"].keys()) == {
        "volt",
        "pulse",
        "cascade",
        "guardian",
    }
    assert result["overall_risk"] in {"LOW", "MODERATE", "HIGH"}
    assert any("Do not execute switching" in r for r in result["recommendations"])
    # Overloaded line (95%) must be detected at the 80% threshold
    assert result["findings"]["volt"]["overloaded_lines"]
    assert result["findings"]["cascade"]["risk_level"] == "HIGH"
