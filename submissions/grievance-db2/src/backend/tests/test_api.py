import pytest
from fastapi.testclient import TestClient

import sys
import os
# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from database import SessionLocal, init_db
from scripts.seed_data import seed_grievances


@pytest.fixture(scope="module", autouse=True)
def setup_db2_data():
    """Ensure IBM Db2 tables and seed data exist before running tests."""
    init_db()
    with SessionLocal() as db:
        seed_grievances(db)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    """Test health check endpoint against live IBM Db2."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["database"]["type"] == "IBM Db2"
    assert data["database"]["status"] == "connected"
    assert data["database"]["total_grievances"] >= 60


def test_list_departments(client):
    """Test listing of departments in IBM Db2."""
    response = client.get("/api/departments")
    assert response.status_code == 200
    departments = response.json()
    assert len(departments) >= 7
    codes = [d["code"] for d in departments]
    assert "water" in codes
    assert "electricity" in codes
    assert "roads" in codes


def test_get_demo_grievance(client):
    """Test fetching the demo grievance seeded in IBM Db2."""
    response = client.get("/api/grievances/GRV-2026-4821")
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    grv = result["data"]
    assert grv["tracking_id"] == "GRV-2026-4821"
    assert grv["citizen_name"] == "Amitabh Verma"
    assert grv["category"] == "water"
    assert len(grv["updates"]) >= 1


def test_create_grievance(client):
    """Test lodging a new citizen grievance in IBM Db2."""
    payload = {
        "citizen_name": "Ramesh Chandra",
        "contact": "9876501234 / ramesh.c@example.com",
        "category": "electricity",
        "subject": "Sparking transformer near community school",
        "description": "The local 100kVA transformer has been sparking during evening peak hours. Potential safety risk.",
        "ward": "Ward 14 - Rohini East",
        "priority": "Critical",
        "state": "Delhi (NCT)",
        "pincode": "110085",
        "latitude": 28.7152,
        "longitude": 77.1215
    }
    response = client.post("/api/grievances", json=payload)
    assert response.status_code == 201
    res = response.json()
    assert res["success"] is True
    assert "tracking_id" in res
    assert res["tracking_id"].startswith("GRV-2026-")

    # Verify grievance in database
    tracking_id = res["tracking_id"]
    get_res = client.get(f"/api/grievances/{tracking_id}")
    assert get_res.status_code == 200
    data = get_res.json()["data"]
    assert data["citizen_name"] == "Ramesh Chandra"
    assert data["status"] == "Filed"
    assert len(data["updates"]) >= 1
    assert data["updates"][0]["new_status"] == "Filed"


def test_list_grievances_with_filters(client):
    """Test filtering grievances in IBM Db2 by category, status, priority, and ward."""
    # Filter by category
    res_water = client.get("/api/grievances?category=water")
    assert res_water.status_code == 200
    data_water = res_water.json()
    assert data_water["total"] >= 10
    for item in data_water["items"]:
        assert item["category"].lower() == "water"

    # Filter by priority
    res_crit = client.get("/api/grievances?priority=Critical")
    assert res_crit.status_code == 200
    data_crit = res_crit.json()
    assert data_crit["total"] >= 5

    # Filter by status
    res_res = client.get("/api/grievances?status=Resolved")
    assert res_res.status_code == 200
    data_res = res_res.json()
    assert data_res["total"] >= 15


def test_update_grievance_status(client):
    """Test updating status and appending audit history in IBM Db2."""
    # First create a grievance
    payload = {
        "citizen_name": "Divya Prakash",
        "contact": "9811002233",
        "category": "roads",
        "subject": "Hazardous road pothole on main road",
        "description": "Deep depression on road causing severe traffic backup and risk of accidents.",
        "ward": "Ward 22 - Connaught Place",
        "priority": "High"
    }
    create_res = client.post("/api/grievances", json=payload)
    tracking_id = create_res.json()["tracking_id"]

    # Transition to Under Review
    patch_payload = {
        "status": "Under Review",
        "notes": "Docket assigned to PWD Assistant Engineer for inspection.",
        "updated_by": "Assistant Engineer",
        "priority": "High"
    }
    patch_res = client.patch(f"/api/grievances/{tracking_id}/status", json=patch_payload)
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "Under Review"

    # Transition to Resolved
    patch_resolved = {
        "status": "Resolved",
        "notes": "Pothole filled with cold mix bituminous concrete. Road restored to traffic.",
        "updated_by": "Executive Engineer"
    }
    patch_res2 = client.patch(f"/api/grievances/{tracking_id}/status", json=patch_resolved)
    assert patch_res2.status_code == 200
    assert patch_res2.json()["status"] == "Resolved"

    # Verify timeline in GET
    fetch_res = client.get(f"/api/grievances/{tracking_id}")
    grv_data = fetch_res.json()["data"]
    assert grv_data["status"] == "Resolved"
    assert grv_data["resolved_at"] is not None
    assert len(grv_data["updates"]) >= 3  # Filed -> Under Review -> Resolved


def test_get_nonexistent_grievance(client):
    """Test 404 response for invalid tracking ID in IBM Db2."""
    response = client.get("/api/grievances/GRV-2026-999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_stats(client):
    """Test statistical aggregation endpoint in IBM Db2."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_grievances"] >= 60
    assert "status_breakdown" in stats
    assert "category_breakdown" in stats
    assert "priority_breakdown" in stats
    assert stats["resolved_count"] > 0
    assert stats["resolution_rate"] > 0.0


