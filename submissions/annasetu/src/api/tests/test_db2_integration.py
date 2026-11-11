"""Opt-in end-to-end checks against a separate IBM Db2 test database.

Run with ANNASETU_INTEGRATION=1 and DB2_NAME=ANNATEST after creating that
database. This keeps test batches out of the AnnaSetu demo database.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app.config import settings

pytestmark = pytest.mark.skipif(os.getenv("ANNASETU_INTEGRATION") != "1", reason="live Db2 test is opt-in")


@pytest.fixture(scope="session")
def client():
    if settings.db2_name.upper() != "ANNATEST":
        pytest.fail("Refusing to run live integration tests outside DB2_NAME=ANNATEST")
    from api.app.main import app
    with TestClient(app) as test_client:
        yield test_client


def access_token(client, email):
    from api.app import db
    from api.app.security import issue_token

    user = db.row("SELECT USER_ID,EMAIL,DISPLAY_NAME,ROLE FROM USERS WHERE LOWER(EMAIL)=LOWER(?)", (email,))
    assert user is not None, f"Expected test role account {email} to exist in the isolated ANNATEST database."
    return issue_token({
        "user_id": user["user_id"].strip(), "email": user["email"],
        "display_name": user["display_name"], "role": user["role"],
    })


def create_batch(client, donor_token, title, quantity_kg=1.0, category="prepared meals", use_by=None):
    now = datetime.now(timezone.utc)
    if not title.startswith("SYNTHETIC QA | "):
        title = f"SYNTHETIC QA | {title}"
    response = client.post("/api/food", headers={"Authorization": f"Bearer {donor_token}"}, json={
        "title": title,
        "category": category,
        "quantity_kg": quantity_kg,
        "prepared_at": (now - timedelta(hours=1)).isoformat(),
        "use_by": (use_by or now + timedelta(hours=8)).isoformat(),
        "storage_type": "cold",
        "storage_temp_c": 4.0,
        "allergens": ["milk"],
        "allergens_confirmed": True,
        "ingredients": ["rice", "vegetables"],
        "pickup_address": "SYNTHETIC QA location; no pickup",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "storage_note": "SYNTHETIC QA only; no real food or pickup.",
    })
    assert response.status_code == 201, response.text
    return response.json()["batch_id"]


def create_synthetic_receivers(capacities, owner_emails=None):
    from api.app import db

    owner_emails = owner_emails or ["admin@annasetu.local"] * len(capacities)
    owners = [db.row("SELECT USER_ID FROM USERS WHERE EMAIL=?", (email,)) for email in owner_emails]
    assert len(owners) == len(capacities) and all(owners)
    conn = db.connect()
    created = []
    try:
        for capacity, owner in zip(capacities, owners):
            receiver_id = str(uuid4())
            name = f"SYNTHETIC QA receiver {uuid4().hex[:8]}"
            db.execute(
                """INSERT INTO NGOS (NGO_ID,OWNER_USER_ID,NAME,VERIFIED,AVAILABLE_KG,
                   ACCEPTED_CATEGORIES,STORAGE_CAPABILITIES,LATITUDE,LONGITUDE,RECEIVING_HOURS,ACTIVE)
                   VALUES (?,?,?,1,?,?,?,?,?,?,1)""",
                (receiver_id, owner["user_id"], name, capacity, json.dumps(["prepared meals"]),
                 "cold,hot", 12.9716, 77.5946, "SYNTHETIC QA only; no real receiving site"), conn,
            )
            created.append({"ngo_id": receiver_id, "name": name, "available_kg": capacity})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return created


def create_synthetic_ngo_owner():
    from api.app import db
    from api.app.security import password_hash

    user_id = str(uuid4())
    email = f"synthetic-qa-{uuid4().hex[:12]}@annasetu.local"
    password = f"{uuid4().hex}A1!"
    db.execute("INSERT INTO USERS (USER_ID,EMAIL,DISPLAY_NAME,ROLE,PASSWORD_HASH) VALUES (?,?,?,?,?)",
               (user_id, email, "SYNTHETIC QA NGO Owner", "ngo", password_hash(password)))
    return {"user_id": user_id, "email": email, "display_name": "SYNTHETIC QA NGO Owner",
            "role": "ngo", "password": password}


def test_real_db2_food_allocation_otp_rag_and_audit(client):
    from api.app import db
    from api.app.config import settings
    from api.app.seed import DEMO_USERS
    from api.app.security import password_matches

    health = client.get("/api/health")
    assert health.status_code == 200, health.text
    assert health.json()["database"] == "IBM Db2"
    listed_accounts = client.get("/api/auth/demo-accounts")
    assert listed_accounts.status_code == 200
    assert {row["role"] for row in listed_accounts.json()} == {role for _, role in DEMO_USERS.values()}
    assert all(set(row) == {"role"} for row in listed_accounts.json())
    for email, (_, expected_role) in DEMO_USERS.items():
        stored_user = db.row("SELECT ROLE,PASSWORD_HASH FROM USERS WHERE LOWER(EMAIL)=LOWER(?)", (email,))
        assert stored_user is not None
        assert stored_user["role"] == expected_role
        assert password_matches(settings.demo_password, stored_user["password_hash"])
        login_response = client.post("/api/auth/login", json={"email": email, "password": settings.demo_password})
        assert login_response.status_code == 200, f"Demo login failed for role {expected_role}."
        assert login_response.json()["user"]["role"] == expected_role
        role_login = client.post("/api/auth/demo-login", json={"role": expected_role, "password": settings.demo_password})
        assert role_login.status_code == 200, f"Role-only demo login failed for {expected_role}."
        assert role_login.json()["user"]["role"] == expected_role
        assert role_login.json()["user"]["email"] == ""
        role_me = client.get("/api/me", headers={"Authorization": f"Bearer {role_login.json()['access_token']}"})
        assert role_me.status_code == 200 and role_me.json()["role"] == expected_role
        assert role_me.json()["email"] == ""
        bad_role_login = client.post("/api/auth/demo-login", json={
            "role": expected_role, "password": "known-incorrect-qa-password1!"
        })
        assert bad_role_login.status_code == 401
    bad_password = client.post("/api/auth/login", json={
        "email": "admin@annasetu.local", "password": "known-incorrect-qa-password1!"
    })
    assert bad_password.status_code == 401
    unknown_user = client.post("/api/auth/login", json={
        "email": "unknown-qa-account@annasetu.local", "password": "known-incorrect-qa-password1!"
    })
    assert unknown_user.status_code == 401
    requested_email_exists = db.row(
        "SELECT COUNT(*) AS N FROM USERS WHERE LOWER(EMAIL)=LOWER(?)", ("tournamentgaming09@gmail.com",)
    )
    # Only print a boolean diagnostic; never disclose user data from Db2.
    print(f"requested email exists: {bool(requested_email_exists and requested_email_exists['n'])}")
    admin_token = access_token(client, "admin@annasetu.local")
    donor_token = access_token(client, "donor@annasetu.local")
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_synthetic_receivers([1800.0, 1200.0], ["ngo@annasetu.local", "admin@annasetu.local"])
    demo_capacity_before = {row["ngo_id"].strip(): float(row["available_kg"])
                            for row in db.rows("SELECT NGO_ID,AVAILABLE_KG FROM NGOS WHERE NAME NOT LIKE 'SYNTHETIC QA%'")}
    batch_id = create_batch(client, donor_token, f"food passport allocation {uuid4().hex[:8]}", quantity_kg=2500.0)

    stored = db.row("SELECT TITLE FROM FOOD_BATCHES WHERE BATCH_ID=?", (batch_id,))
    assert stored["title"].startswith("SYNTHETIC QA | ")
    assert int(db.row("SELECT COUNT(*) AS N FROM SAFETY_OBSERVATIONS WHERE BATCH_ID=?", (batch_id,))["n"]) == 1

    before_review = client.get(f"/api/food/{batch_id}/evaluate", headers=headers)
    assert before_review.status_code == 200
    assert before_review.json()["status"] == "HOLD"
    assert before_review.json()["remaining_minutes"] > 0
    blocked_allocation = client.post(f"/api/food/{batch_id}/allocate", headers=headers, json={})
    assert blocked_allocation.status_code == 409
    assert int(db.row("SELECT COUNT(*) AS N FROM RESCUES WHERE BATCH_ID=?", (batch_id,))["n"]) == 0

    reviewed = client.post(f"/api/food/{batch_id}/verify", headers=headers, json={
        "decision": "verified", "notes": "SYNTHETIC QA verifier reviewed the test evidence."
    })
    assert reviewed.status_code == 200, reviewed.text
    feasibility = client.get(f"/api/food/{batch_id}/evaluate", headers=headers).json()
    assert feasibility["status"] == "FEASIBLE", feasibility
    assert feasibility["candidates"][0]["estimated_transit_minutes"] == 15
    assert all(candidate["name"].startswith("SYNTHETIC QA") for candidate in feasibility["candidates"][:2])
    assert int(db.row("SELECT COUNT(*) AS N FROM HUMAN_VERIFICATIONS WHERE BATCH_ID=?", (batch_id,))["n"]) == 1

    allocation_response = client.post(f"/api/food/{batch_id}/allocate", headers=headers, json={})
    assert allocation_response.status_code == 201, allocation_response.text
    result = allocation_response.json()
    allocations = result["allocated"]
    assert len(allocations) == 2, allocations
    assert [float(item["allocated_kg"]) for item in allocations] == pytest.approx([1800.0, 700.0])
    assert result["unallocated_kg"] == pytest.approx(0)
    assert all(item["ngo_name"].startswith("SYNTHETIC QA") for item in allocations)
    first, second = allocations
    volunteer_headers = {"Authorization": f"Bearer {access_token(client, 'volunteer@annasetu.local')}"}
    ngo_headers = {"Authorization": f"Bearer {access_token(client, 'ngo@annasetu.local')}"}
    donor_headers = {"Authorization": f"Bearer {donor_token}"}
    pickup_payload = {"stage": "pickup", "otp": first["one_time_codes"]["pickup"]}
    assert client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=volunteer_headers, json=pickup_payload).status_code == 403
    wrong_pickup = client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=donor_headers, json={
        "stage": "pickup", "otp": "000000" if first["one_time_codes"]["pickup"] != "000000" else "000001"
    })
    assert wrong_pickup.status_code == 400
    pickup = client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=donor_headers, json=pickup_payload)
    assert pickup.status_code == 200, pickup.text

    delivery_payload = {"stage": "delivery", "otp": first["one_time_codes"]["delivery"]}
    assert client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=donor_headers, json=delivery_payload).status_code == 403
    assert client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=ngo_headers, json=delivery_payload).status_code == 403
    delivery = client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=volunteer_headers, json=delivery_payload)
    assert delivery.status_code == 200, delivery.text

    distribution_payload = {"stage": "distribution", "otp": first["one_time_codes"]["distribution"],
                            "actual_distributed_kg": 1650.0}
    missing_quantity = client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=ngo_headers, json={
        "stage": "distribution", "otp": first["one_time_codes"]["distribution"]
    })
    assert missing_quantity.status_code == 422
    excess_quantity = client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=ngo_headers, json={
        **distribution_payload, "actual_distributed_kg": 1801.0
    })
    assert excess_quantity.status_code == 422
    assert client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=volunteer_headers, json=distribution_payload).status_code == 403
    distribution = client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=ngo_headers, json=distribution_payload)
    assert distribution.status_code == 200, distribution.text
    assert distribution.json()["actual_distributed_kg"] == pytest.approx(1650.0)

    wrong_order = client.post(f"/api/rescues/{first['rescue_id']}/confirm", headers=headers, json={
        "stage": "pickup", "otp": first["one_time_codes"]["pickup"]
    })
    assert wrong_order.status_code == 409
    second_pickup = client.post(f"/api/rescues/{second['rescue_id']}/confirm", headers=donor_headers, json={
        "stage": "pickup", "otp": second["one_time_codes"]["pickup"]
    })
    assert second_pickup.status_code == 200, second_pickup.text
    failure = client.post(f"/api/rescues/{second['rescue_id']}/fail", headers=volunteer_headers, json={
        "reason": "SYNTHETIC QA delivery failed after pickup; no real food moved."
    })
    assert failure.status_code == 200, failure.text

    persisted_rescues = db.rows("""SELECT R.STATUS,R.PICKED_UP_AT,R.DELIVERED_AT,R.DISTRIBUTED_AT,N.NAME,N.AVAILABLE_KG,
       JSON_VALUE(CAST(A.EVENT_DATA AS CLOB(4000)), '$.data.actual_distributed_kg'
         RETURNING DECIMAL(10,2) NULL ON EMPTY NULL ON ERROR) AS ACTUAL_DISTRIBUTED_KG
       FROM RESCUES R JOIN NGOS N ON N.NGO_ID=R.NGO_ID
       LEFT JOIN AUDIT_EVENTS A ON A.ENTITY_TYPE='rescue' AND A.ENTITY_ID=R.RESCUE_ID
         AND A.EVENT_TYPE='DISTRIBUTION_CONFIRMED'
       WHERE R.BATCH_ID=? ORDER BY R.CREATED_AT""", (batch_id,))
    assert persisted_rescues[0]["status"] == "distributed"
    assert all(persisted_rescues[0][field] is not None for field in ("picked_up_at", "delivered_at", "distributed_at"))
    assert float(persisted_rescues[0]["actual_distributed_kg"]) == pytest.approx(1650.0)
    assert persisted_rescues[1]["status"] == "failed"
    assert float(persisted_rescues[1]["available_kg"]) == pytest.approx(1200.0)
    demo_capacity_after = {row["ngo_id"].strip(): float(row["available_kg"])
                           for row in db.rows("SELECT NGO_ID,AVAILABLE_KG FROM NGOS WHERE NAME NOT LIKE 'SYNTHETIC QA%'")}
    assert demo_capacity_after == demo_capacity_before

    passport = client.get(f"/api/food/{batch_id}/passport", headers=headers).json()
    assert passport["batch"]["human_verified"] is True
    assert len(passport["observations"]) == 1
    assert len(passport["verifications"]) == 1
    assert len(passport["audit_events"]) >= 9
    distribution_audit = [event for event in passport["audit_events"]
                          if event["event_type"] == "DISTRIBUTION_CONFIRMED"]
    assert len(distribution_audit) == 1
    assert json.loads(distribution_audit[0]["event_data"])["data"]["actual_distributed_kg"] == pytest.approx(1650.0)
    assert client.get("/api/audit/verify", headers=headers).json()["valid"] is True
    assert client.patch("/api/audit/events/1", headers=headers, json={"event_type": "rewritten"}).status_code in (404, 405)
    assert client.delete("/api/audit/events/1", headers=headers).status_code in (404, 405)

    vector = client.get("/api/policy/status", headers=headers).json()
    assert vector["ready"] is True, vector
    retrieval = client.post("/api/policy/ask", headers=headers, json={
        "question": "What temperature should chilled food be stored at?"
    })
    assert retrieval.status_code == 200, retrieval.text
    assert retrieval.json()["sources"]

    dashboard = client.get("/api/dashboard", headers=headers).json()
    metrics = dashboard["metrics"]
    expected_donated = float(db.row("SELECT COALESCE(SUM(QUANTITY_KG),0) AS N FROM FOOD_BATCHES")["n"])
    expected_stages = db.row("""SELECT
       COALESCE(SUM(CASE WHEN R.STATUS IN ('picked_up','delivered','distributed') THEN R.ALLOCATED_KG ELSE 0 END),0) AS COLLECTED,
       COALESCE(SUM(CASE WHEN R.STATUS IN ('delivered','distributed') THEN R.ALLOCATED_KG ELSE 0 END),0) AS DELIVERED,
       COALESCE(SUM(CASE WHEN R.STATUS='distributed' THEN
         COALESCE(JSON_VALUE(CAST(A.EVENT_DATA AS CLOB(4000)), '$.data.actual_distributed_kg'
           RETURNING DECIMAL(10,2) NULL ON EMPTY NULL ON ERROR),R.ALLOCATED_KG) ELSE 0 END),0) AS DISTRIBUTED
       FROM RESCUES R LEFT JOIN AUDIT_EVENTS A ON A.ENTITY_TYPE='rescue' AND A.ENTITY_ID=R.RESCUE_ID
         AND A.EVENT_TYPE='DISTRIBUTION_CONFIRMED'""")
    expected_hold = int(db.row("SELECT COUNT(*) AS N FROM FOOD_BATCHES WHERE STATUS='hold'")["n"])
    assert metrics["donated_kg"] == pytest.approx(expected_donated)
    assert metrics["collected_kg"] == pytest.approx(float(expected_stages["collected"]))
    assert metrics["delivered_kg"] == pytest.approx(float(expected_stages["delivered"]))
    assert metrics["distributed_kg"] == pytest.approx(float(expected_stages["distributed"]))
    assert metrics["hold_batches"] == expected_hold
    since = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(days=30)
    distributed = db.row("""SELECT COALESCE(SUM(COALESCE(JSON_VALUE(CAST(A.EVENT_DATA AS CLOB(4000)),
       '$.data.actual_distributed_kg' RETURNING DECIMAL(10,2) NULL ON EMPTY NULL ON ERROR),R.ALLOCATED_KG)),0) AS TOTAL
       FROM RESCUES R
       JOIN FOOD_BATCHES F ON F.BATCH_ID=R.BATCH_ID
       LEFT JOIN AUDIT_EVENTS A ON A.ENTITY_TYPE='rescue' AND A.ENTITY_ID=R.RESCUE_ID
         AND A.EVENT_TYPE='DISTRIBUTION_CONFIRMED'
       WHERE F.CREATED_AT>=? AND R.STATUS='distributed'""", (since,))
    assert sum(float(item["distributed_kg"]) for item in dashboard["trend"]) == pytest.approx(float(distributed["total"]))


def test_allocation_stops_at_synthetic_receiver_capacity(client):
    from api.app import db

    owner = create_synthetic_ngo_owner()
    login = client.post("/api/auth/login", json={"email": owner["email"], "password": owner["password"]})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["role"] == "ngo"
    ngo_token = login.json()["access_token"]
    admin_token = access_token(client, "admin@annasetu.local")
    donor_token = access_token(client, "donor@annasetu.local")
    ngo_headers = {"Authorization": f"Bearer {ngo_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    demo_capacity_before = {row["ngo_id"].strip(): float(row["available_kg"])
                            for row in db.rows("SELECT NGO_ID,AVAILABLE_KG FROM NGOS WHERE NAME NOT LIKE 'SYNTHETIC QA%'")}
    receiver_id = str(uuid4())
    conn = db.connect()
    try:
        db.execute("""INSERT INTO NGOS (NGO_ID,OWNER_USER_ID,NAME,VERIFIED,AVAILABLE_KG,
                    ACCEPTED_CATEGORIES,STORAGE_CAPABILITIES,LATITUDE,LONGITUDE,RECEIVING_HOURS,ACTIVE)
                    VALUES (?,?,?,1,180,?,?,?, ?,?,1)""",
                   (receiver_id, owner["user_id"], f"SYNTHETIC QA capacity cap {uuid4().hex[:8]}",
                    json.dumps(["prepared meals"]), "cold", 12.9716, 77.5946,
                    "SYNTHETIC QA only; no real receiving site"), conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    batch_id = create_batch(client, donor_token, f"capacity capped allocation {uuid4().hex[:8]}", quantity_kg=250.0)
    verified = client.post(f"/api/food/{batch_id}/verify", headers=admin_headers, json={
        "decision": "verified", "notes": "SYNTHETIC QA verifier checked the capacity-cap test batch."
    })
    assert verified.status_code == 200, verified.text
    allocation = client.post(f"/api/food/{batch_id}/allocate", headers=ngo_headers, json={})
    assert allocation.status_code == 201, allocation.text
    result = allocation.json()
    assert result["allocated_kg"] == pytest.approx(180.0)
    assert result["unallocated_kg"] == pytest.approx(70.0)
    assert len(result["allocated"]) == 1
    assert result["allocated"][0]["ngo_id"] == receiver_id
    assert float(db.row("SELECT AVAILABLE_KG FROM NGOS WHERE NGO_ID=?", (receiver_id,))["available_kg"]) == pytest.approx(0.0)

    released = client.post(f"/api/rescues/{result['allocated'][0]['rescue_id']}/fail", headers=admin_headers, json={
        "reason": "SYNTHETIC QA only; return reserved test capacity."
    })
    assert released.status_code == 200, released.text
    assert float(db.row("SELECT AVAILABLE_KG FROM NGOS WHERE NGO_ID=?", (receiver_id,))["available_kg"]) == pytest.approx(180.0)
    db.execute("UPDATE NGOS SET AVAILABLE_KG=0 WHERE NGO_ID=?", (receiver_id,))
    no_capacity_batch = create_batch(client, donor_token, f"zero receiver capacity {uuid4().hex[:8]}")
    review = client.post(f"/api/food/{no_capacity_batch}/verify", headers=admin_headers, json={
        "decision": "verified", "notes": "SYNTHETIC QA zero-capacity verification."
    })
    assert review.status_code == 200, review.text
    no_capacity = client.post(f"/api/food/{no_capacity_batch}/allocate", headers=ngo_headers, json={})
    assert no_capacity.status_code == 409
    assert int(db.row("SELECT COUNT(*) AS N FROM RESCUES WHERE BATCH_ID=?", (no_capacity_batch,))["n"]) == 0
    assert float(db.row("SELECT AVAILABLE_KG FROM NGOS WHERE NGO_ID=?", (receiver_id,))["available_kg"]) == pytest.approx(0.0)
    demo_capacity_after = {row["ngo_id"].strip(): float(row["available_kg"])
                           for row in db.rows("SELECT NGO_ID,AVAILABLE_KG FROM NGOS WHERE NAME NOT LIKE 'SYNTHETIC QA%'")}
    assert demo_capacity_after == demo_capacity_before


def test_expired_batch_is_infeasible_even_without_a_receiver(client):
    donor_token = access_token(client, "donor@annasetu.local")
    admin_headers = {"Authorization": f"Bearer {access_token(client, 'admin@annasetu.local')}"}
    batch_id = create_batch(
        client, donor_token, f"expired no-match evaluation {uuid4().hex[:8]}",
        category="SYNTHETIC QA unmatched category",
        use_by=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    result = client.get(f"/api/food/{batch_id}/evaluate", headers=admin_headers)
    assert result.status_code == 200, result.text
    evaluation = result.json()
    assert evaluation["status"] == "INFEASIBLE"
    assert evaluation["remaining_minutes"] <= 0
    assert evaluation["candidates"] == []
    assert any("use-by time has passed" in reason for reason in evaluation["reasons"])


def test_real_db2_failed_rescue_releases_capacity(client):
    from api.app import db

    admin_token = access_token(client, "admin@annasetu.local")
    donor_token = access_token(client, "donor@annasetu.local")
    headers = {"Authorization": f"Bearer {admin_token}"}
    receiver = db.row("""SELECT NGO_ID,AVAILABLE_KG FROM NGOS WHERE NAME LIKE 'SYNTHETIC QA%'
       AND AVAILABLE_KG>0 ORDER BY AVAILABLE_KG DESC FETCH FIRST 1 ROW ONLY""")
    assert receiver is not None, "A synthetic QA receiver is required for the isolated allocation test."
    capacity_before = float(receiver["available_kg"])
    batch_id = create_batch(client, donor_token, f"failed rescue capacity {uuid4().hex[:8]}")
    assert client.post(f"/api/food/{batch_id}/verify", headers=headers, json={
        "decision": "verified", "notes": "SYNTHETIC QA verifier reviewed the failure-test batch."
    }).status_code == 200
    allocation_response = client.post(f"/api/food/{batch_id}/allocate", headers=headers, json={})
    assert allocation_response.status_code == 201, allocation_response.text
    rescue = allocation_response.json()["allocated"][0]
    assert rescue["ngo_id"] == receiver["ngo_id"].strip()
    capacity_reserved = float(db.row("SELECT AVAILABLE_KG FROM NGOS WHERE NGO_ID=?", (rescue["ngo_id"],))["available_kg"])
    assert capacity_reserved == pytest.approx(capacity_before - float(rescue["allocated_kg"]))
    failure = client.post(f"/api/rescues/{rescue['rescue_id']}/fail", headers=headers, json={
        "reason": "SYNTHETIC QA only; release this test capacity reservation."
    })
    assert failure.status_code == 200, failure.text
    capacity_after = float(db.row("SELECT AVAILABLE_KG FROM NGOS WHERE NGO_ID=?", (rescue["ngo_id"],))["available_kg"])
    assert capacity_after == pytest.approx(capacity_before)


def test_verified_ngo_can_review_open_food(client):
    donor_token = access_token(client, "donor@annasetu.local")
    ngo_token = access_token(client, "ngo@annasetu.local")
    batch_id = create_batch(client, donor_token, f"NGO review test meal {uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {ngo_token}"}

    passport = client.get(f"/api/food/{batch_id}/passport", headers=headers)
    assert passport.status_code == 200, passport.text
    evaluation = client.get(f"/api/food/{batch_id}/evaluate", headers=headers)
    assert evaluation.status_code == 200, evaluation.text
    assert evaluation.json()["candidates"]


def test_db2_triggers_reject_audit_and_evidence_mutation(client):
    from api.app import db

    conn = db.connect()
    try:
        batch = db.row("""SELECT F.BATCH_ID FROM FOOD_BATCHES F
           WHERE F.TITLE LIKE 'SYNTHETIC QA | %'
             AND EXISTS (SELECT 1 FROM HUMAN_VERIFICATIONS V WHERE V.BATCH_ID=F.BATCH_ID)
           ORDER BY F.CREATED_AT DESC FETCH FIRST 1 ROW ONLY""", conn=conn)
        assert batch is not None, "Expected a labelled synthetic QA batch with verification evidence."
        batch_id = batch["batch_id"].strip()
        audit = db.row("""SELECT EVENT_ID AS RECORD_ID FROM AUDIT_EVENTS
           WHERE ENTITY_TYPE='food_batch' AND ENTITY_ID=? FETCH FIRST 1 ROW ONLY""", (batch_id,), conn)
        observation = db.row("SELECT OBSERVATION_ID AS RECORD_ID FROM SAFETY_OBSERVATIONS WHERE BATCH_ID=? FETCH FIRST 1 ROW ONLY", (batch_id,), conn)
        verification = db.row("SELECT VERIFICATION_ID AS RECORD_ID FROM HUMAN_VERIFICATIONS WHERE BATCH_ID=? FETCH FIRST 1 ROW ONLY", (batch_id,), conn)
        targets = [
            ("AUDIT_EVENTS", "EVENT_ID", "EVENT_TYPE=EVENT_TYPE", audit),
            ("SAFETY_OBSERVATIONS", "OBSERVATION_ID", "STORAGE_NOTE=STORAGE_NOTE", observation),
            ("HUMAN_VERIFICATIONS", "VERIFICATION_ID", "NOTES=NOTES", verification),
        ]
        for table, key, assignment, record in targets:
            assert record is not None, f"Expected a synthetic QA row in {table}"
            record_id = record["record_id"]
            for statement in (
                f"UPDATE {table} SET {assignment} WHERE {key}=?",
                f"DELETE FROM {table} WHERE {key}=?",
            ):
                with pytest.raises(Exception) as rejected:
                    db.execute(statement, (record_id,), conn)
                assert "75001" in str(rejected.value), str(rejected.value)
                conn.rollback()
    finally:
        conn.close()


def test_db2_insert_select_update_transaction_rollback(client):
    from api.app import db

    document_id = str(uuid4())
    title = "SYNTHETIC QA | Db2 transaction probe"
    conn = db.connect()
    try:
        db.execute("INSERT INTO POLICY_DOCUMENTS (DOCUMENT_ID,TITLE,SOURCE_URL,CONTENT,ACTIVE) VALUES (?,?,?,?,0)",
                   (document_id, title, "https://example.invalid/synthetic-qa", title), conn)
        inserted = db.row("SELECT TITLE FROM POLICY_DOCUMENTS WHERE DOCUMENT_ID=?", (document_id,), conn)
        assert inserted["title"] == title
        db.execute("UPDATE POLICY_DOCUMENTS SET TITLE=? WHERE DOCUMENT_ID=?", (title + " | UPDATED", document_id), conn)
        updated = db.row("SELECT TITLE FROM POLICY_DOCUMENTS WHERE DOCUMENT_ID=?", (document_id,), conn)
        assert updated["title"] == title + " | UPDATED"
        conn.rollback()
    finally:
        conn.close()
    assert int(db.row("SELECT COUNT(*) AS N FROM POLICY_DOCUMENTS WHERE DOCUMENT_ID=?", (document_id,))["n"]) == 0


def test_real_db2_auth_signup_and_single_use_password_reset(client, monkeypatch):
    import hashlib
    import secrets
    from api.app import db
    from api.app import main
    from api.app.config import settings
    from api.app.security import password_matches

    invalid_password = "weakpass"
    validation = client.post("/api/auth/login", json={"email": "synthetic-qa@example.org", "password": invalid_password})
    assert validation.status_code == 422
    assert invalid_password not in validation.text and "input" not in validation.text

    roles = [
        {"role": "donor"},
        {"role": "volunteer", "service_area": "SYNTHETIC QA service area"},
        {"role": "ngo", "ngo_profile": {
            "name": f"SYNTHETIC QA receiver {uuid4().hex[:8]}", "available_kg": 0,
            "accepted_categories": ["prepared meals"], "storage_capabilities": ["cold"],
            "latitude": 12.9716, "longitude": 77.5946, "receiving_hours": "SYNTHETIC QA hours",
        }},
    ]
    created = []
    for fields in roles:
        email = f"synthetic-qa-auth-{uuid4().hex[:12]}@example.org"
        password = "Synthetic9!qa"
        payload = {"email": email.upper(), "display_name": "SYNTHETIC QA Auth User",
                   "password": password, "confirm_password": password, **fields}
        signup = client.post("/api/auth/signup", json=payload)
        assert signup.status_code == 201, signup.text
        account = signup.json()
        assert account["user"]["email"] == email
        assert account["user"]["role"] == fields["role"]
        assert "password" not in account and "password_hash" not in account
        stored = db.row("SELECT USER_ID,ROLE,PASSWORD_HASH FROM USERS WHERE EMAIL=?", (email,))
        assert stored is not None and stored["role"] == fields["role"]
        assert password not in stored["password_hash"]
        assert password_matches(password, stored["password_hash"])
        created.append({"email": email, "password": password, "user_id": stored["user_id"].strip(), "role": fields["role"]})

        duplicate = client.post("/api/auth/signup", json=payload)
        assert duplicate.status_code == 409, duplicate.text
        login = client.post("/api/auth/login", json={"email": email.swapcase(), "password": password})
        assert login.status_code == 200, login.text
        assert login.json()["user"]["role"] == fields["role"]
        wrong = client.post("/api/auth/login", json={"email": email, "password": "Wrong9!password"})
        assert wrong.status_code == 401

        if fields["role"] == "volunteer":
            assert db.row("SELECT USER_ID FROM VOLUNTEERS WHERE USER_ID=?", (stored["user_id"],))
        if fields["role"] == "ngo":
            profile = db.row("SELECT NGO_ID,VERIFIED,AVAILABLE_KG FROM NGOS WHERE OWNER_USER_ID=?", (stored["user_id"],))
            assert profile is not None and profile["verified"] == 0 and float(profile["available_kg"]) == 0
            owner_headers = {"Authorization": f"Bearer {account['access_token']}"}
            forbidden_review = client.patch(f"/api/ngos/{profile['ngo_id'].strip()}/verification",
                                            headers=owner_headers, json={"verified": True, "notes": "SYNTHETIC QA self-review attempt."})
            assert forbidden_review.status_code == 403
            admin_headers = {"Authorization": f"Bearer {access_token(client, 'admin@annasetu.local')}"}
            reviewed = client.patch(f"/api/ngos/{profile['ngo_id'].strip()}/verification", headers=admin_headers,
                                    json={"verified": True, "notes": "SYNTHETIC QA administrator review."})
            assert reviewed.status_code == 200 and reviewed.json()["verified"] is True
            assert db.row("SELECT VERIFIED FROM NGOS WHERE NGO_ID=?", (profile["ngo_id"],))["verified"] == 1

    demo_accounts = client.get("/api/auth/demo-accounts")
    assert demo_accounts.status_code == 200
    assert {item["role"] for item in demo_accounts.json()} == {"admin", "donor", "ngo", "volunteer"}
    assert all("name" not in item and "display_name" not in item for item in demo_accounts.json())

    # Public requests never reveal whether the account exists and never issue
    # a code. A signed-in admin approves the identity check and receives the
    # one-time code; no email delivery code exists in this MVP.
    monkeypatch.setattr(settings, "environment", "development")
    known_request = client.post("/api/auth/password-reset", json={"email": created[0]["email"]})
    unknown_request = client.post("/api/auth/password-reset", json={"email": f"missing-{uuid4().hex[:8]}@example.org"})
    assert known_request.status_code == unknown_request.status_code == 202
    public_response = known_request.json()
    assert public_response == unknown_request.json()
    assert public_response["recovery_mode"] == "local_admin_approval"
    assert "administrator to verify your identity" in public_response["message"].lower()
    assert "recovery_code" not in public_response
    assert int(db.row("SELECT COUNT(*) AS N FROM PASSWORD_RESET_TOKENS WHERE USER_ID=? AND USED_AT IS NULL",
                      (created[0]["user_id"],))["n"]) == 0

    donor_login = client.post("/api/auth/login", json={"email": created[0]["email"], "password": created[0]["password"]})
    donor_headers = {"Authorization": f"Bearer {donor_login.json()['access_token']}"}
    denied_issue = client.post("/api/auth/password-reset/admin-issue", headers=donor_headers,
                               json={"email": created[0]["email"]})
    assert denied_issue.status_code == 403

    admin_headers = {"Authorization": f"Bearer {access_token(client, 'admin@annasetu.local')}"}
    issued = client.post("/api/auth/password-reset/admin-issue", headers=admin_headers,
                         json={"email": created[0]["email"]})
    assert issued.status_code == 201, issued.text
    first_code = issued.json()["recovery_code"]
    assert issued.json()["expires_in_seconds"] == 300
    assert "verified" in issued.json()["message"].lower()
    stored_code = db.row("SELECT TOKEN_HASH,EXPIRES_AT FROM PASSWORD_RESET_TOKENS WHERE USER_ID=? AND USED_AT IS NULL",
                         (created[0]["user_id"],))
    assert stored_code["token_hash"].strip() == main._hash_reset_token(first_code)
    assert stored_code["token_hash"].strip() != hashlib.sha256(first_code.encode("ascii")).hexdigest()
    assert stored_code["expires_at"] > datetime.now(timezone.utc).replace(tzinfo=None)

    # Issuing a second code invalidates the first and records only a new hash.
    second_response = client.post("/api/auth/password-reset/admin-issue", headers=admin_headers,
                                  json={"email": created[0]["email"]})
    assert second_response.status_code == 201
    local_code = second_response.json()["recovery_code"]
    assert client.post("/api/auth/password-reset/verify", json={"token": first_code}).status_code == 400
    assert client.post("/api/auth/password-reset/verify", json={"token": "000000" if local_code != "000000" else "000001"}).status_code == 400

    # Verify the code, update the hash, and enforce single use through live Db2.
    verified = client.post("/api/auth/password-reset/verify", json={"token": local_code})
    assert verified.status_code == 200 and verified.json() == {"valid": True}
    new_password = "Updated9!qa"
    reset = client.post("/api/auth/password-reset/confirm", json={
        "token": local_code, "password": new_password, "confirm_password": new_password,
    })
    assert reset.status_code == 200, reset.text
    used = db.row("SELECT TOKEN_HASH,USED_AT FROM PASSWORD_RESET_TOKENS WHERE TOKEN_HASH=?",
                  (main._hash_reset_token(local_code),))
    assert used is not None and used["used_at"] is not None
    updated_user = db.row("SELECT PASSWORD_HASH FROM USERS WHERE USER_ID=?", (created[0]["user_id"],))
    assert new_password not in updated_user["password_hash"]
    assert password_matches(new_password, updated_user["password_hash"])
    assert client.post("/api/auth/password-reset/verify", json={"token": local_code}).status_code == 400
    assert client.post("/api/auth/password-reset/confirm", json={
        "token": local_code, "password": new_password, "confirm_password": new_password,
    }).status_code == 400
    assert client.post("/api/auth/login", json={"email": created[0]["email"], "password": new_password}).status_code == 200

    expired_token = f"{secrets.randbelow(1_000_000):06d}"
    expired_hash = main._hash_reset_token(expired_token)
    conn = db.connect()
    try:
        db.execute("INSERT INTO PASSWORD_RESET_TOKENS (RESET_ID,USER_ID,TOKEN_HASH,EXPIRES_AT) VALUES (?,?,?,?)",
                   (str(uuid4()), created[0]["user_id"], expired_hash,
                    datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)), conn)
        conn.commit()
    finally:
        conn.close()
    assert client.post("/api/auth/password-reset/verify", json={"token": expired_token}).status_code == 400
    assert client.post("/api/auth/password-reset/confirm", json={
        "token": expired_token, "password": "Expired9!qa", "confirm_password": "Expired9!qa",
    }).status_code == 400
    expired_record = db.row("SELECT USED_AT FROM PASSWORD_RESET_TOKENS WHERE TOKEN_HASH=?", (expired_hash,))
    assert expired_record is not None and expired_record["used_at"] is not None

    assert client.get("/api/audit/verify", headers={
        "Authorization": f"Bearer {access_token(client, 'admin@annasetu.local')}"
    }).json()["valid"] is True
