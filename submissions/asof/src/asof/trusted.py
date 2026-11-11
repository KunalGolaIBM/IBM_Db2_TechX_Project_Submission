"""Db2 trusted context: each API request runs in Db2 as the API user who made it (ASOF_TRUSTED_CONTEXT=true).

With ASOF_AUTH=users, every /api/ request carries a personal token. Without this, Db2 sees one account for all of
them, the runtime user. With it, the API's runtime connections are trusted connections (the trusted context
ASOF_API_CONTEXT: system authorization ID = the runtime user, ADDRESS = where the API connects from), and each
request switches its connection's session user to the API user's own authorization ID, API_<NAME>, without a
password. So SESSION_USER in a ledger row (STORED_BY) is the person who asked, and Db2 checks that person's
privileges, not the service account's:

- The context's default role, ASOF_API_SESSION, holds what the runtime user holds in the AsOf schema (mirrored from
  the catalog at setup), minus the three procedures that write: APPEND_LEDGER, ADD_SUGGESTION and ADD_NOTICE. It is
  in force only inside a connection that matched the context, so the API_* IDs can do nothing anywhere else (they
  have no password and no operating-system account; switched IDs need neither).
- Those three come with the API user's own roles, granted to its authorization ID: ASOF_API_CHECKER
  (APPEND_LEDGER), ASOF_API_EDITOR (APPEND_LEDGER, ADD_SUGGESTION), ASOF_API_REVIEWER (APPEND_LEDGER, ADD_NOTICE).
  An auditor holds none of them, so Db2 itself refuses an auditor's session that tries to append (42501).
- Every API user's ID holds ASOF_TEXT_READER and ASOF_ALL_DOMAINS directly, as the runtime user does: the ledger's
  column masks and the domain row permissions (06_domain_permissions.sql) ask VERIFY_ROLE_FOR_USER(SESSION_USER, ...),
  which does not see a trusted context's role. Those permissions are evaluated for the switched user: an ID holding
  only a domain role sees, and may append, only that domain's rows.
- The context lists each active API user's ID (WITH USE FOR ... WITHOUT AUTHENTICATION), never PUBLIC: a switch to
  any other ID, the owner's included, is refused by Db2 (SQL20361N). Disabling a user takes its ID off the list.

The policy editor, reviewer, analyst and dbt users keep their own service accounts: only the runtime user's
connections switch. Setup (and python -m asof.users) keep the context, the role grants and the list in step with
ASOF.API_USER through sync(). See docs/trusted-context.md.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field

import ibm_db_dbi

from . import db
from .config import Settings
from .users import ROLES

CONTEXT = "ASOF_API_CONTEXT"
SESSION_ROLE = "ASOF_API_SESSION"
TEXT_READER = "ASOF_TEXT_READER"
ALL_DOMAINS = "ASOF_ALL_DOMAINS"  # rowaccess.ALL_DOMAINS_ROLE: the runtime user holds it too
# The procedures that write, each held only by the API roles that use it.
WRITE_PROCEDURES = ("APPEND_LEDGER", "ADD_SUGGESTION", "ADD_NOTICE")
ROLE_FOR = {"checker": "ASOF_API_CHECKER", "editor": "ASOF_API_EDITOR", "reviewer": "ASOF_API_REVIEWER"}
WRITES_OF = {"ASOF_API_CHECKER": ("APPEND_LEDGER",), "ASOF_API_EDITOR": ("APPEND_LEDGER", "ADD_SUGGESTION"),
             "ASOF_API_REVIEWER": ("APPEND_LEDGER", "ADD_NOTICE")}
API_ROLES = (SESSION_ROLE, *WRITES_OF)
AUTHID_PREFIX = "API_"
_NOT_IDENT = re.compile(r"[.\-]")

SQL_CONTEXT = "SELECT SYSTEMAUTHID, DEFAULTCONTEXTROLE, ENABLED FROM SYSCAT.CONTEXTS WHERE CONTEXTNAME = ?"
SQL_CONTEXT_ADDRESSES = "SELECT ATTR_VALUE FROM SYSCAT.CONTEXTATTRIBUTES WHERE CONTEXTNAME = ? AND ATTR_NAME = 'ADDRESS'"
SQL_CONTEXT_USERS = ("SELECT SURROGATEAUTHID FROM SYSCAT.SURROGATEAUTHIDS WHERE TRUSTEDID = ? AND TRUSTEDIDTYPE = 'C' "
                     "AND SURROGATEAUTHIDTYPE = 'U'")
SQL_OWN_ADDRESS = "SELECT CLIENT_IPADDR FROM TABLE(MON_GET_CONNECTION(MON_GET_APPLICATION_HANDLE(), -1)) AS M"
SQL_ROLE_EXISTS = "SELECT 1 FROM SYSCAT.ROLES WHERE ROLENAME = ?"
SQL_ACTIVE_USERS = "SELECT USER_NAME, CAN_CHECK, CAN_AUDIT, CAN_EDIT, CAN_REVIEW FROM API_USER WHERE DISABLED_AT IS NULL"
SQL_ALL_USERS = "SELECT USER_NAME FROM API_USER"
SQL_ROLES_OF = "SELECT ROLENAME FROM SYSCAT.ROLEAUTH WHERE GRANTEETYPE = 'U' AND GRANTEE = ?"
SQL_RUNTIME_TABLES = ("SELECT TABNAME FROM SYSCAT.TABAUTH WHERE GRANTEE = ? AND GRANTEETYPE = 'U' AND TABSCHEMA = ? "
                      "AND SELECTAUTH IN ('Y', 'G')")
SQL_ROLE_TABLES = ("SELECT TABNAME FROM SYSCAT.TABAUTH WHERE GRANTEE = ? AND GRANTEETYPE = 'R' AND TABSCHEMA = ? "
                   "AND SELECTAUTH IN ('Y', 'G')")
SQL_RUNTIME_ROUTINES = ("SELECT A.SPECIFICNAME, R.ROUTINENAME FROM SYSCAT.ROUTINEAUTH A JOIN SYSCAT.ROUTINES R "
                        "ON R.ROUTINESCHEMA = A.SCHEMA AND R.SPECIFICNAME = A.SPECIFICNAME "
                        "WHERE A.GRANTEE = ? AND A.GRANTEETYPE = ? AND A.SCHEMA = ? AND A.EXECUTEAUTH IN ('Y', 'G') "
                        "AND R.ROUTINETYPE = 'P'")


class TrustedContextError(RuntimeError):
    pass


def authid(user_name: str) -> str:
    """The Db2 authorization ID an API user's requests run as: API_ and the name, upper case, '.' and '-' as '_'."""
    return db.ident(AUTHID_PREFIX + _NOT_IDENT.sub("_", user_name).upper())


