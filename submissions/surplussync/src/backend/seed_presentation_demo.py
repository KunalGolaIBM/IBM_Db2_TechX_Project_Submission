"""Idempotent presentation identity and workflow seed, gated at API startup.

This seeds only tagged fictional profiles, recipients, listings and plans. It
never changes an existing account password or review state. If the reserved
identity is absent (for example after an ephemeral deployment restart), a
server-side SURPLUSSYNC_PRESENTATION_DEMO_PASSWORD is required to recreate it.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from .auth import hash_password, verify_password
from .database import connection, init_db

DEMO_EMAIL = "tournamentgaming07@gmail.com"
RECIPIENT_NAME = "Green Plate Community Kitchen — DEMO"
SCENARIOS = (
    ("prepared_meals_40", "Green Leaf Restaurant — DEMO", "Prepared meals", 40),
    ("bakery_30", "Rajat Bakery Demo", "Bakery", 30),
    ("fresh_produce_25", "Mathura Fresh Foods Demo", "Fresh produce", 25),
)


def seed_presentation_demo(email: str | None = None, password: str | None = None) -> dict:
    """Ensure one Donor/Recipient/Volunteer identity and three persisted plans."""
    if os.getenv("VERCEL", "").lower() in {"1", "true", "yes"}:
        raise RuntimeError("Presentation seeding is intended only for the configured Render/local database.")
    email = (email or os.getenv("SURPLUSSYNC_PRESENTATION_DEMO_EMAIL") or DEMO_EMAIL).strip().lower()
    password = password if password is not None else os.getenv("SURPLUSSYNC_PRESENTATION_DEMO_PASSWORD", "")
    if password and not 12 <= len(password) <= 128:
        raise ValueError("Presentation demo password must be 12–128 characters.")

    init_db()
    now = datetime.now()
    stamp = now.isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        account = db.execute("SELECT id,password_hash,role,status,is_demo FROM user_accounts WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if account and account["role"] == "ADMIN":
            raise RuntimeError("The reserved presentation login cannot be an administrator account.")
        if account and password and not verify_password(password, account["password_hash"]):
            raise RuntimeError("The existing reserved account password does not match the configured secret; it was not changed.")
        if not account:
            if not password:
                raise RuntimeError("Set SURPLUSSYNC_PRESENTATION_DEMO_PASSWORD in the private deployment environment before enabling presentation seeding.")
            user_id = db.execute("INSERT INTO user_accounts(email,password_hash,role,is_demo,created_at,updated_at) VALUES(?,?,'DONOR',1,?,?)",
                                 (email, hash_password(password), stamp, stamp)).lastrowid
        else:
            user_id = account["id"]

        def source_profile(role: str):
            return db.execute("""SELECT p.profile_json,p.status FROM user_profiles p JOIN user_accounts u ON u.id=p.user_id
                WHERE p.role=? AND u.is_demo=1 AND u.email=? COLLATE NOCASE""",
                (role, f"demo-{role.lower()}@surplussync.invalid")).fetchone()

        role_data = {
            "DONOR": (source_profile("DONOR"), {"contact_name": "Fictional Demo Donor", "phone": "000-000-0000", "organization_name": "Green Leaf Restaurant — DEMO", "address": "Fictional Mathura demo location", "pickup_area": "Mathura"}),
            "VOLUNTEER": (source_profile("VOLUNTEER"), {"contact_name": "HyperX Demo Volunteer", "phone": "000-000-0000", "service_area": "Mathura", "availability": "Available for fictional demo tasks; not live-tracked"}),
            "RECIPIENT": (None, {"organization_name": "HyperX Community Food Support — DEMO", "service_area": "Mathura", "food_categories": ["Prepared meals", "Bakery", "Fresh produce"], "capacity": 120}),
        }
        for role, (source, template) in role_data.items():
            current = db.execute("SELECT demo FROM user_profiles WHERE user_id=? AND role=?", (user_id, role)).fetchone()
            if current:
                # Existing personal profile values and approval remain untouched.
                continue
            data = json.loads(source["profile_json"]) if source else template
            if role == "DONOR":
                data.update({"contact_name": "Fictional Demo Donor", "organization_name": "Green Leaf Restaurant — DEMO", "address": "Fictional Mathura demo location", "pickup_area": "Mathura"})
            if role == "VOLUNTEER":
                data.update({"contact_name": "HyperX Demo Volunteer", "service_area": "Mathura", "availability": "Available for fictional demo tasks; not live-tracked"})
            status = "pending" if role == "RECIPIENT" else "approved"
            db.execute("INSERT INTO user_profiles(user_id,role,demo,profile_json,status,created_at,updated_at) VALUES(?,?,1,?,?,?,?)",
                       (user_id, role, json.dumps(data, separators=(",", ":"), sort_keys=True), status, stamp, stamp))

        # Only designated fictional records move from the former local demo
        # donor/volunteer identities. Non-demo records and history are untouched.
        old_donor = db.execute("SELECT id FROM user_accounts WHERE email='demo-donor@surplussync.invalid' COLLATE NOCASE AND is_demo=1").fetchone()
        if old_donor:
            db.execute("UPDATE listings SET donor_user_id=? WHERE donor_user_id=? AND (demo=1 OR demo_scenario IS NOT NULL)", (user_id, old_donor["id"]))
        old_volunteer = db.execute("SELECT id FROM user_accounts WHERE email='demo-volunteer@surplussync.invalid' COLLATE NOCASE AND is_demo=1").fetchone()
        if old_volunteer:
            db.execute("UPDATE rescue_cases SET volunteer_user_id=? WHERE volunteer_user_id=? AND listing_id IN (SELECT id FROM listings WHERE demo=1 OR demo_scenario IS NOT NULL)", (user_id, old_volunteer["id"]))

        recipient = db.execute("SELECT id FROM recipients WHERE demo=1 AND name LIKE 'Green Plate Community Kitchen%DEMO%' ORDER BY id LIMIT 1").fetchone()
        if recipient is None:
            db.execute("INSERT INTO recipients(name,area,capacity,travel_minutes,available,food_categories,demo,created_at,updated_at) VALUES(?,?,120,12,1,?,1,?,?)",
                       (RECIPIENT_NAME, "Mathura", json.dumps(["Prepared meals", "Bakery", "Fresh produce"]), stamp, stamp))
        else:
            db.execute("UPDATE recipients SET name=?,updated_at=? WHERE id=? AND demo=1 AND name LIKE 'Green Plate Community Kitchen%DEMO%'",
                       (RECIPIENT_NAME, stamp, recipient["id"]))
        # Do not reassign an existing candidate-recipient profile to the donor
        # identity; it remains an independent fictional organization.

    # Import lazily: main imports this module only from its lifespan after route
    # registration, avoiding a module initialization cycle.
    from .main import evaluate_current, listing_by_id, save_plan
    with connection(immediate=True) as db:
        user_id = db.execute("SELECT id FROM user_accounts WHERE email=? COLLATE NOCASE", (email,)).fetchone()["id"]
        scenarios = {}
        safety = (0, 0, 0, 0, 0, "DEMO ONLY — no human verification; simulation only")
        for key, donor_name, category, portions in SCENARIOS:
            row = db.execute("SELECT id,demo,donor_user_id FROM listings WHERE demo_scenario=?", (key,)).fetchone()
            if row and (not row["demo"] or row["donor_user_id"] != user_id):
                raise RuntimeError(f"Refusing to change a non-demo listing reserved for scenario {key}.")
            deadline = (datetime.now() + timedelta(hours=8)).isoformat(timespec="minutes")
            if row:
                listing_id = row["id"]
                rescue = db.execute("SELECT status FROM rescue_cases WHERE listing_id=?", (listing_id,)).fetchone()
                if rescue and rescue["status"] != "listed":
                    scenarios[key] = {"listing_id": listing_id, "status": rescue["status"], "preserved": True}
                    continue
                db.execute("""UPDATE listings SET donor_name=?,food_type=?,portions=?,pickup_area='Mathura',deadline=?,prepared_at=?,
                    safety_handling=?,safety_temperature=?,safety_allergens=?,safety_packaging=?,safety_local_rules=?,safety_verified_by=?
                    WHERE id=?""", (donor_name, category, portions, deadline, stamp, *safety, listing_id))
            else:
                listing_id = db.execute("""INSERT INTO listings(donor_name,food_type,portions,pickup_area,deadline,prepared_at,
                    safety_handling,safety_temperature,safety_allergens,safety_packaging,safety_local_rules,safety_verified_by,
                    demo,demo_scenario,donor_user_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
                    (donor_name, category, portions, "Mathura", deadline, stamp, *safety, key, user_id, stamp)).lastrowid
                rescue_id = db.execute("INSERT INTO rescue_cases(listing_id,status,created_at,updated_at) VALUES(?,'listed',?,?)", (listing_id, stamp, stamp)).lastrowid
                db.execute("INSERT INTO rescue_events(rescue_id,event_type,to_status,created_at) VALUES(?,'listed','listed',?)", (rescue_id, stamp))
            listing = listing_by_id(db, listing_id)
            result = evaluate_current(db, listing)
            previous = db.execute("SELECT id FROM rescue_plans WHERE listing_id=? ORDER BY id DESC LIMIT 1", (listing_id,)).fetchone()
            saved = save_plan(db, listing_id, result, stamp, previous["id"] if previous else None)
            scenarios[key] = {"listing_id": listing_id, "plan_id": saved["id"], "feasible_candidates": len(saved["feasible_candidates"]),
                              "recommended_recipient": saved["recommended"]["name"] if saved["recommended"] else None,
                              "synthetic_demo_checks": True, "simulation_only": saved["simulation_only"],
                              "food_safety_passed": saved["food_safety_passed"]}
        return {"email": email, "available_roles": [row["role"] for row in db.execute("SELECT role FROM user_profiles WHERE user_id=? ORDER BY role", (user_id,)).fetchall()],
                "scenarios": scenarios}


def enabled() -> bool:
    return os.getenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def main() -> None:
    import getpass
    email = os.getenv("SURPLUSSYNC_PRESENTATION_DEMO_EMAIL", DEMO_EMAIL)
    init_db()
    with connection() as db:
        exists = db.execute("SELECT 1 FROM user_accounts WHERE email=? COLLATE NOCASE", (email,)).fetchone()
    password = os.getenv("SURPLUSSYNC_PRESENTATION_DEMO_PASSWORD", "")
    if not exists and not password:
        password = getpass.getpass("New local presentation account password (12+ characters): ")
    try:
        result = seed_presentation_demo(email=email, password=password or None)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Shared presentation account is ready. No password was printed or changed.")
    print(f"Login email: {email}")
    print(f"Available role profiles: {', '.join(result['available_roles'])}")
    for key, item in result["scenarios"].items():
        print(f"{key}: listing #{item['listing_id']}, feasible candidates: {item.get('feasible_candidates', 'existing rescue preserved')}")
    print("Recipient registration remains pending until an administrator reviews it. Synthetic checklist data is not human verification or food-safety certification.")


if __name__ == "__main__":
    main()
