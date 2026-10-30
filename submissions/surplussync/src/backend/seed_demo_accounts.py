"""Create or refresh fictional local presentation accounts without deleting data.

Run ``python -m backend.seed_demo_accounts`` from the project root. The tool
prompts for one local-only password shared by the synthetic roles. It refuses
to adopt accounts created through public signup and never runs as part of API
startup. Do not run it against a public deployment.
"""
import getpass
import json
import os
from datetime import datetime

from .auth import audit, hash_password, verify_password
from .database import connection, init_db


def seed_demo_accounts(password: str) -> dict[str, str]:
    """Idempotently ensure a local donor, recipients, volunteer and admin exist.

    Only fixed ``.invalid`` demo identities are changed. Other accounts and all
    listings, plans, recipient rows, rescue cases and history are preserved.
    """
    if len(password) < 12:
        raise ValueError("Choose a local-only demo password of at least 12 characters.")

    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    created_or_updated: list[str] = []
    with connection(immediate=True) as db:
        recipients = db.execute("SELECT * FROM recipients WHERE demo=1 ORDER BY id").fetchall()
        if not recipients:
            raise RuntimeError("No fictional demo recipients exist. Preserve the database and seed its demo network first.")

        accounts: list[tuple[str, str, dict, int | None]] = [
            ("demo-admin@surplussync.invalid", "ADMIN", {}, None),
            ("demo-donor@surplussync.invalid", "DONOR", {
                "contact_name": "Fictional Demo Donor", "phone": "000-000-0000",
                "organization_name": "Demo Bakery", "address": "Civic Centre",
                "pickup_area": "Civic Centre",
            }, None),
            ("demo-volunteer@surplussync.invalid", "VOLUNTEER", {
                "contact_name": "Fictional Demo Volunteer", "phone": "000-000-0000",
                "service_area": "Mathura", "availability": "Available for fictional demo tasks; not live-tracked",
            }, None),
        ]
        for index, recipient in enumerate(recipients, 1):
            profile = {
                "organization_name": recipient["name"], "address": "Fictional demo location",
                "service_area": recipient["area"], "contact_person": "Fictional Demo Contact",
                "phone": "000-000-0000", "receiving_hours": "Demo schedule",
                "registration_type": "Other registered organization", "registration_number": "DEMO-ONLY-NOT-VERIFIED",
                "food_categories": json.loads(recipient["food_categories"]),
                "capacity": recipient["capacity"],
            }
            accounts.append((f"demo-recipient-{index}@surplussync.invalid", "RECIPIENT", profile, recipient["id"]))

        # Preflight identity and ownership conflicts before writing anything.
        expected = {(email, role): recipient_id for email, role, _, recipient_id in accounts}
        existing = {}
        for email, role in expected:
            row = db.execute("SELECT id,role,is_demo FROM user_accounts WHERE email=? COLLATE NOCASE AND role=?", (email, role)).fetchone()
            public_identity = db.execute("SELECT 1 FROM user_accounts WHERE email=? COLLATE NOCASE AND is_demo=0 LIMIT 1", (email,)).fetchone()
            if public_identity or row and not row["is_demo"]:
                raise RuntimeError(f"Refusing to adopt {email} ({role}): it is not an account created by this local demo seeder.")
            existing[(email, role)] = row
        for (email, role), recipient_id in expected.items():
            if recipient_id is None:
                continue
            owner = db.execute("SELECT owner_user_id FROM recipients WHERE id=?", (recipient_id,)).fetchone()["owner_user_id"]
            account = existing[(email, role)]
            if owner is not None and (account is None or owner != account["id"]):
                raise RuntimeError(f"Refusing to reassign demo recipient #{recipient_id}; it already has another owner.")
        donor = existing[("demo-donor@surplussync.invalid", "DONOR")]
        if donor:
            conflict = db.execute("SELECT 1 FROM listings WHERE demo=1 AND donor_user_id IS NOT NULL AND donor_user_id<>? LIMIT 1", (donor["id"],)).fetchone()
        else:
            conflict = db.execute("SELECT 1 FROM listings WHERE demo=1 AND donor_user_id IS NOT NULL LIMIT 1").fetchone()
        if conflict:
            raise RuntimeError("Refusing to reassign a fictional demo listing already owned by another account.")

        password_hash = hash_password(password)
        ids: dict[str, int] = {}
        for email, role, profile, recipient_id in accounts:
            row = existing[(email, role)]
            if row is None:
                user_id = db.execute(
                    "INSERT INTO user_accounts(email,password_hash,role,is_demo,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (email, password_hash, role, 1, now, now),
                ).lastrowid
                changed = True
            else:
                user_id = row["id"]
                stored = db.execute("SELECT password_hash,status FROM user_accounts WHERE id=?", (user_id,)).fetchone()
                password_changed = not verify_password(password, stored["password_hash"])
                changed = password_changed or stored["status"] != "active"
                if changed:
                    db.execute("UPDATE user_accounts SET password_hash=?,status='active',updated_at=? WHERE id=?", (password_hash, now, user_id))

            profile_json = json.dumps(profile, separators=(",", ":"), sort_keys=True)
            if role == "ADMIN":
                ids[(email, role)] = user_id
                continue
            old_profile = db.execute("SELECT profile_json,status,review_reason,demo FROM user_profiles WHERE user_id=? AND role=?", (user_id,role)).fetchone()
            profile_changed = not old_profile or old_profile["profile_json"] != profile_json or old_profile["status"] != "approved" or old_profile["review_reason"] or not old_profile["demo"]
            if profile_changed:
                db.execute("""INSERT INTO user_profiles(user_id,role,demo,profile_json,status,review_reason,created_at,updated_at)
                    VALUES(?,?,1,?,'approved','',?,?) ON CONFLICT(user_id,role) DO UPDATE SET
                    profile_json=excluded.profile_json,status='approved',review_reason='',reviewed_by=NULL,
                    reviewed_at=NULL,demo=1,updated_at=excluded.updated_at""", (user_id,role, profile_json, now, now))
                db.execute("UPDATE user_accounts SET updated_at=? WHERE id=?", (now, user_id))
            if changed or profile_changed:
                created_or_updated.append(email)
            ids[(email, role)] = user_id
            if recipient_id is not None:
                db.execute("UPDATE recipients SET owner_user_id=? WHERE id=? AND owner_user_id IS NULL", (user_id, recipient_id))

        db.execute("UPDATE listings SET donor_user_id=? WHERE demo=1 AND donor_user_id IS NULL", (ids[("demo-donor@surplussync.invalid", "DONOR")],))
        if created_or_updated:
            audit(db, None, "demo_accounts_seeded", "demo", "local", json.dumps({"accounts": created_or_updated}))

    return {"admin": "demo-admin@surplussync.invalid", "donor": "demo-donor@surplussync.invalid",
            "recipient": "demo-recipient-1@surplussync.invalid", "volunteer": "demo-volunteer@surplussync.invalid"}


def main() -> None:
    password = os.getenv("SURPLUSSYNC_DEMO_PASSWORD", "") or getpass.getpass(
        "Local demo password (12+ characters; shared by fictional demo accounts): "
    )
    try:
        accounts = seed_demo_accounts(password)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Fictional local presentation accounts are ready (same password you entered):")
    for role, email in accounts.items():
        print(f"  {role.title()}: {email}")
    print("No listings, recipients, plans, rescue cases or existing user accounts were deleted.")
    print("The local admin account is for this presentation database only; never seed it in production.")


if __name__ == "__main__":
    main()
