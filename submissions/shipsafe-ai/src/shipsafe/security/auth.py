"""API token issuing and role checks.

Tokens look like `ss_<43 url-safe chars>` (256 bits of entropy). Only the
SHA-256 hash is stored in Db2 (API_TOKENS.TOKEN_HASH); the plaintext is shown
exactly once when the token is created.
"""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Tuple

# Ordered from least to most privileged.
ROLES = ("viewer", "operator", "admin")
_RANK = {r: i for i, r in enumerate(ROLES)}


@dataclass(frozen=True)
class Principal:
    token_id: str
    name: str
    role: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token() -> Tuple[str, str, str]:
    """Return (token_id, plaintext_token, token_hash)."""
    token = "ss_" + secrets.token_urlsafe(32)
    return "tok_" + secrets.token_hex(6), token, hash_token(token)


def role_allows(role: str, required: str) -> bool:
    if role not in _RANK or required not in _RANK:
        return False
    return _RANK[role] >= _RANK[required]
