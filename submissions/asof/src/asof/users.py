"""Per-user API authentication (ASOF_AUTH=users): personal tokens and roles, kept in Db2.

    python -m asof.users add maria --roles checker,auditor   # prints maria's token once
    python -m asof.users rotate maria                         # a new token; the old one stops working
    python -m asof.users disable maria
    python -m asof.users list

Roles: checker (submit drafts: /api/gate, the demo assistant), auditor (ledger, replay, evidence, receipts,
the chain and anchor checks, analytics, change impact, Ask the ledger), editor (policy changes and previews,
drafting and approving corrected help-centre answers). Reading the policy timeline needs any role.

Tokens are 256 random bits ("asof_" plus 43 URL-safe characters). Db2 stores only their SHA-256, in
ASOF.API_USER; a token that high in entropy needs no salt or slow hash, and a lookup by hash cannot be
timed into revealing one. The owner account (setup's) adds, rotates and disables users; the runtime user can
only read the table to authenticate. Disabling takes effect on the next request: nothing is cached.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import sys
from dataclasses import dataclass

import ibm_db_dbi

from . import db

ROLES = ("checker", "auditor", "editor")
NAME_RE = re.compile(r"^[a-z][a-z0-9._-]{1,39}$")
TOKEN_RE = re.compile(r"^asof_[A-Za-z0-9_-]{43}$")

SQL_FIND = ("SELECT USER_NAME, CAN_CHECK, CAN_AUDIT, CAN_EDIT FROM API_USER "
            "WHERE TOKEN_SHA256 = ? AND DISABLED_AT IS NULL")
SQL_ADD = "INSERT INTO API_USER (USER_NAME, TOKEN_SHA256, CAN_CHECK, CAN_AUDIT, CAN_EDIT) VALUES (?, ?, ?, ?, ?)"
SQL_ROTATE = "UPDATE API_USER SET TOKEN_SHA256 = ? WHERE USER_NAME = ? AND DISABLED_AT IS NULL"
SQL_DISABLE = "UPDATE API_USER SET DISABLED_AT = CURRENT TIMESTAMP WHERE USER_NAME = ? AND DISABLED_AT IS NULL"
SQL_LIST = ("SELECT USER_NAME, CAN_CHECK, CAN_AUDIT, CAN_EDIT, CREATED_AT, DISABLED_AT FROM API_USER "
            "ORDER BY USER_NAME")


class UserError(ValueError):
    pass


@dataclass(frozen=True)
class APIUser:
    name: str
    roles: frozenset[str]

    def can(self, role: str) -> bool:
        return role in self.roles


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return "asof_" + secrets.token_urlsafe(32)


def _flags(roles: set[str]) -> tuple[int, int, int]:
    unknown = roles - set(ROLES)
    if unknown or not roles:
        raise UserError(f"roles must be one or more of {', '.join(ROLES)}")
    return tuple(int(r in roles) for r in ROLES)  # type: ignore[return-value]


def _check_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise UserError("a user name is 2 to 40 characters: lower-case letters, digits, '.', '_' or '-', "
                        "starting with a letter")
    return name


def add(conn: ibm_db_dbi.Connection, name: str, roles: set[str], schema: str = db.SCHEMA) -> str:
    """Add a user as the owner; returns the token, which is not stored anywhere."""
    flags = _flags(roles)
    token = new_token()
    db.use_schema(conn, schema)
    try:
        db.execute(conn, SQL_ADD, (_check_name(name), token_hash(token), *flags))
        conn.commit()
    except db.DatabaseError as exc:
        conn.rollback()
        if exc.sqlstate == "23505":
            raise UserError(f"a user named {name} already exists") from None
        raise
    return token


def rotate(conn: ibm_db_dbi.Connection, name: str, schema: str = db.SCHEMA) -> str:
    token = new_token()
    db.use_schema(conn, schema)
    if db.execute(conn, SQL_ROTATE, (token_hash(token), _check_name(name))) != 1:
        conn.rollback()
        raise UserError(f"no active user named {name}")
    conn.commit()
    return token


def disable(conn: ibm_db_dbi.Connection, name: str, schema: str = db.SCHEMA) -> bool:
    db.use_schema(conn, schema)
    done = db.execute(conn, SQL_DISABLE, (_check_name(name),)) == 1
    conn.commit()
    return done


def list_users(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> list[dict]:
    db.use_schema(conn, schema)
    return [{"user": r[0].strip(), "roles": [role for role, f in zip(ROLES, r[1:4], strict=True) if f],
             "created_at": r[4], "disabled_at": r[5]} for r in db.query(conn, SQL_LIST)]


def authenticate(conn: ibm_db_dbi.Connection, token: str | None, schema: str = db.SCHEMA) -> APIUser | None:
    """The active user holding this token, or None. Malformed tokens never reach Db2."""
    if not token or not TOKEN_RE.match(token):
        return None
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_FIND, (token_hash(token),))
    if not rows:
        return None
    name, *flags = rows[0]
    return APIUser(name.strip(), frozenset(role for role, f in zip(ROLES, flags, strict=True) if f))


def main(argv: list[str] | None = None) -> int:
    from .config import get_settings

    p = argparse.ArgumentParser(prog="python -m asof.users", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("add", help="add a user and print its token once")
    a.add_argument("name")
    a.add_argument("--roles", required=True, help="comma-separated: checker, auditor, editor")
    sub.add_parser("rotate", help="replace a user's token and print the new one once").add_argument("name")
    sub.add_parser("disable", help="disable a user (takes effect on its next request)").add_argument("name")
    sub.add_parser("list", help="list users and roles (no tokens or hashes)")
    p.add_argument("--schema", default=db.SCHEMA)
    args = p.parse_args(argv)
    try:
        with db.connection(get_settings(), "admin") as conn:
            if args.command == "add":
                token = add(conn, args.name, {r.strip() for r in args.roles.split(",") if r.strip()}, args.schema)
            elif args.command == "rotate":
                token = rotate(conn, args.name, args.schema)
            elif args.command == "disable":
                print(f"{args.name} disabled" if disable(conn, args.name, args.schema)
                      else f"no active user named {args.name}")
                return 0
            else:
                for u in list_users(conn, args.schema):
                    state = f"disabled {u['disabled_at']:%Y-%m-%d}" if u["disabled_at"] else "active"
                    print(f"{u['user']:<40} {','.join(u['roles']):<24} {state}")
                return 0
    except UserError as exc:
        print(exc)
        return 2
    print(f"Token for {args.name}. It is shown once and not stored; give it to {args.name} now:")
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
