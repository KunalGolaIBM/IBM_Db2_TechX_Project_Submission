import json
import sqlite3
import hashlib
import math
import os
import re
import secrets
import smtplib
import base64
import binascii
import struct
import zlib
from email.message import EmailMessage
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Load local settings before importing modules that read database configuration.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from .database import connection, init_db, recipient_dict, reset_demo_data
from .models import AvailabilityUpdate, ListingCreate, RescueProposal, RescueDecision, RescueTransition, SignupRequest, LoginRequest, AccountDeleteRequest, PasswordResetRequest, PasswordResetConfirm, ProfileUpdate, VerificationDecision, VolunteerAssignment, OrganizationApplicationRequest, RoleProfileCreate, RoleSwitch
from .feasibility import evaluate
from .auth import SESSION_COOKIE, audit, create_session, current_user, digest, hash_password, public_user, require_csrf, verify_password
from .db2_ai import router as db2_ai_router

@asynccontextmanager
async def lifespan(_app):
    init_db()
    from .seed_presentation_demo import enabled, seed_presentation_demo
    if enabled():
        seed_presentation_demo()
    yield

app = FastAPI(title="SurplusSync API", version="1.0.0", lifespan=lifespan)
app.include_router(db2_ai_router)
cors_origins=[origin.strip() for origin in os.getenv("SURPLUSSYNC_CORS_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_credentials=True, allow_methods=["GET","POST","PATCH","PUT","DELETE"], allow_headers=["Content-Type","X-CSRF-Token"])

PUBLIC_AUTH = {("GET", "/api/health"), ("POST", "/api/auth/signup"), ("POST", "/api/auth/login"),
               ("POST", "/api/auth/password/forgot"), ("POST", "/api/auth/password/reset")}

@app.middleware("http")
async def authenticate_api(request: Request, call_next):
    path, method = request.url.path, request.method
    if not path.startswith("/api/") or method == "OPTIONS" or (method, path) in PUBLIC_AUTH:
        return await call_next(request)
    try:
        user = current_user(request)
        if method in {"POST", "PATCH", "PUT", "DELETE"}:
            require_csrf(request, user)
        request.state.user = user
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
    return await call_next(request)

# Operational routes require an approved profile unless the onboarding or logout route opts out.
def actor(request: Request, roles: set[str] | None = None, approved: bool = True) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, detail={"code":"authentication_required","message":"Please log in to continue."})
    if roles and user["role"] not in roles:
        raise HTTPException(403, detail={"code":"role_forbidden","message":"Your account role cannot perform this action."})
    if approved:
        if user["role"] == "RECIPIENT" and user.get("presentation_setup") and not user.get("presentation_demo_mode"):
            raise HTTPException(403,detail={"code":"presentation_demo_disabled","message":"Fictional demo organization access is disabled. Enable presentation mode only for a local or isolated demo database."})
        if user["profile_status"] != "approved":
            if user["role"] == "RECIPIENT" and user.get("profile_demo") and user.get("presentation_demo_mode"):
                message = "Complete and save this fictional demo organization profile before using recipient features."
            else:
                message = "Complete your profile and wait for recipient organization review before using this action." if user["role"] == "RECIPIENT" else "Complete your profile before using this action."
            raise HTTPException(403, detail={"code":"profile_not_approved","message":message})
    return user

def profile_is_valid(role: str, profile: dict) -> bool:
    required = {
        "DONOR": ("contact_name", "phone", "organization_name", "address", "pickup_area"),
        "RECIPIENT": ("organization_name", "address", "service_area", "contact_person", "phone", "receiving_hours", "registration_type", "registration_number", "food_categories", "capacity"),
        "VOLUNTEER": ("contact_name", "phone", "service_area", "availability"),
    }.get(role, ())
    allowed={"DONOR":{"contact_name","phone","organization_name","address","pickup_area"},
             "RECIPIENT":{"organization_name","address","service_area","contact_person","phone","receiving_hours","registration_type","registration_number","food_categories","capacity"},
             "VOLUNTEER":{"contact_name","phone","service_area","availability"}}.get(role,set())
    if not isinstance(profile,dict) or set(profile)-allowed or any(key not in profile for key in required):
        return False
    text_fields=set(required)-({"food_categories","capacity"} if role=="RECIPIENT" else set())
    if any(not isinstance(profile[key],str) or not profile[key].strip() or len(profile[key])>200 for key in text_fields):
        return False
    if role == "RECIPIENT" and not 7 <= len(re.sub(r"\D", "", profile.get("phone", ""))) <= 15:
        return False
    for key in required:
        value = profile[key]
        if isinstance(value, str) and not value.strip():
            return False
    if role == "RECIPIENT":
        categories=profile["food_categories"]
        registration_number=profile.get("registration_number","")
        return (isinstance(registration_number,str) and len(registration_number)<=100
                and isinstance(categories,list) and bool(categories) and len(categories)==len(set(categories))
                and all(isinstance(c,str) and c in {"Prepared meals","Fresh produce","Bakery","Dairy","Packaged groceries"} for c in categories)
                and isinstance(profile["capacity"], int) and not isinstance(profile["capacity"],bool) and 0 < profile["capacity"] <= 100000)
    return True

MAX_CERTIFICATE_BYTES = 5 * 1024 * 1024
CERTIFICATE_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

def private_upload_directory() -> Path:
    configured = os.getenv("SURPLUSSYNC_UPLOAD_DIR", "").strip()
    root = Path(configured).expanduser() if configured else Path(__file__).resolve().parent / "private_uploads"
    root = root.resolve()
    frontend = (Path(__file__).resolve().parents[1] / "frontend").resolve()
    if root == frontend or frontend in root.parents:
        raise RuntimeError("SURPLUSSYNC_UPLOAD_DIR must be outside the publicly served frontend directory.")
    root.mkdir(parents=True, exist_ok=True)
    return root

def max_certificate_bytes() -> int:
    try:
        configured = int(os.getenv("SURPLUSSYNC_MAX_CERTIFICATE_BYTES", str(MAX_CERTIFICATE_BYTES)))
    except ValueError as exc:
        raise RuntimeError("SURPLUSSYNC_MAX_CERTIFICATE_BYTES must be an integer.") from exc
    if not 1024 <= configured <= 20 * 1024 * 1024:
        raise RuntimeError("SURPLUSSYNC_MAX_CERTIFICATE_BYTES must be between 1024 and 20971520.")
    return configured

def decode_certificate(filename: str, encoded: str) -> tuple[bytes, str, str, str]:
    # The client filename is display metadata only; the storage path is random.
    normalized = filename.replace("\\", "/").split("/")[-1].strip()
    extension = Path(normalized).suffix.lower()
    expected_type = CERTIFICATE_TYPES.get(extension)
    if not expected_type or not normalized or len(normalized) > 255 or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(422, detail={"code":"certificate_type_invalid","message":"Upload a PDF, JPG, or PNG registration certificate."})
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, detail={"code":"certificate_encoding_invalid","message":"The certificate upload could not be read. Choose the file again."})
    max_bytes = max_certificate_bytes()
    if not raw or len(raw) > max_bytes:
        raise HTTPException(413, detail={"code":"certificate_size_invalid","message":f"Certificate file exceeds the configured {max_bytes // (1024 * 1024)} MB limit."})
    if expected_type == "application/pdf":
        valid = raw.startswith(b"%PDF-") and b"%%EOF" in raw[-2048:]
    elif expected_type == "image/jpeg":
        valid = raw.startswith(b"\xff\xd8\xff") and b"\xff\xd9" in raw[-16:]
    else:
        valid = valid_png(raw)
    if not valid:
        raise HTTPException(422, detail={"code":"certificate_content_invalid","message":"The file contents do not match a valid PDF, JPG, or PNG certificate."})
    safe_display_name = re.sub(r"[^A-Za-z0-9._ -]", "_", normalized)[:160] or f"registration-certificate{extension}"
    return raw, extension, expected_type, safe_display_name

def valid_png(raw: bytes) -> bool:
    signature = b"\x89PNG\r\n\x1a\n"
    if not raw.startswith(signature):
        return False
    offset, first, ended = len(signature), True, False
    try:
        while offset + 12 <= len(raw):
            length = struct.unpack(">I",raw[offset:offset+4])[0]
            chunk_type = raw[offset+4:offset+8]
            chunk_end = offset + 12 + length
            if chunk_end > len(raw):
                return False
            chunk_data = raw[offset+8:offset+8+length]
            expected_crc = struct.unpack(">I",raw[offset+8+length:chunk_end])[0]
            if (zlib.crc32(chunk_type + chunk_data) & 0xffffffff) != expected_crc:
                return False
            if first and (chunk_type != b"IHDR" or length != 13):
                return False
            first = False
            offset = chunk_end
            if chunk_type == b"IEND":
                ended = length == 0 and offset == len(raw)
                break
        return ended and not first
    except (struct.error, OverflowError):
        return False

def volunteer_profile_available(profile_json: str) -> bool:
    try:
        availability = str(json.loads(profile_json).get("availability", "")).strip().casefold()
    except (TypeError, ValueError):
        return False
    return bool(availability and availability not in {"unavailable", "not available", "none", "no", "off"})

def available_volunteer_count(db) -> int:
    rows = db.execute("SELECT p.profile_json FROM user_accounts u JOIN user_profiles p ON p.user_id=u.id WHERE p.role='VOLUNTEER' AND u.status='active' AND p.status='approved'").fetchall()
    return sum(volunteer_profile_available(row["profile_json"]) for row in rows)

def evaluate_current(db, listing: dict, excluded: set[int] | None = None) -> dict:
    return evaluate(listing, recipients_for_evaluation(db, exclude_owner_user_id=listing.get("donor_user_id")), excluded, available_volunteer_count(db))

