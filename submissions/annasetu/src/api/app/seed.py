import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from . import db
from .config import settings
from .security import password_hash, password_matches

DEMO_USERS = {
    "admin@annasetu.local": ("AnnaSetu Admin", "admin"),
    "donor@annasetu.local": ("Green Bowl Kitchen", "donor"),
    "ngo@annasetu.local": ("Nayi Disha Foundation", "ngo"),
    "volunteer@annasetu.local": ("Aarav Sharma", "volunteer"),
}

POLICIES = [
    (
        "Cold and hot holding",
        "https://fssai.gov.in/flipbook.php?bookid=31",
        "FSSAI Food Safety at Home guidance says food that must be held for later should be stored cold below 5°C or hot above 60°C. This AnnaSetu MVP uses recorded cold ≤5°C, hot ≥60°C, and frozen ≤−18°C as conservative screening thresholds. A missing, stale, or out-of-range reading places a batch on HOLD for human review; these rules are not a food-safety certification.",
    ),
    (
        "Transport and time-temperature controls",
        "https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Licensing_Regulations_04_08_2021.pdf",
        "FSSAI licensing regulations describe control of time and temperature through storage and distribution, including hot holding at or above 60°C and refrigeration for prolonged storage. AnnaSetu labels travel time as an estimate and checks that the estimated trip fits before the donor-declared use-by time. A verifier must confirm the batch and the receiving volunteer must re-check it at pickup and delivery.",
    ),
    (
        "Human verification and allergens",
        "https://fssai.gov.in/inspection/hygiene-requirements",
        "FSSAI describes food safety management systems as controlling hazards throughout the food chain. This application requires a human verification record and a confirmed allergen declaration before allocation. The software does not determine whether a food is safe to eat and does not replace an FSSAI-compliant food-safety management system.",
    ),
]


def _validate_demo_password() -> None:
    value = settings.demo_password
    if not value or value.startswith("replace-with-") or not 8 <= len(value) <= 128:
        raise RuntimeError("Set a private DEMO_PASSWORD between 8 and 128 characters before demo account seeding.")


def _ensure_demo_accounts(conn) -> dict[str, str]:
    """Create or repair only the four reserved local demo identities in the active QA database."""
    _validate_demo_password()
    user_ids: dict[str, str] = {}
    for email, (name, role) in DEMO_USERS.items():
        existing = db.row(
            "SELECT USER_ID,DISPLAY_NAME,ROLE,PASSWORD_HASH FROM USERS WHERE LOWER(EMAIL)=LOWER(?)",
            (email,), conn,
        )
        if existing is None:
            user_id = str(uuid4())
            db.execute(
                "INSERT INTO USERS (USER_ID,EMAIL,DISPLAY_NAME,ROLE,PASSWORD_HASH) VALUES (?,?,?,?,?)",
                (user_id, email, name, role, password_hash(settings.demo_password)), conn,
            )
        else:
            user_id = existing["user_id"].strip()
            stored_hash = existing["password_hash"]
            valid_hash = password_matches(settings.demo_password, stored_hash)
            if existing["display_name"] != name or existing["role"] != role or not valid_hash:
                repaired_hash = stored_hash if valid_hash else password_hash(settings.demo_password)
                db.execute(
                    "UPDATE USERS SET DISPLAY_NAME=?,ROLE=?,PASSWORD_HASH=? WHERE USER_ID=?",
                    (name, role, repaired_hash, user_id), conn,
                )
        user_ids[email] = user_id
    return user_ids


def _ensure_bootstrap_rows(conn) -> None:
    if not db.row("SELECT COUNT(*) AS N FROM AUDIT_HEAD", conn=conn)["n"]:
        db.execute("INSERT INTO AUDIT_HEAD (HEAD_ID,LAST_EVENT_ID,LAST_HASH) VALUES (1,NULL,?)", ("0" * 64,), conn)
    if not db.row("SELECT COUNT(*) AS N FROM POLICY_DOCUMENTS", conn=conn)["n"]:
        for title, url, content in POLICIES:
            db.execute("INSERT INTO POLICY_DOCUMENTS (DOCUMENT_ID,TITLE,SOURCE_URL,CONTENT) VALUES (?,?,?,?)",
                       (str(uuid4()), title, url, content), conn)