def test_ai_triage_and_hotspot_detection(client):
    """
    Test automated AI Triage (LangChain) on grievance lodging and
    Db2 ward hotspot / duplicate detection.
    """
    payload = {
        "citizen_name": "Siddharth Malhotra",
        "contact": "9812345678",
        "category": "electricity",
        "subject": "Sparks and explosion hazard at transformer",
        "description": "Sparks flying continuously from 11kV transformer with live dangling wire right outside primary school. Emergency hazard.",
        "ward": "Ward 14 - Rohini East",
        "priority": "Medium"  # Should be elevated to Critical by AI Triage
    }
    response = client.post("/api/grievances", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["success"] is True
    assert "ai_triage" in data
    triage = data["ai_triage"]
    assert triage["priority"] == "Critical"
    assert triage["category"] == "electricity"
    assert len(triage["summary"]) > 5

    # Check that Db2 record persisted the AI triage columns
    tracking_id = data["tracking_id"]
    get_res = client.get(f"/api/grievances/{tracking_id}")
    db_record = get_res.json()["data"]
    assert db_record["ai_priority"] == "Critical"
    assert db_record["ai_category"] == "electricity"
    assert db_record["ai_summary"] is not None

    # Check hotspot alert
    assert "hotspot_alert" in data
    assert "is_hotspot" in data["hotspot_alert"]


def test_ask_the_data_natural_language_to_db2_sql(client):
    """
    Test 'Ask the Data' query engine converting natural language to IBM Db2 SQL
    and executing on live Db2 GRIEVDB.
    """
    # 1. Ward complaint aggregation query
    res1 = client.post("/api/ask", json={"question": "Which municipal ward has the highest number of grievances?"})
    assert res1.status_code == 200
    body1 = res1.json()
    assert "SELECT" in body1["generated_sql"].upper()
    assert "GRIEVANCES" in body1["generated_sql"].upper()
    assert "FETCH FIRST" in body1["generated_sql"].upper()
    assert body1["row_count"] > 0
    assert "ward" in [c.lower() for c in body1["columns"]]
    assert "natural_summary" in body1
    assert len(body1["natural_summary"]) > 10

    # 2. SLA breach query testing Db2 DAYS() date arithmetic
    res2 = client.post("/api/ask", json={"question": "Show all grievances that have breached the 15 day SLA"})
    assert res2.status_code == 200
    body2 = res2.json()
    assert "DAYS(CURRENT DATE) - DAYS(DATE(CREATED_AT))" in body2["generated_sql"].upper()
    assert "FETCH FIRST" in body2["generated_sql"].upper()
    assert "natural_summary" in body2


def test_ask_the_data_security_guardrails(client):
    """
    Test strict security guardrails rejecting destructive DDL/DML,
    semicolons, comments, and unauthorized tables.
    """
    from ai_service import validate_and_sanitize_sql

    # 1. Reject DROP TABLE
    with pytest.raises(ValueError, match="Security Violation"):
        validate_and_sanitize_sql("DROP TABLE grievances")

    # 2. Reject INSERT
    with pytest.raises(ValueError, match="Security Violation"):
        validate_and_sanitize_sql("INSERT INTO grievances (tracking_id) VALUES ('HACK')")

    # 3. Reject Semicolon (stacked statements)
    with pytest.raises(ValueError, match="Security Violation"):
        validate_and_sanitize_sql("SELECT * FROM grievances; DROP TABLE departments")

    # 4. Reject SQL comments
    with pytest.raises(ValueError, match="Security Violation"):
        validate_and_sanitize_sql("SELECT * FROM grievances -- bypass filter")

    # 5. Reject unauthorized tables
    with pytest.raises(ValueError, match="Security Violation"):
        validate_and_sanitize_sql("SELECT * FROM syscat.dbauth")

    # 6. Verify valid SELECT is sanitized with Db2 FETCH FIRST syntax
    safe_sql = validate_and_sanitize_sql("SELECT tracking_id, citizen_name FROM grievances")
    assert "FETCH FIRST 50 ROWS ONLY" in safe_sql


def test_advanced_analytics_endpoint(client):
    """
    Test GET /api/analytics returning IBM Db2 date arithmetic metrics,
    SLA breaches (>15 days), and civic distributions.
    """
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()

    assert data["total_grievances"] >= 60
    assert data["resolved_count"] > 0
    assert data["pending_count"] > 0
    assert data["resolution_rate"] > 0.0
    assert data["avg_resolution_days"] >= 0.0
    assert data["sla_breaches_count"] >= 0
    assert isinstance(data["sla_breached_dockets"], list)
    assert len(data["department_breakdown"]) > 0
    assert len(data["ward_breakdown"]) > 0
    assert "Critical" in data["priority_breakdown"]
    assert "water" in data["category_breakdown"]


def test_db2_stored_procedure_escalation(client):
    """
    Test invoking native IBM Db2 Stored Procedure SP_ESCALATE_OVERDUE
    which evaluates continuous date math on Db2 engine.
    """
    response = client.post("/api/escalate-overdue")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["procedure"] == "SP_ESCALATE_OVERDUE"
    assert "escalated_count" in res_data
    assert res_data["escalated_count"] >= 0


def test_officer_dockets_list(client):
    """
    Test officer console dockets list with Db2 date math (days_open)
    and department filtering.
    """
    # 1. Fetch active open dockets
    response = client.get("/api/officer/dockets")
    assert response.status_code == 200
    dockets = response.json()
    assert len(dockets) > 0
    first_docket = dockets[0]
    assert "tracking_id" in first_docket
    assert "days_open" in first_docket
    assert "is_sla_breached" in first_docket
    assert isinstance(first_docket["days_open"], int)
    assert first_docket["status"] in ["Filed", "Under Review", "Forwarded to Dept"]

    # 2. Filter by department
    res_water = client.get("/api/officer/dockets?department=water")
    assert res_water.status_code == 200
    water_dockets = res_water.json()
    assert len(water_dockets) > 0
    for doc in water_dockets:
        assert "water" in doc["category"].lower() or "jal" in (doc["department_name"] or "").lower()


def test_officer_ai_draft_action(client):
    """
    Test LangChain Officer Action Drafter generating formal bureaucratic notice.
    """
    response = client.post("/api/officer/draft-action", json={"tracking_id": "GRV-2026-4821"})
    assert response.status_code == 200
    data = response.json()

    assert data["tracking_id"] == "GRV-2026-4821"
    assert data["action_type"] in ["Field Inspection", "Show-Cause Notice", "Immediate Repair", "Interim Relief"]
    assert len(data["target_officer"]) > 3
    assert data["statutory_deadline_days"] >= 1
    assert len(data["drafted_order_text"]) > 20
    assert data["recommended_status"] in ["Forwarded to Dept", "Resolved"]
    assert "Action Drafter" in data["generated_by"]


def test_officer_resolve_docket(client):
    """
    Test Officer Quick Resolve executing atomic Db2 resolution & audit logging.
    """
    # First lodge a fresh grievance
    create_res = client.post("/api/grievances", json={
        "citizen_name": "Kavita Singhal",
        "contact": "9812981298",
        "category": "sanitation",
        "subject": "Overflowing waste bin outside market gate",
        "description": "Garbage has not been collected for three days causing foul smell and health hazard.",
        "ward": "Ward 12 - Karol Bagh",
        "priority": "High"
    })
    tracking_id = create_res.json()["tracking_id"]

    # Resolve docket as Officer
    resolve_payload = {
        "tracking_id": tracking_id,
        "officer_notes": "Dispatched zonal sanitary loader truck. Cleaned entire market perimeter and sprayed disinfectant.",
        "resolution_summary": "Garbage cleared and waste bin restored to operational condition.",
        "officer_name": "Sanitary Superintendent V.K. Rao"
    }
    resolve_res = client.post("/api/officer/resolve", json=resolve_payload)
    assert resolve_res.status_code == 200
    res_body = resolve_res.json()
    assert res_body["success"] is True
    assert res_body["status"] == "Resolved"

    # Verify status and audit history in Db2
    fetch_res = client.get(f"/api/grievances/{tracking_id}")
    grv_data = fetch_res.json()["data"]
    assert grv_data["status"] == "Resolved"
    assert grv_data["resolved_at"] is not None
    assert grv_data["ai_summary"] == "Garbage cleared and waste bin restored to operational condition."
    
    # Check that audit log has the officer resolution record
    officer_updates = [u for u in grv_data["updates"] if u["updated_by"] == "Sanitary Superintendent V.K. Rao"]
    assert len(officer_updates) > 0
    assert officer_updates[0]["new_status"] == "Resolved"
    assert "Cleaned entire market perimeter" in officer_updates[0]["notes"]


def test_db2_kernel_trigger_audit(client):
    """
    Test IBM Db2 Kernel Trigger (TRG_AUDIT_STATUS_CHANGE).
    Directly updates a grievance status/priority and verifies that the Db2 engine
    automatically writes an audit log row to grievance_updates.
    """
    # 1. Lodge a grievance to test
    create_res = client.post("/api/grievances", json={
        "citizen_name": "Ramesh Chander",
        "contact": "9876543210",
        "category": "electricity",
        "subject": "Fluctuating line voltage damaging appliances",
        "description": "Continuous voltage spikes exceeding 280V in Phase 2 residential blocks.",
        "ward": "Ward 18 - Vasant Kunj",
        "priority": "Medium"
    })
    assert create_res.status_code == 201
    tracking_id = create_res.json()["tracking_id"]

    # 2. Update status and priority via PATCH
    patch_res = client.patch(
        f"/api/grievances/{tracking_id}/status",
        json={
            "status": "Under Review",
            "priority": "High",
            "notes": "Escalated for line voltage inspection",
            "updated_by": "Zonal Superintending Engineer"
        }
    )
    assert patch_res.status_code == 200

    # 3. Fetch docket and inspect audit updates
    fetch_res = client.get(f"/api/grievances/{tracking_id}")
    assert fetch_res.status_code == 200
    grv_data = fetch_res.json()["data"]

    # Verify that the native Db2 kernel trigger created an audit row
    trigger_updates = [
        u for u in grv_data["updates"]
        if u["updated_by"] == "Db2 Engine (TRG_AUDIT_STATUS_CHANGE)"
    ]
    assert len(trigger_updates) >= 1, "Db2 Engine kernel trigger TRG_AUDIT_STATUS_CHANGE did not fire or record audit row"
    trigger_row = trigger_updates[-1]
    assert "Kernel Trigger Audit" in trigger_row["notes"]
    assert trigger_row["new_status"] == "Under Review"


def test_geo_hotspots_endpoint(client):
    """
    Test GIS Municipal Ward Geo-Hotspots Analytics endpoint (/api/analytics/geo-hotspots).
    Verifies that open grievance counts are aggregated by ward from IBM Db2 with accurate
    Delhi NCT latitude/longitude coordinates, SLA breach metrics, and GeoJSON formatting.
    """
    res = client.get("/api/analytics/geo-hotspots")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "total_wards" in data
    assert data["total_wards"] > 0
    assert "wards" in data
    assert len(data["wards"]) > 0

    # Verify structure of each ward entry
    sample_ward = data["wards"][0]
    required_keys = [
        "ward", "lat", "lng", "total_cases", 
        "critical_cases", "sla_breaches", "is_hotspot", "primary_category"
    ]
    for key in required_keys:
        assert key in sample_ward, f"Missing required key '{key}' in geo hotspot ward payload"

    # Verify latitude and longitude fall within Delhi NCR geographic bounding box
    assert 28.3 <= sample_ward["lat"] <= 28.9, f"Invalid latitude {sample_ward['lat']} for Delhi ward"
    assert 76.8 <= sample_ward["lng"] <= 77.4, f"Invalid longitude {sample_ward['lng']} for Delhi ward"

    # Verify counts are non-negative integers
    assert sample_ward["total_cases"] >= 0
    assert sample_ward["critical_cases"] >= 0
    assert sample_ward["sla_breaches"] >= 0
    assert isinstance(sample_ward["is_hotspot"], bool)

    # Verify GeoJSON FeatureCollection consistency
    assert "geojson" in data
    geojson = data["geojson"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == len(data["wards"])
    assert geojson["features"][0]["geometry"]["type"] == "Point"
    assert len(geojson["features"][0]["geometry"]["coordinates"]) == 2


def test_sahayak_agent_chat_docket_lookup(client):
    """
    Test Agentic Sahayak Assistant tool-calling: Docket Lookup (/api/sahayak/chat).
    Asks the agent 'What is the status of GRV-2026-1028?' and verifies that the agent
    autonomously selects and executes tool_track_docket against live IBM Db2.
    """
    payload = {"message": "What is the status of GRV-2026-1028?"}
    res = client.post("/api/sahayak/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["tool_used"] == "tool_track_docket"
    assert data["data_payload"] is not None
    assert data["data_payload"]["tracking_id"] == "GRV-2026-1028"
    assert data["data_payload"]["found"] is True
    assert "Ashok Khurana" in data["data_payload"]["citizen_name"]
    assert "GRV-2026-1028" in data["reply"]


def test_sahayak_agent_chat_ward_inquiry(client):
    """
    Test Agentic Sahayak Assistant tool-calling: Ward Inquiry (/api/sahayak/chat).
    Asks the agent 'Are there active complaints in Rohini?' and verifies that the agent
    autonomously selects and executes tool_ward_status against live IBM Db2 telemetry.
    """
    payload = {"message": "Are there active complaints in Rohini?"}
    res = client.post("/api/sahayak/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["tool_used"] == "tool_ward_status"
    assert data["data_payload"] is not None
    assert "Rohini" in data["data_payload"]["ward"]
    assert data["data_payload"]["total_cases"] > 0
    assert "open_cases" in data["data_payload"]
    assert "Rohini" in data["reply"]



