"""Install and remove the AsOf schema from the SQL files in asof/sql/.

The schema name is the only identifier that varies (ASOF normally, ASOF_TEST in tests).
It is validated against a strict pattern and substituted into the SQL text by code,
never taken from user input.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from importlib import resources

import ibm_db_dbi

from . import db

log = logging.getLogger(__name__)

SCHEMA_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")
USER_RE = re.compile(r"^[a-z][a-z0-9]{0,7}$")
GRANTS_PREFIX = "90_"
NOT_HELD = "42504"  # REVOKE of a privilege that is not held
_MARKER = re.compile(r"^--\s*(table|index|versioning|trigger|procedure|function|view|grant|other):\s*([A-Z0-9_]+)\s*$", re.M)
_SCHEMA_TOKEN = re.compile(r"\bASOF\.")


@dataclass(frozen=True)
class Statement:
    kind: str
    name: str
    sql: str
    source: str


def validate_schema(schema: str) -> str:
    if not SCHEMA_RE.match(schema):
        raise ValueError(f"invalid schema name {schema!r}")
    return schema


def load_statements(schema: str = db.SCHEMA, grants: bool = False) -> list[Statement]:
    """Statements from the object files (grants=False) or the grants file (grants=True)."""
    validate_schema(schema)
    statements: list[Statement] = []
    sql_dir = resources.files("asof") / "sql"
    for entry in sorted(sql_dir.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith(".sql") or entry.name.startswith(GRANTS_PREFIX) != grants:
            continue
        text = entry.read_text(encoding="utf-8")
        for block in re.split(r"^@\s*$", text, flags=re.M):
            marker = _MARKER.search(block)
            body = "\n".join(line for line in block.splitlines() if not line.lstrip().startswith("--")).strip()
            if not body:
                continue
            if marker is None:
                raise ValueError(f"{entry.name}: statement without a '-- kind: NAME' marker:\n{body[:120]}")
            statements.append(
                Statement(marker.group(1), marker.group(2), _SCHEMA_TOKEN.sub(f"{schema}.", body), entry.name)
            )
    return statements


def _exists(conn: ibm_db_dbi.Connection, schema: str, st: Statement) -> bool:
    if st.kind == "table":
        sql = "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?"
    elif st.kind == "index":
        sql = "SELECT 1 FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = ?"
    elif st.kind == "versioning":
        sql = "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ? AND TEMPORALTYPE IN ('S', 'B')"
    else:
        return False  # triggers, procedures, views and grants use CREATE OR REPLACE or are idempotent
    return bool(db.query(conn, sql, (schema, st.name)))


def install(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> dict[str, int]:
    """Create missing objects and replace routines. Returns counts of created and skipped."""
    validate_schema(schema)
    counts = {"created": 0, "skipped": 0}
    for st in load_statements(schema):
        if _exists(conn, schema, st):
            counts["skipped"] += 1
            continue
        try:
            db.execute(conn, st.sql)
            conn.commit()
        except db.DatabaseError as exc:
            conn.rollback()
            raise db.DatabaseError(f"{st.source} {st.kind} {st.name}: {exc}", exc.sqlstate, exc.sqlcode) from None
        counts["created"] += 1
    return counts


def apply_grants(conn: ibm_db_dbi.Connection, app_user: str, editor_user: str, schema: str = db.SCHEMA) -> dict[str, int]:
    """Revoke PUBLIC defaults and grant the two users exactly what they need."""
    for user in (app_user, editor_user):
        if not USER_RE.match(user):
            raise ValueError(f"invalid Db2 user name {user!r}")
    counts = {"applied": 0, "already_revoked": 0}
    for st in load_statements(schema, grants=True):
        sql = st.sql.replace("ASOF_APP_USER", app_user.upper()).replace("ASOF_EDITOR_USER", editor_user.upper())
        try:
            db.execute(conn, sql)
            conn.commit()
            counts["applied"] += 1
        except db.DatabaseError as exc:
            conn.rollback()
            if sql.startswith("REVOKE") and exc.sqlstate == NOT_HELD:
                counts["already_revoked"] += 1
                continue
            raise db.DatabaseError(f"{st.source} {st.name}: {exc}", exc.sqlstate, exc.sqlcode) from None
    return counts


def drop(conn: ibm_db_dbi.Connection, schema: str) -> None:
    """Remove every object in `schema`, then the schema. Used by tests and `setup --reset`."""
    validate_schema(schema)
    q = lambda sql: [r[0].strip() for r in db.query(conn, sql, (schema,))]  # noqa: E731
    steps: list[str] = []
    steps += [f"DROP TRIGGER {schema}.{n}" for n in q("SELECT TRIGNAME FROM SYSCAT.TRIGGERS WHERE TRIGSCHEMA = ?")]
    steps += [f"DROP SPECIFIC PROCEDURE {schema}.{n}" for n in q(
        "SELECT SPECIFICNAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? AND ROUTINETYPE = 'P'")]
    steps += [f"DROP SPECIFIC FUNCTION {schema}.{n}" for n in q(
        "SELECT SPECIFICNAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? AND ROUTINETYPE = 'F'")]
    steps += [f"DROP VIEW {schema}.{n}" for n in q("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'V'")]
    steps += [f"ALTER TABLE {schema}.{n} DROP VERSIONING" for n in q(
        "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TEMPORALTYPE IN ('S', 'B')")]
    for stmt in steps:
        db.execute(conn, stmt)
    conn.commit()
    # Tables in dependency order: children first. Retry passes handle foreign keys.
    remaining = q("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T'")
    for _ in range(len(remaining) + 1):
        if not remaining:
            break
        left = []
        for name in remaining:
            try:
                db.execute(conn, f"DROP TABLE {schema}.{name}")
                conn.commit()
            except db.DatabaseError:
                conn.rollback()
                left.append(name)
        remaining = left
    if remaining:
        raise db.DatabaseError(f"could not drop tables in {schema}: {remaining}")
    if q("SELECT SCHEMANAME FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?"):
        db.execute(conn, f"DROP SCHEMA {schema} RESTRICT")
        conn.commit()
