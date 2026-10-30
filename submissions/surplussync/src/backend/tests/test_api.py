import asyncio
import base64
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from backend import database
from backend import main as api_main
from backend.main import app
from backend.auth import digest as database_digest, hash_password
from backend.seed_demo_accounts import seed_demo_accounts
from backend.seed_demo_workflows import seed_demo_workflows
from backend.seed_presentation_demo import seed_presentation_demo, enabled as presentation_demo_enabled


async def assert_signup(client, response, email):
    """Compatibility helper: signup is immediately usable without email."""
    assert response.status_code == 201, response.text
    assert "verify" not in str(response.json()).lower()


def run_api(coro):
    return asyncio.run(coro)


@asynccontextmanager
async def client(role="DONOR", recipient_id=None):
    # httpx's ASGI transport is in-process and never opens a network socket.
    database.init_db()
    email=f"test-{role.lower()}@example.test"
    profiles={"DONOR":{"contact_name":"Test Donor","phone":"0000000000","organization_name":"Test Donor Org","address":"Test Street","pickup_area":"Central"},
              "RECIPIENT":{"organization_name":"Test Recipient Org","address":"Private test address","service_area":"Central","contact_person":"Test Contact","phone":"0000000000","receiving_hours":"Always","registration_type":"Registered trust","registration_number":"","food_categories":["Prepared meals","Bakery","Fresh produce","Packaged groceries"],"capacity":1000},
              "VOLUNTEER":{"contact_name":"Test Volunteer","phone":"0000000000","service_area":"Central","availability":"available"},
              "ADMIN":{}}
    with database.connection() as db:
        row=db.execute("SELECT id FROM user_accounts WHERE email=?",(email,)).fetchone()
        if row:
            user_id=row["id"]
        else:
            now=datetime.now().isoformat(timespec="seconds")
            cur=db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",(email,hash_password("Test-password-123"),role,now,now))
            user_id=cur.lastrowid
            if role != "ADMIN":
                db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,?,?,'approved',?,?)",(user_id,role,json.dumps(profiles[role]),now,now))
        if role=="RECIPIENT" and recipient_id is not None:
            db.execute("UPDATE recipients SET owner_user_id=? WHERE id=?",(user_id,recipient_id))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        login=await c.post("/api/auth/login",json={"email":email,"password":"Test-password-123","role":role if role!="ADMIN" else "ADMIN"})
        assert login.status_code==200,login.text
        c.headers["X-CSRF-Token"]=login.json()["csrf_token"]
        yield c


def client_user_id(role):
    with database.connection() as db:
        return db.execute("SELECT id FROM user_accounts WHERE email=?",(f"test-{role.lower()}@example.test",)).fetchone()[0]


