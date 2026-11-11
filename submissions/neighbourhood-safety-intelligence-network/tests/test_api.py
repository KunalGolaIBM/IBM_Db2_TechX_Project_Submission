"""End-to-end API workflows (fixtures live in conftest.py)."""
from backend.app.ai.crewai.agents import crew_orchestrator
from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "database" in data
    assert data["database"]["mode"] in ["sqlite", "postgresql", "db2"]

def test_auth_login_and_profile(client):
    # Test seeded resident login
    response = client.post("/api/v1/auth/login", json={
        "email": "resident@neighbourhood.org",
        "password": "Password123!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "resident"

    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test profile access
    prof_res = client.get("/api/v1/profiles/me", headers=headers)
    assert prof_res.status_code == 200
    assert prof_res.json()["email"] == "resident@neighbourhood.org"

def test_trusted_contacts_workflow(client):
    login_res = client.post("/api/v1/auth/login", json={
        "email": "resident@neighbourhood.org",
        "password": "Password123!"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add contact
    add_res = client.post("/api/v1/trusted-contacts", json={
        "name": "Arjun Kapoor",
        "relationship": "Father",
        "phone": "+91 99887 76655",
        "email": "arjun@example.com",
        "can_receive_sos": True,
        "can_track_location": True
    }, headers=headers)
    assert add_res.status_code == 201
    contact_id = add_res.json()["id"]

    # Verify list
    list_res = client.get("/api/v1/trusted-contacts", headers=headers)
    assert list_res.status_code == 200
    contacts = list_res.json()
    assert any(c["id"] == contact_id for c in contacts)

    # Delete contact
    del_res = client.delete(f"/api/v1/trusted-contacts/{contact_id}", headers=headers)
    assert del_res.status_code == 204

def test_incident_lifecycle_cross_client(client):
    # 1. Resident creates an incident
    res_login = client.post("/api/v1/auth/login", json={
        "email": "resident@neighbourhood.org",
        "password": "Password123!"
    })
    res_token = res_login.json()["access_token"]
    res_headers = {"Authorization": f"Bearer {res_token}"}

    create_res = client.post("/api/v1/incidents", json={
        "title": "Suspicious package near community center entrance",
        "description": "Unattended bag with ticking sound or battery pack observed on the steps.",
        "incident_type": "hazard",
        "priority": "P2_HIGH",
        "location_address": "Community Hall, Gate 1"
    }, headers=res_headers)
    assert create_res.status_code == 201
    inc = create_res.json()
    incident_id = inc["id"]
    assert inc["status"] == "reported"

    # 2. Responder logs in and acknowledges the incident
    resp_login = client.post("/api/v1/auth/login", json={
        "email": "responder@neighbourhood.org",
        "password": "Password123!"
    })
    resp_token = resp_login.json()["access_token"]
    resp_headers = {"Authorization": f"Bearer {resp_token}"}

    ack_res = client.post(f"/api/v1/incidents/{incident_id}/acknowledge", headers=resp_headers)
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "acknowledged"

    # 3. Responder updates status to 'on_scene'
    status_res = client.post(f"/api/v1/incidents/{incident_id}/status", json={
        "status": "on_scene",
        "notes": "Responder arrived on scene. Area cordoned off; package inspected."
    }, headers=resp_headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "on_scene"

    # 4. Resident checks incident and sees the updated timeline
    check_res = client.get(f"/api/v1/incidents/{incident_id}", headers=res_headers)
    assert check_res.status_code == 200
    detail = check_res.json()
    assert detail["status"] == "on_scene"
    assert len(detail["status_history"]) >= 3

def test_sos_trigger(client):
    login_res = client.post("/api/v1/auth/login", json={
        "email": "resident@neighbourhood.org",
        "password": "Password123!"
    })
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    sos_res = client.post("/api/v1/sos", json={
        "latitude": 12.9716,
        "longitude": 77.5946,
        "location_address": "7th Cross, Near Metro Station",
        "description": "Emergency distress button activated."
    }, headers=headers)
    assert sos_res.status_code == 201
    sos_data = sos_res.json()
    assert sos_data["priority"] == "P1_CRITICAL"
    assert sos_data["status"] == "reported"

def test_haystack_rag_retrieval():
    # Test valid query
    res = retrieve_safety_guidance("What is the protocol for emergency SOS and medical dispatch?")
    assert res["found"] is True
    assert len(res["results"]) > 0
    assert "source" in res["results"][0]

    # Test unknown query fallback
    fallback = retrieve_safety_guidance("Quantum astrophysics spaceship orbit")
    assert fallback["found"] is False

def test_crewai_agent_workflow():
    report = "A car is blocking the fire hydrant and three dogs are barking aggressively near 12th Avenue playground."
    out = crew_orchestrator.run_incident_assistance_workflow(report)
    assert "parsed_category" in out
    assert "suggested_priority" in out
    assert "immediate_safety_checklist" in out
    assert len(out["immediate_safety_checklist"]) > 0
    assert "advisory_notice" in out


def test_ai_triage_persists_analysis(client):
    login = client.post("/api/v1/auth/login", json={
        "email": "resident@neighbourhood.org",
        "password": "Password123!"
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post("/api/v1/incidents", json={
        "title": "Elderly neighbour fell on stairs",
        "description": "Neighbour fell near Block C stairwell and cannot stand up.",
        "incident_type": "medical",
        "priority": "P2_HIGH",
        "location_address": "Block C stairwell"
    }, headers=headers)
    assert created.status_code == 201
    incident_id = created.json()["id"]

    payload = {
        "raw_text": "Elderly neighbour fell on the stairs near Block C and has an injury, needs a doctor.",
        "incident_id": incident_id,
    }
    first = client.post("/api/v1/ai/incident-assistance", json=payload, headers=headers)
    assert first.status_code == 200
    first_id = first.json()["persisted_analysis_id"]
    assert first_id is not None

    # Re-running triage updates the same row instead of creating a duplicate.
    second = client.post("/api/v1/ai/incident-assistance", json=payload, headers=headers)
    assert second.json()["persisted_analysis_id"] == first_id

    missing = client.post("/api/v1/ai/incident-assistance",
                          json={"raw_text": "test report", "incident_id": 999999}, headers=headers)
    assert missing.status_code == 404
