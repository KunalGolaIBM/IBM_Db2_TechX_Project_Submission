"""Static bearer-token authentication with two roles.

* ``analyst``  - may create investigations, run the investigator, propose recommendations.
* ``reviewer`` - may approve / reject recommendations.
Both may read investigation data. Reviewer identity always comes from the token,
never from the request body, so a caller cannot claim to be someone else.

Tokens are configured with ``CIVICLENS_AUTH_TOKENS="id:role:token,..."``. They are
compared in constant time. If no tokens are configured the API fails closed.
This is deliberately simple (hackathon scope); production would use OIDC / IBM App ID.
"""

from __future__ import annotations

import hmac
import logging
import re
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from civiclens.config import Settings, get_settings

logger = logging.getLogger("civiclens")

ROLES = frozenset({"analyst", "reviewer"})
_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
MIN_TOKEN_LENGTH = 24

_bearer = HTTPBearer(auto_error=False)

# What each role may do. The UI reads this from /api/me instead of hardcoding role logic;
# the endpoints enforce it independently with require_role().
CAPABILITIES: dict[str, tuple[str, ...]] = {
    "analyst": (
        "complaint:create",
        "investigation:create",
        "evidence:attach",
        "investigation:run",
        "recommendation:propose",
    ),
    "reviewer": ("recommendation:decide",),
}


def capabilities_for(role: str) -> tuple[str, ...]:
    return CAPABILITIES.get(role, ())


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str


class AuthConfigError(ValueError):
    pass


def parse_tokens(raw: str) -> dict[str, Principal]:
    """Parse ``id:role:token`` entries into ``{token: Principal}``; reject weak or duplicate ones."""
    result: dict[str, Principal] = {}
    ids: set[str] = set()
    for entry in (e.strip() for e in raw.split(",")):
        if not entry:
            continue
        parts = entry.split(":", 2)
        if len(parts) != 3:
            raise AuthConfigError("Each auth entry must look like id:role:token.")
        user_id, role, token = parts
        if not _ID.match(user_id):
            raise AuthConfigError("Invalid user id in auth tokens.")
        if role not in ROLES:
            raise AuthConfigError(f"Invalid role for {user_id!r}; expected one of {sorted(ROLES)}.")
        if len(token) < MIN_TOKEN_LENGTH:
            raise AuthConfigError(f"Token for {user_id!r} is shorter than {MIN_TOKEN_LENGTH} characters.")
        if token in result or user_id in ids:
            raise AuthConfigError("Duplicate user id or token in auth configuration.")
        ids.add(user_id)
        result[token] = Principal(user_id, role)
    return result


def authenticate(token: str, settings: Settings) -> Principal | None:
    if settings.civiclens_auth_tokens is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "AUTH_NOT_CONFIGURED", "message": "Authentication is not configured."},
        )
    try:
        table = parse_tokens(settings.civiclens_auth_tokens.get_secret_value())
    except AuthConfigError as exc:
        # The reason names a configured user id: operators read it in the log, callers get a generic body.
        logger.error("Authentication is misconfigured: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AUTH_MISCONFIGURED",
                "message": "Authentication is misconfigured on the server.",
            },
        ) from None
    found: Principal | None = None
    for known, principal in table.items():  # compare against every token: no early exit
        if hmac.compare_digest(known.encode(), token.encode()):
            found = principal
    return found


def current_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    unauthorized = HTTPException(
        status_code=401,
        detail={"code": "UNAUTHENTICATED", "message": "A valid bearer token is required."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or not creds.credentials:
        # still hit config check so a misconfigured server reports 503, not 401
        authenticate("-", get_settings())
        raise unauthorized
    principal = authenticate(creds.credentials, get_settings())
    if principal is None:
        raise unauthorized
    return principal


def require_role(*roles: str):
    allowed = frozenset(roles)

    def dependency(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": f"Role {principal.role!r} may not do this."},
            )
        return principal

    return dependency


AnyUser = Depends(current_principal)
Analyst = Depends(require_role("analyst"))
Reviewer = Depends(require_role("reviewer"))
