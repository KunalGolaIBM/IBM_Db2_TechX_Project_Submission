"""Password hashing (bcrypt) and access tokens (HS256 JWT)."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from backend.app.core.config import settings

BCRYPT_ROUNDS = 12


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash in storage: treat as a failed login rather than a server error.
        return False


# Hash of a random string, compared against when an email does not exist so that
# login takes the same time for unknown and known accounts (no user enumeration by timing).
DUMMY_PASSWORD_HASH = get_password_hash("nsin-timing-equaliser")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    claims = {**data, "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Return the token claims, or None if the signature, algorithm or expiry check fails."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
