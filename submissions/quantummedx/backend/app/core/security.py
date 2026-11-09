"""Password hashing (PBKDF2) and signed expiring tokens. Standard library only."""
import base64, hashlib, hmac, json, os, secrets, time


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2$200000${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def _secret() -> bytes:
    s = os.getenv("JWT_SECRET")
    if not s or len(s) < 16:
        raise RuntimeError("JWT_SECRET must be set (16+ characters) in your .env")
    return s.encode()


def create_token(user_id: int, role: str, ttl_seconds: int = 3600) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"sub": user_id, "role": role, "exp": int(time.time()) + ttl_seconds}).encode()).decode()
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_token(token: str) -> dict | None:
    try:
        body, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest(), sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
        return data if data["exp"] > time.time() else None
    except Exception:
        return None
