"""Create the initial administrator through a trusted local PowerShell session.

Run: python -m backend.create_admin admin@example.org
The password is read interactively and is never accepted in command arguments.
"""
import getpass
import json
import re
import sys
from datetime import datetime

from .auth import audit, hash_password
from .database import connection, init_db


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", sys.argv[1]):
        raise SystemExit("Usage: python -m backend.create_admin admin@example.org")
    email = sys.argv[1].strip().lower()
    password = getpass.getpass("New admin password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        if db.execute("SELECT 1 FROM user_accounts WHERE email=? COLLATE NOCASE AND role='ADMIN'", (email,)).fetchone():
            raise SystemExit("That account already exists; this tool does not elevate existing accounts.")
        cur = db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES(?,?,'ADMIN',?,?)",
                         (email, hash_password(password), now, now))
        db.execute("INSERT INTO user_profiles(user_id,profile_json,status,created_at,updated_at) VALUES(?,'{}','approved',?,?)",
                   (cur.lastrowid, now, now))
        audit(db, cur.lastrowid, "admin_bootstrapped", "user", cur.lastrowid, json.dumps({"process": "local_cli"}))
    print(f"Created initial administrator {email}.")


if __name__ == "__main__":
    main()
