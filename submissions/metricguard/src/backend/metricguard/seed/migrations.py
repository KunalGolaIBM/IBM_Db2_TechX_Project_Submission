"""Idempotent, non-destructive schema migrations and least-privilege grants.

`metricguard db migrate` applies these to an existing database without dropping or
reloading anything. `metricguard db init` applies them after creating the base schema.
"""

from __future__ import annotations

from typing import Callable

from metricguard.config import Settings
from metricguard.db import Db2Client

SCHEMA = "METRICGUARD"
Log = Callable[[str], None]

# Audit columns (all nullable: adding them needs no REORG and keeps existing rows valid).
AUDIT_COLUMNS: list[tuple[str, str]] = [
    ("EXECUTION_MODE", "VARCHAR(24)"),     # LLM | DEMO_RULE_BASED
    ("PLANNER_MODEL", "VARCHAR(80)"),      # e.g. claude-sonnet-5-5; NULL for the rule planner
    ("METRIC_DEFS_JSON", "CLOB(64K)"),     # [{ref, definition_hash, db2_hash_match}]
    ("ANSWER_SUMMARY", "VARCHAR(2000)"),   # deterministic template summary
]


def migrate_audit_table(db: Db2Client, log: Log) -> list[str]:
    existing = {
        r[0].strip()
        for r in db.query(
            "SELECT COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TABNAME = 'QUERY_AUDIT_LOG'", (SCHEMA,)
        ).rows
    }
    added = []
    for name, sql_type in AUDIT_COLUMNS:
        if name not in existing:
            db.execute(f"ALTER TABLE {SCHEMA}.QUERY_AUDIT_LOG ADD COLUMN {name} {sql_type}")
            added.append(name)
    if db.scalar("SELECT COUNT(*) FROM SYSCAT.CHECKS WHERE TABSCHEMA = ? AND CONSTNAME = 'CK_AUDIT_MODE'",
                 (SCHEMA,)) == 0:
        db.execute(f"ALTER TABLE {SCHEMA}.QUERY_AUDIT_LOG ADD CONSTRAINT CK_AUDIT_MODE CHECK "
                   "(EXECUTION_MODE IS NULL OR EXECUTION_MODE IN ('LLM', 'DEMO_RULE_BASED'))")
        added.append("CK_AUDIT_MODE")
    if db.scalar("SELECT COUNT(*) FROM SYSCAT.INDEXES WHERE TABSCHEMA = ? AND INDNAME = 'IX_AUDIT_CREATED'",
                 (SCHEMA,)) == 0:
        db.execute(f"CREATE INDEX {SCHEMA}.IX_AUDIT_CREATED ON {SCHEMA}.QUERY_AUDIT_LOG (CREATED_AT DESC)")
        added.append("IX_AUDIT_CREATED")
    log(f"audit table migration: {'added ' + ', '.join(added) if added else 'already up to date'}")
    return added


def grant_audit_writer(db: Db2Client, settings: Settings, log: Log) -> bool:
    """CONNECT + INSERT/SELECT on QUERY_AUDIT_LOG only. No UPDATE or DELETE: the log is append-only."""
    user = settings.db2_audit_user
    if not user:
        log("no DB2_AUDIT_USER configured; audit writes will use the admin connection")
        return False
    user = user.upper()
    db.execute(f"GRANT CONNECT ON DATABASE TO USER {user}")
    db.execute(f"GRANT INSERT, SELECT ON {SCHEMA}.QUERY_AUDIT_LOG TO USER {user}")
    log(f"granted CONNECT + INSERT, SELECT on {SCHEMA}.QUERY_AUDIT_LOG to {user} (no UPDATE/DELETE, "
        "no business tables)")
    return True


def privileges(db: Db2Client) -> list[dict[str, str]]:
    """Table privileges held by non-owner principals on the METRICGUARD schema (for evidence)."""
    rows = db.query(
        "SELECT GRANTEE, TABNAME, SELECTAUTH, INSERTAUTH, UPDATEAUTH, DELETEAUTH, ALTERAUTH, CONTROLAUTH "
        "FROM SYSCAT.TABAUTH WHERE TABSCHEMA = ? AND GRANTEE <> 'DB2INST1' ORDER BY GRANTEE, TABNAME", (SCHEMA,)
    ).rows
    out = []
    for r in rows:
        privs = [p for p, flag in zip(["SELECT", "INSERT", "UPDATE", "DELETE", "ALTER", "CONTROL"], r[2:])
                 if flag.strip() in ("Y", "G")]
        out.append({"grantee": r[0].strip(), "table": r[1].strip(), "privileges": ",".join(privs)})
    return out