def check_address(address: str) -> str:
    """An IPv4 or IPv6 address, as Db2's ADDRESS attribute takes it (a literal in the DDL)."""
    try:
        return str(ipaddress.ip_address(address.strip()))
    except ValueError:
        raise TrustedContextError(f"ASOF_TRUSTED_CONTEXT_ADDRESS {address!r} is not an IP address") from None


@dataclass
class SyncReport:
    action: str  # created, updated, unchanged, dropped, off
    address: str | None = None
    users: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)


def _run(conn: ibm_db_dbi.Connection, sql: str, changes: list[str], label: str) -> None:
    db.execute(conn, sql)
    conn.commit()
    changes.append(label)


def _active_users(conn: ibm_db_dbi.Connection, schema: str) -> dict[str, set[str]]:
    """Active API users' authorization IDs and the Db2 roles their API roles call for."""
    db.use_schema(conn, schema)
    out: dict[str, set[str]] = {}
    names: dict[str, str] = {}
    for name, *flags in db.query(conn, SQL_ACTIVE_USERS):
        name = name.strip()
        held = {role for role, f in zip(ROLES, flags, strict=True) if f}
        aid = authid(name)
        if aid in names:
            raise TrustedContextError(f"API users {names[aid]!r} and {name!r} map to the same Db2 ID {aid}; "
                                      "rename one (python -m asof.users)")
        names[aid] = name
        out[aid] = {TEXT_READER, ALL_DOMAINS} | {ROLE_FOR[r] for r in held if r in ROLE_FOR}
    return out


