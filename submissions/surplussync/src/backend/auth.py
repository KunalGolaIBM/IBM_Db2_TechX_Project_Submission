"""Password and opaque-cookie session helpers for the local SurplusSync API."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request

from .database import connection

PASSWORD_ITERATIONS = 600_000
SESSION_COOKIE = "surplussync_session"
SESSION_HOURS = 12


def _now() -> datetime:
    return datetime.now()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def public_user(db, user_id: int, active_role: str | None = None) -> dict | None:
    account = db.execute("SELECT id,email,role,status,is_demo FROM user_accounts WHERE id=?", (user_id,)).fetchone()
    if account is None:
        return None
    profile_rows = db.execute("SELECT role,status,demo FROM user_profiles WHERE user_id=? ORDER BY role", (user_id,)).fetchall()
    roles = [item["role"] for item in profile_rows]
    if account["role"] == "ADMIN":
        roles = ["ADMIN"]
    role = active_role or (account["role"] if account["role"] in roles else (roles[0] if roles else account["role"]))
    row = db.execute("""SELECT p.status AS profile_status,
        p.profile_json,p.review_reason,p.reviewed_at,p.demo AS profile_demo,ov.status AS organization_verification_status,
        ov.registration_type,ov.registration_number,ov.review_reason AS organization_review_reason
        FROM user_profiles p LEFT JOIN organization_verifications ov ON ov.user_id=p.user_id
        WHERE p.user_id=? AND p.role=?""", (user_id, role)).fetchone()
    if role == "ADMIN":
        return {"id": account["id"], "email": account["email"], "role": "ADMIN", "is_demo": bool(account["is_demo"]),
                "status": account["status"], "profile_status": "approved", "profile": {}, "review_reason": "",
                "reviewed_at": None, "organization_verification_status": None, "organization_review_reason": "",
                "available_roles": roles, "role_profiles": []}
    if row is None:
        return None
    import json
    organization_status = row["organization_verification_status"] or \
        ("approved_legacy" if role == "RECIPIENT" and row["profile_status"] == "approved" else row["profile_status"] if role == "RECIPIENT" else None)
    if role == "RECIPIENT" and row["profile_demo"]:
        organization_status = "demo_fixture"
    profile_data = json.loads(row["profile_json"])
    return {"id": account["id"], "email": account["email"], "role": role, "is_demo": bool(account["is_demo"]),
            "profile_demo": bool(row["profile_demo"]), "status": account["status"], "profile_status": row["profile_status"],
            "profile": profile_data, "presentation_setup": profile_data.get("_presentation_setup") is True, "review_reason": row["review_reason"],
            "reviewed_at": row["reviewed_at"],
            "organization_verification_status": organization_status,
            "organization_review_reason": row["organization_review_reason"] or row["review_reason"] if role == "RECIPIENT" else "",
            "presentation_demo_mode": os.getenv("SURPLUSSYNC_PRESENTATION_DEMO_ENABLED", "").strip().lower() in {"1", "true", "yes"},
            "available_roles": roles,
            "role_profiles": [{"role": item["role"], "profile_status": item["status"], "demo": bool(item["demo"])} for item in profile_rows]}


def current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, detail={"code": "authentication_required", "message": "Please log in to continue."})
    now = _now().isoformat(timespec="seconds")
    with connection() as db:
        row = db.execute("SELECT user_id,active_role FROM auth_sessions WHERE token_hash=? AND expires_at>?",
                         (digest(token), now)).fetchone()
        user = public_user(db, row["user_id"], row["active_role"]) if row else None
    if not user or user["status"] != "active":
        raise HTTPException(401, detail={"code": "session_expired", "message": "Your session has expired. Please log in again."})
    return user


def require_csrf(request: Request, user: dict) -> None:
    token = request.headers.get("X-CSRF-Token", "")
    session = request.cookies.get(SESSION_COOKIE, "")
    if not token or not session:
        raise HTTPException(403, detail={"code": "csrf_required", "message": "Refresh your session and try again."})
    with connection() as db:
        row = db.execute("SELECT csrf_hash FROM auth_sessions WHERE token_hash=? AND user_id=? AND expires_at>?",
                         (digest(session), user["id"], _now().isoformat(timespec="seconds"))).fetchone()
    if not row or not hmac.compare_digest(row["csrf_hash"], digest(token)):
        raise HTTPException(403, detail={"code": "csrf_invalid", "message": "The request security token is invalid. Refresh and try again."})


def create_session(db, user_id: int, active_role: str | None = None) -> tuple[str, str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    created = _now()
    expires = created + timedelta(hours=SESSION_HOURS)
    db.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (created.isoformat(timespec="seconds"),))
    if active_role is None:
        row = db.execute("SELECT role FROM user_accounts WHERE id=?", (user_id,)).fetchone()
        active_role = row["role"] if row else "DONOR"
    db.execute("INSERT INTO auth_sessions(token_hash,csrf_hash,user_id,active_role,expires_at,created_at) VALUES(?,?,?,?,?,?)",
               (digest(token), digest(csrf), user_id, active_role, expires.isoformat(timespec="seconds"), created.isoformat(timespec="seconds")))
    return token, csrf, expires.isoformat(timespec="seconds")


def audit(db, actor_id: int | None, action: str, subject_type: str, subject_id: object = "", details: str = "{}") -> None:
    db.execute("INSERT INTO security_audit(actor_user_id,action,subject_type,subject_id,details,created_at) VALUES(?,?,?,?,?,?)",
               (actor_id, action, subject_type, str(subject_id), details, _now().isoformat(timespec="seconds")))
