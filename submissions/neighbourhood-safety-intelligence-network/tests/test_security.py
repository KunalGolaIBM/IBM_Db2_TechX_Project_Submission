"""Security and integrity guarantees: access control, validation, state machine, auditing."""
import datetime
import re

from backend.app.api.v1.auth import login_throttle
from backend.app.database import base as db_base
from backend.app.models.entities import AuditEvent, ChildJourney

from conftest import auth_headers, unique_email

API = "/api/v1"


def _register(client, role="resident", password="Str0ngPass!", **extra):
    email = unique_email(role)
    res = client.post(f"{API}/auth/register", json={
        "email": email, "password": password, "full_name": "Test Person", "role": role, **extra,
    })
    return email, res


def _new_incident(client, headers, **overrides):
    body = {"title": "Broken streetlight on Lane 4", "description": "Lane 4 is completely dark after 7 pm.",
            "incident_type": "hazard", "priority": "P3_MODERATE", **overrides}
    res = client.post(f"{API}/incidents", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# --- Registration and authentication ---------------------------------------------------------

def test_admin_role_cannot_be_self_registered(client):
    _, res = _register(client, role="admin")
    assert res.status_code == 422


def test_registration_validates_input(client):
    assert _register(client, password="short")[1].status_code == 422
    assert client.post(f"{API}/auth/register", json={
        "email": "not-an-email", "password": "Str0ngPass!", "full_name": "X Y"}).status_code == 422
    assert _register(client, password="x" * 73)[1].status_code == 422  # beyond bcrypt's 72-byte limit


def test_duplicate_registration_conflicts(client):
    email, res = _register(client)
    assert res.status_code == 201
    again = client.post(f"{API}/auth/register", json={
        "email": email.upper(), "password": "Str0ngPass!", "full_name": "Dup"})
    assert again.status_code == 409


def test_self_registered_responder_needs_admin_verification(client, admin):
    email, res = _register(client, role="responder")
    assert res.status_code == 201
    user_id = res.json()["user_id"]
    pending = auth_headers(client, email, "Str0ngPass!")

    assert client.get(f"{API}/responders/assignments", headers=pending).status_code == 403

    resident = auth_headers(client, "resident@neighbourhood.org")
    incident = _new_incident(client, resident)
    assert client.post(f"{API}/incidents/{incident['id']}/acknowledge", headers=pending).status_code == 403

    # Residents cannot verify responders; admins can.
    assert client.post(f"{API}/responders/{user_id}/verify", headers=resident).status_code == 403
    assert client.post(f"{API}/responders/{user_id}/verify", headers=admin).status_code == 200
    ack = client.post(f"{API}/incidents/{incident['id']}/acknowledge", headers=pending)
    assert ack.status_code == 200, ack.text


def test_login_is_throttled_after_repeated_failures(client):
    email, res = _register(client)
    assert res.status_code == 201
    for _ in range(5):
        bad = client.post(f"{API}/auth/login", json={"email": email, "password": "wrong-password"})
        assert bad.status_code == 401
    blocked = client.post(f"{API}/auth/login", json={"email": email, "password": "Str0ngPass!"})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    login_throttle._failures.clear()


def test_unknown_email_and_wrong_password_look_identical(client):
    a = client.post(f"{API}/auth/login", json={"email": unique_email(), "password": "whatever123"})
    b = client.post(f"{API}/auth/login", json={"email": "resident@neighbourhood.org", "password": "wrong-pass"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    login_throttle._failures.clear()


def test_tampered_or_missing_token_is_rejected(client, resident):
    token = resident["Authorization"].split()[1]
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert client.get(f"{API}/profiles/me", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401
    assert client.get(f"{API}/profiles/me").status_code == 401
    assert client.get(f"{API}/profiles/me", headers={"Authorization": token}).status_code == 401


def test_security_headers_present(client):
    res = client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "no-referrer"


# --- Authorisation and privacy -----------------------------------------------------------------

def test_private_incidents_are_invisible_to_other_residents(client, resident):
    other = auth_headers(client, "maya.sen@neighbourhood.org")
    private = _new_incident(client, resident, incident_type="medical", title="Private medical issue")

    assert client.get(f"{API}/incidents/{private['id']}", headers=other).status_code == 404
    listed = [i["id"] for i in client.get(f"{API}/incidents", headers=other).json()]
    assert private["id"] not in listed


def test_public_alerts_hide_reporter_identity_and_coordinates(client, resident):
    other = auth_headers(client, "maya.sen@neighbourhood.org")
    alert = _new_incident(client, resident, latitude=28.61, longitude=77.21)

    seen = client.get(f"{API}/incidents/{alert['id']}", headers=other).json()
    assert seen["reporter_name"] is None and seen["latitude"] is None and seen["longitude"] is None
    own = client.get(f"{API}/incidents/{alert['id']}", headers=resident).json()
    assert own["reporter_name"] and own["latitude"] == 28.61


def test_roster_hides_responder_locations_from_residents(client, resident, responder):
    client.patch(f"{API}/responders/availability", headers=responder,
                 json={"is_available": True, "current_lat": 28.6, "current_lng": 77.2})
    as_resident = client.get(f"{API}/responders/roster", headers=resident).json()
    assert all(r["current_lat"] is None and r["current_lng"] is None for r in as_resident)
    as_staff = client.get(f"{API}/responders/roster", headers=responder).json()
    assert any(r["current_lat"] is not None for r in as_staff)


def test_residents_cannot_act_on_others_incidents(client, resident):
    other = auth_headers(client, "maya.sen@neighbourhood.org")
    alert = _new_incident(client, resident)
    res = client.post(f"{API}/incidents/{alert['id']}/status", json={"status": "resolved"}, headers=other)
    assert res.status_code == 403
    res = client.post(f"{API}/incidents/{alert['id']}/acknowledge", headers=other)
    assert res.status_code == 403


# --- Validation, state machine and integrity -------------------------------------------------

def test_input_limits_match_db2_column_sizes(client, resident):
    assert client.post(f"{API}/incidents", headers=resident, json={
        "title": "x" * 201, "description": "long title"}).status_code == 422
    assert client.post(f"{API}/incidents", headers=resident, json={
        "title": "Bad type", "description": "invalid type", "incident_type": "alien"}).status_code == 422
    assert client.post(f"{API}/sos", headers=resident, json={"latitude": 123.0}).status_code == 422


def test_incident_state_machine_rejects_illegal_transitions(client, resident, responder):
    inc = _new_incident(client, resident)
    url = f"{API}/incidents/{inc['id']}"
    assert client.post(f"{url}/acknowledge", headers=responder).status_code == 200
    assert client.post(f"{url}/acknowledge", headers=responder).status_code == 409   # already acknowledged
    assert client.post(f"{url}/status", json={"status": "resolved"}, headers=responder).status_code == 200
    reopened = client.post(f"{url}/status", json={"status": "on_scene"}, headers=responder)
    assert reopened.status_code == 409                                                 # closed is final
    assert client.post(f"{url}/status", json={"status": "teleported"}, headers=responder).status_code == 422


def test_reference_codes_are_unique_and_derived_from_identity(client, resident):
    codes = [_new_incident(client, resident)["reference_code"] for _ in range(5)]
    sos = client.post(f"{API}/sos", json={"latitude": 28.6, "longitude": 77.2}, headers=resident).json()
    codes.append(sos["reference_code"])
    assert len(set(codes)) == len(codes)
    assert all(re.fullmatch(r"(INC|SOS)-\d{6}-\d{5}", c) for c in codes)


def test_sos_records_alert_routing_and_audit_event(client, resident):
    sos = client.post(f"{API}/sos", json={"latitude": 28.6, "longitude": 77.2}, headers=resident)
    assert sos.status_code == 201
    body = sos.json()
    assert body["priority"] == "P1_CRITICAL"
    assert "trusted contact" in body["status_history"][0]["notes"]

    db = db_base.SessionLocal()
    try:
        audit = db.query(AuditEvent).filter(AuditEvent.action == "sos_triggered",
                                            AuditEvent.resource_id == str(body["id"])).one()
        assert audit.user_id == body["reporter_id"]
    finally:
        db.close()


def test_overdue_child_journeys_are_flagged(client, resident):
    res = client.post(f"{API}/children/journeys", headers=resident, json={
        "child_name": "Aarav", "origin": "Home", "destination": "School", "expected_duration_minutes": 20})
    assert res.status_code == 201
    journey_id = res.json()["id"]

    db = db_base.SessionLocal()
    try:
        journey = db.get(ChildJourney, journey_id)
        journey.expected_arrival_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
        db.commit()
    finally:
        db.close()

    journeys = client.get(f"{API}/children/journeys", headers=resident).json()
    assert next(j for j in journeys if j["id"] == journey_id)["status"] == "delayed"
    assert client.post(f"{API}/children/journeys", headers=resident, json={
        "child_name": "A", "origin": "Home", "destination": "School",
        "expected_duration_minutes": -5}).status_code == 422


def test_ai_triage_cannot_be_attached_to_someone_elses_incident(client, resident):
    other = auth_headers(client, "maya.sen@neighbourhood.org")
    private = _new_incident(client, resident, incident_type="medical", title="Fall in the bathroom")
    public = _new_incident(client, resident)
    body = {"raw_text": "Someone fell and is injured", "incident_id": private["id"]}
    assert client.post(f"{API}/ai/incident-assistance", json=body, headers=other).status_code == 404
    body["incident_id"] = public["id"]
    assert client.post(f"{API}/ai/incident-assistance", json=body, headers=other).status_code == 403
    assert client.post(f"{API}/ai/incident-assistance", json=body, headers=resident).status_code == 200
