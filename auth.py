from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header
from pydantic import BaseModel, EmailStr, Field
from pathlib import Path
import sqlite3, secrets, hashlib, hmac, os, re
from datetime import datetime, timezone

router = APIRouter()
BASE = Path(__file__).resolve().parent
DB = BASE / "digital_suraksha.db"
UPLOADS = BASE / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, mobile TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, photo TEXT, created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
init_db()

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return salt.hex() + "$" + digest.hex()

def verify_password(password: str, saved: str) -> bool:
    try:
        salt_hex, digest_hex = saved.split("$", 1)
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 310000).hex()
        return hmac.compare_digest(calculated, digest_hex)
    except Exception:
        return False

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(
    name: str = Form(...), mobile: str = Form(...), email: str = Form(...),
    password: str = Form(...), confirm_password: str = Form(...),
    profile_photo: UploadFile | None = File(None)
):
    name, mobile, email = name.strip(), mobile.strip(), email.strip().lower()
    if len(name) < 2:
        raise HTTPException(400, "Please enter your full name.")
    if not re.fullmatch(r"[6-9]\d{9}", mobile):
        raise HTTPException(400, "Enter a valid 10-digit Indian mobile number.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Enter a valid email address.")
    if len(password) < 10 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(400, "Password must be at least 10 characters and include letters and numbers.")
    if password != confirm_password:
        raise HTTPException(400, "Password and confirmation do not match.")
    photo_path = None
    if profile_photo and profile_photo.filename:
        content = await profile_photo.read(2 * 1024 * 1024 + 1)
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(413, "Profile photo must be 2 MB or smaller.")
        ext = Path(profile_photo.filename).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(415, "Profile photo must be JPG, PNG, or WEBP.")
        filename = secrets.token_hex(12) + ext
        path = UPLOADS / filename
        path.write_bytes(content)
        photo_path = "/static/uploads/" + filename
    try:
        with connect() as con:
            con.execute("INSERT INTO users(name,mobile,email,password_hash,photo,created_at) VALUES(?,?,?,?,?,?)",
                (name, mobile, email, hash_password(password), photo_path, datetime.now(timezone.utc).isoformat()))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This mobile number or email is already registered.")
    return {"status": "created", "message": "Registration successful. You can now log in.", "otp_verification": "not configured"}

@router.post("/login")
async def login(body: LoginRequest):
    with connect() as con:
        user = con.execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),)).fetchone()
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Invalid email or password.")
        token = secrets.token_urlsafe(32)
        con.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)",
            (token, user["id"], datetime.now(timezone.utc).isoformat()))
    return {"status": "success", "token": token, "user": {
        "id": user["id"], "name": user["name"], "mobile": user["mobile"],
        "email": user["email"], "photo": user["photo"]
    }}

@router.get("/me")
async def me(authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(401, "Provide Authorization: Bearer <token>.")
    token = authorization.removeprefix("Bearer ").strip()
    with connect() as con:
        row = con.execute("""SELECT u.id,u.name,u.mobile,u.email,u.photo FROM users u
            JOIN sessions s ON s.user_id=u.id WHERE s.token=?""", (token,)).fetchone()
    if not row:
        raise HTTPException(401, "Invalid session.")
    return dict(row)

@router.post("/logout")
async def logout(authorization: str | None = Header(default=None)):
    if not authorization:
        return {"status": "success"}
    token = authorization.removeprefix("Bearer ").strip()
    with connect() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))
    return {"status": "success"}
