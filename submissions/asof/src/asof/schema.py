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

SCHEMA_RE = db.SCHEMA_RE
USER_RE = re.compile(r"^[a-z][a-z0-9]{0,7}$")
GRANTS_PREFIX = "90_"
NOT_HELD = "42504"  # REVOKE of a privilege that is not held
_MARKER = re.compile(r"^--\s*(bufferpool|tablespace|table|index|versioning|trigger|procedure|function|view|mask|role"
                     r"|grant|other):"
                     r"\s*([A-Z0-9_]+)\s*$", re.M)
_SCHEMA_TOKEN = re.compile(r"\bASOF\.")


@dataclass(frozen=True)
class Statement:
    kind: str
    name: str
    sql: str
    source: str


validate_schema = db.validate_schema


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
    elif st.kind == "bufferpool":  # database-level, shared by every AsOf schema
        return bool(db.query(conn, "SELECT 1 FROM SYSCAT.BUFFERPOOLS WHERE BPNAME = ?", (st.name,)))
    elif st.kind == "tablespace":
        return bool(db.query(conn, "SELECT 1 FROM SYSCAT.TABLESPACES WHERE TBSPACE = ?", (st.name,)))
    else:
        return False  # triggers, procedures, views and grants use CREATE OR REPLACE or are idempotent
    return bool(db.query(conn, sql, (schema, st.name)))


def table_exists(conn: ibm_db_dbi.Connection, schema: str, table: str) -> bool:
    return bool(db.query(conn, "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?", (schema, table)))


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


DEFAULT_ANALYST_USER = "asofread"
ALREADY_GRANTED = ("42502", "01548")  # role already granted (error on some levels, warning on others)


def apply_grants(conn: ibm_db_dbi.Connection, app_user: str, editor_user: str, schema: str = db.SCHEMA,
                 analyst_user: str = DEFAULT_ANALYST_USER) -> dict[str, int]:
    """Revoke PUBLIC defaults, create the two roles if missing, and grant each user exactly what it needs."""
    for user in (app_user, editor_user, analyst_user):
        if not USER_RE.match(user):
            raise ValueError(f"invalid Db2 user name {user!r}")
    names = {"ASOF_APP_USER": db.ident(app_user), "ASOF_EDITOR_USER": db.ident(editor_user),
             "ASOF_ANALYST_USER": db.ident(analyst_user)}
    counts = {"applied": 0, "already_revoked": 0}
    for st in load_statements(schema, grants=True):
        if st.kind == "role" and db.query(conn, "SELECT 1 FROM SYSCAT.ROLES WHERE ROLENAME = ?", (st.name,)):
            continue
        sql = re.sub(r"\bASOF_(APP|EDITOR|ANALYST)_USER\b", lambda m: names[m.group(0)], st.sql)
        try:
            db.execute(conn, sql)
            conn.commit()
            counts["applied"] += 1
        except db.DatabaseError as exc:
            conn.rollback()
            if sql.startswith("REVOKE") and exc.sqlstate == NOT_HELD:
                counts["already_revoked"] += 1
                continue
            if sql.startswith("GRANT ROLE") and exc.sqlstate in ALREADY_GRANTED:
                continue
            raise db.DatabaseError(f"{st.source} {st.name}: {exc}", exc.sqlstate, exc.sqlcode) from None
    return counts


