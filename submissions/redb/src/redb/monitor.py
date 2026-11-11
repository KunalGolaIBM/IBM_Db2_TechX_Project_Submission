"""Observe: read Db2's in-memory monitoring (MON_GET_*) and catalog health."""
from __future__ import annotations

import re
from typing import Any

TOP_SQL = """SELECT HEX(EXECUTABLE_ID) AS EXEC_ID, NUM_EXECUTIONS, STMT_EXEC_TIME,
 TOTAL_CPU_TIME, ROWS_READ, ROWS_RETURNED,
 CAST(SUBSTR(STMT_TEXT,1,8000) AS VARCHAR(8000)) AS STMT_TEXT
FROM TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)) T
WHERE NUM_EXECUTIONS > 0 ORDER BY STMT_EXEC_TIME DESC FETCH FIRST 200 ROWS ONLY"""

INTERNAL_MARKERS = ("/*REDB*/", "MON_GET", "EXPLAIN", "SYSCAT", "SYSIBM.SYSDUMMY1")

BUFFERPOOL_SQL = """SELECT SUM(POOL_DATA_L_READS + POOL_INDEX_L_READS) AS L,
 SUM(POOL_DATA_P_READS + POOL_INDEX_P_READS) AS P
FROM TABLE(MON_GET_BUFFERPOOL('', -2)) B"""

TABLE_SQL = """SELECT TABNAME, SUM(TABLE_SCANS) AS TABLE_SCANS, SUM(ROWS_READ) AS ROWS_READ,
 SUM(ROWS_INSERTED + ROWS_UPDATED + ROWS_DELETED) AS ROWS_WRITTEN
FROM TABLE(MON_GET_TABLE(?, '', -2)) T GROUP BY TABNAME ORDER BY 3 DESC"""

UNUSED_INDEX_SQL = """SELECT I.TABNAME, I.INDNAME, I.COLNAMES, M.INDEX_SCANS, M.INDEX_ONLY_SCANS
FROM TABLE(MON_GET_INDEX(?, '', -2)) M
JOIN SYSCAT.INDEXES I ON I.TABSCHEMA = M.TABSCHEMA AND I.TABNAME = M.TABNAME AND I.IID = M.IID
WHERE I.UNIQUERULE = 'D' AND M.INDEX_SCANS = 0 AND M.INDEX_ONLY_SCANS = 0"""

STALE_SQL = """SELECT TABNAME, CARD, STATS_TIME FROM SYSCAT.TABLES
WHERE TABSCHEMA = ? AND TYPE = 'T' AND (STATS_TIME IS NULL OR CARD < 0)"""


def is_candidate(stmt_text: str, schema: str) -> bool:
    t = stmt_text.strip()
    up = t.upper()
    if not re.match(r"^\(*\s*(SELECT|WITH)\b", up):
        return False
    if any(m in up for m in INTERNAL_MARKERS):
        return False
    return f"{schema.upper()}." in up


def shape_statement(row: dict[str, Any]) -> dict[str, Any]:
    n = int(row["NUM_EXECUTIONS"] or 0)
    exec_ms = float(row["STMT_EXEC_TIME"] or 0)
    rr, ret = int(row["ROWS_READ"] or 0), int(row["ROWS_RETURNED"] or 0)
    return {
        "exec_id": row["EXEC_ID"],
        "sql": row["STMT_TEXT"].strip(),
        "executions": n,
        "total_ms": exec_ms,
        "avg_ms": exec_ms / n if n else 0.0,
        "cpu_us": int(row["TOTAL_CPU_TIME"] or 0),
        "rows_read": rr,
        "rows_returned": ret,
        "read_per_returned": rr / max(ret, 1),
    }


def write_pct(rows_read, rows_written) -> float:
    """Share of a table's row activity that is writes (index maintenance cost signal)."""
    r, w = float(rows_read or 0), float(rows_written or 0)
    return round(100 * w / (r + w), 1) if r + w else 0.0


def top_statements(db, schema: str, limit: int = 10) -> list[dict[str, Any]]:
    rows = db.query(TOP_SQL)
    out = [shape_statement(r) for r in rows if is_candidate(r["STMT_TEXT"] or "", schema)]
    return out[:limit]


def health(db, schema: str) -> dict[str, Any]:
    bp = db.query(BUFFERPOOL_SQL)[0]
    logical, physical = float(bp["L"] or 0), float(bp["P"] or 0)
    hit = 100.0 * (1 - physical / logical) if logical else 100.0
    tables = db.query(TABLE_SQL, (schema,))
    return {
        "bufferpool_hit_pct": round(hit, 2),
        "tables": [{"table": t["TABNAME"].strip(), "table_scans": int(t["TABLE_SCANS"] or 0),
                    "rows_read": int(t["ROWS_READ"] or 0), "rows_written": int(t["ROWS_WRITTEN"] or 0),
                    "write_pct": write_pct(t["ROWS_READ"], t["ROWS_WRITTEN"])} for t in tables],
        "table_scans": sum(int(t["TABLE_SCANS"] or 0) for t in tables),
        "unused_indexes": [{"table": r["TABNAME"].strip(), "index": r["INDNAME"].strip(), "colnames": r["COLNAMES"]}
                           for r in db.query(UNUSED_INDEX_SQL, (schema,))],
        "stale_tables": [r["TABNAME"] for r in db.query(STALE_SQL, (schema,))],
    }
