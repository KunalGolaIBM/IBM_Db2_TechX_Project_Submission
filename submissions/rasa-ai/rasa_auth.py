"""Local-first account and email-OTP authentication for RASA AI.

Passwords are PBKDF2-HMAC-SHA256 hashes. OTPs are hashed at rest and expire.
The SQLite account database and each user's data directory stay on this machine.
Configure RASA_SMTP_EMAIL and RASA_SMTP_APP_PASSWORD (Gmail App Password)
to enable email delivery.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import smtplib
import sqlite3
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "rasaai_private_data"
DB_PATH = ROOT / "auth.sqlite3"
USERS_DIR = ROOT / "users"
OTP_TTL_SECONDS = 10 * 60
PBKDF2_ROUNDS = 310_000


def _setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def _connect():
    ROOT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_otps (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            purpose TEXT NOT NULL,
            otp_salt TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            password_salt TEXT,
            password_hash TEXT
        )
    """)
    conn.commit()
    return conn


def _password_hash(password: str, salt: bytes | None = None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()


def _verify_password(password: str, salt_hex: str, expected_hex: str) -> bool:
    _, actual = _password_hash(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(actual, expected_hex)


def _send_otp(email: str, otp: str, purpose: str):
    sender = _setting("RASA_SMTP_EMAIL") or _setting("GMAIL_ADDRESS") or _setting("SMTP_EMAIL")
    app_password = (
        _setting("RASA_SMTP_APP_PASSWORD")
        or _setting("GMAIL_APP_PASSWORD")
        or _setting("SMTP_APP_PASSWORD")
    )
    if not sender or not app_password:
        raise RuntimeError(
            "Email OTP is not configured. Add RASA_SMTP_EMAIL and "
            "RASA_SMTP_APP_PASSWORD to Streamlit secrets (use a Gmail App Password)."
        )
    message = EmailMessage()
    message["Subject"] = "Your RASA AI verification code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Your RASA AI {purpose} verification code is {otp}.\n\n"
        f"It expires in 10 minutes. If you did not request this, ignore this email."
    )
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(sender, app_password)
        server.send_message(message)


def begin_registration(email: str, password: str):
    email = email.strip().lower()
    if not email or "@" not in email or not email.endswith("@gmail.com"):
        raise ValueError("Enter a valid Gmail address.")
    if len(password) < 12:
        raise ValueError("Use a unique password with at least 12 characters.")
    conn = _connect()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError("An account already exists for this Gmail address. Sign in instead.")
        salt, password_digest = _password_hash(password)
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_salt = secrets.token_bytes(16)
        otp_digest = hashlib.pbkdf2_hmac("sha256", otp.encode(), otp_salt, 120_000).hex()
        conn.execute(
            "INSERT OR REPLACE INTO pending_otps "
            "(email,purpose,otp_salt,otp_hash,expires_at,password_salt,password_hash) "
            "VALUES (?,?,?,?,?,?,?)",
            (email, "registration", otp_salt.hex(), otp_digest,
             int(time.time()) + OTP_TTL_SECONDS, salt, password_digest),
        )
        conn.commit()
        _send_otp(email, otp, "registration")
    except Exception:
        conn.close()
        raise
    conn.close()


def verify_registration(email: str, otp: str):
    email = email.strip().lower()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM pending_otps WHERE email=? AND purpose='registration'", (email,)
        ).fetchone()
        if not row:
            raise ValueError("No pending registration was found. Request a new code.")
        if int(time.time()) > row["expires_at"]:
            conn.execute("DELETE FROM pending_otps WHERE email=?", (email,))
            conn.commit()
            raise ValueError("The code has expired. Start registration again.")
        digest = hashlib.pbkdf2_hmac(
            "sha256", otp.strip().encode(), bytes.fromhex(row["otp_salt"]), 120_000
        ).hex()
        if not hmac.compare_digest(digest, row["otp_hash"]):
            raise ValueError("Incorrect verification code.")
        user_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO users(user_id,email,password_salt,password_hash,created_at) VALUES(?,?,?,?,?)",
            (user_id, email, row["password_salt"], row["password_hash"], int(time.time())),
        )
        conn.execute("DELETE FROM pending_otps WHERE email=?", (email,))
        conn.commit()
        (USERS_DIR / user_id).mkdir(parents=True, exist_ok=True)
        return {"user_id": user_id, "email": email}
    finally:
        conn.close()


def authenticate(email: str, password: str):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not row or not _verify_password(password, row["password_salt"], row["password_hash"]):
            return None
        return {"user_id": row["user_id"], "email": row["email"]}
    finally:
        conn.close()


def begin_password_reset(email: str):
    email = email.strip().lower()
    conn = _connect()
    try:
        user = conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
        if not user:
            raise ValueError("No account was found for that Gmail address.")
        otp = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", otp.encode(), salt, 120_000).hex()
        conn.execute(
            "INSERT OR REPLACE INTO pending_otps "
            "(email,purpose,otp_salt,otp_hash,expires_at,password_salt,password_hash) "
            "VALUES(?,?,?,?,?,NULL,NULL)",
            (email, "reset", salt.hex(), digest, int(time.time()) + OTP_TTL_SECONDS),
        )
        conn.commit()
        _send_otp(email, otp, "password reset")
    finally:
        conn.close()


def finish_password_reset(email: str, otp: str, new_password: str):
    if len(new_password) < 12:
        raise ValueError("Use a unique password with at least 12 characters.")
    email = email.strip().lower()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM pending_otps WHERE email=? AND purpose='reset'", (email,)
        ).fetchone()
        if not row or int(time.time()) > row["expires_at"]:
            raise ValueError("The reset code is missing or expired. Request a new one.")
        digest = hashlib.pbkdf2_hmac(
            "sha256", otp.strip().encode(), bytes.fromhex(row["otp_salt"]), 120_000
        ).hex()
        if not hmac.compare_digest(digest, row["otp_hash"]):
            raise ValueError("Incorrect verification code.")
        salt, password_digest = _password_hash(new_password)
        conn.execute(
            "UPDATE users SET password_salt=?, password_hash=? WHERE email=?",
            (salt, password_digest, email),
        )
        conn.execute("DELETE FROM pending_otps WHERE email=?", (email,))
        conn.commit()
    finally:
        conn.close()