def persist_risk(db, listing_id: int, result: dict, now: str, plan_id: int | None = None, rescue_id: int | None = None) -> None:
    risk = result["risk_assessment"]
    db.execute("INSERT INTO rescue_risk_assessments(listing_id,plan_id,rescue_id,category,score,reasons,alternative_recipient_ids,volunteer_available_count,assessed_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (listing_id,plan_id,rescue_id,risk["category"],risk["score"],json.dumps(risk["reasons"]),json.dumps(risk["alternative_recipient_ids"]),risk["volunteer_available_count"],now))

def refresh_active_rescue_risks(db, now: str) -> None:
    rows = db.execute("SELECT id,listing_id FROM rescue_cases WHERE status IN ('awaiting_confirmation','accepted','ready_for_pickup','collected')").fetchall()
    for row in rows:
        listing = listing_by_id(db,row["listing_id"])
        if listing:
            result = evaluate(listing,recipients_for_evaluation(db,exclude_rescue_id=row["id"],exclude_owner_user_id=listing.get("donor_user_id")),rejected_ids(db,row["listing_id"]),available_volunteer_count(db))
            persist_risk(db,row["listing_id"],result,now,rescue_id=row["id"])

def refresh_listed_plans(db, now: str) -> None:
    """Re-rank unoffered plans immediately after availability/capacity changes."""
    rows = db.execute("SELECT p.id,p.listing_id FROM rescue_plans p JOIN rescue_cases rc ON rc.listing_id=p.listing_id WHERE rc.status='listed'").fetchall()
    for row in rows:
        listing = listing_by_id(db, row["listing_id"])
        if listing:
            result = evaluate_current(db, listing, rejected_ids(db, row["listing_id"]))
            save_plan(db, row["listing_id"], result, now, row["id"])

def check_rate_limit(db, key: str, limit: int, minutes: int = 15, message: str = "Too many attempts. Wait a while before trying again.") -> None:
    now = datetime.now()
    row = db.execute("SELECT attempts,window_started_at FROM auth_attempts WHERE bucket=?", (key,)).fetchone()
    if row:
        started = datetime.fromisoformat(row["window_started_at"])
        if started + timedelta(minutes=minutes) <= now:
            db.execute("UPDATE auth_attempts SET attempts=1,window_started_at=? WHERE bucket=?", (now.isoformat(timespec="seconds"),key))
        elif row["attempts"] >= limit:
            retry_after = max(1, math.ceil((started + timedelta(minutes=minutes) - now).total_seconds()))
            retry_message = f"{message} Try again in about {retry_after} seconds."
            raise HTTPException(429, detail={"code":"rate_limited","message":retry_message}, headers={"Retry-After": str(retry_after)})
        else:
            db.execute("UPDATE auth_attempts SET attempts=attempts+1 WHERE bucket=?", (key,))
    else:
        db.execute("INSERT INTO auth_attempts(bucket,attempts,window_started_at) VALUES(?,1,?)", (key,now.isoformat(timespec="seconds")))

def request_bucket(request: Request, value: str) -> str:
    return hashlib.sha256(f"{request.client.host if request.client else 'unknown'}:{value}".encode()).hexdigest()

def enforce_rate_limit(bucket: str, limit: int, minutes: int, message: str | None = None) -> None:
    with connection(immediate=True) as db:
        if message is None:
            check_rate_limit(db,bucket,limit,minutes)
        else:
            check_rate_limit(db,bucket,limit,minutes,message)

def user_role_is_donor(request: Request) -> bool:
    user=getattr(request.state,"user",None)
    return bool(user and user["role"]=="DONOR")

def set_session_cookie(response, token: str, expires_at: str) -> None:
    secure = os.getenv("SURPLUSSYNC_COOKIE_SECURE", "").lower() in {"1","true","yes"}
    # Use max_age only: database timestamps intentionally use local naive time,
    # while Starlette requires an aware UTC datetime for the Expires header.
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=secure, samesite="lax", path="/",
                        max_age=12*60*60)


def send_reset_email(email: str, token: str) -> bool:
    host = os.getenv("SURPLUSSYNC_SMTP_HOST")
    if not host:
        return False
    message = EmailMessage()
    message["Subject"] = "Reset your SurplusSync password"
    message["From"] = os.getenv("SURPLUSSYNC_SMTP_FROM", "surplussync@localhost")
    message["To"] = email
    url = os.getenv("SURPLUSSYNC_FRONTEND_URL", "http://localhost:5173") + "/?reset_token=" + token
    message.set_content(f"Use this one-time link within 30 minutes to reset your password: {url}\nIf you did not request this, ignore this message.")
    port = int(os.getenv("SURPLUSSYNC_SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        username = os.getenv("SURPLUSSYNC_SMTP_USERNAME")
        if username:
            server.login(username, os.getenv("SURPLUSSYNC_SMTP_PASSWORD", ""))
        server.send_message(message)
    return True

@app.get("/api/auth/csrf")
def auth_csrf(request: Request):
    user = current_user(request)
    token = secrets.token_urlsafe(32)
    session = request.cookies.get(SESSION_COOKIE, "")
    with connection() as db:
        db.execute("UPDATE auth_sessions SET csrf_hash=? WHERE token_hash=? AND user_id=?", (digest(token),digest(session),user["id"]))
    return {"csrf_token": token}

@app.post("/api/auth/signup", status_code=201)
def signup(body: SignupRequest, request: Request):
    ip_bucket = request_bucket(request, "signup")
    enforce_rate_limit(ip_bucket,5,60)
    now = datetime.now().isoformat(timespec="seconds")
    password_hash=hash_password(body.password)
    with connection(immediate=True) as db:
        if db.execute("SELECT 1 FROM user_accounts WHERE email=? COLLATE NOCASE", (body.email,)).fetchone():
            raise HTTPException(409, detail={"code":"account_exists","message":"An account with this email already exists. Log in, then add another role profile from account settings."})
        cur = db.execute("INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
                         (body.email,password_hash,body.role,now,now))
        db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,?,'{}','pending',?,?)",(cur.lastrowid,body.role,now,now))
        audit(db,cur.lastrowid,"account_created","user",cur.lastrowid,json.dumps({"role":body.role}))
    return {"message": "Account created. You can log in now.", "available_roles": [body.role]}

@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request):
    bucket=request_bucket(request,"login:"+body.email)
    enforce_rate_limit(bucket,5,15)
    now=datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        row=db.execute("SELECT id,password_hash,status,role FROM user_accounts WHERE email=? COLLATE NOCASE",(body.email,)).fetchone()
        invalid = not row or not verify_password(body.password,row["password_hash"]) or row["status"]!="active"
        if invalid:
            audit(db,None,"login_failed","account",body.email[:254])
        if not invalid:
            roles=[item["role"] for item in db.execute("SELECT role FROM user_profiles WHERE user_id=? ORDER BY role",(row["id"],)).fetchall()]
            if row["role"] == "ADMIN":
                roles=["ADMIN"]
            if body.role and body.role not in roles:
                raise HTTPException(403,detail={"code":"role_not_available","message":"This account does not have the selected role profile."})
            if not body.role and len(roles)>1:
                raise HTTPException(409,detail={"code":"role_selection_required","message":"Choose which role profile to open.","roles":roles})
            active_role=body.role or (roles[0] if roles else row["role"])
            db.execute("DELETE FROM auth_attempts WHERE bucket=?",(bucket,))
            token,csrf,expires=create_session(db,row["id"],active_role)
            audit(db,row["id"],"login_succeeded","user",row["id"])
            user=public_user(db,row["id"],active_role)
    if invalid:
        raise HTTPException(401,detail={"code":"invalid_credentials","message":"Email or password is incorrect."})
    response=JSONResponse({"user":user,"csrf_token":csrf})
    set_session_cookie(response,token,expires)
    return response

@app.post("/api/auth/role-profiles", status_code=201)
def create_role_profile(body: RoleProfileCreate, request: Request):
    """Add a role profile to the authenticated identity; recipient status remains pending admin review."""
    user=actor(request,approved=False)
    now=datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        if user["role"] == "ADMIN":
            raise HTTPException(403,detail={"code":"admin_role_separate","message":"Administrator accounts cannot add public operational profiles."})
        if db.execute("SELECT 1 FROM user_profiles WHERE user_id=? AND role=?",(user["id"],body.role)).fetchone():
            raise HTTPException(409,detail={"code":"role_profile_exists","message":"This role profile already exists."})
        db.execute("INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,?,'{}','pending',?,?)",(user["id"],body.role,now,now))
        db.execute("UPDATE auth_sessions SET active_role=? WHERE token_hash=?",(body.role,digest(request.cookies.get(SESSION_COOKIE,""))))
        audit(db,user["id"],"role_profile_created","profile",body.role)
        profile=public_user(db,user["id"],body.role)
    return {"user":profile,"message":"Role profile created. Complete its details; recipient organizations still require administrator approval."}

@app.post("/api/auth/active-role")
def switch_active_role(body: RoleSwitch, request: Request):
    user=actor(request,approved=False)
    if body.role != "ADMIN":
        with connection() as db:
            exists=db.execute("SELECT 1 FROM user_profiles WHERE user_id=? AND role=?",(user["id"],body.role)).fetchone()
        if not exists:
            raise HTTPException(403,detail={"code":"role_not_available","message":"Add and complete this role profile before switching to it."})
    elif user["role"] != "ADMIN":
        raise HTTPException(403,detail={"code":"role_forbidden","message":"Administrator access is managed separately."})
    token=request.cookies.get(SESSION_COOKIE,"")
    with connection(immediate=True) as db:
        db.execute("UPDATE auth_sessions SET active_role=? WHERE token_hash=? AND user_id=?",(body.role,digest(token),user["id"]))
        audit(db,user["id"],"active_role_changed","profile",body.role)
        updated=public_user(db,user["id"],body.role)
    return {"user":updated}

@app.get("/api/auth/me")
def auth_me(request: Request):
    return {"user":current_user(request)}

@app.post("/api/auth/logout")
def logout(request: Request):
    # A pending/rejected user must still be able to end their session.
    user=actor(request, approved=False)
    token=request.cookies.get(SESSION_COOKIE,"" )
    with connection() as db:
        db.execute("DELETE FROM auth_sessions WHERE token_hash=?",(digest(token),))
        audit(db,user["id"],"logout","user",user["id"])
    response=JSONResponse({"ok":True})
    response.delete_cookie(SESSION_COOKIE,path="/",httponly=True,samesite="lax")
    return response