@asynccontextmanager
async def account_client(email, password):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        login = await c.post("/api/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        yield c


def lifecycle_payload(name="Lifecycle donor", verified=True):
    safety = {"handling_verified": verified, "temperature_verified": verified,
              "allergens_verified": verified, "packaging_verified": verified,
              "local_requirements_verified": verified}
    return {"donor_name": name, "food_type": "Prepared meals", "portions": 10,
            "pickup_area": "Central", "deadline": (datetime.now()+timedelta(hours=2)).isoformat(),
            "safety_verified_by": "Demo verifier" if verified else "", "safety": safety}

def organization_application(profile):
    # Small deterministic PDF-like fixture; upload unit/integration tests do
    # not send or claim to validate a real NGO certificate.
    certificate=b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    return {"profile":profile,"certificate_filename":"fictional-registration.pdf",
            "certificate_base64":base64.b64encode(certificate).decode("ascii")}


def test_legacy_database_migration_preserves_listings_and_requires_safety(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy.db")
    with database.connection() as db:
        db.execute("CREATE TABLE recipients (id INTEGER PRIMARY KEY,name TEXT NOT NULL,area TEXT NOT NULL,capacity INTEGER NOT NULL,travel_minutes INTEGER NOT NULL,available INTEGER NOT NULL DEFAULT 1)")
        db.execute("INSERT INTO recipients VALUES(1,'Legacy recipient','Central',40,15,1)")
        db.execute("CREATE TABLE listings (id INTEGER PRIMARY KEY AUTOINCREMENT,donor_name TEXT NOT NULL,food_type TEXT NOT NULL,portions INTEGER NOT NULL,pickup_area TEXT NOT NULL,deadline TEXT NOT NULL,prepared_at TEXT,created_at TEXT NOT NULL)")
        db.execute("INSERT INTO listings(donor_name,food_type,portions,pickup_area,deadline,created_at) VALUES('Legacy donor','Prepared meals',10,'Central','2099-01-01T10:00:00','2026-01-01T10:00:00')")
        db.execute("INSERT INTO listings(donor_name,food_type,portions,pickup_area,deadline,created_at) VALUES('Integration Demo','Prepared meals',10,'Central','2099-01-01T10:00:00','2026-01-01T10:00:00')")
    database.init_db()
    with database.connection() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(listings)")}
        assert {"safety_handling", "safety_temperature", "safety_allergens", "safety_packaging", "safety_local_rules", "safety_verified_by", "audit", "demo"} <= columns
        listing = db.execute("SELECT * FROM listings WHERE id=1").fetchone()
        assert listing["donor_name"] == "Legacy donor"
        assert all(listing[name] == 0 for name in ("safety_handling", "safety_temperature", "safety_allergens", "safety_packaging", "safety_local_rules"))
        assert db.execute("SELECT audit FROM listings WHERE donor_name='Integration Demo'").fetchone()[0] == 1
        sample = db.execute("SELECT * FROM listings WHERE demo=1").fetchone()
        assert sample["donor_name"] == "Demo: Community Bakery"
        assert all(sample[name] == 0 for name in ("safety_handling", "safety_temperature", "safety_allergens", "safety_packaging", "safety_local_rules"))


def test_full_workflow_and_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "workflow.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            assert (await c.get("/api/health")).json()["status"] == "ok"
            assert len((await c.get("/api/recipients")).json()) >= 1
            created = await c.post("/api/listings", json=lifecycle_payload("Demo Donor"))
            assert created.status_code == 201 and not created.json()["demo"] and not created.json()["audit"]
            assert (await c.get("/api/listings")).json()[0]["id"] == created.json()["id"]
            plan = await c.post(f"/api/listings/{created.json()['id']}/plan")
            assert plan.status_code == 201 and plan.json()["feasible"]
            risk=plan.json()["risk_assessment"]
            assert risk["category"] in {"Low","Medium","High"} and risk["method"].startswith("Transparent rule-based")
            with database.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM rescue_risk_assessments WHERE plan_id=?",(plan.json()["id"],)).fetchone()[0]==1
            assert (await c.get(f"/api/plans/{plan.json()['id']}")).json()["recommended"] is not None
            assert (await c.get(f"/api/listings/{created.json()['id']}/plans/latest")).json()["plan"]["id"] == plan.json()["id"]
            assert len((await c.get("/api/listings")).json()) == 1
            recipient = (await c.get("/api/recipients")).json()[0]
            assert (await c.patch(f"/api/recipients/{recipient['id']}/availability", json={"available": False})).status_code==403
            async with client("ADMIN") as admin:
                assert (await admin.patch(f"/api/recipients/{recipient['id']}/availability", json={"available": False})).status_code == 200
            assert any(not r["available"] for r in (await c.get("/api/recipients")).json())
            assert (await c.post(f"/api/plans/{plan.json()['id']}/recalculate")).status_code == 200
    run_api(exercise())


def test_latest_plan_returns_stable_null_envelope(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "latest.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            payload = lifecycle_payload("Demo Donor")
            payload["safety"] = {}
            listing = (await c.post("/api/listings", json=payload)).json()
            response = await c.get(f"/api/listings/{listing['id']}/plans/latest")
            assert response.status_code == 200 and response.json() == {"plan": None}
    run_api(exercise())


def test_invalid_and_past_listing_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "invalid.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            payload = lifecycle_payload("Donor")
            payload["portions"] = 0
            assert (await c.post("/api/listings", json=payload)).status_code == 422
            payload["portions"] = -1
            assert (await c.post("/api/listings", json=payload)).status_code == 422
            payload["portions"] = 5
            payload["safety_verified_by"] = ""
            assert (await c.post("/api/listings", json=payload)).json()["detail"]["code"] == "missing_safety_verifier"
            payload["safety"] = {"handling_verified":True,"temperature_verified":True,"allergens_verified":False,"packaging_verified":True,"local_requirements_verified":True}
            assert (await c.post("/api/listings", json=payload)).json()["detail"]["code"] == "missing_safety_verifier"
            payload["safety"] = {}
            payload["deadline"] = (datetime.now() - timedelta(minutes=2)).isoformat()
            assert (await c.post("/api/listings", json=payload)).status_code == 422
            payload["deadline"] = (datetime.now() + timedelta(hours=1)).isoformat()
            listing = await c.post("/api/listings", json=payload)
            plan = (await c.post(f"/api/listings/{listing.json()['id']}/plan")).json()
            assert not plan["food_safety_passed"] and not plan["feasible"]
    run_api(exercise())


def test_unavailable_preferred_recipient_promotes_alternative(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "alternative.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            listing = (await c.post("/api/listings", json=lifecycle_payload("Donor"))).json()
            first = (await c.post(f"/api/listings/{listing['id']}/plan")).json()
            preferred = first["recommended"]["id"]
            assert first["alternative"] is not None
            async with client("ADMIN") as admin:
                assert (await admin.patch(f"/api/recipients/{preferred}/availability", json={"available": False})).status_code == 200
            immediately_ranked=(await c.get(f"/api/plans/{first['id']}")).json()
            assert immediately_ranked["recommended"]["id"]==first["alternative"]["id"]
            with database.connection() as db:
                assert db.execute("SELECT recipient_id,rank FROM candidate_evaluations WHERE plan_id=? AND feasible=1 ORDER BY rank LIMIT 1",(first["id"],)).fetchone()["recipient_id"]==first["alternative"]["id"]
            recalculated = (await c.post(f"/api/plans/{first['id']}/recalculate")).json()
            assert recalculated["recommended"]["id"] == first["alternative"]["id"]
            assert any("unavailable" in reason.lower() for candidate in recalculated["rejected_candidates"] if candidate["id"] == preferred for reason in candidate["reasons"])
    run_api(exercise())


def test_prepared_meal_matching_uses_saved_human_checks_and_matches_api_plan_response(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "prepared-matching.db")
    database.init_db()
    async def exercise():
        async with client() as donor:
            blocked_payload = lifecycle_payload("Prepared meal safety blocker")
            blocked_payload["safety"]["local_requirements_verified"] = False
            blocked_listing = (await donor.post("/api/listings", json=blocked_payload)).json()
            blocked_plan = (await donor.post(f"/api/listings/{blocked_listing['id']}/plan")).json()
            assert blocked_plan["feasible_candidates"] == []
            assert len(blocked_plan["rejected_candidates"]) == 4
            assert all(any("local requirements" in reason.lower() for reason in row["reasons"])
                       for row in blocked_plan["rejected_candidates"])
            assert "responsible human must complete or verify" in blocked_plan["explanation"].lower()
            assert "local requirements" in blocked_plan["explanation"].lower()
            assert blocked_plan["risk_assessment"]["score"] != 70
            current_plan = (await donor.get(f"/api/plans/{blocked_plan['id']}")).json()
            assert current_plan["feasible_candidates"] == blocked_plan["feasible_candidates"]
            assert current_plan["rejected_candidates"] == blocked_plan["rejected_candidates"]
            assert current_plan["risk_assessment"] == blocked_plan["risk_assessment"]

            valid_listing = (await donor.post("/api/listings", json=lifecycle_payload("Verified prepared meals"))).json()
            valid_plan = (await donor.post(f"/api/listings/{valid_listing['id']}/plan")).json()
            assert {row["id"] for row in valid_plan["feasible_candidates"]} == {1, 2, 4}
            assert valid_plan["recommended"]["id"] == valid_plan["feasible_candidates"][0]["id"]
            sunrise = next(row for row in valid_plan["rejected_candidates"] if row["id"] == 3)
            assert any("Prepared meals" in reason and "not accepted" in reason for reason in sunrise["reasons"])
            assert valid_plan["food_safety_passed"] is True
    run_api(exercise())


def test_donor_can_update_unoffered_listing_and_existing_plan_refreshes_without_auto_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "listing-update.db")
    database.init_db()
    async def exercise():
        async with client() as donor:
            pending_payload=lifecycle_payload("Human review pending",False)
            pending_payload["safety"]["local_requirements_verified"]=False
            listing=(await donor.post("/api/listings",json=pending_payload)).json()
            plan=(await donor.post(f"/api/listings/{listing['id']}/plan")).json()
            assert not plan["feasible"]

            valid_payload=lifecycle_payload("Edited donor",True)
            valid_payload.update({
                "food_type":"Bakery",
                "portions":170,
                "pickup_area":"East Market",
                "deadline":(datetime.now()+timedelta(hours=3)).isoformat(timespec="minutes"),
                "prepared_at":(datetime.now()-timedelta(minutes=30)).isoformat(timespec="minutes"),
                "safety_verified_by":"Responsible human reviewer",
            })
            expected_deadline=datetime.fromisoformat(valid_payload["deadline"]).isoformat()
            expected_prepared_at=datetime.fromisoformat(valid_payload["prepared_at"]).isoformat()
            invalid_date={**valid_payload,"deadline":(datetime.now()-timedelta(minutes=1)).isoformat(timespec="minutes")}
            assert (await donor.patch(f"/api/listings/{listing['id']}",json=invalid_date)).status_code==422
            invalid_quantity={**valid_payload,"portions":0}
            assert (await donor.patch(f"/api/listings/{listing['id']}",json=invalid_quantity)).status_code==422
            unverified_payload={**valid_payload,"safety_verified_by":"","safety":{key:False for key in valid_payload["safety"]}}
            unverified_update=await donor.patch(f"/api/listings/{listing['id']}",json=unverified_payload)
            assert unverified_update.status_code==200
            assert not any(unverified_update.json()["safety"].values())
            assert not (await donor.get(f"/api/plans/{plan['id']}")).json()["feasible"]

            tight_deadline_payload={**valid_payload,"deadline":(datetime.now()+timedelta(minutes=5)).isoformat(timespec="minutes")}
            tight_deadline_update=await donor.patch(f"/api/listings/{listing['id']}",json=tight_deadline_payload)
            assert tight_deadline_update.status_code==200
            deadline_plan=(await donor.get(f"/api/plans/{plan['id']}")).json()
            assert deadline_plan["feasible_candidates"]==[]
            assert all(any("Estimated travel" in reason for reason in candidate["reasons"])
                       for candidate in deadline_plan["rejected_candidates"])

            updated=await donor.patch(f"/api/listings/{listing['id']}",json=valid_payload)
            assert updated.status_code==200
            assert updated.json()["donor_name"]=="Edited donor"
            assert updated.json()["food_type"]=="Bakery"
            assert updated.json()["portions"]==170
            assert updated.json()["pickup_area"]=="East Market"
            assert updated.json()["deadline"]==expected_deadline
            assert updated.json()["prepared_at"]==expected_prepared_at
            assert updated.json()["safety"]["local_requirements_verified"] is True
            refreshed=(await donor.get(f"/api/plans/{plan['id']}")).json()
            assert {candidate["id"] for candidate in refreshed["feasible_candidates"]}=={4}
            assert refreshed["food_safety_passed"] is True
            persisted_listing=next(row for row in (await donor.get("/api/listings")).json() if row["id"]==listing["id"])
            assert persisted_listing["food_type"]=="Bakery" and persisted_listing["portions"]==170
            assert persisted_listing["pickup_area"]=="East Market"
            assert persisted_listing["deadline"]==expected_deadline
            assert refreshed["risk_assessment"]["score"]<plan["risk_assessment"]["score"]
            with database.connection() as db:
                assert db.execute("SELECT safety_local_rules FROM listings WHERE id=?",(listing["id"],)).fetchone()[0]==1
                persisted=db.execute("SELECT donor_name,food_type,portions,pickup_area,deadline,prepared_at FROM listings WHERE id=?",(listing["id"],)).fetchone()
                assert tuple(persisted)==("Edited donor","Bakery",170,"East Market",expected_deadline,expected_prepared_at)
                assert db.execute("SELECT COUNT(*) FROM security_audit WHERE action='listing_updated' AND subject_id=?",(str(listing["id"]),)).fetchone()[0]==3
                assert db.execute("SELECT COUNT(*) FROM rescue_risk_assessments WHERE plan_id=?",(plan["id"],)).fetchone()[0]==4
                assert db.execute("SELECT COUNT(*) FROM rescue_events WHERE rescue_id=(SELECT id FROM rescue_cases WHERE listing_id=?)",(listing["id"],)).fetchone()[0]==1

            # Keep the previous full-replacement method working for existing clients.
            legacy_payload={**valid_payload,"donor_name":"Legacy PUT compatibility"}
            legacy=await donor.put(f"/api/listings/{listing['id']}",json=legacy_payload)
            assert legacy.status_code==200 and legacy.json()["donor_name"]=="Legacy PUT compatibility"

            recipient_id=refreshed["recommended"]["id"]
            assert (await donor.post(f"/api/listings/{listing['id']}/rescue/propose",json={"recipient_id":recipient_id})).status_code==201
            locked=await donor.patch(f"/api/listings/{listing['id']}",json=valid_payload)
            assert locked.status_code==409 and locked.json()["detail"]["code"]=="listing_locked"
        async with client("ADMIN") as admin:
            denied=await admin.put(f"/api/listings/{listing['id']}",json=lifecycle_payload("Unauthorized edit"))
            assert denied.status_code==403
    run_api(exercise())


def test_demo_reset_restores_demo_network_and_preserves_user_listings(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "reset.db")
    database.init_db()
    with database.connection() as db:
        db.execute("INSERT INTO recipients(name,area,capacity,travel_minutes,available,food_categories,demo,created_at,updated_at) VALUES('User recipient','West',30,10,0,'[]',0,'2026-01-01','2026-01-01')")
        db.execute("INSERT INTO listings(donor_name,food_type,portions,pickup_area,deadline,prepared_at,safety_handling,safety_temperature,safety_allergens,safety_packaging,safety_local_rules,safety_verified_by,audit,demo,created_at) VALUES('User listing','Bakery',5,'West','2099-01-01T10:00:00',NULL,0,0,0,0,0,'',0,0,'2026-01-01')")
    with database.connection() as db:
        db.execute("UPDATE recipients SET available=0 WHERE demo=1")
    async def exercise():
        async with client("ADMIN") as c:
            response = await c.post("/api/demo/reset")
            assert response.status_code == 200
            assert response.json()["recipients"] == 4
            assert response.json()["demo_listings"] == 1
            assert response.json()["listings_preserved"] == 1
    run_api(exercise())
    with database.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM listings WHERE donor_name='User listing'").fetchone()[0] == 1
        assert db.execute("SELECT available FROM recipients WHERE name='User recipient'").fetchone()[0] == 0


def test_rescue_accept_status_transitions_cancellation_and_dashboard_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "lifecycle.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            listing = (await c.post("/api/listings", json=lifecycle_payload())).json()
            plan = (await c.post(f"/api/listings/{listing['id']}/plan")).json()
            recipient_id = plan["recommended"]["id"]
            offer = await c.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": recipient_id})
            assert offer.status_code == 201 and offer.json()["status"] == "awaiting_confirmation"
            assert offer.json()["portions_reserved"] == 10 and offer.json()["selected_recipient"]["id"] == recipient_id
            metrics = (await c.get("/api/dashboard/metrics")).json()
            assert metrics["awaiting_confirmation"]["portions"] == 10 and metrics["accepted"]["portions"] == 0
            async with client("ADMIN") as admin:
                assert (await admin.patch(f"/api/rescues/{offer.json()['id']}/status", json={"status": "collected"})).status_code == 409
            async with client("RECIPIENT", recipient_id) as recipient_client:
                accepted = await recipient_client.post(f"/api/rescues/{offer.json()['id']}/accept", json={"recipient_id": recipient_id})
            assert accepted.status_code == 200 and accepted.json()["accepted_at"]
            ready = await c.patch(f"/api/rescues/{offer.json()['id']}/status", json={"status": "ready_for_pickup", "pickup_notes": "Side entrance"})
            assert ready.status_code == 200 and ready.json()["pickup_notes"] == "Side entrance" and ready.json()["ready_for_pickup_at"]
            async with client("VOLUNTEER") as unassigned:
                assert (await unassigned.patch(f"/api/rescues/{offer.json()['id']}/status", json={"status":"collected"})).status_code==403
            async with client("VOLUNTEER"):
                pass
            volunteer_id = client_user_id("VOLUNTEER")
            assignment = await c.post(f"/api/rescues/{offer.json()['id']}/volunteer", json={"volunteer_user_id": volunteer_id})
            assert assignment.status_code == 200
            async with client("VOLUNTEER") as volunteer_client:
                collected = await volunteer_client.patch(f"/api/rescues/{offer.json()['id']}/status", json={"status": "collected"})
                assert collected.status_code == 200 and collected.json()["collected_at"]
                delivered = await volunteer_client.patch(f"/api/rescues/{offer.json()['id']}/status", json={"status": "delivered", "delivery_notes": "Received by pantry"})
            assert delivered.status_code == 200 and delivered.json()["delivery_notes"] == "Received by pantry" and delivered.json()["delivered_at"]
            assert (await c.get("/api/dashboard/metrics")).json()["delivered"]["portions"] == 10
            assert len((await c.get(f"/api/rescues/{offer.json()['id']}")).json()["timeline"]) == 7
            locked=await c.put(f"/api/listings/{listing['id']}",json=lifecycle_payload("Completed rescue must stay unchanged"))
            assert locked.status_code==409 and locked.json()["detail"]["code"]=="listing_locked"
            second = (await c.post("/api/listings", json=lifecycle_payload("Cancel donor"))).json()
            case = next(row for row in (await c.get("/api/rescues")).json() if row["listing_id"] == second["id"])
            cancelled = await c.patch(f"/api/rescues/{case['id']}/status", json={"status": "cancelled"})
            assert cancelled.status_code == 200 and cancelled.json()["cancelled_at"]
            async with client("ADMIN") as admin:
                assert (await admin.patch(f"/api/rescues/{case['id']}/status", json={"status": "delivered"})).status_code == 409
    run_api(exercise())


def test_rejection_reason_alternative_and_safety_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "reject.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            listing = (await c.post("/api/listings", json=lifecycle_payload())).json()
            plan = (await c.post(f"/api/listings/{listing['id']}/plan")).json()
            first, alternative = plan["recommended"]["id"], plan["alternative"]["id"]
            offer = (await c.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": first})).json()
            async with client("RECIPIENT", first) as recipient_client:
                rejected = await recipient_client.post(f"/api/rescues/{offer['id']}/reject", json={"recipient_id": first, "reason": "Pickup vehicle unavailable"})
            assert rejected.status_code == 200 and rejected.json()["status"] == "listed"
            assert rejected.json()["rejection_reason"] == "Pickup vehicle unavailable"
            assert rejected.json()["alternative_recommendation"]["id"] == alternative
            latest = (await c.get(f"/api/listings/{listing['id']}/plans/latest")).json()["plan"]
            assert latest["recommended"]["id"] == alternative
            assert any("already rejected" in reason for candidate in latest["rejected_candidates"] if candidate["id"] == first for reason in candidate["reasons"])
            assert rejected.json()["timeline"][-1]["reason"] == "Pickup vehicle unavailable"
            next_offer = await c.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": alternative})
            assert next_offer.status_code == 201 and next_offer.json()["selected_recipient"]["id"] == alternative
            unverified = (await c.post("/api/listings", json=lifecycle_payload("Unverified donor", False))).json()
            denied = await c.post(f"/api/listings/{unverified['id']}/rescue/propose")
            assert denied.status_code == 409 and denied.json()["detail"]["code"] == "no_feasible_recipient"
            assert any("verified by a human" in reason for reason in denied.json()["detail"]["reasons"])
    run_api(exercise())


def test_recipients_can_discover_pending_safety_listing_but_cannot_accept_it(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "discovery.db")
    database.init_db()
    async def exercise():
        async with client() as donor:
            pending = lifecycle_payload("Visible while verification is pending", False)
            listing = (await donor.post("/api/listings", json=pending)).json()
            async with client("RECIPIENT", 1) as recipient:
                discovered = await recipient.get("/api/listings")
                assert discovered.status_code == 200
                visible = next(row for row in discovered.json() if row["id"] == listing["id"])
                assert visible["safety"]["temperature_verified"] is False
                assert visible["safety"]["allergens_verified"] is False
                with database.connection() as db:
                    rescue_id = db.execute("SELECT id FROM rescue_cases WHERE listing_id=?",(listing["id"],)).fetchone()[0]
                accept = await recipient.post(f"/api/rescues/{rescue_id}/accept", json={"recipient_id":1})
                assert accept.status_code == 403
                denied = await donor.post(f"/api/listings/{listing['id']}/rescue/propose")
                assert denied.status_code == 409
                assert any("temperature" in reason.lower() for reason in denied.json()["detail"]["reasons"])
                assert not any("allergen" in reason.lower() for reason in denied.json()["detail"]["reasons"])
    run_api(exercise())


def test_donor_listing_deletion_is_owner_checked_cascades_dependents_and_allows_recreation(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "listing-delete.db")
    database.init_db()
    async def exercise():
        async with client() as owner:
            listing = (await owner.post("/api/listings", json=lifecycle_payload("Delete and recreate"))).json()
            plan = (await owner.post(f"/api/listings/{listing['id']}/plan")).json()
            recipient_id = plan["recommended"]["id"]
            offer = (await owner.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": recipient_id})).json()

            now = datetime.now().isoformat(timespec="seconds")
            with database.connection() as db:
                outsider_id = db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)", ("outsider-delete@example.test", hash_password("Test-password-123"), "DONOR", now, now)).lastrowid
                profile = {"contact_name":"Other Donor","phone":"0000000000","organization_name":"Other Org","address":"Other Street","pickup_area":"Central"}
                db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,'DONOR',?, 'approved',?,?)", (outsider_id,json.dumps(profile),now,now))
            async with account_client("outsider-delete@example.test", "Test-password-123") as outsider:
                assert (await outsider.delete(f"/api/listings/{listing['id']}")).status_code == 403
                other_listing = await outsider.post("/api/listings", json=lifecycle_payload("Unrelated owner listing"))
                assert other_listing.status_code == 201

            deleted = await owner.delete(f"/api/listings/{listing['id']}")
            assert deleted.status_code == 200 and deleted.json() == {"deleted":True,"listing_id":listing["id"]}
            assert (await owner.get(f"/api/listings/{listing['id']}/plans/latest")).status_code == 404
            assert (await owner.get(f"/api/rescues/{offer['id']}")).status_code == 404
            recreated = await owner.post("/api/listings", json=lifecycle_payload("Replacement after deletion"))
            assert recreated.status_code == 201
            assert (await owner.delete(f"/api/listings/{listing['id']}")).status_code == 404
            with database.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM rescue_plans WHERE listing_id=?",(listing["id"],)).fetchone()[0] == 0
                assert db.execute("SELECT COUNT(*) FROM rescue_cases WHERE listing_id=?",(listing["id"],)).fetchone()[0] == 0
                assert db.execute("SELECT COUNT(*) FROM rescue_events WHERE rescue_id=?",(offer["id"],)).fetchone()[0] == 0
                assert db.execute("SELECT COUNT(*) FROM security_audit WHERE action='listing_deleted' AND subject_id=?",(str(listing["id"]),)).fetchone()[0] == 1
                assert db.execute("SELECT COUNT(*) FROM listings WHERE id=?",(other_listing.json()["id"],)).fetchone()[0] == 1
                assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    run_api(exercise())


def test_concurrent_offers_cannot_reserve_same_listing_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "race.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            listing = (await c.post("/api/listings", json=lifecycle_payload())).json()
            recipients = (await c.get("/api/recipients")).json()
            first, second = recipients[0]["id"], recipients[1]["id"]
            results = await asyncio.gather(c.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": first}), c.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": second}))
            assert sorted(response.status_code for response in results) == [201, 409]
            active = (await c.get("/api/rescues")).json()
            matches = [row for row in active if row["listing_id"] == listing["id"]]
            assert len(matches) == 1 and matches[0]["status"] == "awaiting_confirmation"
            with database.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM rescue_events WHERE rescue_id=? AND event_type='offer_sent'", (matches[0]["id"],)).fetchone()[0] == 1
    run_api(exercise())


def test_acceptance_rechecks_recipient_availability(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "eligibility.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            listing = (await c.post("/api/listings", json=lifecycle_payload())).json()
            recipient = (await c.post(f"/api/listings/{listing['id']}/plan")).json()["recommended"]["id"]
            offer = (await c.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": recipient})).json()
            async with client("ADMIN") as admin:
                await admin.patch(f"/api/recipients/{recipient}/availability", json={"available": False})
            async with client("RECIPIENT", recipient) as recipient_client:
                denied = await recipient_client.post(f"/api/rescues/{offer['id']}/accept", json={"recipient_id": recipient})
            assert denied.status_code == 409 and denied.json()["detail"]["code"] == "recipient_no_longer_eligible"
            assert any("unavailable" in reason.lower() for reason in denied.json()["detail"]["reasons"])
    run_api(exercise())


def test_capacity_shortfall_blocks_rescue_offer(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "capacity.db")
    database.init_db()
    async def exercise():
        async with client() as c:
            body = lifecycle_payload("Large listing")
            body["portions"] = 1000
            listing = await c.post("/api/listings", json=body)
            assert listing.status_code == 201
            plan = (await c.post(f"/api/listings/{listing.json()['id']}/plan")).json()
            assert not plan["feasible"]
            assert all(any("Capacity" in reason for reason in candidate["reasons"]) for candidate in plan["rejected_candidates"])
            offer = await c.post(f"/api/listings/{listing.json()['id']}/rescue/propose")
            assert offer.status_code == 409 and offer.json()["detail"]["code"] == "no_feasible_recipient"
    run_api(exercise())


def test_auth_signup_duplicate_login_logout_and_admin_self_signup_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"auth.db")
    database.init_db()
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            assert (await c.get("/api/listings")).status_code==401
            payload={"email":"new@example.test","password":"Strong-Password-123","role":"DONOR"}
            created=await c.post("/api/auth/signup",json=payload)
            assert created.status_code==201 and created.json()["message"]
            first_login = await c.post("/api/auth/login",json=payload)
            assert first_login.status_code == 200
            await assert_signup(c,created,payload["email"])
            assert (await c.post("/api/auth/signup",json=payload)).status_code==409
            forbidden={**payload,"email":"admin@example.test","role":"ADMIN"}
            assert (await c.post("/api/auth/signup",json=forbidden)).status_code==422
            assert (await c.post("/api/auth/login",json={"email":payload["email"],"password":"incorrect"})).status_code==401
            login=await c.post("/api/auth/login",json=payload)
            assert login.status_code==200 and "password_hash" not in str(login.json())
            c.headers["X-CSRF-Token"]=login.json()["csrf_token"]
            assert (await c.get("/api/auth/me")).json()["user"]["email"]==payload["email"]
            assert (await c.get("/api/admin/verifications")).status_code==403
            assert (await c.post("/api/listings",json=lifecycle_payload())).status_code==403
            csrf=c.headers.pop("X-CSRF-Token")
            assert (await c.post("/api/auth/logout")).status_code==403
            c.headers["X-CSRF-Token"]=csrf
            assert (await c.post("/api/auth/logout")).json()["ok"]
            assert (await c.get("/api/listings")).status_code==401
    run_api(exercise())


def test_profile_approval_queue_and_recipient_reapproval_is_idempotent(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"review.db")
    monkeypatch.setenv("SURPLUSSYNC_UPLOAD_DIR",str(tmp_path/"private-documents"))
    database.init_db()
    async def exercise():
        email="org@example.test"; password="Strong-Password-123"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as user_client:
            created=await user_client.post("/api/auth/signup",json={"email":email,"password":password,"role":"RECIPIENT"})
            await assert_signup(user_client,created,email)
            login=await user_client.post("/api/auth/login",json={"email":email,"password":password})
            user_client.headers["X-CSRF-Token"]=login.json()["csrf_token"]
            profile={"organization_name":"A Pantry","address":"Private test address","service_area":"West neighborhood","contact_person":"Morgan","phone":"0000000000","receiving_hours":"Weekdays","registration_type":"Registered trust","registration_number":"T-123","food_categories":["Bakery"],"capacity":80}
            assert (await user_client.put("/api/auth/profile",json={"profile":profile})).status_code==409
            saved=await user_client.put("/api/auth/organization/application",json=organization_application(profile))
            assert saved.status_code==200 and saved.json()["user"]["profile_status"]=="pending"
            assert saved.json()["user"]["organization_verification_status"]=="pending"
        async with client("ADMIN") as admin:
            queue=await admin.get("/api/admin/verifications");row=next(x for x in queue.json() if x["email"]==email)
            assert row["certificate_name"]=="fictional-registration.pdf" and row["registration_type"]=="Registered trust"
            document=await admin.get(f"/api/admin/verifications/{row['user_id']}/document")
            assert document.status_code==200 and document.content.startswith(b"%PDF-")
            reviewed=await admin.patch(f"/api/admin/verifications/{row['user_id']}",json={"decision":"approved"})
            assert reviewed.status_code==200 and reviewed.json()["user"]["profile_status"]=="approved" and reviewed.json()["user"]["organization_verification_status"]=="approved"
            public_recipient=next(x for x in (await admin.get("/api/recipients")).json() if x["name"]=="A Pantry")
            assert public_recipient["area"]=="West neighborhood" and "owner_user_id" not in public_recipient and "address" not in public_recipient
            assert (await admin.patch(f"/api/admin/verifications/{row['user_id']}?role=RECIPIENT",json={"decision":"approved"})).status_code==409
        with database.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM recipients WHERE owner_user_id=?",(row["user_id"],)).fetchone()[0]==1
    run_api(exercise())


def test_password_reset_token_expires_and_is_single_use(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"reset-password.db")
    monkeypatch.setenv("SURPLUSSYNC_DEV_RESET_TOKEN","1")
    monkeypatch.delenv("SURPLUSSYNC_SMTP_HOST",raising=False)
    database.init_db()
    async def exercise():
        email="reset@example.test";old="Old-Password-123";new="New-Password-456"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            created=await c.post("/api/auth/signup",json={"email":email,"password":old,"role":"DONOR"})
            await assert_signup(c,created,email)
            requested=await c.post("/api/auth/password/forgot",json={"email":email})
            token=requested.json()["development_token"]
            second=(await c.post("/api/auth/password/forgot",json={"email":email})).json()["development_token"]
            expired=(await c.post("/api/auth/password/forgot",json={"email":email})).json()["development_token"]
            with database.connection() as db:
                db.execute("UPDATE password_reset_tokens SET expires_at='2000-01-01T00:00:00' WHERE token_hash=?",(database_digest(expired),))
            assert (await c.post("/api/auth/password/reset",json={"email":email,"token":expired,"new_password":old})).status_code==400
            changed=await c.post("/api/auth/password/reset",json={"email":email,"token":token,"new_password":new})
            assert changed.status_code==200
            assert (await c.post("/api/auth/password/reset",json={"email":email,"token":token,"new_password":old})).status_code==400
            assert (await c.post("/api/auth/password/reset",json={"email":email,"token":second,"new_password":old})).status_code==400
            assert (await c.post("/api/auth/login",json={"email":email,"password":old})).status_code==401
            assert (await c.post("/api/auth/login",json={"email":email,"password":new})).status_code==200
    run_api(exercise())


def test_active_rescue_reservations_reduce_capacity_for_other_offers(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"capacity-reservations.db")
    database.init_db()
    with database.connection() as db:
        target=db.execute("SELECT id FROM recipients WHERE name='Green Plate Community Kitchen'").fetchone()["id"]
        db.execute("UPDATE recipients SET capacity=100 WHERE id=?",(target,))
    async def exercise():
        async with client() as donor:
            a=await donor.post("/api/listings",json={**lifecycle_payload(),"portions":70})
            b=await donor.post("/api/listings",json={**lifecycle_payload(),"portions":70})
            assert a.status_code==201 and b.status_code==201
            first=await donor.post(f"/api/listings/{a.json()['id']}/rescue/propose",json={"recipient_id":target})
            assert first.status_code==201
            plan=await donor.post(f"/api/listings/{b.json()['id']}/plan")
            rejected=next(x for x in plan.json()["rejected_candidates"] if x["id"]==target)
            assert any("30 remain after active reservations" in reason for reason in rejected["reasons"])
            second=await donor.post(f"/api/listings/{b.json()['id']}/rescue/propose",json={"recipient_id":target})
            assert second.status_code==409 and "active reservations" in second.json()["detail"]["reasons"][0]
    run_api(exercise())


def test_donor_listing_ownership_and_recipient_availability_scope(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"ownership.db")
    database.init_db()
    async def exercise():
        async with client() as owner:
            listing=(await owner.post("/api/listings",json=lifecycle_payload())).json()
            plan=(await owner.post(f"/api/listings/{listing['id']}/plan")).json()
            now=datetime.now().isoformat(timespec="seconds")
            with database.connection() as db:
                created=db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES('second@example.test',?,'DONOR',?,?)",(hash_password("Second-Account-Password-123"),now,now))
                second_id=created.lastrowid
                db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,'DONOR','{}','approved',?,?)",(second_id,now,now))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as second:
                login=await second.post("/api/auth/login",json={"email":"second@example.test","password":"Second-Account-Password-123"})
                second.headers["X-CSRF-Token"]=login.json()["csrf_token"]
                assert (await second.get("/api/listings")).json()==[]
                assert (await second.get(f"/api/plans/{plan['id']}")).status_code==403
                assert (await second.get("/api/admin/verifications")).status_code==403
                assert (await second.patch(f"/api/listings/{listing['id']}",json=lifecycle_payload("Malicious edit"))).status_code==403
        recipients=database.connection()
        with recipients as db:
            ids=[r["id"] for r in db.execute("SELECT id FROM recipients ORDER BY id")]
        async with client("RECIPIENT",ids[0]) as recipient:
            assert (await recipient.patch(f"/api/recipients/{ids[0]}/availability",json={"available":False})).status_code==200
            assert (await recipient.patch(f"/api/recipients/{ids[1]}/availability",json={"available":False})).status_code==403
    run_api(exercise())


def test_login_rate_limit_is_enforced(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"rate-limit.db")
    database.init_db()
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            for _ in range(5):
                assert (await c.post("/api/auth/login",json={"email":"nobody@example.test","password":"wrong"})).status_code==401
            response=await c.post("/api/auth/login",json={"email":"nobody@example.test","password":"wrong"})
            assert response.status_code==429 and response.json()["detail"]["code"]=="rate_limited"
    run_api(exercise())


def test_unapproved_recipient_cannot_read_operational_data_but_can_logout(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"pending-recipient.db")
    database.init_db()
    monkeypatch.delenv("SURPLUSSYNC_SMTP_HOST",raising=False)
    async def exercise():
        email="pending-recipient@example.test"
        password="Strong-Password-123"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            created=await c.post("/api/auth/signup",json={"email":email,"password":password,"role":"RECIPIENT"})
            await assert_signup(c,created,email)
            login=await c.post("/api/auth/login",json={"email":email,"password":password})
            assert login.status_code==200
            c.headers["X-CSRF-Token"]=login.json()["csrf_token"]
            for path in ("/api/listings","/api/recipients","/api/rescues","/api/dashboard/metrics"):
                response=await c.get(path)
                assert response.status_code==403,path
                assert response.json()["detail"]["code"]=="profile_not_approved"
            logged_out=await c.post("/api/auth/logout")
            assert logged_out.status_code==200 and logged_out.json()["ok"]
            assert (await c.get("/api/auth/me")).status_code==401
    run_api(exercise())


def test_demo_seed_is_repeatable_and_supports_approved_role_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "demo-accounts.db")
    monkeypatch.setenv("SURPLUSSYNC_UPLOAD_DIR", str(tmp_path / "private-documents"))
    database.init_db()
    password = "Local-Demo-Password-2026!"
    accounts = seed_demo_accounts(password)
    with database.connection() as db:
        first_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        for table in ("user_accounts", "recipients", "listings", "rescue_plans", "rescue_cases")}
        users = db.execute("SELECT email,role,is_demo FROM user_accounts ORDER BY email").fetchall()
        demo_users = [row for row in users if row["is_demo"]]
        assert len(demo_users) == 7
        assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE is_demo=1").fetchone()[0] == 7
        assert {row["role"] for row in demo_users} == {"ADMIN", "DONOR", "RECIPIENT", "VOLUNTEER"}
        assert db.execute("SELECT COUNT(*) FROM user_profiles p JOIN user_accounts u ON u.id=p.user_id WHERE u.is_demo=1 AND p.status='approved'").fetchone()[0] == 6  # admin is an account role, not an operational profile
        assert db.execute("SELECT COUNT(*) FROM recipients WHERE demo=1 AND owner_user_id IS NOT NULL").fetchone()[0] == 4
        assert db.execute("SELECT COUNT(*) FROM listings WHERE demo=1 AND donor_user_id IS NOT NULL").fetchone()[0] == 1

    # A second setup with the same password is safe and does not duplicate or reset records.
    assert seed_demo_accounts(password) == accounts
    with database.connection() as db:
        repeated_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                           for table in first_counts}
        assert repeated_counts == first_counts

    async def exercise():
        # A public signup can neither request ADMIN nor log in as the locally seeded admin.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as public:
            assert (await public.post("/api/auth/signup", json={"email":"attacker@example.test","password":password,"role":"ADMIN"})).status_code == 422
            assert (await public.post("/api/auth/signup", json={"email":accounts["admin"],"password":password,"role":"ADMIN"})).status_code == 422

        async with account_client(accounts["donor"], password) as donor:
            assert (await donor.get("/api/admin/verifications")).status_code == 403
            listing_response = await donor.post("/api/listings", json=lifecycle_payload("Seeded demo workflow"))
            assert listing_response.status_code == 201, listing_response.text
            listing = listing_response.json()
            plan_response = await donor.post(f"/api/listings/{listing['id']}/plan")
            assert plan_response.status_code == 201, plan_response.text
            plan = plan_response.json()
            assert plan["recommended"] and plan["feasible_candidates"]
            recipient_id = plan["recommended"]["id"]
            offer = await donor.post(f"/api/listings/{listing['id']}/rescue/propose", json={"recipient_id": recipient_id})
            assert offer.status_code == 201 and offer.json()["status"] == "awaiting_confirmation"
            rescue_id = offer.json()["id"]

            with database.connection() as db:
                recipient_email = db.execute("SELECT u.email FROM recipients r JOIN user_accounts u ON u.id=r.owner_user_id WHERE r.id=?", (recipient_id,)).fetchone()["email"]
                volunteer_id = db.execute("SELECT id FROM user_accounts WHERE email=?", (accounts["volunteer"],)).fetchone()["id"]

            async with account_client(recipient_email, password) as recipient:
                assert (await recipient.post(f"/api/rescues/{rescue_id}/accept", json={"recipient_id":recipient_id})).status_code == 200
                assert (await recipient.post("/api/listings", json=lifecycle_payload("Unauthorized recipient listing"))).status_code == 403
            assert (await donor.patch(f"/api/rescues/{rescue_id}/status", json={"status":"ready_for_pickup"})).status_code == 200

            async with account_client(accounts["volunteer"], password) as volunteer:
                assert (await volunteer.get(f"/api/rescues/{rescue_id}")).status_code == 403
                assert (await donor.post(f"/api/rescues/{rescue_id}/volunteer", json={"volunteer_user_id":volunteer_id})).status_code == 200
                assert (await volunteer.patch(f"/api/rescues/{rescue_id}/status", json={"status":"collected"})).status_code == 200
                delivered = await volunteer.patch(f"/api/rescues/{rescue_id}/status", json={"status":"delivered"})
                assert delivered.status_code == 200 and delivered.json()["status"] == "delivered"

            # New organizations stay pending until the demo admin explicitly approves them.
            email = "pending-judge-org@example.test"
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)), base_url="http://test") as public:
                created=await public.post("/api/auth/signup", json={"email":email,"password":password,"role":"RECIPIENT"})
                assert created.status_code == 201
                await assert_signup(public,created,email)
            async with account_client(email, password) as pending:
                profile = {"organization_name":"Judge Demo Pantry","address":"Fictional local address",
                           "service_area":"Civic Centre","contact_person":"Demo Contact","phone":"000-000-0000",
                           "receiving_hours":"Demo schedule","registration_type":"Registered society","registration_number":"DEMO-001","food_categories":["Prepared meals"],"capacity":40}
                assert (await pending.put("/api/auth/profile", json={"profile":profile})).status_code == 409
                saved = await pending.put("/api/auth/organization/application", json=organization_application(profile))
                assert saved.status_code == 200 and saved.json()["user"]["profile_status"] == "pending"
                blocked = await pending.get("/api/recipients")
                assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "profile_not_approved"
            with database.connection() as db:
                pending_id = db.execute("SELECT id FROM user_accounts WHERE email=?", (email,)).fetchone()["id"]
            async with account_client(accounts["admin"], password) as admin:
                review = await admin.patch(f"/api/admin/verifications/{pending_id}", json={"decision":"approved","reason":"Local demo review"})
                assert review.status_code == 200 and review.json()["user"]["profile_status"] == "approved"
            async with account_client(email, password) as approved:
                assert (await approved.get("/api/recipients")).status_code == 200

            metrics = await donor.get("/api/dashboard/metrics")
            assert metrics.status_code == 200 and metrics.json()["delivered"]["portions"] == 10
            return listing["id"]

    listing_id = run_api(exercise())
    # Seeding again after user activity leaves the listing, its plan, and rescue intact.
    seed_demo_accounts(password)
    with database.connection() as db:
        assert db.execute("SELECT 1 FROM listings WHERE id=?", (listing_id,)).fetchone()
        assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE is_demo=1").fetchone()[0] == 7
        assert db.execute("SELECT COUNT(*) FROM rescue_cases WHERE listing_id=? AND status='delivered'", (listing_id,)).fetchone()[0] == 1


