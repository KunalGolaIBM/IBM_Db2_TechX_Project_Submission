"""Domain-scoped access: which Db2 role sees which policy domain's decisions, and the users who hold those roles.

Db2 does the enforcing. The row permissions in sql/06_domain_permissions.sql show a decision row only to holders of
ASOF_ALL_DOMAINS, to SECADM (the owner), and to holders of a role that <schema>.DOMAIN_ACCESS maps to the row's
policy document. This module only writes that mapping and grants the roles (setup, through schema.apply_grants):

- every domain in asof/domains.py gets a role ASOF_DOMAIN_<KEY> and a DOMAIN_ACCESS row for its DOC_ID, so a new
  domain is covered by the same permissions without a change to any SQL;
- each domain with users configured (config.py: an analyst and a specialist) has them hold that role, plus
  ASOF_ANALYST (the audit views, the analyst workload) or ASOF_SPECIALIST (the inbox's two procedures).

A domain user never holds ASOF_ALL_DOMAINS, and none of the all-domain users may double as one: apply_grants refuses.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import ibm_db_dbi

from . import db
from .config import Settings
from .domains import DOMAINS, Domain

ALL_DOMAINS_ROLE = "ASOF_ALL_DOMAINS"
ANALYST_ROLE = "ASOF_ANALYST"
SPECIALIST_ROLE = "ASOF_SPECIALIST"
ALREADY_GRANTED = ("42502", "01548")  # as in schema.py: role already granted (error on some levels, warning on others)

# The users setup creates by default, per domain key: (analyst, specialist). Mirrors config.py's defaults.
DEFAULT_DOMAIN_USERS: dict[str, tuple[str, str]] = {"airline": ("airread", "airrev"), "bank": ("bankread", "bankrev")}

SQL_ROLE_EXISTS = "SELECT 1 FROM SYSCAT.ROLES WHERE ROLENAME = ?"
SQL_CURRENT_SCHEMA = "VALUES CURRENT SCHEMA"
# Only for a document the schema holds (DOMAIN_ACCESS's foreign key); the role is created either way.
SQL_MAP_DOMAIN = """MERGE INTO DOMAIN_ACCESS T
USING (SELECT D.DOC_ID, CAST(? AS VARCHAR(128)) AS ROLE_NAME FROM POLICY_DOC D WHERE D.DOC_ID = ?) AS S
ON T.DOC_ID = S.DOC_ID AND T.ROLE_NAME = S.ROLE_NAME
WHEN NOT MATCHED THEN INSERT (DOC_ID, ROLE_NAME) VALUES (S.DOC_ID, S.ROLE_NAME)"""


def role_for(domain: Domain) -> str:
    """The Db2 role that sees this domain's decisions."""
    return db.ident(f"ASOF_DOMAIN_{domain.key.upper()}")


def connection_role(kind: str, domain_key: str) -> str | None:
    """The db.py connection role for a domain's analyst or specialist ("analyst" or "review"), if it has one."""
    name = f"{kind}_{domain_key}"
    return name if name in db.DOMAIN_ROLES else None


def domain_users(settings: Settings) -> dict[str, tuple[str, str]]:
    """Domain key -> (analyst, specialist) user names, from the settings, for the domains that have them."""
    out = {}
    for key in {k.split("_", 1)[1] for k in db.DOMAIN_ROLES}:
        analyst, review = connection_role("analyst", key), connection_role("review", key)
        if analyst and review:
            out[key] = (getattr(settings, db.DOMAIN_ROLES[analyst] + "_user"),
                        getattr(settings, db.DOMAIN_ROLES[review] + "_user"))
    return out


@dataclass(frozen=True)
class Scope:
    """A choice in Ask the ledger: every domain (the all-domain analyst) or one (that domain's analyst)."""

    key: str
    label: str
    doc_ids: tuple[str, ...]
    connection: str  # a db.Role
    user: str

    def as_dict(self) -> dict[str, object]:
        return {"key": self.key, "label": self.label, "doc_ids": list(self.doc_ids), "user": self.user}


def scopes(settings: Settings) -> list[Scope]:
    """All domains first, then one scope per domain whose analyst is configured, in the order of asof/domains.py."""
    out = [Scope("all", "All domains", tuple(DOMAINS), "analyst", settings.asof_analyst_user)]
    for d in DOMAINS.values():
        role = connection_role("analyst", d.key)
        if role:
            out.append(Scope(d.key, d.name, (d.doc_id,), role, getattr(settings, db.DOMAIN_ROLES[role] + "_user")))
    return out


def _grant_role(conn: ibm_db_dbi.Connection, role: str, user: str) -> None:
    try:
        db.execute(conn, f"GRANT ROLE {db.ident(role)} TO USER {db.ident(user)}")
        conn.commit()
    except db.DatabaseError as exc:
        conn.rollback()
        if exc.sqlstate not in ALREADY_GRANTED:
            raise


def check_users(users: Mapping[str, tuple[str, str]], all_domain_users: Iterable[str]) -> None:
    """A domain-scoped user must not also be one of the users that see every domain: it would see them all."""
    everyone = {u.lower() for u in all_domain_users}
    clash = sorted({u for pair in users.values() for u in pair if u.lower() in everyone})
    if clash:
        raise ValueError(f"domain-scoped users {clash} are also all-domain users; give each domain its own users")


def grant_domains(conn: ibm_db_dbi.Connection, schema: str, users: Mapping[str, tuple[str, str]]) -> int:
    """Create each domain's role, map its DOC_ID to it in <schema>.DOMAIN_ACCESS, and grant it to the domain's users.
    Idempotent. Returns the number of domains. Runs as the owner (CREATE ROLE and GRANT ROLE need SECADM)."""
    target = db.validate_schema(schema)
    previous = str(db.query(conn, SQL_CURRENT_SCHEMA)[0][0]).strip()
    db.use_schema(conn, target)  # SQL_MAP_DOMAIN names its tables unqualified
    try:
        for d in DOMAINS.values():
            role = role_for(d)
            if not db.query(conn, SQL_ROLE_EXISTS, (role,)):
                db.execute(conn, f"CREATE ROLE {db.ident(role)}")
            db.execute(conn, SQL_MAP_DOMAIN, (role, d.doc_id))
            conn.commit()
            if d.key in users:
                analyst, specialist = users[d.key]
                for user, kind in ((analyst, ANALYST_ROLE), (specialist, SPECIALIST_ROLE)):
                    _grant_role(conn, kind, user)
                    _grant_role(conn, role, user)
    finally:
        db.use_schema(conn, previous)
    return len(DOMAINS)
