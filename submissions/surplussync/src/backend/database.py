"""SQLite persistence. All demonstration recipients are fictional."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(os.getenv("SURPLUSSYNC_DB_PATH", str(Path(__file__).with_name("surplussync.db")))).expanduser()
DEMO_RECIPIENTS = [
    ("Green Plate Community Kitchen", "Civic Centre", 120, 18, '["Prepared meals","Bakery","Fresh produce"]'),
    ("Harbour Hope Shelter", "East Market", 75, 32, '["Prepared meals","Packaged groceries"]'),
    ("Sunrise Neighbourhood Pantry", "Riverside", 50, 24, '["Fresh produce","Bakery","Packaged groceries"]'),
    ("Maple Street Food Bank", "Old Town", 200, 45, '["Prepared meals","Fresh produce","Bakery","Dairy","Packaged groceries"]'),
]

@contextmanager
def connection(immediate=False):
    remote_url = os.getenv("TURSO_DATABASE_URL", "").strip()
    remote_token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
    if remote_url or remote_token:
        if not remote_url or not remote_token:
            raise RuntimeError("Both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are required for the production database.")
        try:
            import turso_serverless
        except ImportError as exc:
            raise RuntimeError("The configured Turso database driver is unavailable.") from exc
        db = turso_serverless.connect(remote_url, auth_token=remote_token)
        db.row_factory = turso_serverless.Row
        remote = True
    else:
        # Vercel functions have no durable local filesystem. Fail closed rather
        # than silently creating a per-instance SQLite database.
        if os.getenv("VERCEL", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError("Configure the persistent Turso database before serving production requests.")
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(DB_PATH, timeout=10)
        db.row_factory = sqlite3.Row
        remote = False
    db.execute("PRAGMA foreign_keys=ON")
    if not remote:
        db.execute("PRAGMA busy_timeout=10000")
    try:
        if immediate:
            db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS recipients (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL,
          capacity INTEGER NOT NULL CHECK(capacity > 0), travel_minutes INTEGER NOT NULL CHECK(travel_minutes >= 0),
          available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1)),
          food_categories TEXT NOT NULL DEFAULT '[]', demo INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS listings (
          id INTEGER PRIMARY KEY AUTOINCREMENT, donor_name TEXT NOT NULL, food_type TEXT NOT NULL,
          portions INTEGER NOT NULL CHECK(portions > 0), pickup_area TEXT NOT NULL,
          deadline TEXT NOT NULL, prepared_at TEXT, safety_handling INTEGER NOT NULL,
          safety_temperature INTEGER NOT NULL, safety_allergens INTEGER NOT NULL,
          safety_packaging INTEGER NOT NULL, safety_local_rules INTEGER NOT NULL,
          safety_verified_by TEXT NOT NULL DEFAULT '',
          audit INTEGER NOT NULL DEFAULT 0 CHECK(audit IN (0,1)),
          demo INTEGER NOT NULL DEFAULT 0 CHECK(demo IN (0,1)),
          demo_scenario TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rescue_plans (
          id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
          recommended_recipient_id INTEGER REFERENCES recipients(id), created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS candidate_evaluations (
          id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL REFERENCES rescue_plans(id) ON DELETE CASCADE,
          recipient_id INTEGER NOT NULL REFERENCES recipients(id), feasible INTEGER NOT NULL,
          reasons TEXT NOT NULL, travel_minutes INTEGER NOT NULL, capacity_after INTEGER NOT NULL,
          rank INTEGER, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rescue_cases (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          listing_id INTEGER NOT NULL UNIQUE REFERENCES listings(id) ON DELETE CASCADE,
          recipient_id INTEGER REFERENCES recipients(id),
          portions_reserved INTEGER NOT NULL DEFAULT 0 CHECK(portions_reserved >= 0),
          status TEXT NOT NULL DEFAULT 'listed' CHECK(status IN ('listed','awaiting_confirmation','accepted','ready_for_pickup','collected','delivered','cancelled')),
          rejection_reason TEXT NOT NULL DEFAULT '',
          pickup_notes TEXT NOT NULL DEFAULT '', delivery_notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          accepted_at TEXT, ready_for_pickup_at TEXT, collected_at TEXT, delivered_at TEXT, cancelled_at TEXT
        );
        CREATE TABLE IF NOT EXISTS rescue_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          rescue_id INTEGER NOT NULL REFERENCES rescue_cases(id) ON DELETE CASCADE,
          event_type TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
          recipient_id INTEGER REFERENCES recipients(id), reason TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL COLLATE NOCASE,
          password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('DONOR','RECIPIENT','VOLUNTEER','ADMIN')),
          status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','disabled')),
          is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
          user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
          role TEXT NOT NULL CHECK(role IN ('DONOR','RECIPIENT','VOLUNTEER','ADMIN')),
          demo INTEGER NOT NULL DEFAULT 0 CHECK(demo IN (0,1)),
          profile_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','approved','rejected')),
          review_reason TEXT NOT NULL DEFAULT '', reviewed_by INTEGER REFERENCES user_accounts(id),
          reviewed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          PRIMARY KEY(user_id,role)
        );
        CREATE TABLE IF NOT EXISTS organization_verifications (
          user_id INTEGER PRIMARY KEY REFERENCES user_accounts(id) ON DELETE CASCADE,
          registration_type TEXT NOT NULL,
          registration_number TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','resubmission_required')),
          review_reason TEXT NOT NULL DEFAULT '',
          reviewed_by INTEGER REFERENCES user_accounts(id),
          reviewed_at TEXT,
          submitted_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS organization_documents (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
          storage_name TEXT NOT NULL UNIQUE,
          original_name TEXT NOT NULL,
          content_type TEXT NOT NULL CHECK(content_type IN ('application/pdf','image/jpeg','image/png')),
          size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
          sha256 TEXT NOT NULL,
          is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
          submitted_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS organization_documents_owner ON organization_documents(user_id,is_current);
        CREATE TABLE IF NOT EXISTS rescue_risk_assessments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
          plan_id INTEGER REFERENCES rescue_plans(id) ON DELETE CASCADE,
          rescue_id INTEGER REFERENCES rescue_cases(id) ON DELETE CASCADE,
          category TEXT NOT NULL CHECK(category IN ('Low','Medium','High')),
          score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
          reasons TEXT NOT NULL,
          alternative_recipient_ids TEXT NOT NULL DEFAULT '[]',
          volunteer_available_count INTEGER NOT NULL DEFAULT 0 CHECK(volunteer_available_count >= 0),
          assessed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS rescue_risk_listing ON rescue_risk_assessments(listing_id,assessed_at);
        CREATE TABLE IF NOT EXISTS auth_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT NOT NULL UNIQUE,
          csrf_hash TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
          active_role TEXT NOT NULL DEFAULT 'DONOR',
          expires_at TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions(expires_at);
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
          token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_attempts (
          bucket TEXT PRIMARY KEY, attempts INTEGER NOT NULL, window_started_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS security_audit (
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor_user_id INTEGER REFERENCES user_accounts(id),
          action TEXT NOT NULL, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL DEFAULT '',
          details TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
        );
        """)
        account_columns = {row["name"] for row in db.execute("PRAGMA table_info(user_accounts)")}
        if "is_demo" not in account_columns:
            # Additive marker: existing accounts remain non-demo unless explicitly
            # created by the trusted local demo seeder.
            db.execute("ALTER TABLE user_accounts ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1))")
        # Role profiles now belong to one identity. Older versions used one
        # profile/account per role. Preserve IDs and profile data while adding
        # the profile discriminator; do not silently merge duplicate identities.
        existing_tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "user_profiles_role_migration" in existing_tables:
            primary_rows = db.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0]
            stranded_rows = db.execute("SELECT COUNT(*) FROM user_profiles_role_migration").fetchone()[0]
            if primary_rows == 0 and stranded_rows:
                # Recover an interrupted one-time schema change. The source
                # remains in the migration table until a clean copy succeeds.
                db.execute("DROP TABLE user_profiles")
                db.execute("ALTER TABLE user_profiles_role_migration RENAME TO user_profiles")
            elif stranded_rows == 0:
                db.execute("DROP TABLE user_profiles_role_migration")
            else:
                raise RuntimeError("Both current and interrupted profile-migration tables contain rows; preserve both and review the merge before continuing.")
        profile_columns = {row["name"] for row in db.execute("PRAGMA table_info(user_profiles)")}
        profile_table_sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_profiles'").fetchone()["sql"] or ""
        profile_pk = [row["name"] for row in sorted(db.execute("PRAGMA table_info(user_profiles)").fetchall(), key=lambda item: item["pk"]) if row["pk"]]
        if "role" not in profile_columns or profile_pk != ["user_id", "role"] or "'ADMIN'" not in profile_table_sql:
            duplicate_emails = db.execute("SELECT email FROM user_accounts GROUP BY email COLLATE NOCASE HAVING COUNT(*)>1 LIMIT 1").fetchone()
            if duplicate_emails:
                raise RuntimeError("Cannot migrate role profiles: existing case-insensitive duplicate email accounts need a reviewed identity merge first.")
            legacy_columns = profile_columns
            db.execute("ALTER TABLE user_profiles RENAME TO user_profiles_role_migration")
            db.execute("""CREATE TABLE user_profiles (
              user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
              role TEXT NOT NULL CHECK(role IN ('DONOR','RECIPIENT','VOLUNTEER','ADMIN')),
              demo INTEGER NOT NULL DEFAULT 0 CHECK(demo IN (0,1)),
              profile_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','approved','rejected')),
              review_reason TEXT NOT NULL DEFAULT '', reviewed_by INTEGER REFERENCES user_accounts(id),
              reviewed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY(user_id,role)
            )""")
            demo_expr = "p.demo" if "demo" in legacy_columns else "0"
            db.execute(f"""INSERT INTO user_profiles(user_id,role,demo,profile_json,status,review_reason,reviewed_by,reviewed_at,created_at,updated_at)
              SELECT p.user_id,u.role,{demo_expr},p.profile_json,p.status,p.review_reason,p.reviewed_by,p.reviewed_at,p.created_at,p.updated_at
              FROM user_profiles_role_migration p JOIN user_accounts u ON u.id=p.user_id""")
            db.execute("DROP TABLE user_profiles_role_migration")
        elif "demo" not in profile_columns:
            db.execute("ALTER TABLE user_profiles ADD COLUMN demo INTEGER NOT NULL DEFAULT 0 CHECK(demo IN (0,1))")

        session_columns = {row["name"] for row in db.execute("PRAGMA table_info(auth_sessions)")}
        if "active_role" not in session_columns:
            db.execute("ALTER TABLE auth_sessions ADD COLUMN active_role TEXT NOT NULL DEFAULT 'DONOR'")
            db.execute("UPDATE auth_sessions SET active_role=COALESCE((SELECT role FROM user_accounts WHERE id=auth_sessions.user_id),'DONOR')")

        # Enforce exactly one login identity per normalized email. Existing
        # duplicate email accounts cannot be guessed together safely.
        unique_indexes = []
        for index in db.execute("PRAGMA index_list(user_accounts)").fetchall():
            if not index["unique"]:
                continue
            columns = [item["name"] for item in db.execute(f"PRAGMA index_info('{index['name']}')").fetchall()]
            unique_indexes.append((index["name"], columns))
        if db.execute("SELECT 1 FROM user_accounts GROUP BY email COLLATE NOCASE HAVING COUNT(*)>1 LIMIT 1").fetchone():
            raise RuntimeError("Cannot migrate to one-login role profiles: duplicate case-insensitive account emails need a reviewed merge plan.")
        for index_name, columns in unique_indexes:
            if columns == ["email", "role"]:
                db.execute(f'DROP INDEX "{index_name.replace(chr(34), chr(34)*2)}"')
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS user_accounts_email_unique ON user_accounts(email COLLATE NOCASE)")
        # Older databases may still have inert verification columns/tokens.
        # Keep those legacy records for data preservation; current auth routes
        # never read or write them.
        recipient_columns = {row["name"] for row in db.execute("PRAGMA table_info(recipients)")}
        if "owner_user_id" not in recipient_columns:
            db.execute("ALTER TABLE recipients ADD COLUMN owner_user_id INTEGER REFERENCES user_accounts(id)")
        rescue_columns = {row["name"] for row in db.execute("PRAGMA table_info(rescue_cases)")}
        if "volunteer_user_id" not in rescue_columns:
            db.execute("ALTER TABLE rescue_cases ADD COLUMN volunteer_user_id INTEGER REFERENCES user_accounts(id)")
        # Migrate databases created by the first MVP schema in place.
        recipient_columns = {row["name"] for row in db.execute("PRAGMA table_info(recipients)")}
        if "food_categories" not in recipient_columns:
            db.execute("ALTER TABLE recipients ADD COLUMN food_categories TEXT NOT NULL DEFAULT '[]'")
        if "demo" not in recipient_columns:
            db.execute("ALTER TABLE recipients ADD COLUMN demo INTEGER NOT NULL DEFAULT 1")
        if "created_at" not in recipient_columns:
            db.execute("ALTER TABLE recipients ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        if "updated_at" not in recipient_columns:
            db.execute("ALTER TABLE recipients ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        now = datetime.now().isoformat(timespec="seconds")
        db.execute("UPDATE recipients SET created_at=? WHERE created_at=''", (now,))
        db.execute("UPDATE recipients SET updated_at=? WHERE updated_at=''", (now,))
        # The first MVP stored listings before adding the mandatory safety checklist.
        # Add the verification flags as false so legacy donations cannot bypass safety gating.
        listing_columns = {row["name"] for row in db.execute("PRAGMA table_info(listings)")}
        legacy_safety_columns = {
            "safety_handling": "safety_handling",
            "safety_temperature": "safety_temperature",
            "safety_allergens": "safety_allergens",
            "safety_packaging": "safety_packaging",
            "safety_local_rules": "safety_local_rules",
        }
        for column in legacy_safety_columns:
            if column not in listing_columns:
                db.execute(f"ALTER TABLE listings ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")
        if "safety_verified_by" not in listing_columns:
            db.execute("ALTER TABLE listings ADD COLUMN safety_verified_by TEXT NOT NULL DEFAULT ''")
        if "audit" not in listing_columns:
            db.execute("ALTER TABLE listings ADD COLUMN audit INTEGER NOT NULL DEFAULT 0")
            # These names were confirmed in the existing local database as test records.
            # Preserve them but exclude them from presentation metrics by default.
            db.execute("""UPDATE listings SET audit=1 WHERE donor_name IN (
                'Integration Demo','Final Integration Check','Audit UI Test Donor',
                'Deadline State Audit Test','Rejected Past Deadline Test',
                'Past Deadline Test','Deadline Future Verification')""")
        if "demo" not in listing_columns:
            db.execute("ALTER TABLE listings ADD COLUMN demo INTEGER NOT NULL DEFAULT 0")
        if "demo_scenario" not in listing_columns:
            db.execute("ALTER TABLE listings ADD COLUMN demo_scenario TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS listings_demo_scenario_unique ON listings(demo_scenario) WHERE demo_scenario IS NOT NULL")
        if "donor_user_id" not in listing_columns:
            db.execute("ALTER TABLE listings ADD COLUMN donor_user_id INTEGER REFERENCES user_accounts(id)")
        if not db.execute("SELECT 1 FROM recipients LIMIT 1").fetchone():
            now = datetime.now().isoformat(timespec="seconds")
            db.executemany("INSERT INTO recipients(name,area,capacity,travel_minutes,food_categories,demo,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)", [(*s,now,now) for s in DEMO_RECIPIENTS])
        seed_demo_listing(db)
        # Backfill lifecycle records for existing listings without changing them.
        for row in db.execute("SELECT id,created_at FROM listings WHERE id NOT IN (SELECT listing_id FROM rescue_cases)").fetchall():
            created = row["created_at"] or now
            cur = db.execute("INSERT INTO rescue_cases(listing_id,status,created_at,updated_at) VALUES(?,'listed',?,?)", (row["id"],created,created))
            db.execute("INSERT INTO rescue_events(rescue_id,event_type,from_status,to_status,created_at) VALUES(?,'listed',NULL,'listed',?)", (cur.lastrowid,created))

def seed_demo_listing(db):
    if db.execute("SELECT 1 FROM listings WHERE demo=1 LIMIT 1").fetchone():
        return
    now = datetime.now()
    cur = db.execute("""INSERT INTO listings(donor_name,food_type,portions,pickup_area,deadline,prepared_at,
      safety_handling,safety_temperature,safety_allergens,safety_packaging,safety_local_rules,
      safety_verified_by,audit,demo,created_at) VALUES(?,?,?,?,?,NULL,0,0,0,0,0,'',0,1,?)""",
      ("Demo: Community Bakery", "Bakery", 24, "Civic Centre", (now + timedelta(hours=5)).isoformat(timespec="minutes"), now.isoformat(timespec="seconds")))
    created = now.isoformat(timespec="seconds")
    case = db.execute("INSERT INTO rescue_cases(listing_id,status,created_at,updated_at) VALUES(?,'listed',?,?)", (cur.lastrowid,created,created))
    db.execute("INSERT INTO rescue_events(rescue_id,event_type,to_status,created_at) VALUES(?,'listed','listed',?)", (case.lastrowid,created))

def reset_demo_data():
    """Restore fictional recipients and the unverified sample without touching other rows."""
    init_db()
    with connection() as db:
        db.execute("DELETE FROM listings WHERE demo=1")
        now = datetime.now().isoformat(timespec="seconds")
        for name, area, capacity, travel_minutes, categories in DEMO_RECIPIENTS:
            existing = db.execute("SELECT id FROM recipients WHERE name=? AND demo=1", (name,)).fetchone()
            if existing:
                db.execute("UPDATE recipients SET area=?,capacity=?,travel_minutes=?,available=1,food_categories=?,updated_at=? WHERE id=?",
                           (area, capacity, travel_minutes, categories, now, existing["id"]))
            else:
                db.execute("INSERT INTO recipients(name,area,capacity,travel_minutes,available,food_categories,demo,created_at,updated_at) VALUES(?,?,?,?,1,?,1,?,?)",
                           (name, area, capacity, travel_minutes, categories, now, now))
        seed_demo_listing(db)
        return {"recipients": db.execute("SELECT COUNT(*) FROM recipients WHERE demo=1").fetchone()[0],
                "demo_listings": db.execute("SELECT COUNT(*) FROM listings WHERE demo=1").fetchone()[0],
                "demo_listing_id": db.execute("SELECT id FROM listings WHERE demo=1 ORDER BY id DESC LIMIT 1").fetchone()[0],
                "listings_preserved": db.execute("SELECT COUNT(*) FROM listings WHERE demo=0").fetchone()[0]}

def recipient_dict(row):
    import json
    item = dict(row)
    item["available"] = bool(item["available"])
    item["food_categories"] = json.loads(item["food_categories"])
    return item