def test_demo_seed_refuses_to_adopt_publicly_created_reserved_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "demo-collision.db")
    database.init_db()
    email = "demo-admin@surplussync.invalid"
    password = "Local-Demo-Password-2026!"

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)), base_url="http://test") as public:
            response = await public.post("/api/auth/signup", json={"email":email,"password":password,"role":"DONOR"})
            assert response.status_code == 201

    run_api(exercise())
    with database.connection() as db:
        before = db.execute("SELECT id,role,is_demo FROM user_accounts WHERE email=?", (email,)).fetchone()
        assert before["role"] == "DONOR" and before["is_demo"] == 0
    try:
        seed_demo_accounts(password)
    except RuntimeError as exc:
        assert "Refusing to adopt" in str(exc)
    else:
        raise AssertionError("The local seeder must not adopt an identity created through public signup.")
    with database.connection() as db:
        after = db.execute("SELECT id,role,is_demo FROM user_accounts WHERE email=?", (email,)).fetchone()
        assert tuple(after) == tuple(before)
        assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE role='ADMIN'").fetchone()[0] == 0


def test_account_demo_marker_migrates_existing_users_as_non_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy-auth.db")
    with database.connection() as db:
        db.execute("""CREATE TABLE user_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,role TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
        db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES('existing@example.test','legacy-hash','DONOR','2026-01-01','2026-01-01')")
    database.init_db()
    with database.connection() as db:
        row = db.execute("SELECT email,role,is_demo FROM user_accounts WHERE email='existing@example.test'").fetchone()
        assert tuple(row) == ("existing@example.test", "DONOR", 0)


def test_account_email_role_migration_preserves_foreign_keys_and_enables_role_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy-email-unique.db")
    with database.connection() as db:
        db.executescript("""
          CREATE TABLE user_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,role TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,updated_at TEXT NOT NULL,email_verified_at TEXT);
          CREATE TABLE user_profiles (
            user_id INTEGER PRIMARY KEY REFERENCES user_accounts(id) ON DELETE CASCADE,
            profile_json TEXT NOT NULL DEFAULT '{}',status TEXT NOT NULL DEFAULT 'pending',
            review_reason TEXT NOT NULL DEFAULT '',reviewed_by INTEGER REFERENCES user_accounts(id),
            reviewed_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,token_hash TEXT NOT NULL UNIQUE,csrf_hash TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,created_at TEXT NOT NULL);
          INSERT INTO user_accounts(id,email,password_hash,role,created_at,updated_at,email_verified_at)
            VALUES(41,'kept@example.test','legacy-hash','DONOR','2026-01-01','2026-01-01','2025-12-31');
          INSERT INTO user_profiles(user_id,profile_json,status,created_at,updated_at)
            VALUES(41,'{"contact_name":"Preserve me"}','approved','2026-01-01','2026-01-01');
          INSERT INTO auth_sessions(token_hash,csrf_hash,user_id,expires_at,created_at)
            VALUES('legacy-session','legacy-csrf',41,'2099-01-01','2026-01-01');
        """)

    database.init_db()
    with database.connection() as db:
        account = db.execute("SELECT id,email,password_hash,role,is_demo FROM user_accounts WHERE id=41").fetchone()
        assert tuple(account) == (41, "kept@example.test", "legacy-hash", "DONOR", 0)
        assert db.execute("SELECT email_verified_at FROM user_accounts WHERE id=41").fetchone()[0] == "2025-12-31"
        assert db.execute("SELECT profile_json FROM user_profiles WHERE user_id=41").fetchone()[0] == '{"contact_name":"Preserve me"}'
        assert db.execute("SELECT COUNT(*) FROM auth_sessions WHERE user_id=41").fetchone()[0] == 1
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
                       ("KEPT@example.test", "second-hash", "RECIPIENT", "2026-01-02", "2026-01-02"))
        db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(41,'VOLUNTEER','{}','pending','2026-01-02','2026-01-02')")
        assert db.execute("SELECT COUNT(*) FROM user_profiles WHERE user_id=41").fetchone()[0] == 2


def test_one_identity_adds_and_switches_role_profiles_securely(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "multi-role.db")
    database.init_db()

    async def exercise():
        email, password = "Shared-Email@example.test", "Strong-Password-123"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            created = await c.post("/api/auth/signup", json={"email": f" {email} ", "password": password, "role": "DONOR"})
            assert created.status_code == 201, created.text
            duplicate = await c.post("/api/auth/signup", json={"email": email.upper(), "password": password, "role": "RECIPIENT"})
            assert duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "account_exists"
            logged = await c.post("/api/auth/login", json={"email": email, "password": password})
            assert logged.status_code == 200 and logged.json()["user"]["role"] == "DONOR"
            c.cookies.update(logged.cookies)
            c.headers["X-CSRF-Token"] = logged.json()["csrf_token"]
            for role in ("RECIPIENT", "VOLUNTEER"):
                added = await c.post("/api/auth/role-profiles", json={"role": role})
                assert added.status_code == 201, added.text
                assert added.json()["user"]["role"] == role
                assert added.json()["user"]["profile_status"] == "pending"
            duplicate_profile = await c.post("/api/auth/role-profiles", json={"role": "VOLUNTEER"})
            assert duplicate_profile.status_code == 409
            ambiguous = await c.post("/api/auth/login", json={"email": email, "password": password})
            assert ambiguous.status_code == 409
            assert ambiguous.json()["detail"]["code"] == "role_selection_required"
            assert ambiguous.json()["detail"]["roles"] == ["DONOR", "RECIPIENT", "VOLUNTEER"]
            forged_admin = await c.post("/api/auth/login", json={"email": email, "password": password, "role": "ADMIN"})
            assert forged_admin.status_code == 403 and forged_admin.json()["detail"]["code"] == "role_not_available"
            for role in ("DONOR", "VOLUNTEER", "RECIPIENT"):
                login = await c.post("/api/auth/login", json={"email": email, "password": password, "role": role})
                assert login.status_code == 200 and login.json()["user"]["role"] == role
                c.cookies.update(login.cookies)
                c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
                me = await c.get("/api/auth/me")
                assert me.status_code == 200 and me.json()["user"]["role"] == role
                if role == "DONOR":
                    saved = await c.put("/api/auth/profile", json={"profile":{"contact_name":"Shared Donor","phone":"0000000000","organization_name":"Shared Donor Org","address":"Mathura","pickup_area":"Mathura"}})
                    assert saved.status_code == 200 and saved.json()["user"]["profile_status"] == "approved"
                if role == "VOLUNTEER":
                    saved = await c.put("/api/auth/profile", json={"profile":{"contact_name":"Shared Volunteer","phone":"0000000000","service_area":"Mathura","availability":"available"}})
                    assert saved.status_code == 200 and saved.json()["user"]["profile_status"] == "approved"
                if role == "RECIPIENT":
                    forbidden_listing = await c.post("/api/listings", json=lifecycle_payload())
                    assert forbidden_listing.status_code == 403 and forbidden_listing.json()["detail"]["code"] == "role_forbidden"
            switched = await c.post("/api/auth/active-role", json={"role": "DONOR"})
            assert switched.status_code == 200 and switched.json()["user"]["role"] == "DONOR"
            forbidden = await c.post("/api/auth/active-role", json={"role": "ADMIN"})
            assert forbidden.status_code == 403
            forgot = await c.post("/api/auth/password/forgot", json={"email": email})
            assert forgot.status_code == 200

    run_api(exercise())


def test_demo_workflow_seed_is_repeatable_and_persists_feasible_category_specific_plans(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "demo-workflows.db")
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    password = "Local-Demo-Password-2026!"
    first = seed_demo_workflows(password)
    with database.connection() as db:
        first_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        for table in ("user_accounts", "recipients", "listings", "rescue_plans", "candidate_evaluations")}
        assert db.execute("SELECT COUNT(*) FROM listings WHERE demo_scenario IS NOT NULL").fetchone()[0] == 3
        demo_recipient = db.execute("""SELECT r.*,u.role,p.status AS profile_status FROM recipients r
            JOIN user_accounts u ON u.id=r.owner_user_id JOIN user_profiles p ON p.user_id=u.id
            WHERE r.name=?""", ("Green Plate Community Kitchen — DEMO",)).fetchone()
        assert demo_recipient and demo_recipient["role"] == "RECIPIENT" and demo_recipient["profile_status"] == "approved"
        assert demo_recipient["area"] == "Mathura" and demo_recipient["demo"] == 1
        assert demo_recipient["travel_minutes"] == 12
        volunteer = db.execute("""SELECT p.profile_json,p.status FROM user_accounts u JOIN user_profiles p ON p.user_id=u.id
            WHERE u.email=? AND u.role='VOLUNTEER' AND u.is_demo=1""", (first["volunteer"],)).fetchone()
        assert volunteer and volunteer["status"] == "approved"
        assert json.loads(volunteer["profile_json"])["service_area"] == "Mathura"
        assert "not live-tracked" in json.loads(volunteer["profile_json"])["availability"]

        for scenario, expected_category, expected_portions in (
            ("prepared_meals_40", "Prepared meals", 40),
            ("bakery_30", "Bakery", 30),
            ("fresh_produce_25", "Fresh produce", 25),
        ):
            seeded = first["scenarios"][scenario]
            listing = db.execute("SELECT * FROM listings WHERE id=?", (seeded["listing_id"],)).fetchone()
            assert listing["food_type"] == expected_category and listing["portions"] == expected_portions
            assert listing["deadline"] > datetime.now().isoformat(timespec="minutes")
            assert listing["safety_verified_by"].startswith("DEMO ONLY")
            assert all(listing[column] == 0 for column in ("safety_handling", "safety_temperature", "safety_allergens", "safety_packaging", "safety_local_rules"))
            assert seeded["simulation_only"] is True
            assert seeded["food_safety_passed"] is False
            plan = db.execute("SELECT id,recommended_recipient_id FROM rescue_plans WHERE listing_id=?", (listing["id"],)).fetchone()
            assert plan and plan["id"] == seeded["plan_id"] and plan["recommended_recipient_id"] is not None
            candidates = db.execute("SELECT recipient_id,feasible FROM candidate_evaluations WHERE plan_id=? AND feasible=1", (plan["id"],)).fetchall()
            assert candidates
            chosen = db.execute("SELECT name,food_categories FROM recipients WHERE id=?", (plan["recommended_recipient_id"],)).fetchone()
            assert expected_category in json.loads(chosen["food_categories"])
            assert chosen["name"] == "Green Plate Community Kitchen — DEMO"

    second = seed_demo_workflows(password)
    with database.connection() as db:
        second_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in first_counts}
        assert second_counts == first_counts
        assert {key: second["scenarios"][key]["listing_id"] for key in second["scenarios"]} == {
            key: first["scenarios"][key]["listing_id"] for key in first["scenarios"]}

    async def verify_saved_api_responses():
        async with account_client(first["accounts"]["donor"], password) as donor:
            listings = await donor.get("/api/listings")
            assert listings.status_code == 200
            visible_ids = {item["id"] for item in listings.json()}
            for seeded in second["scenarios"].values():
                assert seeded["listing_id"] in visible_ids
                response = await donor.get(f"/api/listings/{seeded['listing_id']}/plans/latest")
                assert response.status_code == 200, response.text
                saved_plan = response.json()["plan"]
                assert saved_plan["feasible"] is True
                assert saved_plan["recommended"] is not None
                assert saved_plan["simulation_only"] is True
                assert saved_plan["food_safety_passed"] is False

            # Exercise a complete, persisted demo lifecycle. Every status is
            # explicitly simulation-only; no synthetic check becomes verified.
            workflow = second["scenarios"]["prepared_meals_40"]
            plan = await donor.post(f"/api/listings/{workflow['listing_id']}/plan")
            assert plan.status_code == 201
            assert plan.json()["simulation_only"] is True and not plan.json()["food_safety_passed"]
            recipient_id = plan.json()["recommended"]["id"]
            with database.connection() as db:
                recipient_email = db.execute(
                    "SELECT u.email FROM recipients r JOIN user_accounts u ON u.id=r.owner_user_id WHERE r.id=?",
                    (recipient_id,),
                ).fetchone()["email"]
                volunteer_id = db.execute(
                    "SELECT id FROM user_accounts WHERE email=? COLLATE NOCASE AND role='VOLUNTEER'",
                    (second["accounts"]["volunteer"],),
                ).fetchone()["id"]
            offer = await donor.post(f"/api/listings/{workflow['listing_id']}/rescue/propose", json={"recipient_id": recipient_id})
            assert offer.status_code == 201 and offer.json()["simulation_only"] is True
            rescue_id = offer.json()["id"]
            async with account_client(recipient_email, password) as recipient:
                accepted = await recipient.post(f"/api/rescues/{rescue_id}/accept", json={"recipient_id": recipient_id})
                assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
                assert accepted.json()["simulation_only"] is True
            ready = await donor.patch(f"/api/rescues/{rescue_id}/status", json={"status":"ready_for_pickup"})
            assert ready.status_code == 200 and ready.json()["status"] == "ready_for_pickup"
            assigned = await donor.post(f"/api/rescues/{rescue_id}/volunteer", json={"volunteer_user_id": volunteer_id})
            assert assigned.status_code == 200
            async with account_client(second["accounts"]["volunteer"], password) as volunteer:
                assigned_tasks = await volunteer.get("/api/rescues")
                assert assigned_tasks.status_code == 200
                assert [item["id"] for item in assigned_tasks.json()] == [rescue_id]
                collected = await volunteer.patch(f"/api/rescues/{rescue_id}/status", json={"status":"collected"})
                assert collected.status_code == 200 and collected.json()["status"] == "collected"
                delivered = await volunteer.patch(f"/api/rescues/{rescue_id}/status", json={"status":"delivered"})
                assert delivered.status_code == 200 and delivered.json()["status"] == "delivered"
                assert delivered.json()["simulation_only"] is True
                assert delivered.json()["risk_assessment"]["category"] != "Low"
                assert any("simulation only" in reason.lower() for reason in delivered.json()["risk_assessment"]["reasons"])
            async with account_client(second["accounts"]["donor"], password) as refreshed_donor:
                saved = await refreshed_donor.get(f"/api/rescues/{rescue_id}")
                assert saved.status_code == 200 and saved.json()["status"] == "delivered"
                assert saved.json()["simulation_only"] is True
                metrics = await refreshed_donor.get("/api/dashboard/metrics")
                assert metrics.status_code == 200
                assert metrics.json()["delivered"]["portions"] == 40
    run_api(verify_saved_api_responses())


def test_demo_workflow_seed_reuses_existing_passwords_without_refreshing_demo_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "demo-workflows-existing-accounts.db")
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    database.init_db()
    password = "Local-Demo-Password-2026!"
    seeded_accounts = seed_demo_accounts(password)
    with database.connection() as db:
        old_hashes = {row["email"]: row["password_hash"] for row in db.execute("SELECT email,password_hash FROM user_accounts WHERE is_demo=1")}
        before_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in ("user_accounts", "recipients", "listings", "rescue_plans")}

    first = seed_demo_workflows()
    with database.connection() as db:
        new_hashes = {row["email"]: row["password_hash"] for row in db.execute("SELECT email,password_hash FROM user_accounts WHERE is_demo=1")}
        for email, password_hash in old_hashes.items():
            assert new_hashes[email] == password_hash
        assert new_hashes[first["recipient_account"]] == old_hashes[seeded_accounts["donor"]]
        assert db.execute("SELECT status FROM user_profiles WHERE user_id=(SELECT id FROM user_accounts WHERE email=? AND role='RECIPIENT')",
                          (first["recipient_account"],)).fetchone()[0] == "approved"
        after_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        for table in before_counts}
        assert after_counts["user_accounts"] == before_counts["user_accounts"] + 1

    second = seed_demo_workflows()
    with database.connection() as db:
        repeated_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                           for table in before_counts}
        assert repeated_counts == after_counts
        assert second["recipient_account"] == first["recipient_account"]


def test_legacy_synthetic_demo_checks_are_never_returned_as_human_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy-synthetic-demo.db")
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    password = "Local-Demo-Password-2026!"
    seeded = seed_demo_workflows(password)
    listing_id = seeded["scenarios"]["prepared_meals_40"]["listing_id"]
    with database.connection() as db:
        # Recreate the earlier synthetic fixture state in this isolated DB.
        db.execute("UPDATE listings SET safety_handling=1,safety_temperature=1,safety_allergens=1,safety_packaging=1,safety_local_rules=1,safety_verified_by=? WHERE id=?",
                   ("DEMO ONLY synthetic; no human verification", listing_id))

    async def inspect_sanitized_api_state():
        async with account_client(seeded["accounts"]["donor"], password) as donor:
            response = await donor.get("/api/listings")
            assert response.status_code == 200
            item = next(row for row in response.json() if row["id"] == listing_id)
            assert item["demo"] is True
            assert not any(item["safety"].values())
            assert item["safety_verified_by"].startswith("DEMO ONLY")
            plan = await donor.post(f"/api/listings/{listing_id}/plan")
            assert plan.status_code == 201
            assert plan.json()["feasible"] is True
            assert plan.json()["simulation_only"] is True
            assert plan.json()["food_safety_passed"] is False
            assert "does not make the listing operationally eligible" in plan.json()["explanation"].lower()

    run_api(inspect_sanitized_api_state())


def test_shared_presentation_identity_seeds_three_roles_and_feasible_workflows_idempotently(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "shared-demo.db")
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED", raising=False)
    monkeypatch.setenv("SURPLUSSYNC_PRESENTATION_DEMO_PASSWORD", "Private-Demo-Password-2026!")
    assert not presentation_demo_enabled()
    first = seed_presentation_demo(email="shared-demo@example.test")
    with database.connection() as db:
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("user_accounts", "user_profiles", "listings", "rescue_plans")}
        identity = db.execute("SELECT id,role,is_demo FROM user_accounts WHERE email=?", ("shared-demo@example.test",)).fetchone()
        assert identity and identity["role"] != "ADMIN"
        assert {row["role"] for row in db.execute("SELECT role FROM user_profiles WHERE user_id=?", (identity["id"],))} == {"DONOR", "RECIPIENT", "VOLUNTEER"}
        assert db.execute("SELECT status FROM user_profiles WHERE user_id=? AND role='RECIPIENT'", (identity["id"],)).fetchone()[0] == "pending"
        assert db.execute("SELECT COUNT(*) FROM recipients WHERE name LIKE 'Green Plate Community Kitchen%DEMO%' AND demo=1").fetchone()[0] == 1
    assert set(first["available_roles"]) == {"DONOR", "RECIPIENT", "VOLUNTEER"}
    assert len(first["scenarios"]) == 3
    assert all(item["feasible_candidates"] > 0 and item["plan_id"] for item in first["scenarios"].values())
    assert all(item["simulation_only"] and not item["food_safety_passed"] for item in first["scenarios"].values())
    second = seed_presentation_demo(email="shared-demo@example.test")
    with database.connection() as db:
        assert {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in counts} == counts
        assert db.execute("SELECT COUNT(*) FROM listings WHERE demo_scenario IS NOT NULL").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE email='shared-demo@example.test'").fetchone()[0] == 1
    assert all(item["feasible_candidates"] > 0 for item in second["scenarios"].values())
    assert all(item["simulation_only"] and not item["food_safety_passed"] for item in second["scenarios"].values())


def test_shared_presentation_seed_preserves_existing_recipient_profile_and_password(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "shared-existing.db")
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    database.init_db()
    with database.connection() as db:
        now = datetime.now().isoformat(timespec="seconds")
        user_id = db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
                             ("shared-existing@example.test", hash_password("Existing-Password-2026!"), "RECIPIENT", now, now)).lastrowid
        stored_hash = db.execute("SELECT password_hash FROM user_accounts WHERE id=?", (user_id,)).fetchone()[0]
        original = json.dumps({"organization_name":"Existing Pending Organization","registration_number":"NOT-REVIEWED"})
        db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,'RECIPIENT',?,'pending',?,?)", (user_id, original, now, now))
    result = seed_presentation_demo(email="shared-existing@example.test")
    assert set(result["available_roles"]) == {"DONOR", "RECIPIENT", "VOLUNTEER"}
    with database.connection() as db:
        assert db.execute("SELECT password_hash FROM user_accounts WHERE id=?", (user_id,)).fetchone()[0] == stored_hash
        assert tuple(db.execute("SELECT profile_json,status FROM user_profiles WHERE user_id=? AND role='RECIPIENT'", (user_id,)).fetchone()) == (original, "pending")
        assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE email='shared-existing@example.test'").fetchone()[0] == 1


def test_signup_login_without_email_requirement_and_legacy_user(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "signup-no-email.db")
    database.init_db()
    with database.connection() as db:
        now = datetime.now().isoformat(timespec="seconds")
        # Old DBs may retain this nullable legacy field; it no longer gates auth.
        db.execute("ALTER TABLE user_accounts ADD COLUMN email_verified_at TEXT")
        user_id = db.execute("INSERT INTO user_accounts(email,password_hash,role,email_verified_at,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                             ("legacy@example.test", hash_password("Legacy-Password-123"), "DONOR", None, now, now)).lastrowid
        db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,'DONOR','{}','approved',?,?)", (user_id, now, now))

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            email, password = "new@example.test", "Strong-Password-123"
            created = await c.post("/api/auth/signup", json={"email":email,"password":password,"role":"DONOR"})
            assert created.status_code == 201 and "email" not in created.json()
            assert "verify" not in str(created.json()).lower()
            assert (await c.post("/api/auth/signup", json={"email":email,"password":password,"role":"DONOR"})).status_code == 409
            assert (await c.post("/api/auth/signup", json={"email":"admin@example.test","password":password,"role":"ADMIN"})).status_code == 422
            login = await c.post("/api/auth/login", json={"email":email,"password":password})
            assert login.status_code == 200 and "email_verified" not in login.json()["user"]
            c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            assert (await c.get("/api/auth/me")).status_code == 200
            assert (await c.get("/api/admin/verifications")).status_code == 403
            await c.post("/api/auth/logout")
            assert (await c.get("/api/auth/me")).status_code == 401
            legacy = await c.post("/api/auth/login", json={"email":"legacy@example.test","password":"Legacy-Password-123"})
            assert legacy.status_code == 200
        api_routes = {(method, route.path) for route in app.routes if hasattr(route, "methods") for method in (route.methods or set())}
        assert ("POST", "/api/auth/email/verify") not in api_routes
        assert ("POST", "/api/auth/email/resend") not in api_routes
    run_api(exercise())


def test_new_donor_can_complete_profile_without_email_and_org_still_requires_admin_review(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "profile-no-email.db")
    monkeypatch.setenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED","true")
    database.init_db()

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            email, password = "donor@example.test", "Strong-Password-123"
            assert (await c.post("/api/auth/signup", json={"email":email,"password":password,"role":"DONOR"})).status_code == 201
            login = await c.post("/api/auth/login", json={"email":email,"password":password})
            assert login.status_code == 200
            c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            profile = {"contact_name":"Test contact","phone":"0000000000","organization_name":"Test bakery","address":"Demo address","pickup_area":"Central"}
            saved = await c.put("/api/auth/profile", json={"profile":profile})
            assert saved.status_code == 200 and saved.json()["user"]["profile_status"] == "approved"
            org = await c.post("/api/auth/signup", json={"email":"org@example.test","password":password,"role":"RECIPIENT"})
            assert org.status_code == 201
            org_login = await c.post("/api/auth/login", json={"email":"org@example.test","password":password})
            assert org_login.status_code == 200 and org_login.json()["user"]["profile_status"] == "pending"
            c.headers["X-CSRF-Token"] = org_login.json()["csrf_token"]
            assert (await c.get("/api/recipients")).status_code == 403
            bypass=await c.put("/api/auth/profile",json={"profile":{"organization_name":"Should Not Bypass Review","service_area":"West","capacity":20,"food_categories":["Bakery"]}})
            assert bypass.status_code==409 and bypass.json()["detail"]["code"]=="certificate_required"
    run_api(exercise())


def test_presentation_demo_organization_setup_skips_certificate_but_never_official_review(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"presentation-org.db")
    monkeypatch.delenv("TURSO_DATABASE_URL",raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN",raising=False)
    monkeypatch.delenv("VERCEL",raising=False)
    monkeypatch.setenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED","true")
    password="Private-Presentation-Password-2026!"
    seed_presentation_demo(email="presentation-org@example.test",password=password)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as shared:
            login=await shared.post("/api/auth/login",json={"email":"presentation-org@example.test","password":password,"role":"RECIPIENT"})
            assert login.status_code==200
            assert login.json()["user"]["profile_demo"] is True and login.json()["user"]["presentation_demo_mode"] is True
            shared.headers["X-CSRF-Token"]=login.json()["csrf_token"]
            blocked=await shared.get("/api/recipients")
            assert blocked.status_code==403 and blocked.json()["detail"]["code"]=="profile_not_approved"
            profile={"organization_name":"Fictional Court Pantry","service_area":"Mathura","capacity":70,"food_categories":["Prepared meals","Bakery"]}
            saved=await shared.put("/api/auth/profile",json={"profile":profile})
            assert saved.status_code==200,saved.text
            assert saved.json()["user"]["profile_status"]=="approved"
            assert saved.json()["user"]["organization_verification_status"]=="demo_fixture"
            assert "not legal registration" in saved.json()["message"]
            recipients=await shared.get("/api/recipients")
            assert recipients.status_code==200
            own=next(item for item in recipients.json() if item.get("can_manage"))
            assert own["name"]=="Fictional Court Pantry — DEMO" and bool(own["demo"]) is True and own["food_categories"]==profile["food_categories"]
            with database.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM organization_documents WHERE user_id=(SELECT id FROM user_accounts WHERE email='presentation-org@example.test')").fetchone()[0]==0
                assert db.execute("SELECT COUNT(*) FROM organization_verifications WHERE user_id=(SELECT id FROM user_accounts WHERE email='presentation-org@example.test')").fetchone()[0]==0
                assert db.execute("SELECT demo,status FROM user_profiles WHERE user_id=(SELECT id FROM user_accounts WHERE email='presentation-org@example.test') AND role='RECIPIENT'").fetchone()["demo"]==1

            recipient_id=own["id"]
            changed=await shared.post("/api/auth/active-role",json={"role":"DONOR"})
            assert changed.status_code==200 and changed.json()["user"]["role"]=="DONOR"
            donor_listing=await shared.post("/api/listings",json=lifecycle_payload("Shared identity donor workflow"))
            assert donor_listing.status_code==201
            plan=await shared.post(f"/api/listings/{donor_listing.json()['id']}/plan")
            assert plan.status_code==201 and plan.json()["recommended"]
            assert recipient_id not in {candidate["id"] for candidate in plan.json()["feasible_candidates"]}
            assert recipient_id not in {candidate["id"] for candidate in plan.json()["rejected_candidates"]}
            assert (await shared.post("/api/auth/active-role",json={"role":"RECIPIENT"})).status_code==200
            async with client("DONOR") as outside_donor:
                offered_listing=(await outside_donor.post("/api/listings",json=lifecycle_payload("External donor workflow"))).json()
                offer=await outside_donor.post(f"/api/listings/{offered_listing['id']}/rescue/propose",json={"recipient_id":recipient_id})
                assert offer.status_code==201,offer.text
            accepted=await shared.post(f"/api/rescues/{offer.json()['id']}/accept",json={"recipient_id":recipient_id})
            assert accepted.status_code==200 and accepted.json()["status"]=="accepted"

            monkeypatch.setenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED","false")
            disabled=await shared.get("/api/recipients")
            assert disabled.status_code==403 and disabled.json()["detail"]["code"]=="presentation_demo_disabled"

    run_api(exercise())


def test_account_deletion_revokes_session_anonymizes_owned_data_and_releases_email(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "account-delete.db")
    database.init_db()

    async def exercise():
        async with client("DONOR") as donor:
            user_id = client_user_id("DONOR")
            created = await donor.post("/api/listings", json=lifecycle_payload())
            assert created.status_code == 201, created.text
            listing_id = created.json()["id"]
            with database.connection() as db:
                assert db.execute("SELECT donor_user_id FROM listings WHERE id=?", (listing_id,)).fetchone()[0] == user_id
                assert db.execute("SELECT COUNT(*) FROM auth_sessions WHERE user_id=?", (user_id,)).fetchone()[0] == 1
                demo_count = db.execute("SELECT COUNT(*) FROM listings WHERE demo=1").fetchone()[0]

            request_body = {"confirm_email":"test-donor@example.test", "password":"wrong-password"}
            assert (await donor.post("/api/auth/account/delete", json=request_body)).status_code == 403
            assert (await donor.post("/api/auth/account/delete", json={**request_body,"confirm_email":"someone-else@example.test","password":"Test-password-123"})).status_code == 422
            assert (await donor.get("/api/auth/me")).status_code == 200

            removed = await donor.post("/api/auth/account/delete", json={**request_body,"password":"Test-password-123"})
            assert removed.status_code == 200, removed.text
            assert (await donor.get("/api/auth/me")).status_code == 401
            recreated=await donor.post("/api/auth/signup",json={"email":"test-donor@example.test","password":"New-Password-123","role":"DONOR"})
            assert recreated.status_code==201

            with database.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE id=?", (user_id,)).fetchone()[0] == 0
                assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE email='test-donor@example.test'").fetchone()[0] == 1
                assert db.execute("SELECT COUNT(*) FROM auth_sessions WHERE user_id=?", (user_id,)).fetchone()[0] == 0
                assert db.execute("SELECT COUNT(*) FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()[0] == 0
                anonymized=db.execute("SELECT donor_user_id,donor_name FROM listings WHERE id=?", (listing_id,)).fetchone()
                assert tuple(anonymized)==(None,"Deleted donor")
                assert db.execute("SELECT status FROM rescue_cases WHERE listing_id=?", (listing_id,)).fetchone()[0] == "listed"
                assert db.execute("SELECT COUNT(*) FROM listings WHERE demo=1").fetchone()[0] == demo_count

        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 4321))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as public:
            again = await public.post("/api/auth/signup", json={"email":"test-donor@example.test","password":"Test-password-123","role":"DONOR"})
            assert again.status_code == 409, again.text
            login = await public.post("/api/auth/login", json={"email":"test-donor@example.test","password":"New-Password-123"})
            assert login.status_code == 200

    run_api(exercise())


def test_recipient_account_deletion_blocks_active_rescue_then_preserves_anonymized_history(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "recipient-delete.db")
    database.init_db()
    with database.connection() as db:
        recipient_id = db.execute("SELECT id FROM recipients ORDER BY id LIMIT 1").fetchone()[0]
        listing_id = db.execute("SELECT id FROM listings WHERE demo=1 ORDER BY id LIMIT 1").fetchone()[0]
        case = db.execute("SELECT id FROM rescue_cases WHERE listing_id=?", (listing_id,)).fetchone()[0]
        now = datetime.now().isoformat(timespec="seconds")
        db.execute("UPDATE rescue_cases SET recipient_id=?,status='accepted',portions_reserved=12,accepted_at=?,updated_at=? WHERE id=?", (recipient_id,now,now,case))
        db.execute("INSERT INTO rescue_events(rescue_id,event_type,from_status,to_status,recipient_id,created_at) VALUES(?,'accepted','awaiting_confirmation','accepted',?,?)", (case,recipient_id,now))
        plan = db.execute("INSERT INTO rescue_plans(listing_id,recommended_recipient_id,created_at,updated_at) VALUES(?,?,?,?)", (listing_id,recipient_id,now,now)).lastrowid
        db.execute("INSERT INTO candidate_evaluations(plan_id,recipient_id,feasible,reasons,travel_minutes,capacity_after,rank,created_at) VALUES(?,?,1,'[]',15,20,1,?)", (plan,recipient_id,now))

    async def exercise():
        async with client("RECIPIENT", recipient_id) as recipient:
            user_id = client_user_id("RECIPIENT")
            deletion_body={"confirm_email":"test-recipient@example.test","password":"Test-password-123"}
            blocked=await recipient.post("/api/auth/account/delete",json=deletion_body)
            assert blocked.status_code==409 and blocked.json()["detail"]["code"]=="active_rescue_assignments"
            assert (await recipient.get("/api/auth/me")).status_code==200
            with database.connection() as db:
                db.execute("UPDATE rescue_cases SET status='cancelled',portions_reserved=0 WHERE id=?",(case,))
            removed = await recipient.post("/api/auth/account/delete", json=deletion_body)
            assert removed.status_code == 200, removed.text
            assert (await recipient.get("/api/auth/me")).status_code == 401

        with database.connection() as db:
            rescue = db.execute("SELECT status,recipient_id,portions_reserved FROM rescue_cases WHERE id=?", (case,)).fetchone()
            assert tuple(rescue) == ("cancelled",recipient_id,0)
            timeline = db.execute("SELECT to_status,recipient_id FROM rescue_events WHERE rescue_id=? ORDER BY id DESC LIMIT 1", (case,)).fetchone()
            assert tuple(timeline) == ("accepted",recipient_id)
            assert db.execute("SELECT recommended_recipient_id FROM rescue_plans WHERE id=?", (plan,)).fetchone()[0] == recipient_id
            assert db.execute("SELECT COUNT(*) FROM candidate_evaluations WHERE plan_id=?", (plan,)).fetchone()[0] == 1
            anonymized=db.execute("SELECT name,owner_user_id,available FROM recipients WHERE id=?", (recipient_id,)).fetchone()
            assert tuple(anonymized)==(f"Former recipient #{recipient_id}",None,0)
            assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE id=?", (user_id,)).fetchone()[0] == 0

    run_api(exercise())


def test_last_admin_cannot_delete_own_account(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "last-admin-delete.db")
    database.init_db()

    async def exercise():
        async with client("ADMIN") as admin:
            response = await admin.post("/api/auth/account/delete", json={"confirm_email":"test-admin@example.test","password":"Test-password-123"})
            assert response.status_code == 409
            with database.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE email='test-admin@example.test'").fetchone()[0] == 1

    run_api(exercise())


def test_signup_ignores_smtp_and_legacy_email_routes_are_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "no-email-dependencies.db")
    with database.connection() as db:
        db.execute("CREATE TABLE email_verification_tokens (id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL)")
        db.execute("INSERT INTO email_verification_tokens(token_hash) VALUES('legacy-token-hash')")
    database.init_db()
    def smtp_must_not_be_used(*args, **kwargs):
        raise AssertionError("Signup must not send email")
    monkeypatch.setattr(api_main.smtplib, "SMTP", smtp_must_not_be_used)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            body = {"email":"no-email@example.test","password":"Strong-Password-123","role":"DONOR"}
            signup = await c.post("/api/auth/signup", json=body)
            assert signup.status_code == 201 and signup.json()["message"] == "Account created. You can log in now."
            assert (await c.post("/api/auth/login", json=body)).status_code == 200
            # Missing legacy routes are confirmed from the route table below;
            # unknown /api POSTs are stopped earlier by CSRF middleware.
        with database.connection() as db:
            assert db.execute("SELECT token_hash FROM email_verification_tokens").fetchone()[0] == "legacy-token-hash"
            assert db.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[0] == 0
    run_api(exercise())


def test_ngo_document_validation_private_review_resubmission_and_approval(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"ngo-review.db")
    monkeypatch.setenv("SURPLUSSYNC_UPLOAD_DIR",str(tmp_path/"private-documents"))
    database.init_db()
    profile={"organization_name":"Fictional Pantry","address":"Private test address","service_area":"Central",
             "contact_person":"Authorized Test Contact","phone":"+91 98765 43210","receiving_hours":"Weekdays",
             "registration_type":"Registered trust","registration_number":"TEST-REG-001",
             "food_categories":["Prepared meals"],"capacity":50}

    async def exercise():
        email="ngo-review@example.test";password="Strong-Password-123"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as public:
            assert (await public.post("/api/auth/signup",json={"email":email,"password":password,"role":"RECIPIENT"})).status_code==201
        async with account_client(email,password) as ngo:
            me=(await ngo.get("/api/auth/me")).json()["user"]
            assert me["profile_status"]=="pending" and me["organization_verification_status"]=="pending"
            assert (await ngo.get("/api/recipients")).status_code==403
            assert (await ngo.put("/api/auth/organization/application",json={"profile":profile})).status_code==422
            assert (await ngo.put("/api/auth/profile",json={"profile":profile})).status_code==409
            for registration_number in ("", "   "):
                incomplete = dict(profile)
                incomplete["registration_number"] = registration_number
                assert (await ngo.put("/api/auth/organization/application",json=organization_application(incomplete))).status_code==422
            incomplete = dict(profile)
            incomplete.pop("registration_number")
            assert (await ngo.put("/api/auth/organization/application",json=organization_application(incomplete))).status_code==422
            invalid=organization_application(profile)
            invalid["certificate_filename"]="certificate.exe"
            assert (await ngo.put("/api/auth/organization/application",json=invalid)).status_code==422
            invalid=organization_application(profile)
            invalid["certificate_base64"]=base64.b64encode(b"MZ\x00not-a-pdf").decode()
            assert (await ngo.put("/api/auth/organization/application",json=invalid)).status_code==422
            invalid=organization_application(profile)
            invalid["certificate_filename"]="../certificate.pdf"
            assert (await ngo.put("/api/auth/organization/application",json=invalid)).status_code==422

            async with client("ADMIN") as admin:
                queue=await admin.get("/api/admin/verifications")
                row=next(item for item in queue.json() if item["email"]==email)
                denied_approval=await admin.patch(f"/api/admin/verifications/{row['user_id']}",json={"decision":"approved"})
                assert denied_approval.status_code==409 and denied_approval.json()["detail"]["code"]=="certificate_required"
            async with client("DONOR") as donor:
                assert (await donor.get(f"/api/admin/verifications/{row['user_id']}/document")).status_code==403

            submitted=await ngo.put("/api/auth/organization/application",json=organization_application(profile))
            assert submitted.status_code==200 and submitted.json()["user"]["organization_verification_status"]=="pending"
            own_doc=await ngo.get("/api/auth/organization/document")
            assert own_doc.status_code==200 and own_doc.content.startswith(b"%PDF-")

            async with client("ADMIN") as admin:
                row=next(item for item in (await admin.get("/api/admin/verifications")).json() if item["email"]==email)
                assert row["profile"]["contact_person"]=="Authorized Test Contact"
                assert row["registration_number"]=="TEST-REG-001"
                assert row["certificate_name"]=="fictional-registration.pdf"
                private_doc=await admin.get(f"/api/admin/verifications/{row['user_id']}/document")
                assert private_doc.status_code==200 and private_doc.headers["cache-control"]=="private, no-store"
                request_resubmit=await admin.patch(f"/api/admin/verifications/{row['user_id']}",json={"decision":"resubmission_required","reason":"Please replace the document with a readable registration page."})
                assert request_resubmit.status_code==200
            state=(await ngo.get("/api/auth/me")).json()["user"]
            assert state["profile_status"]=="rejected" and state["organization_verification_status"]=="resubmission_required"
            assert (await ngo.get("/api/recipients")).status_code==403
            resubmitted=await ngo.put("/api/auth/organization/application",json=organization_application(profile))
            assert resubmitted.status_code==200 and resubmitted.json()["user"]["organization_verification_status"]=="pending"
            with database.connection() as db:
                docs=db.execute("SELECT storage_name,is_current FROM organization_documents WHERE user_id=? ORDER BY id",(row["user_id"],)).fetchall()
                assert len(docs)==2 and [item["is_current"] for item in docs]==[0,1]
                for item in docs:
                    stored=tmp_path/"private-documents"/item["storage_name"]
                    assert stored.is_file() and stored.parent != Path(__file__).resolve().parents[2]/"frontend"/"public"

            async with client("ADMIN") as admin:
                row=next(item for item in (await admin.get("/api/admin/verifications")).json() if item["email"]==email)
                approved=await admin.patch(f"/api/admin/verifications/{row['user_id']}",json={"decision":"approved","reason":"Document reviewed by test admin."})
                assert approved.status_code==200 and approved.json()["user"]["organization_verification_status"]=="approved"
            assert (await ngo.get("/api/recipients")).status_code==200
            with database.connection() as db:
                owned_recipient=db.execute("SELECT id FROM recipients WHERE owner_user_id=?",(row["user_id"],)).fetchone()[0]
                stored_names=[item["storage_name"] for item in db.execute("SELECT storage_name FROM organization_documents WHERE user_id=?",(row["user_id"],)).fetchall()]
            removed=await ngo.post("/api/auth/account/delete",json={"confirm_email":email,"password":password})
            assert removed.status_code==200 and (await ngo.get("/api/auth/me")).status_code==401
            with database.connection() as db:
                anonymized=db.execute("SELECT name,owner_user_id,available FROM recipients WHERE id=?",(owned_recipient,)).fetchone()
                assert tuple(anonymized)==(f"Former recipient #{owned_recipient}",None,0)
                assert db.execute("SELECT COUNT(*) FROM organization_documents WHERE user_id=?",(row["user_id"],)).fetchone()[0]==0
                assert db.execute("SELECT COUNT(*) FROM user_accounts WHERE email=?",(email,)).fetchone()[0]==0
            assert all(not (tmp_path/"private-documents"/name).exists() for name in stored_names)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as public:
                again=await public.post("/api/auth/signup",json={"email":email,"password":password,"role":"RECIPIENT"})
                assert again.status_code==201
        with database.connection() as db:
            audit_rows=db.execute("SELECT action,actor_user_id,subject_type,subject_id,details FROM security_audit").fetchall()
            assert sum(row["action"].startswith(("organization_","verification_")) for row in audit_rows)>=4
            anonymized_events=[row for row in audit_rows if row["action"].startswith(("organization_","verification_")) and row["subject_type"]=="anonymized"]
            assert len(anonymized_events)>=2
            assert all(row["actor_user_id"] is None and row["subject_id"]=="" and row["details"]=="{}" for row in anonymized_events)

    run_api(exercise())


def test_certificate_size_limit_is_configurable(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"size-limit.db")
    monkeypatch.setenv("SURPLUSSYNC_UPLOAD_DIR",str(tmp_path/"private-documents"))
    monkeypatch.setenv("SURPLUSSYNC_MAX_CERTIFICATE_BYTES","1024")
    database.init_db()
    profile={"organization_name":"Size Test","address":"Test street","service_area":"Central","contact_person":"Test Contact","phone":"0000000000","receiving_hours":"Always","registration_type":"Registered society","registration_number":"SIZE-TEST-001","food_categories":["Bakery"],"capacity":25}
    async def exercise():
        email="size@example.test";password="Strong-Password-123"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as public:
            await public.post("/api/auth/signup",json={"email":email,"password":password,"role":"RECIPIENT"})
        async with account_client(email,password) as ngo:
            limit=await ngo.get("/api/auth/organization/application-limit")
            assert limit.status_code==200 and limit.json()["max_certificate_bytes"]==1024
            large=b"%PDF-1.4\n"+b"0"*2048+b"\n%%EOF"
            payload={"profile":profile,"certificate_filename":"large.pdf","certificate_base64":base64.b64encode(large).decode()}
            response=await ngo.put("/api/auth/organization/application",json=payload)
            assert response.status_code==413 and response.json()["detail"]["code"]=="certificate_size_invalid"
    run_api(exercise())


def test_account_deletion_rejects_active_donor_assignment(tmp_path,monkeypatch):
    monkeypatch.setattr(database,"DB_PATH",tmp_path/"active-donor-delete.db")
    database.init_db()
    async def exercise():
        async with client("DONOR") as donor:
            listing=(await donor.post("/api/listings",json=lifecycle_payload())).json()
            plan=(await donor.post(f"/api/listings/{listing['id']}/plan")).json()
            offer=await donor.post(f"/api/listings/{listing['id']}/rescue/propose",json={"recipient_id":plan["recommended"]["id"]})
            assert offer.status_code==201
            response=await donor.post("/api/auth/account/delete",json={"confirm_email":"test-donor@example.test","password":"Test-password-123"})
            assert response.status_code==409 and response.json()["detail"]["code"]=="active_rescue_assignments"
            assert (await donor.get("/api/auth/me")).status_code==200
    run_api(exercise())