@app.post("/api/auth/account/delete")
def delete_account(body: AccountDeleteRequest, request: Request):
    """Permanently remove the authenticated account and its owned records."""
    user = actor(request, approved=False)
    now = datetime.now().isoformat(timespec="seconds")
    document_paths = []
    with connection(immediate=True) as db:
        row = db.execute("SELECT id,email,password_hash,role FROM user_accounts WHERE id=?", (user["id"],)).fetchone()
        if not row or row["email"].casefold() != body.confirm_email.casefold():
            raise HTTPException(422, detail={"code":"account_confirmation_mismatch","message":"Enter the exact email address on this account to confirm deletion."})
        if not verify_password(body.password, row["password_hash"]):
            raise HTTPException(403, detail={"code":"account_password_invalid","message":"The password is incorrect. Your account was not deleted."})
        if row["role"] == "ADMIN" and db.execute("SELECT COUNT(*) FROM user_accounts WHERE role='ADMIN' AND status='active'").fetchone()[0] <= 1:
            raise HTTPException(409, detail={"code":"last_admin_account","message":"The last active administrator cannot delete its account."})

        user_id, email, role = row["id"], row["email"], row["role"]
        active_statuses = ("awaiting_confirmation", "accepted", "ready_for_pickup", "collected")
        placeholders = ",".join("?" for _ in active_statuses)
        profile_roles={item["role"] for item in db.execute("SELECT role FROM user_profiles WHERE user_id=?",(user_id,)).fetchall()}
        if "DONOR" in profile_roles and db.execute(f"SELECT 1 FROM rescue_cases rc JOIN listings l ON l.id=rc.listing_id WHERE l.donor_user_id=? AND rc.status IN ({placeholders}) LIMIT 1", (user_id,*active_statuses)).fetchone():
            raise HTTPException(409, detail={"code":"active_rescue_assignments","message":"Complete or cancel your active rescues before deleting this donor account. No data was changed."})
        if "RECIPIENT" in profile_roles and db.execute(f"SELECT 1 FROM rescue_cases rc JOIN recipients r ON r.id=rc.recipient_id WHERE r.owner_user_id=? AND rc.status IN ({placeholders}) LIMIT 1", (user_id,*active_statuses)).fetchone():
            raise HTTPException(409, detail={"code":"active_rescue_assignments","message":"Resolve active rescue offers before deleting this organization account. No data was changed."})
        if "VOLUNTEER" in profile_roles and db.execute(f"SELECT 1 FROM rescue_cases WHERE volunteer_user_id=? AND status IN ({placeholders}) LIMIT 1", (user_id,*active_statuses)).fetchone():
            raise HTTPException(409, detail={"code":"active_rescue_assignments","message":"Complete or request reassignment for your active rescue tasks before deleting this volunteer account. No data was changed."})

        # Preserve listing, matching, rescue and timeline history while removing
        # the deleted donor's identity and ownership link.
        db.execute("UPDATE listings SET donor_name='Deleted donor',donor_user_id=NULL WHERE donor_user_id=?", (user_id,))

        owned = [r["id"] for r in db.execute("SELECT id FROM recipients WHERE owner_user_id=?", (user_id,)).fetchall()]
        for recipient_id in owned:
            db.execute("UPDATE recipients SET name=?,owner_user_id=NULL,available=0,demo=0,updated_at=? WHERE id=?",
                       (f"Former recipient #{recipient_id}",now,recipient_id))

        document_names = [r["storage_name"] for r in db.execute("SELECT storage_name FROM organization_documents WHERE user_id=?", (user_id,)).fetchall()]
        upload_root = private_upload_directory()
        document_paths = [upload_root / name for name in document_names if Path(name).name == name]

        # Keep rescue history but remove personal assignment and reviewer links.
        db.execute("UPDATE rescue_cases SET volunteer_user_id=NULL WHERE volunteer_user_id=?", (user_id,))
        db.execute("UPDATE user_profiles SET reviewed_by=NULL WHERE reviewed_by=?", (user_id,))
        # Preserve the security-event history while removing fields that could
        # identify the deleted account or contain its personal data.
        db.execute("UPDATE security_audit SET actor_user_id=NULL,subject_type='anonymized',subject_id='',details='{}' WHERE actor_user_id=? OR (subject_type='user' AND subject_id=?) OR (subject_type='account' AND subject_id=? COLLATE NOCASE)", (user_id,str(user_id),email))
        db.execute("DELETE FROM auth_attempts WHERE bucket=?", (request_bucket(request, "login:"+email),))
        db.execute("DELETE FROM user_accounts WHERE id=?", (user_id,))
        db.execute("INSERT INTO security_audit(actor_user_id,action,subject_type,subject_id,details,created_at) VALUES(NULL,'account_deleted','account',?,?,?)", (str(user_id),json.dumps({"role":role}),now))

    for path in document_paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # An inaccessible orphan remains private and is not referenced by
            # the deleted account. Never log its contents or any credential.
            pass

    response = JSONResponse({"ok":True,"message":"Your account and its associated personal data were permanently deleted."})
    response.delete_cookie(SESSION_COOKIE,path="/",httponly=True,samesite="lax")
    return response

@app.put("/api/auth/profile")
def update_profile(body: ProfileUpdate, request: Request):
    # Profile submission/resubmission is the path out of pending/rejected state.
    user=actor(request, approved=False)
    profile=body.profile
    if user["role"]=="RECIPIENT":
        if user.get("profile_demo") and not user.get("presentation_demo_mode"):
            raise HTTPException(409,detail={"code":"presentation_demo_disabled","message":"Presentation mode is disabled. Enable it only for a local or isolated demo database."})
        if not user.get("profile_demo"):
            raise HTTPException(409,detail={"code":"certificate_required","message":"Organization details must be submitted with a valid registration certificate using the organization application form."})
        required={"organization_name","service_area","capacity","food_categories"}
        allowed=required
        categories=profile.get("food_categories") if isinstance(profile,dict) else None
        valid=(isinstance(profile,dict) and set(profile)==allowed
               and all(isinstance(profile.get(key),str) and profile[key].strip() and len(profile[key].strip())<=100 for key in ("organization_name","service_area"))
               and isinstance(profile.get("capacity"),int) and not isinstance(profile.get("capacity"),bool) and 0<profile["capacity"]<=100000
               and isinstance(categories,list) and bool(categories)
               and all(isinstance(item,str) and item in {"Prepared meals","Fresh produce","Bakery","Dairy","Packaged groceries"} for item in categories)
               and len(categories)==len(set(categories)))
        if not valid:
            raise HTTPException(422,detail={"code":"demo_organization_profile_invalid","message":"Enter a demo organization name, receiving area, capacity from 1 to 100000, and at least one accepted food category."})
        now=datetime.now().isoformat(timespec="seconds")
        with connection(immediate=True) as db:
            current=db.execute("SELECT id,demo FROM recipients WHERE owner_user_id=?",(user["id"],)).fetchone()
            if current and not current["demo"]:
                raise HTTPException(409,detail={"code":"real_organization_preserved","message":"A real organization record cannot be converted to a presentation demo profile."})
            stored_profile={**profile,"_presentation_setup":True}
            profile_json=json.dumps(stored_profile,separators=(",",":"),sort_keys=True)
            db.execute("UPDATE user_profiles SET profile_json=?,status='approved',review_reason='',reviewed_by=NULL,reviewed_at=NULL,updated_at=? WHERE user_id=? AND role='RECIPIENT' AND demo=1",
                       (profile_json,now,user["id"]))
            display_name=profile["organization_name"].strip()
            if not display_name.endswith("— DEMO"):
                display_name += " — DEMO"
            encoded_categories=json.dumps(categories,separators=(",",":"))
            if current:
                db.execute("UPDATE recipients SET name=?,area=?,capacity=?,food_categories=?,available=1,updated_at=? WHERE id=? AND owner_user_id=? AND demo=1",
                           (display_name,profile["service_area"].strip(),profile["capacity"],encoded_categories,now,current["id"],user["id"]))
            else:
                db.execute("INSERT INTO recipients(name,area,capacity,travel_minutes,available,food_categories,demo,owner_user_id,created_at,updated_at) VALUES(?,?,?,15,1,?,1,?,?,?)",
                           (display_name,profile["service_area"].strip(),profile["capacity"],encoded_categories,user["id"],now,now))
            audit(db,user["id"],"demo_organization_profile_saved","profile",user["id"],json.dumps({"fictional_demo":True}))
            refresh_listed_plans(db,now)
            refresh_active_rescue_risks(db,now)
            return {"user":public_user(db,user["id"],"RECIPIENT"),"message":"Fictional demo organization saved and available in the demo network. This is not legal registration or official verification."}
    if user["role"]=="ADMIN" or not profile_is_valid(user["role"],profile):
        raise HTTPException(422,detail={"code":"invalid_profile","message":"Complete all required fields for your selected role."})
    allowed={"DONOR":{"contact_name","phone","organization_name","address","pickup_area"},
             "RECIPIENT":{"organization_name","address","service_area","contact_person","phone","receiving_hours","food_categories","capacity"},
             "VOLUNTEER":{"contact_name","phone","service_area","availability"}}[user["role"]]
    if set(profile)-allowed:
        raise HTTPException(422,detail={"code":"unexpected_profile_field","message":"Profile contains fields not allowed for this role."})
    now=datetime.now().isoformat(timespec="seconds")
    next_status = "pending" if user["role"] == "RECIPIENT" else "approved"
    with connection() as db:
        db.execute("UPDATE user_profiles SET profile_json=?,status=?,review_reason='',reviewed_by=NULL,reviewed_at=NULL,updated_at=? WHERE user_id=? AND role=?",
                   (json.dumps(profile),next_status,now,user["id"],user["role"]))
        if user["role"]=="RECIPIENT":
            db.execute("UPDATE recipients SET available=0,updated_at=? WHERE owner_user_id=?",(now,user["id"]))
        audit(db,user["id"],"profile_submitted","profile",user["id"],json.dumps({"status":next_status}))
        refresh_listed_plans(db,now)
        refresh_active_rescue_risks(db,now)
        return {"user":public_user(db,user["id"],user["role"]), "message": "Recipient profile submitted for organization review." if user["role"] == "RECIPIENT" else "Profile complete. You can now use your account."}