def _sync_role_privileges(conn: ibm_db_dbi.Connection, settings: Settings, schema: str, changes: list[str]) -> None:
    """ASOF_API_SESSION mirrors the runtime user's SELECTs and procedures in `schema`, minus the writes; each API role
    gets its writes. Grants what is missing and revokes what the runtime user no longer holds."""
    app = db.ident(settings.asof_app_user)
    s = db.ident(schema)
    for role in API_ROLES:
        if not db.query(conn, SQL_ROLE_EXISTS, (role,)):
            _run(conn, f"CREATE ROLE {db.ident(role)}", changes, f"role {role}")
    want_tables = {r[0].strip() for r in db.query(conn, SQL_RUNTIME_TABLES, (app, s))}
    have_tables = {r[0].strip() for r in db.query(conn, SQL_ROLE_TABLES, (SESSION_ROLE, s))}
    for t in sorted(want_tables - have_tables):
        _run(conn, f"GRANT SELECT ON TABLE {db.ident(s)}.{db.ident(t)} TO ROLE {db.ident(SESSION_ROLE)}", changes,
             f"SELECT {t}")
    for t in sorted(have_tables - want_tables):
        _run(conn, f"REVOKE ALL ON TABLE {db.ident(s)}.{db.ident(t)} FROM ROLE {db.ident(SESSION_ROLE)}", changes,
             f"no SELECT {t}")  # the role holds nothing but SELECT on tables
    runtime = {spec.strip(): name.strip() for spec, name in db.query(conn, SQL_RUNTIME_ROUTINES, (app, "U", s))}
    procs_by_name: dict[str, list[str]] = {}
    for spec, name in db.query(conn, "SELECT SPECIFICNAME, ROUTINENAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? "
                                     "AND ROUTINETYPE = 'P'", (s,)):
        procs_by_name.setdefault(name.strip(), []).append(spec.strip())
    want: dict[str, set[str]] = {SESSION_ROLE: {spec for spec, name in runtime.items() if name not in WRITE_PROCEDURES}}
    for role, writes in WRITES_OF.items():
        want[role] = {spec for name in writes for spec in procs_by_name.get(name, [])}
    for role, specs in want.items():
        have = {r[0].strip() for r in db.query(conn, SQL_RUNTIME_ROUTINES, (role, "R", s))}
        for spec in sorted(specs - have):
            _run(conn, f"GRANT EXECUTE ON SPECIFIC PROCEDURE {db.ident(s)}.{db.ident(spec)} TO ROLE {db.ident(role)}",
                 changes, f"{role} EXECUTE {spec}")
        for spec in sorted(have - specs):
            _run(conn, f"REVOKE EXECUTE ON SPECIFIC PROCEDURE {db.ident(s)}.{db.ident(spec)} FROM ROLE "
                       f"{db.ident(role)} RESTRICT", changes, f"{role} no EXECUTE {spec}")
    if not db.query(conn, "SELECT 1 FROM SYSCAT.DBAUTH WHERE GRANTEE = ? AND GRANTEETYPE = 'R' AND CONNECTAUTH = 'Y'",
                    (SESSION_ROLE,)):
        _run(conn, f"GRANT CONNECT ON DATABASE TO ROLE {db.ident(SESSION_ROLE)}", changes, "CONNECT for the session role")


def _sync_user_roles(conn: ibm_db_dbi.Connection, schema: str, wanted: dict[str, set[str]], changes: list[str]) -> None:
    """Each active API user's ID holds exactly its roles; a disabled user's ID holds none of AsOf's API roles."""
    db.use_schema(conn, schema)
    known = {authid(r[0].strip()) for r in db.query(conn, SQL_ALL_USERS)}
    managed = {TEXT_READER, ALL_DOMAINS, *WRITES_OF}
    for aid in sorted(known | set(wanted)):
        have = {r[0].strip() for r in db.query(conn, SQL_ROLES_OF, (aid,))} & managed
        want = wanted.get(aid, set())
        for role in sorted(want - have):
            _run(conn, f"GRANT ROLE {db.ident(role)} TO USER {db.ident(aid)}", changes, f"{aid} +{role}")
        for role in sorted(have - want):
            _run(conn, f"REVOKE ROLE {db.ident(role)} FROM USER {db.ident(aid)}", changes, f"{aid} -{role}")


