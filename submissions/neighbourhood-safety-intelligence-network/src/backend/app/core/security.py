import os
import hmac
import hashlib
import base64
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from backend.app.core.config import settings

def _hash_password_fallback(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"pbkdf2:{salt}:{key.hex()}"

def _verify_password_fallback(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or not hashed_password.startswith("pbkdf2:"):
        return False
    parts = hashed_password.split(":")
    if len(parts) != 3:
        return False
    salt = parts[1]
    expected_hex = parts[2]
    key = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return hmac.compare_digest(key.hex(), expected_hex)

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    def get_password_hash(password: str) -> str:
        try:
            return pwd_context.hash(password)
        except Exception:
            return _hash_password_fallback(password)

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if hashed_password.startswith("pbkdf2:"):
            return _verify_password_fallback(plain_password, hashed_password)
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return _verify_password_fallback(plain_password, hashed_password)
except Exception:
    def get_password_hash(password: str) -> str:
        return _hash_password_fallback(password)

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return _verify_password_fallback(plain_password, hashed_password)

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def _b64url_decode(data_str: str) -> bytes:
    padding = '=' * (4 - len(data_str) % 4) if len(data_str) % 4 != 0 else ''
    return base64.urlsafe_b64decode((data_str + padding).encode('utf-8'))

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp()), "iat": int(time.time())})
    
    try:
        from jose import jwt
        return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    except Exception:
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = _b64url_encode(json.dumps(header).encode('utf-8'))
        payload_b64 = _b64url_encode(json.dumps(to_encode).encode('utf-8'))
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        signature = hmac.new(settings.JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        signature_b64 = _b64url_encode(signature)
        return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        from jose import jwt
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, payload_b64, signature_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
            expected_sig = hmac.new(settings.JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
            actual_sig = _b64url_decode(signature_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None
            payload_json = _b64url_decode(payload_b64).decode('utf-8')
            payload = json.loads(payload_json)
            if "exp" in payload and payload["exp"] < time.time():
                return None
            return payload
        except Exception:
            return None
