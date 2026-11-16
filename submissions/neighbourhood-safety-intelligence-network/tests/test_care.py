"""Elder care, child journeys and profile endpoints."""
from conftest import auth_headers

API = "/api/v1"


def test_elder_checkin_and_assistance_request_flow(client, responder):
    elder = auth_headers(client, "elder.ramesh@neighbourhood.org")
    res = client.post(f"{API}/elder-care/checkins", json={"wellness_status": "needs_assistance", "notes": "Knee pain"},
                      headers=elder)
    assert res.status_code == 201 and res.json()["wellness_status"] == "needs_assistance"
    assert client.post(f"{API}/elder-care/checkins", json={"wellness_status": "sleepy"}, headers=elder).status_code == 422

    req = client.post(f"{API}/elder-care/assistance-requests", headers=elder,
                      json={"request_type": "medicine", "description": "BP tablets running out", "urgency": "high"})
    assert req.status_code == 201 and req.json()["status"] == "open"

    own = client.get(f"{API}/elder-care/assistance-requests", headers=elder).json()
    assert all(r["user_id"] == req.json()["user_id"] for r in own)
    staff_view = client.get(f"{API}/elder-care/assistance-requests", headers=responder).json()
    assert any(r["id"] == req.json()["id"] for r in staff_view)
    assert client.get(f"{API}/elder-care/checkins", headers=responder).status_code == 200
    assert any(c["notes"] == "Knee pain" for c in client.get(f"{API}/elder-care/checkins", headers=elder).json())


def test_child_journey_check_in_completes_once(client, resident):
    j = client.post(f"{API}/children/journeys", headers=resident,
                    json={"child_name": "Ira", "origin": "Home", "destination": "Music class", "expected_duration_minutes": 25})
    assert j.status_code == 201
    jid = j.json()["id"]
    done = client.post(f"{API}/children/journeys/{jid}/check-in", headers=resident,
                       json={"status": "completed", "notes": "Reached safely"})
    assert done.status_code == 200 and done.json()["actual_arrival_time"] and "Reached safely" in done.json()["notes"]
    assert client.post(f"{API}/children/journeys/{jid}/check-in", headers=resident, json={"status": "delayed"}).status_code == 409
    other = auth_headers(client, "maya.sen@neighbourhood.org")
    assert client.post(f"{API}/children/journeys/{jid}/check-in", headers=other, json={"status": "delayed"}).status_code == 404


def test_profile_read_and_validated_update(client, resident):
    me = client.get(f"{API}/profiles/me", headers=resident)
    assert me.status_code == 200 and me.json()["email"] == "resident@neighbourhood.org"
    upd = client.patch(f"{API}/profiles/me", headers=resident, json={"phone": "+91 98765 43210", "address": "Flat 402"})
    assert upd.status_code == 200 and upd.json()["phone"] == "+91 98765 43210"
    assert client.patch(f"{API}/profiles/me", headers=resident, json={"phone": "call me maybe"}).status_code == 422


def test_trusted_contact_lifecycle_and_isolation(client, resident):
    c = client.post(f"{API}/trusted-contacts", headers=resident,
                    json={"name": "Asha", "relationship": "Sister", "phone": "+91 90000 11111"})
    assert c.status_code == 201
    other = auth_headers(client, "maya.sen@neighbourhood.org")
    assert client.delete(f"{API}/trusted-contacts/{c.json()['id']}", headers=other).status_code == 404
    assert client.delete(f"{API}/trusted-contacts/{c.json()['id']}", headers=resident).status_code == 204


def test_hazard_report_and_listing(client, resident):
    h = client.post(f"{API}/community/hazards", headers=resident,
                    json={"title": "Fallen wire near gate", "hazard_type": "electrical", "severity": "high", "address": "Gate 3"})
    assert h.status_code == 201 and h.json()["status"] == "active"
    assert any(x["id"] == h.json()["id"] for x in client.get(f"{API}/community/hazards", headers=resident).json())