def _drop_code_objects(conn: ibm_db_dbi.Connection, schema: str) -> None:
    """Drop every view, trigger, procedure and function in `schema`, whatever depends on what.

    Each pass drops what it can; objects still needed by another are retried in the next
    pass. Recreating routines from scratch (rather than CREATE OR REPLACE over invalidated
    ones) also avoids Db2 keeping an old resolution timestamp on a revalidated procedure,
    which made it miss a function replaced after it (SQL0440N).
    """
    validate_schema(schema)
    q = lambda sql: [r[0].strip() for r in db.query(conn, sql, (schema,))]  # noqa: E731
    pending = (
        [f"DROP VIEW {db.ident(schema)}.{db.ident(n)}"
         for n in q("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'V'")]
        + [f"DROP TRIGGER {db.ident(schema)}.{db.ident(n)}"
           for n in q("SELECT TRIGNAME FROM SYSCAT.TRIGGERS WHERE TRIGSCHEMA = ?")]
        + [f"DROP SPECIFIC PROCEDURE {db.ident(schema)}.{db.ident(n)}" for n in q(
            "SELECT SPECIFICNAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? AND ROUTINETYPE = 'P'")]
        + [f"DROP SPECIFIC FUNCTION {db.ident(schema)}.{db.ident(n)}" for n in q(
            "SELECT SPECIFICNAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? AND ROUTINETYPE = 'F'")]
    )
    for _ in range(len(pending) + 1):
        if not pending:
            return
        left = []
        for stmt in pending:
            try:
                db.execute(conn, stmt)
                conn.commit()
            except db.DatabaseError:
                conn.rollback()
                left.append(stmt)
        if len(left) == len(pending):
            break
        pending = left
    if pending:
        raise db.DatabaseError(f"could not drop in {schema}: {pending}")


def drop(conn: ibm_db_dbi.Connection, schema: str) -> None:
    """Remove every object in `schema`, then the schema. Used by tests and `setup --reset`."""
    validate_schema(schema)
    q = lambda sql: [r[0].strip() for r in db.query(conn, sql, (schema,))]  # noqa: E731
    _drop_code_objects(conn, schema)
    for name in q("SELECT MODELNAME FROM SYSCAT.EXTERNALMODELS WHERE MODELSCHEMA = ?"):  # in-database models
        db.execute(conn, f"DROP EXTERNAL MODEL {db.ident(schema)}.{db.ident(name)}")
    conn.commit()
    for name in q("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TEMPORALTYPE IN ('S', 'B')"):
        db.execute(conn, f"ALTER TABLE {db.ident(schema)}.{db.ident(name)} DROP VERSIONING")
    conn.commit()
    # Tables in dependency order: children first. Retry passes handle foreign keys.
    remaining = q("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T'")
    for _ in range(len(remaining) + 1):
        if not remaining:
            break
        left = []
        for name in remaining:
            try:
                db.execute(conn, f"DROP TABLE {db.ident(schema)}.{db.ident(name)}")
                conn.commit()
            except db.DatabaseError:
                conn.rollback()
                left.append(name)
        remaining = left
    if remaining:
        raise db.DatabaseError(f"could not drop tables in {schema}: {remaining}")
    if q("SELECT SCHEMANAME FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?"):
        db.execute(conn, f"DROP SCHEMA {db.ident(schema)} RESTRICT")
        conn.commit()


# Children first. The drafted corrections go too: each cites the ledger row of its check (FK_SUGGESTION_CHECK).
LEDGER_TABLES = ("ANSWER_SUGGESTION", "CLAIM_CITATION", "ANSWER_LEDGER", "CHAIN_HEAD")


def reset_ledger(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> int:
    """DEMO ONLY. Drop and recreate the ledger tables, deleting every recorded decision.

    The ledger is append-only by design: no user can UPDATE or DELETE its rows. This does
    not work around that. As the owner, it drops the three ledger tables outright (their
    triggers go with them), and the change-impact agent's drafted corrections, which cite
    ledger rows, and rebuilds them from the same SQL files, then starts a fresh chain.
    Views, triggers and routines are rebuilt too. Policy clauses, their history and the
    help-centre answers (including approved corrections) are untouched.
    Returns the number of ledger rows that existed before the reset.
    """
    validate_schema(schema)
    db.use_schema(conn, schema)
    before = int(db.query(conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0])
    _drop_code_objects(conn, schema)  # views, triggers and routines are rebuilt by install()
    for table in LEDGER_TABLES:
        db.execute(conn, f"DROP TABLE {db.ident(schema)}.{db.ident(table)}")
    conn.commit()
    install(conn, schema)  # recreates the tables, indexes, triggers and routines that are now missing
    return before