def own_address(conn: ibm_db_dbi.Connection) -> str:
    """The client address Db2 sees for this connection: through Docker's port mapping, the bridge gateway."""
    rows = db.query(conn, SQL_OWN_ADDRESS)
    if not rows or not rows[0][0]:
        raise TrustedContextError("Db2 reported no client address for this connection (a local IPC connection?); "
                                  "set ASOF_TRUSTED_CONTEXT_ADDRESS")
    return check_address(str(rows[0][0]))


def drop(conn: ibm_db_dbi.Connection) -> bool:
    if not db.query(conn, SQL_CONTEXT, (CONTEXT,)):
        return False
    db.execute(conn, f"DROP TRUSTED CONTEXT {db.ident(CONTEXT)}")
    conn.commit()
    return True


def sync(conn: ibm_db_dbi.Connection, settings: Settings, schema: str = db.SCHEMA) -> SyncReport:
    """As the owner (SECADM): make the trusted context, its roles and its user list match the settings and API_USER.

    Off: drop the context if it exists (the roles and grants stay; without the context nobody can switch to an API
    ID, and those IDs have no other way in). On: create or fix it."""
    db.validate_schema(schema)
    if not settings.asof_trusted_context:
        return SyncReport("dropped" if drop(conn) else "off")
    if settings.asof_auth != "users":
        raise TrustedContextError("ASOF_TRUSTED_CONTEXT=true needs ASOF_AUTH=users: the session user is the API user")
    changes: list[str] = []
    address = (check_address(settings.asof_trusted_context_address) if settings.asof_trusted_context_address
               else own_address(conn))
    _sync_role_privileges(conn, settings, schema, changes)
    wanted = _active_users(conn, schema)
    _sync_user_roles(conn, schema, wanted, changes)
    system = db.ident(settings.asof_app_user)
    current = db.query(conn, SQL_CONTEXT, (CONTEXT,))
    addresses = {r[0].strip() for r in db.query(conn, SQL_CONTEXT_ADDRESSES, (CONTEXT,))}
    if current and (current[0][0].strip() != system or (current[0][1] or "").strip() != SESSION_ROLE
                    or current[0][2].strip() != "Y" or addresses != {address}):
        drop(conn)  # a different system ID, role or address: rebuild it rather than patch it
        changes.append("rebuilt the context")
        current = []
    users = sorted(wanted)
    action = "updated"
    if not current:  # created with no user; the list is added below, one ALTER per user
        db.execute(conn, f"CREATE TRUSTED CONTEXT {db.ident(CONTEXT)} BASED UPON CONNECTION USING SYSTEM AUTHID "
                         f"{db.ident(system)} ATTRIBUTES (ADDRESS {db.string_literal(address)}) "
                         f"DEFAULT ROLE {db.ident(SESSION_ROLE)} ENABLE")
        conn.commit()
        action = "created"
    listed = {r[0].strip() for r in db.query(conn, SQL_CONTEXT_USERS, (CONTEXT,))}
    for u in sorted(set(users) - listed):
        _run(conn, f"ALTER TRUSTED CONTEXT {db.ident(CONTEXT)} ADD USE FOR {db.ident(u)} WITHOUT AUTHENTICATION",
             changes, f"use for {u}")
    for u in sorted(listed - set(users)):
        _run(conn, f"ALTER TRUSTED CONTEXT {db.ident(CONTEXT)} DROP USE FOR {db.ident(u)}", changes, f"no use for {u}")
    return SyncReport(action if action == "created" or changes else "unchanged", address, users, changes)


def describe(report: SyncReport) -> str:
    """One line for setup and python -m asof.users."""
    if report.action == "off":
        return "off (ASOF_TRUSTED_CONTEXT=false)"
    if report.action == "dropped":
        return f"dropped {CONTEXT} (ASOF_TRUSTED_CONTEXT=false)"
    who = ", ".join(report.users) if report.users else "no API users yet (python -m asof.users add ...)"
    return (f"{CONTEXT} {report.action}: connections as the runtime user from {report.address} may switch to "
            f"{who}; {len(report.changes)} change{'s' if len(report.changes) != 1 else ''}")
