"""Seed repeatable fictional rescue scenarios for a local presentation.

Run ``python -m backend.seed_demo_workflows`` from the project root. This is
explicitly local-only; it never runs at API startup and refuses configured
remote/production databases. Checklist values are synthetic demonstration
inputs, not actual human checks or food-safety certification.
"""
import getpass
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Match the running FastAPI service's project-root configuration before the
# database module reads SURPLUSSYNC_DB_PATH or the remote-database settings.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from .database import connection, init_db
from .seed_demo_accounts import seed_demo_accounts

SCENARIOS = (
    ("prepared_meals_40", "Green Leaf Restaurant — DEMO", "Prepared meals", 40),
    ("bakery_30", "Rajat Bakery — DEMO", "Bakery", 30),
    ("fresh_produce_25", "Mathura Fresh Foods — DEMO", "Fresh produce", 25),
)
DEMO_RECIPIENT_NAME = "Green Plate Community Kitchen — DEMO"
DEMO_CHECK_LABEL = "DEMO ONLY — synthetic checklist"


def seed_demo_workflows(password: str | None = None) -> dict:
    if os.getenv("VERCEL", "").lower() in {"1", "true", "yes"} or os.getenv("TURSO_DATABASE_URL") or os.getenv("TURSO_AUTH_TOKEN"):
        raise RuntimeError("Demo workflow seeding is restricted to a local SQLite database.")
    if password is not None and not 12 <= len(password) <= 128:
        raise ValueError("Choose a local-only demo password between 12 and 128 characters.")

    init_db()
    now = datetime.now()
    stamp = now.isoformat(timespec="seconds")
    categories = json.dumps(["Prepared meals", "Bakery", "Fresh produce"])
    with connection(immediate=True) as db:
        recipient = db.execute("SELECT id FROM recipients WHERE name=? AND demo=1", (DEMO_RECIPIENT_NAME,)).fetchone()
        if recipient is None:
            recipient_id = db.execute(
                """INSERT INTO recipients(name,area,capacity,travel_minutes,available,food_categories,demo,created_at,updated_at)
                   VALUES(?, 'Mathura', 120, 12, 1, ?, 1, ?, ?)""",
                (DEMO_RECIPIENT_NAME, categories, stamp, stamp),
            ).lastrowid
        else:
            recipient_id = recipient["id"]
            # Fixed static travel estimate used only by this fictional demo row.
            # Do not change its configured availability or other capacities.
            db.execute("UPDATE recipients SET travel_minutes=12,updated_at=? WHERE id=? AND demo=1", (stamp, recipient_id))

    # Reuse existing local demo passwords by default. Supplying a password
    # explicitly refreshes only the seeder-managed .invalid demo accounts.
    recipient_index = 1
    if password is not None:
        accounts = seed_demo_accounts(password)
        with connection() as db:
            ordered_ids = [row["id"] for row in db.execute("SELECT id FROM recipients WHERE demo=1 ORDER BY id")]
            if recipient_id not in ordered_ids:
                raise RuntimeError("The local fictional recipient record is missing.")
            recipient_index = ordered_ids.index(recipient_id) + 1
    else:
        recipient_index = 1
        with connection() as db:
            ordered_ids = [row["id"] for row in db.execute("SELECT id FROM recipients WHERE demo=1 ORDER BY id")]
            if recipient_id not in ordered_ids:
                raise RuntimeError("The local fictional recipient record is missing.")
            recipient_index = ordered_ids.index(recipient_id) + 1
        with connection(immediate=True) as db:
            demo_recipients = db.execute("SELECT id,name,area,capacity,food_categories,owner_user_id FROM recipients WHERE demo=1 ORDER BY id").fetchall()
            target = next((item for item in demo_recipients if item["id"] == recipient_id), None)
            if not target:
                raise RuntimeError("The local fictional recipient record is missing.")
            recipient_index = next(index for index, item in enumerate(demo_recipients, 1) if item["id"] == recipient_id)
            donor = db.execute("SELECT id,password_hash FROM user_accounts WHERE email='demo-donor@surplussync.invalid' COLLATE NOCASE AND role='DONOR' AND is_demo=1 AND status='active'").fetchone()
            volunteer = db.execute("SELECT id FROM user_accounts WHERE email='demo-volunteer@surplussync.invalid' COLLATE NOCASE AND role='VOLUNTEER' AND is_demo=1 AND status='active'").fetchone()
            admin = db.execute("SELECT id FROM user_accounts WHERE email='demo-admin@surplussync.invalid' COLLATE NOCASE AND role='ADMIN' AND is_demo=1 AND status='active'").fetchone()
            if not donor or not volunteer or not admin:
                raise RuntimeError("Seed the fictional demo accounts once before seeding workflows, or supply a local demo password to create them.")
            recipient_email = f"demo-recipient-{recipient_index}@surplussync.invalid"
            recipient_account = db.execute("SELECT id,is_demo FROM user_accounts WHERE email=? COLLATE NOCASE AND role='RECIPIENT'", (recipient_email,)).fetchone()
            if recipient_account and not recipient_account["is_demo"]:
                raise RuntimeError("Refusing to adopt a recipient identity created through public signup.")
            user_id = recipient_account["id"] if recipient_account else db.execute(
                "INSERT INTO user_accounts(email,password_hash,role,is_demo,created_at,updated_at) VALUES(?,?,'RECIPIENT',1,?,?)",
                (recipient_email, donor["password_hash"], stamp, stamp),
            ).lastrowid
            if target["owner_user_id"] is not None and target["owner_user_id"] != user_id:
                raise RuntimeError("Refusing to reassign the fictional recipient record to a different account.")
            profile = {"organization_name": target["name"], "address": "Fictional demo location",
                       "service_area": target["area"], "contact_person": "Fictional Demo Contact",
                       "phone": "000-000-0000", "receiving_hours": "Demo schedule",
                       "registration_type": "Other registered organization",
                       "registration_number": "DEMO-ONLY-NOT-VERIFIED",
                       "food_categories": json.loads(target["food_categories"]), "capacity": target["capacity"]}
            db.execute("""INSERT INTO user_profiles(user_id,role,demo,profile_json,status,review_reason,created_at,updated_at)
                VALUES(?,'RECIPIENT',1,?,'approved','',?,?) ON CONFLICT(user_id,role) DO UPDATE SET
                profile_json=excluded.profile_json,status='approved',review_reason='',demo=1,updated_at=excluded.updated_at""",
                (user_id, json.dumps(profile, separators=(",", ":"), sort_keys=True), stamp, stamp))
            db.execute("UPDATE recipients SET owner_user_id=? WHERE id=? AND owner_user_id IS NULL", (user_id, recipient_id))
            volunteer_row = db.execute("SELECT user_id,profile_json FROM user_profiles WHERE user_id=? AND role='VOLUNTEER'", (volunteer["id"],)).fetchone()
            if not volunteer_row:
                raise RuntimeError("The local demo volunteer profile is incomplete. Re-run the trusted demo account seeder.")
            volunteer_profile = json.loads(volunteer_row["profile_json"])
            volunteer_profile.update({"service_area": "Mathura", "availability": "Available for fictional demo tasks; not live-tracked"})
            db.execute("UPDATE user_profiles SET profile_json=?,status='approved',updated_at=? WHERE user_id=? AND role='VOLUNTEER'",
                       (json.dumps(volunteer_profile, separators=(",", ":"), sort_keys=True), stamp, volunteer["id"]))
            donor_id = donor["id"]
            # Existing fixed demo roles remain unchanged; the added recipient
            # profile receives the same local demo password hash as the donor.
            accounts = {"admin": "demo-admin@surplussync.invalid", "donor": "demo-donor@surplussync.invalid",
                        "recipient": recipient_email, "volunteer": "demo-volunteer@surplussync.invalid"}
    with connection(immediate=True) as db:
        donor = db.execute("SELECT id FROM user_accounts WHERE email=? COLLATE NOCASE AND role='DONOR' AND is_demo=1",
                           (accounts["donor"],)).fetchone()
        if not donor:
            raise RuntimeError("The local fictional donor profile could not be prepared.")

        results = {}
        # Keep synthetic values explicitly unverified. The planner's demo-only
        # simulation path can still exercise matching without treating these
        # values as a human food-safety check.
        synthetic_safety = (0, 0, 0, 0, 0, DEMO_CHECK_LABEL)
        for scenario, donor_name, food_type, portions in SCENARIOS:
            row = db.execute("SELECT id,demo,donor_user_id FROM listings WHERE demo_scenario=?", (scenario,)).fetchone()
            if row and (not row["demo"] or row["donor_user_id"] != donor["id"]):
                raise RuntimeError(f"Refusing to modify listing record reserved for demo scenario {scenario}.")
            deadline = (datetime.now() + timedelta(hours=8)).isoformat(timespec="minutes")
            if row:
                rescue = db.execute("SELECT id,status FROM rescue_cases WHERE listing_id=?", (row["id"],)).fetchone()
                if rescue and rescue["status"] != "listed":
                    results[scenario] = {"listing_id": row["id"], "status": rescue["status"], "preserved": True}
                    continue
                db.execute("""UPDATE listings SET donor_name=?,food_type=?,portions=?,pickup_area='Mathura',deadline=?,
                    prepared_at=?,safety_handling=?,safety_temperature=?,safety_allergens=?,safety_packaging=?,
                    safety_local_rules=?,safety_verified_by=? WHERE id=?""",
                    (donor_name, food_type, portions, deadline, stamp, *synthetic_safety, row["id"]))
                listing_id = row["id"]
            else:
                listing_id = db.execute("""INSERT INTO listings(donor_name,food_type,portions,pickup_area,deadline,prepared_at,
                    safety_handling,safety_temperature,safety_allergens,safety_packaging,safety_local_rules,safety_verified_by,
                    audit,demo,demo_scenario,donor_user_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?,?)""",
                    (donor_name, food_type, portions, "Mathura", deadline, stamp, *synthetic_safety,
                     scenario, donor["id"], stamp)).lastrowid
                rescue_id = db.execute("INSERT INTO rescue_cases(listing_id,status,created_at,updated_at) VALUES(?,'listed',?,?)",
                                       (listing_id, stamp, stamp)).lastrowid
                db.execute("INSERT INTO rescue_events(rescue_id,event_type,to_status,created_at) VALUES(?,'listed','listed',?)",
                           (rescue_id, stamp))

            from .main import evaluate_current, listing_by_id, save_plan
            listing = listing_by_id(db, listing_id)
            plan_result = evaluate_current(db, listing)
            prior_plan = db.execute("SELECT id FROM rescue_plans WHERE listing_id=? ORDER BY id DESC LIMIT 1", (listing_id,)).fetchone()
            plan = save_plan(db, listing_id, plan_result, stamp, prior_plan["id"] if prior_plan else None)
            results[scenario] = {"listing_id": listing_id, "plan_id": plan["id"],
                                 "feasible_candidates": len(plan["feasible_candidates"]),
                                 "recommended_recipient": plan["recommended"]["name"] if plan["recommended"] else None,
                                 "simulated_demo_checks": True, "simulation_only": plan["simulation_only"],
                                 "food_safety_passed": plan["food_safety_passed"], "deadline": deadline}

    recipient_account_email = accounts["recipient"] if password is None else f"demo-recipient-{recipient_index}@surplussync.invalid"
    return {"accounts": accounts, "recipient": DEMO_RECIPIENT_NAME, "recipient_account": recipient_account_email,
            "volunteer": accounts["volunteer"], "scenarios": results}


def main() -> None:
    password = os.getenv("SURPLUSSYNC_DEMO_PASSWORD", "") or getpass.getpass(
        "Optional local demo password (press Enter to preserve existing demo passwords): "
    ) or None
    try:
        result = seed_demo_workflows(password)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Fictional local demo workflows are ready. New demo roles share the existing donor's local demo password.")
    print(f"Demo recipient: {result['recipient']}")
    print(f"Demo volunteer: {result['volunteer']}")
    for name, details in result["scenarios"].items():
        print(f"{name}: listing #{details['listing_id']}, feasible candidates: {details.get('feasible_candidates', 'already in progress')}")
    print("Synthetic checklist inputs are only for software demonstration and are not human verification or food-safety certification.")


if __name__ == "__main__":
    main()