def seed_database() -> None:
    conn = db.connect()
    try:
        users_exist = bool(db.row("SELECT COUNT(*) AS N FROM USERS", conn=conn)["n"])
        if users_exist:
            _ensure_bootstrap_rows(conn)
            # Repair the explicitly requested local demo accounts only in ANNATEST.
            # Non-QA databases retain their existing identities and password hashes.
            if settings.db2_name.upper() == "ANNATEST":
                _ensure_demo_accounts(conn)
            conn.commit()
            return

        # A fresh database receives the existing complete demo dataset as before.
        user_ids = _ensure_demo_accounts(conn)

        ngo_rows = [
            ("Nayi Disha Foundation", 110.0, ["prepared meals", "produce", "bakery", "dairy"], ["cold", "hot"], 12.9716, 77.5946, "Daily · 08:00–20:00"),
            ("Sahaya Community Kitchen", 76.0, ["prepared meals", "produce", "bakery"], ["cold", "hot", "frozen"], 12.9352, 77.6245, "Daily · 07:00–19:00"),
            ("Udaya Relief Network", 42.0, ["prepared meals", "dairy"], ["cold", "hot"], 12.9980, 77.5690, "Mon–Sat · 09:00–18:00"),
        ]
        ngo_ids: list[str] = []
        for index, (name, cap, categories, storage, lat, lon, hours) in enumerate(ngo_rows):
            ngo_id = str(uuid4())
            ngo_ids.append(ngo_id)
            owner = user_ids["ngo@annasetu.local"] if index == 0 else user_ids["admin@annasetu.local"]
            db.execute(
                """INSERT INTO NGOS (NGO_ID,OWNER_USER_ID,NAME,VERIFIED,AVAILABLE_KG,
                   ACCEPTED_CATEGORIES,STORAGE_CAPABILITIES,LATITUDE,LONGITUDE,RECEIVING_HOURS)
                   VALUES (?,?,?,1,?,?,?,?,?,?)""",
                (ngo_id, owner, name, cap, json.dumps(categories), ",".join(storage), lat, lon, hours), conn,
            )

        volunteer_id = str(uuid4())
        db.execute("INSERT INTO VOLUNTEERS (VOLUNTEER_ID,USER_ID,SERVICE_AREA) VALUES (?,?,?)",
                    (volunteer_id, user_ids["volunteer@annasetu.local"], "Central Bengaluru · 12 km"), conn)
        db.execute("INSERT INTO AUDIT_HEAD (HEAD_ID,LAST_EVENT_ID,LAST_HASH) VALUES (1,NULL,?)", ("0" * 64,), conn)
        for title, url, content in POLICIES:
            db.execute("INSERT INTO POLICY_DOCUMENTS (DOCUMENT_ID,TITLE,SOURCE_URL,CONTENT) VALUES (?,?,?,?)",
                        (str(uuid4()), title, url, content), conn)

        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        batch_ids: list[str] = []
        batches = [
            ("Fresh lunch bowls · 96 portions", "prepared meals", 48.0, "cold", 4.0, "distributed", True, True, 12.9710, 77.5910),
            ("Seasonal fruit boxes", "produce", 36.0, "cold", 3.5, "delivered", True, True, 12.9640, 77.6080),
            ("Bakery assortment", "bakery", 42.0, "ambient", None, "allocated", False, True, 12.9790, 77.5860),
            ("Cream dessert trays", "dairy", 18.0, "cold", None, "hold", False, False, 12.9500, 77.6200),
        ]
        for title, category, kg, storage_type, temp, status, verified, allergen_ok, lat, lon in batches:
            batch_id = str(uuid4())
            batch_ids.append(batch_id)
            verifier = user_ids["admin@annasetu.local"] if verified else None
            db.execute(
                """INSERT INTO FOOD_BATCHES
                   (BATCH_ID,DONOR_ID,TITLE,CATEGORY,QUANTITY_KG,PREPARED_AT,USE_BY,STORAGE_TYPE,
                    STORAGE_TEMP_C,ALLERGENS,ALLERGENS_CONFIRMED,INGREDIENTS,PICKUP_ADDRESS,LATITUDE,
                    LONGITUDE,HUMAN_VERIFIED,VERIFIED_BY,VERIFIED_AT,STATUS,NOTES)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (batch_id, user_ids["donor@annasetu.local"], title, category, kg,
                 now - timedelta(hours=2), now + timedelta(hours=18), storage_type, temp,
                 json.dumps(["milk", "gluten"] if category in {"prepared meals", "bakery", "dairy"} else []),
                 int(allergen_ok), json.dumps(["seasonal ingredients"]), "Indiranagar, Bengaluru",
                 lat, lon, int(verified), verifier, now - timedelta(minutes=25) if verified else None, status,
                 "Seeded sample record for local demonstration."), conn,
            )
            db.execute("INSERT INTO SAFETY_OBSERVATIONS (OBSERVATION_ID,BATCH_ID,RECORDED_BY,TEMP_C,STORAGE_NOTE) VALUES (?,?,?,?,?)",
                        (str(uuid4()), batch_id, user_ids["donor@annasetu.local"], temp,
                         "Sample observation; verify before any real-world distribution."), conn)

        otp_hash = hashlib.sha256(b"demo-code-disabled").hexdigest()
        for batch_index, ngo_index, kg, status in [(0, 0, 30.0, "distributed"), (0, 1, 18.0, "distributed"), (1, 1, 36.0, "delivered"), (2, 0, 32.0, "allocated")]:
            db.execute(
                """INSERT INTO RESCUES (RESCUE_ID,BATCH_ID,NGO_ID,VOLUNTEER_ID,ALLOCATED_KG,STATUS,
                   PICKUP_OTP_HASH,DELIVERY_OTP_HASH,DISTRIBUTION_OTP_HASH)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (str(uuid4()), batch_ids[batch_index], ngo_ids[ngo_index], volunteer_id, kg, status,
                 otp_hash, otp_hash, otp_hash), conn,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
