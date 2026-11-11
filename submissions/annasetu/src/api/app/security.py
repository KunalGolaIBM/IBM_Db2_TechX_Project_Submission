import base64
import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone


_EMAIL_LOCAL_ATOM = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
_EMAIL_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_EMAIL_RE = re.compile(rf"{_EMAIL_LOCAL_ATOM}(?:\.{_EMAIL_LOCAL_ATOM})*@{_EMAIL_LABEL}(?:\.{_EMAIL_LABEL})+\Z")


def normalize_email(value: str) -> str:
    """Return a canonical ASCII mailbox address or reject malformed input."""
    if not isinstance(value, str):
        raise ValueError("Enter a valid email address.")
    email = value.strip().casefold()
    if len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    local, domain = email.rsplit("@", 1)
    labels = domain.split(".")
    if len(local.encode("ascii")) > 64 or len(domain) > 253:
        raise ValueError("Enter a valid email address.")
    if any(len(label) > 63 for label in labels):
        raise ValueError("Enter a valid email address.")
    top_level = labels[-1]
    if not (re.fullmatch(r"[a-z]{2,}", top_level) or re.fullmatch(r"xn--[a-z0-9-]{2,}", top_level)):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(password: str) -> str:
    """Apply the same minimum complexity policy to every authentication flow."""
    if not isinstance(password, str) or not 6 <= len(password) <= 128:
        raise ValueError("Password must be between 6 and 128 characters.")
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("Password must contain at least one letter.")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one number.")
    if not re.search(r"[^A-Za-z0-9\s]", password):
        raise ValueError("Password must contain at least one special character.")
    return password

def password_hash(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def password_matches(password: str, stored: str) -> bool:
    try:
        scheme, salt_text, digest_text = stored.split("$", 2)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(user: dict) -> str:
    import jwt
    from .config import settings

    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user["user_id"].strip(), "email": user.get("email", ""), "name": user["display_name"],
         "role": user["role"], "exp": expires},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_token(token: str) -> dict:
    import jwt
    from .config import settings

    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
