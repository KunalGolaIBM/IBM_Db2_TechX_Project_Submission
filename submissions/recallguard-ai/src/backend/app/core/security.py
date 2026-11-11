"""Role-aware access control (authentication-ready).

The hackathon build identifies the caller from two headers so that an identity
provider (IBM App ID / OIDC / API gateway) can be dropped in front without
changing any service code:

    X-User-Id:   analyst@recallguard.demo
    X-User-Role: viewer | analyst | recall_manager | admin

A production deployment would replace `get_principal` with JWT validation.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from .config import get_settings

ROLES = ("viewer", "analyst", "recall_manager", "admin")

PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"read"},
    "analyst": {"read", "incident:write", "investigate", "evidence:write", "recall:generate", "comment"},
    "recall_manager": {"read", "incident:write", "investigate", "evidence:write", "recall:generate", "comment",
                       "recall:approve", "recall:execute", "supplier:sensitive"},
    "admin": {"read", "incident:write", "investigate", "evidence:write", "recall:generate", "comment",
              "recall:approve", "recall:execute", "supplier:sensitive", "admin"},
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str

    def can(self, perm: str) -> bool:
        return perm in PERMISSIONS.get(self.role, set())


def get_principal(
    x_user_id: str | None = Header(default=None, max_length=80),
    x_user_role: str | None = Header(default=None, max_length=30),
) -> Principal:
    settings = get_settings()
    if not x_user_id or not x_user_role:
        if settings.require_auth_headers:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-User-Id / X-User-Role headers")
        return Principal("demo.analyst@recallguard.demo", "analyst")
    role = x_user_role.strip().lower()
    if role not in ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Unknown role '{x_user_role}'")
    return Principal(x_user_id.strip()[:80], role)


def require(perm: str):
    def _dep(p: Principal = Depends(get_principal)) -> Principal:
        if not p.can(perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{p.role}' lacks permission '{perm}'")
        return p

    return _dep
