"""All relational Db2 access. Every value is bound as a parameter (qmark style)."""

from __future__ import annotations

from typing import Any, Iterable

from config import Settings


def connect(settings: Settings):
    """Open an ibm_db_dbi connection to Db2."""
    import ibm_db_dbi  # imported lazily so offline unit tests need no driver

    return ibm_db_dbi.connect(settings.dsn, "", "")


def ensure_schema(conn, settings: Settings) -> None:
    """Create the relational tables and indexes if they are missing."""
    statements = [
        f"""CREATE TABLE IF NOT EXISTS {settings.kb_table} (
                SQLCODE     VARCHAR(12)  NOT NULL PRIMARY KEY,
                SQLSTATE    CHAR(5),
                TITLE       VARCHAR(200) NOT NULL,
                CAUSE       VARCHAR(2000) NOT NULL,
                FIX         VARCHAR(2000) NOT NULL,
                EXAMPLE_SQL VARCHAR(1000)
            )""",
        f"""CREATE TABLE IF NOT EXISTS {settings.log_table} (
                ID            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                ASKED_AT      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ERROR_TEXT    VARCHAR(2000) NOT NULL,
                PARSED_CODE   VARCHAR(12),
                MATCHED_CODE  VARCHAR(12),
                MATCH_TYPE    VARCHAR(10) NOT NULL,
                DISTANCE      DOUBLE
            )""",
    ]
    cur = conn.cursor()
    try:
        for ddl in statements:
            cur.execute(ddl)
        # Index for the per-code analytics in `stats`.
        cur.execute(
            "SELECT 1 FROM SYSCAT.INDEXES WHERE INDNAME = ? AND TABNAME = ?",
            (f"{settings.log_table}_CODE_IX"[:128], settings.log_table),
        )
        if cur.fetchone() is None:
            cur.execute(
                f"CREATE INDEX {settings.log_table}_CODE_IX "
                f"ON {settings.log_table} (MATCHED_CODE, ASKED_AT)"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def replace_kb(conn, settings: Settings, entries: Iterable[dict[str, Any]]) -> int:
    """Reload the relational knowledge base in one transaction."""
    rows = [
        (e["sqlcode"], e.get("sqlstate"), e["title"], e["cause"], e["fix"], e.get("example_sql"))
        for e in entries
    ]
    cur = conn.cursor()
    try:
        cur.execute(f"DELETE FROM {settings.kb_table}")
        cur.executemany(
            f"INSERT INTO {settings.kb_table} "
            "(SQLCODE, SQLSTATE, TITLE, CAUSE, FIX, EXAMPLE_SQL) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
    return len(rows)


def lookup_code(conn, settings: Settings, sqlcode: str) -> dict[str, Any] | None:
    """Exact primary-key lookup of a parsed SQLCODE."""
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT SQLCODE, SQLSTATE, TITLE, CAUSE, FIX, EXAMPLE_SQL "
            f"FROM {settings.kb_table} WHERE SQLCODE = ?",
            (sqlcode,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
    if row is None:
        return None
    keys = ("sqlcode", "sqlstate", "title", "cause", "fix", "example_sql")
    return dict(zip(keys, row))


def log_query(
    conn,
    settings: Settings,
    error_text: str,
    parsed_code: str | None,
    matched_code: str | None,
    match_type: str,
    distance: float | None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            f"INSERT INTO {settings.log_table} "
            "(ERROR_TEXT, PARSED_CODE, MATCHED_CODE, MATCH_TYPE, DISTANCE) VALUES (?, ?, ?, ?, ?)",
            (error_text[:2000], parsed_code, matched_code, match_type, distance),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def top_errors(conn, settings: Settings, limit: int = 10) -> list[tuple]:
    """Most frequently diagnosed errors, joined back to the knowledge base."""
    limit = max(1, min(int(limit), 50))
    cur = conn.cursor()
    try:
        cur.execute(
            f"""SELECT l.MATCHED_CODE, k.TITLE, COUNT(*) AS HITS,
                       MAX(l.ASKED_AT) AS LAST_SEEN
                FROM {settings.log_table} l
                LEFT JOIN {settings.kb_table} k ON k.SQLCODE = l.MATCHED_CODE
                WHERE l.MATCHED_CODE IS NOT NULL
                GROUP BY l.MATCHED_CODE, k.TITLE
                ORDER BY HITS DESC, LAST_SEEN DESC
                FETCH FIRST {limit} ROWS ONLY"""
        )
        return cur.fetchall()
    finally:
        cur.close()