@app.put("/api/auth/organization/application")
def submit_organization_application(body: OrganizationApplicationRequest, request: Request):
    user = actor(request, {"RECIPIENT"}, approved=False)
    profile = body.profile
    if not profile_is_valid("RECIPIENT", profile):
        raise HTTPException(422, detail={"code":"organization_profile_invalid","message":"Complete the organization name, authorized contact, official address, service area, phone, receiving hours, NGO registration type and number, capacity, and accepted food categories."})
    raw, extension, content_type, display_name = decode_certificate(body.certificate_filename, body.certificate_base64)
    root = private_upload_directory()
    storage_name = secrets.token_hex(32) + extension
    destination = (root / storage_name).resolve()
    if destination.parent != root:
        raise HTTPException(500, detail={"code":"private_storage_error","message":"Private document storage is not configured safely."})
    try:
        with destination.open("xb") as document:
            document.write(raw)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
        now = datetime.now().isoformat(timespec="seconds")
        with connection(immediate=True) as db:
            profile_row = db.execute("SELECT status FROM user_profiles WHERE user_id=? AND role='RECIPIENT'", (user["id"],)).fetchone()
            verification = db.execute("SELECT status FROM organization_verifications WHERE user_id=?", (user["id"],)).fetchone()
            if not profile_row:
                raise HTTPException(404, detail={"code":"profile_not_found","message":"Organization profile not found."})
            if profile_row["status"] == "approved" or verification and verification["status"] == "approved":
                raise HTTPException(409, detail={"code":"organization_already_approved","message":"Contact an administrator if an approved organization needs its details changed."})
            db.execute("UPDATE organization_documents SET is_current=0 WHERE user_id=?", (user["id"],))
            db.execute("INSERT INTO organization_documents(user_id,storage_name,original_name,content_type,size_bytes,sha256,is_current,submitted_at) VALUES(?,?,?,?,?,?,1,?)",
                       (user["id"],storage_name,display_name,content_type,len(raw),hashlib.sha256(raw).hexdigest(),now))
            db.execute("""INSERT INTO organization_verifications(user_id,registration_type,registration_number,status,review_reason,reviewed_by,reviewed_at,submitted_at,updated_at)
                VALUES(?,?,?,'pending','',NULL,NULL,?,?) ON CONFLICT(user_id) DO UPDATE SET
                registration_type=excluded.registration_type,registration_number=excluded.registration_number,status='pending',review_reason='',
                reviewed_by=NULL,reviewed_at=NULL,submitted_at=excluded.submitted_at,updated_at=excluded.updated_at""",
                (user["id"],profile["registration_type"].strip(),str(profile.get("registration_number", "")).strip(),now,now))
            db.execute("UPDATE user_profiles SET profile_json=?,status='pending',review_reason='',reviewed_by=NULL,reviewed_at=NULL,updated_at=? WHERE user_id=? AND role='RECIPIENT' ",
                       (json.dumps(profile),now,user["id"]))
            db.execute("UPDATE recipients SET available=0,updated_at=? WHERE owner_user_id=?", (now,user["id"]))
            audit(db,user["id"],"organization_application_submitted","organization",user["id"],json.dumps({"document_sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw)}))
            refresh_listed_plans(db,now)
            refresh_active_rescue_risks(db,now)
            result = public_user(db,user["id"],"RECIPIENT")
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return {"user":result,"message":"Organization application submitted. Your account remains unavailable for recipient operations until an administrator approves the profile and certificate."}

@app.get("/api/auth/organization/application-limit")
def organization_application_limit(request: Request):
    actor(request,{"RECIPIENT"},approved=False)
    return {"max_certificate_bytes":max_certificate_bytes(),"allowed_types":["application/pdf","image/jpeg","image/png"]}

def private_document_response(db, user_id: int):
    row = db.execute("SELECT storage_name,original_name,content_type FROM organization_documents WHERE user_id=? AND is_current=1 ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail={"code":"certificate_not_found","message":"No current registration certificate is on file."})
    root = private_upload_directory()
    path = (root / row["storage_name"]).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(404, detail={"code":"certificate_not_found","message":"The stored registration certificate is unavailable."})
    return FileResponse(path, media_type=row["content_type"], filename=row["original_name"], content_disposition_type="inline",
                        headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","Content-Security-Policy":"sandbox"})

@app.get("/api/admin/verifications/{user_id}/document")
def admin_organization_document(user_id: int, request: Request):
    admin = actor(request, {"ADMIN"})
    with connection() as db:
        target = db.execute("SELECT 1 FROM user_profiles WHERE user_id=? AND role='RECIPIENT'", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, detail={"code":"organization_not_found","message":"Organization application not found."})
        audit(db,admin["id"],"organization_certificate_accessed","organization",user_id)
        return private_document_response(db,user_id)

@app.get("/api/auth/organization/document")
def own_organization_document(request: Request):
    user = actor(request, {"RECIPIENT"}, approved=False)
    with connection() as db:
        return private_document_response(db,user["id"])

@app.post("/api/auth/password/forgot")
def password_forgot(body: PasswordResetRequest, request: Request):
    enforce_rate_limit(request_bucket(request,"password-reset"),5,60)
    with connection(immediate=True) as db:
        row=db.execute("SELECT id FROM user_accounts WHERE email=? COLLATE NOCASE",(body.email,)).fetchone()
        token=secrets.token_urlsafe(32)
        if row:
            now=datetime.now()
            db.execute("INSERT INTO password_reset_tokens(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)",
                       (row["id"],digest(token),(now+timedelta(minutes=30)).isoformat(timespec="seconds"),now.isoformat(timespec="seconds")))
            audit(db,row["id"],"password_reset_requested","user",row["id"])
    if row:
        try:
            sent=send_reset_email(body.email,token)
        except (OSError, ValueError, smtplib.SMTPException):
            sent=False
    else:
        sent=False
    result={"message":"If that account exists, reset instructions will be sent."}
    # Explicit local-only escape hatch for development when SMTP is not configured.
    if row and not sent and os.getenv("SURPLUSSYNC_DEV_RESET_TOKEN","").lower() in {"1","true","yes"}:
        result["development_token"]=token
    return result

@app.post("/api/auth/password/reset")
def password_reset(body: PasswordResetConfirm, request: Request):
    enforce_rate_limit(request_bucket(request,"password-reset-confirm"),8,15)
    now=datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        row=db.execute("SELECT t.id,t.user_id FROM password_reset_tokens t JOIN user_accounts u ON u.id=t.user_id WHERE u.email=? COLLATE NOCASE AND t.token_hash=? AND t.used_at IS NULL AND t.expires_at>?",
                       (body.email,digest(body.token),now)).fetchone()
        if not row:
            raise HTTPException(400,detail={"code":"reset_token_invalid","message":"Reset link is invalid or expired. Request a new one."})
        db.execute("UPDATE user_accounts SET password_hash=?,updated_at=? WHERE id=?",(hash_password(body.new_password),now,row["user_id"]))
        db.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",(now,row["user_id"]))
        db.execute("DELETE FROM auth_sessions WHERE user_id=?",(row["user_id"],))
        audit(db,row["user_id"],"password_reset_completed","user",row["user_id"])
    return {"ok":True,"message":"Password changed. Log in with your new password."}

@app.get("/api/admin/verifications")
def verification_queue(request: Request):
    admin=actor(request,{"ADMIN"})
    with connection() as db:
        rows=db.execute("""SELECT u.id,u.email,p.role,p.profile_json,p.status AS profile_status,p.created_at AS profile_created_at,
          ov.registration_type,ov.registration_number,ov.status AS verification_status,
          ov.review_reason,ov.submitted_at,doc.original_name AS certificate_name,
          doc.size_bytes AS certificate_size,doc.content_type AS certificate_type
          FROM user_accounts u JOIN user_profiles p ON p.user_id=u.id
          LEFT JOIN organization_verifications ov ON ov.user_id=u.id
          LEFT JOIN organization_documents doc ON doc.user_id=u.id AND doc.is_current=1
          WHERE p.demo=0 AND (p.status='pending' OR p.role='RECIPIENT' AND ov.status='pending')
          ORDER BY COALESCE(ov.submitted_at,p.created_at)""").fetchall()
        return [{"user_id":r["id"],"email":r["email"],"role":r["role"],"profile":json.loads(r["profile_json"]),
          "verification_status":r["verification_status"] or r["profile_status"],
          "registration_type":r["registration_type"],"registration_number":r["registration_number"],
          "review_reason":r["review_reason"],"certificate_name":r["certificate_name"],"certificate_size":r["certificate_size"],
          "certificate_type":r["certificate_type"],"submitted_at":r["submitted_at"] or r["profile_created_at"]} for r in rows]

@app.patch("/api/admin/verifications/{user_id}")
def review_verification(user_id: int, body: VerificationDecision, request: Request, role: str | None = None):
    admin=actor(request,{"ADMIN"})
    now=datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        if role not in {"DONOR","RECIPIENT","VOLUNTEER"}:
            pending=[item["role"] for item in db.execute("SELECT role FROM user_profiles WHERE user_id=? AND status='pending'",(user_id,)).fetchall()]
            if len(pending)!=1: raise HTTPException(422,detail={"code":"profile_role_required","message":"Select the role profile being reviewed."})
            role=pending[0]
        profile=db.execute("SELECT p.*,p.role,ov.status AS organization_status FROM user_profiles p LEFT JOIN organization_verifications ov ON ov.user_id=p.user_id WHERE p.user_id=? AND p.role=?",(user_id,role)).fetchone()
        if not profile: raise HTTPException(404,detail={"code":"profile_not_found","message":"Reviewable profile not found."})
        if profile["demo"]:
            raise HTTPException(409,detail={"code":"demo_profile_not_reviewable","message":"Fictional presentation profiles are labeled as DEMO and are not official organization approvals."})
        if profile["status"]!="pending": raise HTTPException(409,detail={"code":"profile_already_reviewed","message":"This profile has already been reviewed."})
        if body.decision in {"rejected","resubmission_required"} and not body.reason: raise HTTPException(422,detail={"code":"review_reason_required","message":"A reason is required when rejecting or requesting a resubmission."})
        if body.decision=="resubmission_required" and profile["role"]!="RECIPIENT": raise HTTPException(422,detail={"code":"resubmission_not_supported","message":"Document resubmission applies to recipient organizations only."})
        if profile["role"]=="RECIPIENT" and body.decision=="approved":
            document=db.execute("SELECT id FROM organization_documents WHERE user_id=? AND is_current=1",(user_id,)).fetchone()
            if not profile["organization_status"] or not document:
                raise HTTPException(409,detail={"code":"certificate_required","message":"A current valid registration certificate is required before approving this organization."})
        next_profile_status="approved" if body.decision=="approved" else "rejected"
        db.execute("UPDATE user_profiles SET status=?,review_reason=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE user_id=? AND role=?",
                   (next_profile_status,body.reason,admin["id"],now,now,user_id,role))
        profile_data=json.loads(profile["profile_json"])
        if profile["role"]=="RECIPIENT":
            organization_status=body.decision
            db.execute("UPDATE organization_verifications SET status=?,review_reason=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE user_id=?",
                       (organization_status,body.reason,admin["id"],now,now,user_id))
        if body.decision=="approved" and profile["role"]=="RECIPIENT":
            categories=json.dumps(profile_data["food_categories"])
            existing=db.execute("SELECT id FROM recipients WHERE owner_user_id=?",(user_id,)).fetchone()
            if existing:
                db.execute("UPDATE recipients SET name=?,area=?,capacity=?,food_categories=?,updated_at=? WHERE id=?",
                       (profile_data["organization_name"],profile_data["service_area"],profile_data["capacity"],categories,now,existing["id"]))
            else:
                db.execute("INSERT INTO recipients(name,area,capacity,travel_minutes,available,food_categories,demo,owner_user_id,created_at,updated_at) VALUES(?,?,?,30,1,?,0,?,?,?)",
                           (profile_data["organization_name"],profile_data["service_area"],profile_data["capacity"],categories,user_id,now,now))
            db.execute("UPDATE recipients SET available=1 WHERE owner_user_id=?",(user_id,))
        elif profile["role"]=="RECIPIENT":
            db.execute("UPDATE recipients SET available=0,updated_at=? WHERE owner_user_id=?",(now,user_id))
        audit(db,admin["id"],f"verification_{body.decision}","user",user_id,json.dumps({"reason":body.reason}))
        refresh_listed_plans(db,now)
        return {"user":public_user(db,user_id,role)}

@app.exception_handler(sqlite3.Error)
def database_error(_, exc):
    return JSONResponse(status_code=503, content={"detail":"The database is temporarily unavailable.","code":"database_error"})

try:
    from turso_serverless import DatabaseError as TursoDatabaseError
except ImportError:
    TursoDatabaseError = None
if TursoDatabaseError is not None:
    app.add_exception_handler(TursoDatabaseError, database_error)

@app.get("/api/health")
def health():
    # Health means both the API runtime and its configured durable database work.
    with connection() as db:
        db.execute("SELECT 1").fetchone()
    return {"status":"ok","service":"SurplusSync API"}

@app.post("/api/demo/reset")
def reset_demo(request: Request):
    """Restore fictional demo data while preserving non-demo and audit listings."""
    actor(request,{"ADMIN"})
    return reset_demo_data()

@app.get("/api/recipients")
def list_recipients(request: Request):
    user=actor(request)
    with connection() as db:
        capacities={r["id"]:r["available_capacity"] for r in recipients_for_evaluation(db)}
        result=[]
        for row in db.execute("SELECT * FROM recipients WHERE demo=1 OR owner_user_id IS NOT NULL ORDER BY name"):
            item=recipient_dict(row)
            item["can_manage"] = user["role"]=="ADMIN" or (user["role"]=="RECIPIENT" and row["owner_user_id"]==user["id"])
            item["available_capacity"]=capacities[row["id"]]
            item.pop("owner_user_id",None);item.pop("created_at",None);item.pop("updated_at",None)
            result.append(item)
        return result

@app.patch("/api/recipients/{recipient_id}/availability")
def update_availability(recipient_id: int, body: AvailabilityUpdate, request: Request):
    user=actor(request,{"RECIPIENT","ADMIN"},approved=True)
    now = datetime.now().isoformat(timespec="seconds")
    with connection() as db:
        owner=db.execute("SELECT owner_user_id FROM recipients WHERE id=?",(recipient_id,)).fetchone()
        if not owner: raise HTTPException(404,detail={"code":"recipient_not_found","message":"Recipient not found."})
        if user["role"]!="ADMIN" and owner["owner_user_id"]!=user["id"]:
            raise HTTPException(403,detail={"code":"recipient_forbidden","message":"You may update availability only for your own approved recipient profile."})
        cur = db.execute("UPDATE recipients SET available=?,updated_at=? WHERE id=?", (int(body.available),now,recipient_id))
        if cur.rowcount == 0: raise HTTPException(404, detail={"code":"recipient_not_found","message":"Recipient not found."})
        updated=db.execute("SELECT * FROM recipients WHERE id=?",(recipient_id,)).fetchone()
        item=recipient_dict(updated);item["can_manage"]=True
        item["available_capacity"]=next(r["available_capacity"] for r in recipients_for_evaluation(db) if r["id"]==recipient_id)
        item.pop("owner_user_id",None);item.pop("created_at",None);item.pop("updated_at",None)
        refresh_listed_plans(db,now)
        refresh_active_rescue_risks(db,now)
        return item

@app.post("/api/listings", status_code=201)
def create_listing(body: ListingCreate, request: Request):
    user=actor(request,{"DONOR"},approved=True)
    now = datetime.now()
    if body.deadline <= now: raise HTTPException(422, detail={"code":"past_deadline","message":"Pickup deadline must be in the future using local time."})
    if body.prepared_at and body.prepared_at > now: raise HTTPException(422, detail={"code":"future_preparation","message":"Preparation time cannot be in the future."})
    safety = body.safety.model_dump()
    required_safety_checks = ("handling_verified", "temperature_verified", "packaging_verified", "local_requirements_verified")
    if all(safety[key] for key in required_safety_checks) and not body.safety_verified_by.strip():
        raise HTTPException(422, detail={"code":"missing_safety_verifier","message":"Enter the responsible human verifier's name before submitting all checks as verified."})
    with connection() as db:
        cur = db.execute("""INSERT INTO listings(donor_name,food_type,portions,pickup_area,deadline,prepared_at,
          safety_handling,safety_temperature,safety_allergens,safety_packaging,safety_local_rules,safety_verified_by,donor_user_id,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (body.donor_name,body.food_type,body.portions,body.pickup_area,
          body.deadline.isoformat(),body.prepared_at.isoformat() if body.prepared_at else None,
          int(safety["handling_verified"]),int(safety["temperature_verified"]),int(safety["allergens_verified"]),
          int(safety["packaging_verified"]),int(safety["local_requirements_verified"]),body.safety_verified_by,user["id"],now.isoformat(timespec="seconds")))
        rescue = db.execute("INSERT INTO rescue_cases(listing_id,status,created_at,updated_at) VALUES(?,'listed',?,?)", (cur.lastrowid,now.isoformat(timespec="seconds"),now.isoformat(timespec="seconds")))
        db.execute("INSERT INTO rescue_events(rescue_id,event_type,to_status,created_at) VALUES(?,'listed','listed',?)", (rescue.lastrowid,now.isoformat(timespec="seconds")))
        return listing_by_id(db, cur.lastrowid)

def listing_by_id(db, listing_id):
    row = db.execute("SELECT * FROM listings WHERE id=?",(listing_id,)).fetchone()
    if row is None: return None
    item = dict(row)
    item["audit"] = bool(item["audit"])
    item["demo"] = bool(item["demo"])
    item["safety"] = {"handling_verified":bool(item.pop("safety_handling")),"temperature_verified":bool(item.pop("safety_temperature")),
      "allergens_verified":bool(item.pop("safety_allergens")),"packaging_verified":bool(item.pop("safety_packaging")),
      "local_requirements_verified":bool(item.pop("safety_local_rules"))}
    if item["demo"]:
        # Legacy demo rows may contain synthetic checkboxes set to true. Never
        # expose those values as human verification, and never expose a human's
        # name as the verifier of a fictional fixture.
        item["safety"] = {key: False for key in item["safety"]}
        item["safety_verified_by"] = "DEMO ONLY — no human verification; simulation only"
    return item

def recipients_for_evaluation(db, exclude_rescue_id=None, exclude_owner_user_id=None):
    """Attach capacity remaining after reservations for active rescue cases."""
    recipients=[]
    eligible_sql="""SELECT r.* FROM recipients r WHERE (r.owner_user_id IS NULL OR EXISTS(
      SELECT 1 FROM user_accounts u JOIN user_profiles p ON p.user_id=u.id
      WHERE u.id=r.owner_user_id AND p.role='RECIPIENT' AND u.status='active' AND p.status='approved'))"""
    params=[]
    if exclude_owner_user_id is not None:
        eligible_sql+=" AND (r.owner_user_id IS NULL OR r.owner_user_id<>?)"
        params.append(exclude_owner_user_id)
    eligible_sql+=" ORDER BY r.id"
    for row in db.execute(eligible_sql,params):
        query="SELECT COALESCE(SUM(portions_reserved),0) AS reserved FROM rescue_cases WHERE recipient_id=? AND status IN ('awaiting_confirmation','accepted','ready_for_pickup','collected')"
        params=[row["id"]]
        if exclude_rescue_id is not None:
            query+=" AND id<>?";params.append(exclude_rescue_id)
        reserved=db.execute(query,params).fetchone()["reserved"]
        item=recipient_dict(row)
        item.pop("owner_user_id",None);item.pop("created_at",None);item.pop("updated_at",None)
        item["available_capacity"]=max(0,item["capacity"]-reserved)
        recipients.append(item)
    return recipients

def assert_listing_owner(db, listing_id: int, user: dict) -> None:
    row=db.execute("SELECT donor_user_id FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404,detail={"code":"listing_not_found","message":"Surplus listing not found."})
    if user["role"]!="ADMIN" and row["donor_user_id"]!=user["id"]:
        raise HTTPException(403,detail={"code":"listing_forbidden","message":"You may access only listings owned by your account."})

def assert_rescue_access(db, rescue_id: int, user: dict) -> sqlite3.Row:
    row=db.execute("SELECT rc.*,r.owner_user_id,l.donor_user_id FROM rescue_cases rc JOIN listings l ON l.id=rc.listing_id LEFT JOIN recipients r ON r.id=rc.recipient_id WHERE rc.id=?",(rescue_id,)).fetchone()
    if not row: raise HTTPException(404,detail={"code":"rescue_not_found","message":"Rescue record not found."})
    allowed=(user["role"]=="ADMIN" or
             (user["role"]=="DONOR" and row["donor_user_id"]==user["id"]) or
             (user["role"]=="RECIPIENT" and row["owner_user_id"]==user["id"]) or
             (user["role"]=="VOLUNTEER" and row["volunteer_user_id"]==user["id"]))
    if not allowed: raise HTTPException(403,detail={"code":"rescue_forbidden","message":"This rescue is not assigned to your account."})
    return row

@app.get("/api/listings")
def list_listings(request: Request):
    user=actor(request)
    with connection() as db:
        if user["role"]=="ADMIN":
            query="SELECT id FROM listings ORDER BY id DESC"; params=()
        elif user["role"]=="DONOR":
            query="SELECT id FROM listings WHERE donor_user_id=? ORDER BY id DESC"; params=(user["id"],)
        elif user["role"]=="RECIPIENT":
            # Approved recipients can discover currently listed offers even
            # before a donor proposes them. Incomplete safety checks remain
            # visible in the listing, while the feasibility/offer flow still
            # blocks operational acceptance until required human checks pass.
            query="SELECT DISTINCT l.id FROM listings l JOIN rescue_cases rc ON rc.listing_id=l.id LEFT JOIN recipients r ON r.id=rc.recipient_id WHERE l.audit=0 AND (rc.status='listed' OR r.owner_user_id=?) ORDER BY l.id DESC"; params=(user["id"],)
        else:
            query="SELECT DISTINCT l.id FROM listings l JOIN rescue_cases rc ON rc.listing_id=l.id WHERE rc.volunteer_user_id=? ORDER BY l.id DESC"; params=(user["id"],)
        return [listing_by_id(db,r["id"]) for r in db.execute(query,params)]

@app.patch("/api/listings/{listing_id}")
@app.put("/api/listings/{listing_id}")
def update_listing(listing_id: int, body: ListingCreate, request: Request):
    """Update an unoffered listing through PATCH (or legacy PUT).

    The authenticated owner must submit the complete listing form. This route
    records only the human verification values explicitly submitted by them.
    """
    user=actor(request,{"DONOR"},approved=True)
    now=datetime.now()
    if body.deadline <= now:
        raise HTTPException(422,detail={"code":"past_deadline","message":"Pickup deadline must be in the future using local time."})
    if body.prepared_at and body.prepared_at > now:
        raise HTTPException(422,detail={"code":"future_preparation","message":"Preparation time cannot be in the future."})
    safety=body.safety.model_dump()
    required_safety_checks=("handling_verified","temperature_verified","packaging_verified","local_requirements_verified")
    if all(safety[key] for key in required_safety_checks) and not body.safety_verified_by.strip():
        raise HTTPException(422,detail={"code":"missing_safety_verifier","message":"Enter the responsible human verifier's name before submitting all checks as verified."})
    with connection(immediate=True) as db:
        assert_listing_owner(db,listing_id,user)
        rescue=db.execute("SELECT status FROM rescue_cases WHERE listing_id=?",(listing_id,)).fetchone()
        if rescue and rescue["status"]!="listed":
            raise HTTPException(409,detail={"code":"listing_locked","message":"A listing cannot be edited after a recipient offer or rescue has started."})
        db.execute("""UPDATE listings SET donor_name=?,food_type=?,portions=?,pickup_area=?,deadline=?,prepared_at=?,
          safety_handling=?,safety_temperature=?,safety_allergens=?,safety_packaging=?,safety_local_rules=?,safety_verified_by=?
          WHERE id=?""",(body.donor_name,body.food_type,body.portions,body.pickup_area,body.deadline.isoformat(),
          body.prepared_at.isoformat() if body.prepared_at else None,int(safety["handling_verified"]),
          int(safety["temperature_verified"]),int(safety["allergens_verified"]),int(safety["packaging_verified"]),
          int(safety["local_requirements_verified"]),body.safety_verified_by,listing_id))
        now_text=now.isoformat(timespec="seconds")
        audit(db,user["id"],"listing_updated","listing",listing_id,json.dumps({"fields":["donor_name","food_type","portions","pickup_area","deadline","prepared_at","safety"]}))
        refresh_listed_plans(db,now_text)
        return listing_by_id(db,listing_id)

@app.delete("/api/listings/{listing_id}")
def delete_listing(listing_id: int, request: Request):
    """Permanently remove an owned listing and its dependent rescue history."""
    user=actor(request,{"DONOR"},approved=True)
    with connection(immediate=True) as db:
        assert_listing_owner(db,listing_id,user)
        dependent_counts = {
            "plans": db.execute("SELECT COUNT(*) FROM rescue_plans WHERE listing_id=?",(listing_id,)).fetchone()[0],
            "rescue_cases": db.execute("SELECT COUNT(*) FROM rescue_cases WHERE listing_id=?",(listing_id,)).fetchone()[0],
            "risk_assessments": db.execute("SELECT COUNT(*) FROM rescue_risk_assessments WHERE listing_id=?",(listing_id,)).fetchone()[0],
        }
        audit(db,user["id"],"listing_deleted","listing",listing_id,json.dumps({"cascade_deleted":dependent_counts}))
        db.execute("DELETE FROM listings WHERE id=?",(listing_id,))
        return {"deleted":True,"listing_id":listing_id}

@app.post("/api/listings/{listing_id}/plan", status_code=201)
def create_plan(listing_id: int, request: Request):
    user=actor(request,{"DONOR","ADMIN"})
    if user["role"]=="DONOR" and user["profile_status"]!="approved": actor(request,{"DONOR"},approved=True)
    with connection() as db:
        assert_listing_owner(db,listing_id,user)
        listing = listing_by_id(db,listing_id)
        if not listing: raise HTTPException(404,detail={"code":"listing_not_found","message":"Surplus listing not found."})
        result = evaluate_current(db,listing,rejected_ids(db, listing_id))
        now = datetime.now().isoformat(timespec="seconds")
        return save_plan(db, listing_id, result, now)

def save_plan(db, listing_id, result, now, plan_id=None):
    if plan_id is None:
        cur = db.execute("INSERT INTO rescue_plans(listing_id,recommended_recipient_id,created_at,updated_at) VALUES(?,?,?,?)",
          (listing_id,result["recommended"]["id"] if result["recommended"] else None,now,now))
        plan_id = cur.lastrowid
    else:
        db.execute("UPDATE rescue_plans SET recommended_recipient_id=?,updated_at=? WHERE id=?",
          (result["recommended"]["id"] if result["recommended"] else None,now,plan_id))
        db.execute("DELETE FROM candidate_evaluations WHERE plan_id=?",(plan_id,))
    for candidate in result["feasible_candidates"] + result["rejected_candidates"]:
        db.execute("INSERT INTO candidate_evaluations(plan_id,recipient_id,feasible,reasons,travel_minutes,capacity_after,rank,created_at) VALUES(?,?,?,?,?,?,?,?)",
          (plan_id,candidate["id"],int(candidate["feasible"]),json.dumps(candidate.get("reasons",[])),candidate["travel_minutes"],candidate["capacity_after"],candidate.get("rank"),now))
    rescue=db.execute("SELECT id FROM rescue_cases WHERE listing_id=?",(listing_id,)).fetchone()
    persist_risk(db,listing_id,result,now,plan_id,rescue["id"] if rescue else None)
    return {"id":plan_id,"listing_id":listing_id,"created_at":now,"updated_at":now,**result}

@app.get("/api/listings/{listing_id}/plans/latest")
def latest_plan(listing_id: int, request: Request):
    user=actor(request,{"DONOR","ADMIN"})
    with connection() as db:
        assert_listing_owner(db,listing_id,user)
        if not db.execute("SELECT 1 FROM listings WHERE id=?",(listing_id,)).fetchone():
            raise HTTPException(404,detail={"code":"listing_not_found","message":"Surplus listing not found."})
        row = db.execute("SELECT id FROM rescue_plans WHERE listing_id=? ORDER BY id DESC LIMIT 1",(listing_id,)).fetchone()
        if not row: return {"plan": None}
        plan_id = row["id"]
    return {"plan": get_plan(plan_id,request)}

@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: int, request: Request):
    user=actor(request,{"DONOR","ADMIN"})
    with connection() as db:
        plan = db.execute("SELECT * FROM rescue_plans WHERE id=?",(plan_id,)).fetchone()
        if not plan: raise HTTPException(404,detail={"code":"plan_not_found","message":"Rescue plan not found."})
        assert_listing_owner(db,plan["listing_id"],user)
        listing = listing_by_id(db,plan["listing_id"])
        excluded = rejected_ids(db, plan["listing_id"])
        result = evaluate_current(db,listing,excluded)
    # Read returns an up-to-date explanation; POST /recalculate stores a snapshot.
    return {"id":plan_id,"listing_id":plan["listing_id"],"created_at":plan["created_at"],"updated_at":plan["updated_at"],**result}

@app.post("/api/plans/{plan_id}/recalculate")
def recalculate_plan(plan_id: int, request: Request):
    user=actor(request,{"DONOR","ADMIN"})
    with connection() as db:
        plan = db.execute("SELECT * FROM rescue_plans WHERE id=?",(plan_id,)).fetchone()
        if not plan: raise HTTPException(404,detail={"code":"plan_not_found","message":"Rescue plan not found."})
        assert_listing_owner(db,plan["listing_id"],user)
        listing = listing_by_id(db,plan["listing_id"])
        result = evaluate_current(db,listing,rejected_ids(db, plan["listing_id"]))
        now = datetime.now().isoformat(timespec="seconds")
        return save_plan(db, plan["listing_id"], result, now, plan_id)

def rescue_payload(db, rescue_id):
    row = db.execute("""SELECT rc.*,l.donor_name,l.food_type,l.portions,l.pickup_area,l.deadline,l.audit,l.demo,
      r.name AS recipient_name,r.area AS recipient_area
      FROM rescue_cases rc JOIN listings l ON l.id=rc.listing_id
      LEFT JOIN recipients r ON r.id=rc.recipient_id WHERE rc.id=?""", (rescue_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    events = db.execute("SELECT * FROM rescue_events WHERE rescue_id=? ORDER BY id", (rescue_id,)).fetchall()
    item["timeline"] = [dict(event) for event in events]
    risk=db.execute("SELECT category,score,reasons,alternative_recipient_ids,volunteer_available_count,assessed_at FROM rescue_risk_assessments WHERE rescue_id=? ORDER BY id DESC LIMIT 1",(rescue_id,)).fetchone()
    if risk:
        item["risk_assessment"]={"category":risk["category"],"score":risk["score"],"reasons":json.loads(risk["reasons"]),
            "alternative_recipient_ids":json.loads(risk["alternative_recipient_ids"]),"volunteer_available_count":risk["volunteer_available_count"],"assessed_at":risk["assessed_at"],
            "method":"Transparent rule-based assessment; not a trained AI model. Travel estimates are simulated."}
    else:
        item["risk_assessment"]=None
    item["selected_recipient"] = None if item["recipient_id"] is None else {"id":item["recipient_id"],"name":item.pop("recipient_name"),"area":item.pop("recipient_area")}
    if item["recipient_id"] is None:
        item.pop("recipient_name", None); item.pop("recipient_area", None)
    item["audit"] = bool(item["audit"]); item["demo"] = bool(item["demo"])
    item["simulation_only"] = item["demo"]
    return item

def rejected_ids(db, listing_id):
    return {row["recipient_id"] for row in db.execute("SELECT DISTINCT recipient_id FROM rescue_events WHERE event_type='recipient_rejected' AND recipient_id IS NOT NULL AND rescue_id=(SELECT id FROM rescue_cases WHERE listing_id=?)", (listing_id,))}

@app.get("/api/rescues")
def list_rescues(request: Request):
    user=actor(request)
    with connection() as db:
        where=""
        params=()
        if user["role"]=="DONOR": where=" WHERE l.donor_user_id=?"; params=(user["id"],)
        elif user["role"]=="RECIPIENT": where=" JOIN recipients r ON r.id=rc.recipient_id WHERE r.owner_user_id=?"; params=(user["id"],)
        elif user["role"]=="VOLUNTEER": where=" WHERE rc.volunteer_user_id=?"; params=(user["id"],)
        query="SELECT rc.id FROM rescue_cases rc JOIN listings l ON l.id=rc.listing_id"+where+" ORDER BY rc.updated_at DESC,rc.id DESC"
        ids = [row["id"] for row in db.execute(query,params)]
        return [rescue_payload(db, rescue_id) for rescue_id in ids]

@app.get("/api/rescues/{rescue_id}")
def get_rescue(rescue_id: int, request: Request):
    user=actor(request)
    with connection() as db:
        assert_rescue_access(db,rescue_id,user)
        result = rescue_payload(db, rescue_id)
        if result is None: raise HTTPException(404, detail={"code":"rescue_not_found","message":"Rescue record not found."})
        return result

@app.get("/api/dashboard/metrics")
def dashboard_metrics(request: Request):
    """Disjoint portion totals by recorded lifecycle state; proposals are not outcomes."""
    user=actor(request)
    with connection() as db:
        sql="""SELECT rc.status, SUM(l.portions) AS portions, COUNT(*) AS listings
          FROM rescue_cases rc JOIN listings l ON l.id=rc.listing_id WHERE l.audit=0"""
        params=()
        if user["role"]=="DONOR": sql+=" AND l.donor_user_id=?"; params=(user["id"],)
        elif user["role"]=="RECIPIENT": sql+=" AND rc.recipient_id IN (SELECT id FROM recipients WHERE owner_user_id=?)"; params=(user["id"],)
        elif user["role"]=="VOLUNTEER": sql+=" AND rc.volunteer_user_id=?"; params=(user["id"],)
        sql+=" GROUP BY rc.status"
        rows = db.execute(sql,params).fetchall()
    by_status = {row["status"]:{"portions":row["portions"] or 0,"listings":row["listings"]} for row in rows}
    def bucket(*statuses):
        return {"portions":sum(by_status.get(status,{}).get("portions",0) for status in statuses),"listings":sum(by_status.get(status,{}).get("listings",0) for status in statuses)}
    return {"listed":bucket("listed"),"awaiting_confirmation":bucket("awaiting_confirmation"),
      "accepted":bucket("accepted","ready_for_pickup"),"collected":bucket("collected"),
      "delivered":bucket("delivered"),"cancelled":bucket("cancelled"),
      "definition":"Proposed offers are awaiting confirmation and are not counted as accepted, collected or delivered."}

@app.post("/api/listings/{listing_id}/rescue/propose", status_code=201)
def propose_rescue(listing_id: int, request: Request, body: RescueProposal | None = None):
    """Create a single live offer, rechecking current feasibility inside a write lock."""
    user=actor(request,{"DONOR"},approved=True)
    now = datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        assert_listing_owner(db,listing_id,user)
        listing = listing_by_id(db, listing_id)
        if listing is None: raise HTTPException(404, detail={"code":"listing_not_found","message":"Surplus listing not found."})
        if listing["audit"]: raise HTTPException(409, detail={"code":"audit_listing","message":"Audit/test listings cannot be offered to recipients."})
        rescue = db.execute("SELECT * FROM rescue_cases WHERE listing_id=?", (listing_id,)).fetchone()
        if rescue is None: raise HTTPException(409, detail={"code":"missing_rescue_case","message":"Lifecycle record is missing; refresh or contact support."})
        if rescue["status"] != "listed": raise HTTPException(409, detail={"code":"rescue_already_active","message":"This listing already has an active or terminal rescue record."})
        recs = recipients_for_evaluation(db)
        result = evaluate(listing, recs, rejected_ids(db, listing_id),available_volunteer_count(db))
        requested_id = body.recipient_id if body else None
        candidate = next((c for c in result["feasible_candidates"] if requested_id is None or c["id"] == requested_id), None)
        if candidate is None:
            if requested_id is not None:
                rejected = next((c for c in result["rejected_candidates"] if c["id"] == requested_id), None)
                reasons = rejected["reasons"] if rejected else ["Recipient is not eligible for this offer or has already rejected it."]
                raise HTTPException(409, detail={"code":"recipient_ineligible","message":"Recipient cannot be offered this listing.","reasons":reasons})
            raise HTTPException(409, detail={"code":"no_feasible_recipient","message":"No eligible recipient can receive this listing right now.","reasons":[c for row in result["rejected_candidates"] for c in row["reasons"]]})
        cur = db.execute("UPDATE rescue_cases SET recipient_id=?,portions_reserved=?,status='awaiting_confirmation',rejection_reason='',updated_at=? WHERE id=? AND status='listed'", (candidate["id"],listing["portions"],now,rescue["id"]))
        if cur.rowcount != 1: raise HTTPException(409, detail={"code":"rescue_already_active","message":"Another offer was created for this listing."})
        db.execute("INSERT INTO rescue_events(rescue_id,event_type,from_status,to_status,recipient_id,created_at) VALUES(?,'offer_sent','listed','awaiting_confirmation',?,?)", (rescue["id"],candidate["id"],now))
        save_plan(db, listing_id, result, now)
        audit(db,user["id"],"rescue_offer_created","rescue",rescue["id"],json.dumps({"recipient_id":candidate["id"]}))
        return rescue_payload(db, rescue["id"])

@app.post("/api/rescues/{rescue_id}/accept")
def accept_rescue(rescue_id: int, body: RescueDecision, request: Request):
    user=actor(request,{"RECIPIENT"},approved=True)
    now = datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        rescue = db.execute("SELECT * FROM rescue_cases WHERE id=?", (rescue_id,)).fetchone()
        if rescue is None: raise HTTPException(404, detail={"code":"rescue_not_found","message":"Rescue record not found."})
        recipient=db.execute("SELECT owner_user_id FROM recipients WHERE id=?",(rescue["recipient_id"],)).fetchone()
        if not recipient or recipient["owner_user_id"]!=user["id"]: raise HTTPException(403,detail={"code":"recipient_mismatch","message":"Only the proposed recipient can accept this offer."})
        if rescue["status"] != "awaiting_confirmation": raise HTTPException(409, detail={"code":"invalid_transition","message":"Only an awaiting offer can be accepted."})
        if body.recipient_id != rescue["recipient_id"]: raise HTTPException(403, detail={"code":"recipient_mismatch","message":"Only the proposed recipient can accept this offer."})
        listing = listing_by_id(db, rescue["listing_id"])
        recipients = recipients_for_evaluation(db,exclude_rescue_id=rescue_id)
        current = evaluate(listing, recipients, volunteer_available_count=available_volunteer_count(db))
        if not any(c["id"] == body.recipient_id for c in current["feasible_candidates"]):
            candidate = next((c for c in current["rejected_candidates"] if c["id"] == body.recipient_id), None)
            raise HTTPException(409, detail={"code":"recipient_no_longer_eligible","message":"Recipient eligibility changed; the offer cannot be accepted.","reasons":candidate["reasons"] if candidate else ["Recipient is no longer eligible."]})
        db.execute("UPDATE rescue_cases SET status='accepted',accepted_at=?,updated_at=? WHERE id=?", (now,now,rescue_id))
        db.execute("INSERT INTO rescue_events(rescue_id,event_type,from_status,to_status,recipient_id,created_at) VALUES(?,'accepted','awaiting_confirmation','accepted',?,?)", (rescue_id,body.recipient_id,now))
        audit(db,user["id"],"rescue_accepted","rescue",rescue_id)
        refresh_active_rescue_risks(db,now)
        return rescue_payload(db, rescue_id)

@app.post("/api/rescues/{rescue_id}/reject")
def reject_rescue(rescue_id: int, body: RescueDecision, request: Request):
    user=actor(request,{"RECIPIENT"},approved=True)
    if not body.reason: raise HTTPException(422, detail={"code":"rejection_reason_required","message":"Please provide a reason for rejecting this offer."})
    now = datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        rescue = db.execute("SELECT * FROM rescue_cases WHERE id=?", (rescue_id,)).fetchone()
        if rescue is None: raise HTTPException(404, detail={"code":"rescue_not_found","message":"Rescue record not found."})
        recipient=db.execute("SELECT owner_user_id FROM recipients WHERE id=?",(rescue["recipient_id"],)).fetchone()
        if not recipient or recipient["owner_user_id"]!=user["id"]: raise HTTPException(403,detail={"code":"recipient_mismatch","message":"Only the proposed recipient can reject this offer."})
        if rescue["status"] != "awaiting_confirmation": raise HTTPException(409, detail={"code":"invalid_transition","message":"Only an awaiting offer can be rejected."})
        if body.recipient_id != rescue["recipient_id"]: raise HTTPException(403, detail={"code":"recipient_mismatch","message":"Only the proposed recipient can reject this offer."})
        db.execute("UPDATE rescue_cases SET recipient_id=NULL,portions_reserved=0,status='listed',rejection_reason=?,updated_at=? WHERE id=?", (body.reason,now,rescue_id))
        db.execute("INSERT INTO rescue_events(rescue_id,event_type,from_status,to_status,recipient_id,reason,created_at) VALUES(?,'recipient_rejected','awaiting_confirmation','listed',?,?,?)", (rescue_id,body.recipient_id,body.reason,now))
        audit(db,user["id"],"rescue_rejected","rescue",rescue_id,json.dumps({"reason":body.reason}))
        listing = listing_by_id(db, rescue["listing_id"])
        recipients = recipients_for_evaluation(db)
        alternative = evaluate(listing, recipients, rejected_ids(db, rescue["listing_id"]),available_volunteer_count(db))
        plan=db.execute("SELECT id FROM rescue_plans WHERE listing_id=? ORDER BY id DESC LIMIT 1",(rescue["listing_id"],)).fetchone()
        save_plan(db,rescue["listing_id"],alternative,now,plan["id"] if plan else None)
        result = rescue_payload(db, rescue_id)
        result["alternative_recommendation"] = alternative["recommended"]
        result["rejected_candidates"] = alternative["rejected_candidates"]
        return result

@app.patch("/api/rescues/{rescue_id}/status")
def transition_rescue(rescue_id: int, body: RescueTransition, request: Request):
    user=actor(request,{"DONOR","RECIPIENT","VOLUNTEER","ADMIN"})
    transitions = {"listed":{"cancelled"},"accepted":{"ready_for_pickup"},
      "ready_for_pickup":{"collected"},"collected":{"delivered"}}
    now = datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        rescue = db.execute("SELECT * FROM rescue_cases WHERE id=?", (rescue_id,)).fetchone()
        if rescue is None: raise HTTPException(404, detail={"code":"rescue_not_found","message":"Rescue record not found."})
        access=assert_rescue_access(db,rescue_id,user)
        if user["role"]=="DONOR" and body.status not in {"ready_for_pickup","cancelled"}: raise HTTPException(403,detail={"code":"role_forbidden","message":"Donors may mark an accepted rescue ready for pickup or cancel their own rescue."})
        if user["role"]=="RECIPIENT": raise HTTPException(403,detail={"code":"role_forbidden","message":"Use the recipient accept or reject action; pickup and delivery updates are not available to recipient accounts."})
        if user["role"]=="VOLUNTEER" and body.status not in {"collected","delivered"}: raise HTTPException(403,detail={"code":"role_forbidden","message":"Volunteers may record collection or delivery only for assigned rescues."})
        allowed = transitions.get(rescue["status"], set())
        if body.status == "cancelled" and rescue["status"] in {"awaiting_confirmation","accepted","ready_for_pickup"}:
            allowed = {"cancelled"}
        if body.status not in allowed: raise HTTPException(409, detail={"code":"invalid_transition","message":f"Cannot move a {rescue['status'].replace('_',' ')} rescue to {body.status.replace('_',' ')}."})
        fields = {"ready_for_pickup":"ready_for_pickup_at","collected":"collected_at","delivered":"delivered_at","cancelled":"cancelled_at"}
        pickup_notes = rescue["pickup_notes"] if body.pickup_notes is None else body.pickup_notes
        delivery_notes = rescue["delivery_notes"] if body.delivery_notes is None else body.delivery_notes
        db.execute(f"UPDATE rescue_cases SET status=?,{fields[body.status]}=?,pickup_notes=?,delivery_notes=?,updated_at=? WHERE id=?", (body.status,now,pickup_notes,delivery_notes,now,rescue_id))
        db.execute("INSERT INTO rescue_events(rescue_id,event_type,from_status,to_status,recipient_id,notes,created_at) VALUES(?,'status_changed',?,?,?,?,?)", (rescue_id,rescue["status"],body.status,rescue["recipient_id"],body.delivery_notes or body.pickup_notes or "",now))
        audit(db,user["id"],"rescue_status_changed","rescue",rescue_id,json.dumps({"from":rescue["status"],"to":body.status}))
        if body.status in {"delivered","cancelled"}:
            listing=listing_by_id(db,rescue["listing_id"])
            if listing and listing["demo"]:
                # Keep the demo's computed simulation and unverified-safety
                # disclosure; terminal status must not turn its risk score Low.
                result=evaluate_current(db,listing,rejected_ids(db,rescue["listing_id"]))
                persist_risk(db,rescue["listing_id"],result,now,rescue_id=rescue_id)
            else:
                db.execute("UPDATE rescue_risk_assessments SET category='Low',score=0,reasons=?,alternative_recipient_ids='[]',assessed_at=? WHERE id=(SELECT MAX(id) FROM rescue_risk_assessments WHERE rescue_id=?)",
                    (json.dumps([f"Rescue status is {body.status}; no active pickup risk remains."]),now,rescue_id))
                if db.execute("SELECT changes()").fetchone()[0] == 0:
                    result=evaluate_current(db,listing,rejected_ids(db,rescue["listing_id"]))
                    result["risk_assessment"]={**result["risk_assessment"],"category":"Low","score":0,"reasons":[f"Rescue status is {body.status}; no active pickup risk remains."],"alternative_recipient_ids":[]}
                    persist_risk(db,rescue["listing_id"],result,now,rescue_id=rescue_id)
        else:
            refresh_active_rescue_risks(db,now)
        return rescue_payload(db, rescue_id)

@app.post("/api/rescues/{rescue_id}/volunteer")
def assign_volunteer(rescue_id: int, body: VolunteerAssignment, request: Request):
    user=actor(request,{"DONOR","ADMIN"},approved=user_role_is_donor(request))
    now=datetime.now().isoformat(timespec="seconds")
    with connection(immediate=True) as db:
        rescue=assert_rescue_access(db,rescue_id,user)
        volunteer=db.execute("SELECT u.id,p.profile_json FROM user_accounts u JOIN user_profiles p ON p.user_id=u.id WHERE u.id=? AND p.role='VOLUNTEER' AND u.status='active' AND p.status='approved'",(body.volunteer_user_id,)).fetchone()
        if not volunteer or not volunteer_profile_available(volunteer["profile_json"]): raise HTTPException(409,detail={"code":"volunteer_ineligible","message":"Only an approved volunteer with a usable availability profile can be assigned."})
        if rescue["status"] not in {"accepted","ready_for_pickup"}: raise HTTPException(409,detail={"code":"invalid_assignment_status","message":"A volunteer can be assigned after an offer is accepted and before delivery."})
        db.execute("UPDATE rescue_cases SET volunteer_user_id=?,updated_at=? WHERE id=?",(body.volunteer_user_id,now,rescue_id))
        db.execute("INSERT INTO rescue_events(rescue_id,event_type,to_status,reason,created_at) VALUES(?,'volunteer_assigned',?,'Volunteer assigned by an authorized user.',?)",(rescue_id,rescue["status"],now))
        audit(db,user["id"],"volunteer_assigned","rescue",rescue_id,json.dumps({"volunteer_user_id":body.volunteer_user_id}))
        refresh_active_rescue_risks(db,now)
        return rescue_payload(db,rescue_id)

@app.get("/api/volunteers")
def list_approved_volunteers(request: Request):
    actor(request,{"DONOR","ADMIN"},approved=user_role_is_donor(request))
    with connection() as db:
        rows=db.execute("SELECT u.id,u.email,p.profile_json FROM user_accounts u JOIN user_profiles p ON p.user_id=u.id WHERE p.role='VOLUNTEER' AND u.status='active' AND p.status='approved' ORDER BY u.id").fetchall()
        return [{"user_id":row["id"],"email":row["email"],"service_area":json.loads(row["profile_json"]).get("service_area",""),"availability":json.loads(row["profile_json"]).get("availability","")} for row in rows if volunteer_profile_available(row["profile_json"])]

# In production, FastAPI serves the separately built Vite app from the same
# origin. Local development still uses the independent Vite dev server.
frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if (frontend_dist / "index.html").is_file() and (frontend_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    def frontend_index():
        return FileResponse(frontend_dist / "index.html")
