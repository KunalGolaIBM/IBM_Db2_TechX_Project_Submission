"""Change ledger: a system-period temporal table that records every change reDB makes."""
from __future__ import annotations

import re
from typing import Any

DDL = [
    """CREATE TABLE REDB.CHANGES (
  CHANGE_ID INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  KIND VARCHAR(20) NOT NULL, TITLE VARCHAR(400), STMT_TEXT VARCHAR(8000),
  DDL VARCHAR(4000), UNDO_DDL VARCHAR(4000), STATUS VARCHAR(20) NOT NULL,
  COST_BEFORE DOUBLE, COST_AFTER DOUBLE, MS_BEFORE DOUBLE, MS_AFTER DOUBLE,
  RATIONALE VARCHAR(8000), APPROVED_BY VARCHAR(128),
  SYS_START TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN,
  SYS_END TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END,
  TRANS_ID TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID,
  PERIOD SYSTEM_TIME (SYS_START, SYS_END)) IN REDB_TS32""",
    "CREATE TABLE REDB.CHANGES_HISTORY LIKE REDB.CHANGES IN REDB_TS32",
    "ALTER TABLE REDB.CHANGES ADD VERSIONING USE HISTORY TABLE REDB.CHANGES_HISTORY",
]

_ID = r'"[A-Z0-9_#@$]+"'
UNDO_OK = re.compile(rf'^(DROP INDEX {_ID}\.{_ID}|CREATE INDEX {_ID}\.{_ID} ON {_ID}\.{_ID} '
                     rf'\({_ID} (ASC|DESC)(, {_ID} (ASC|DESC))*\))$')

COLS = ("CHANGE_ID, KIND, TITLE, STMT_TEXT, DDL, UNDO_DDL, STATUS, COST_BEFORE, COST_AFTER, "
        "MS_BEFORE, MS_AFTER, RATIONALE, APPROVED_BY, CHAR(SYS_START) AS SYS_START, CHAR(SYS_END) AS SYS_END")


def _clip(s: Any, n: int) -> Any:
    return s[:n] if isinstance(s, str) else s


def record(db, kind: str, title: str, stmt_text: str, ddl: str, undo_ddl: str, status: str,
           cost_before: float | None = None, cost_after: float | None = None,
           ms_before: float | None = None, rationale: str = "", approved_by: str = "") -> int:
    return int(db.scalar(
        """SELECT CHANGE_ID FROM FINAL TABLE (INSERT INTO REDB.CHANGES
           (KIND, TITLE, STMT_TEXT, DDL, UNDO_DDL, STATUS, COST_BEFORE, COST_AFTER, MS_BEFORE, RATIONALE, APPROVED_BY)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?))""",
        (kind, _clip(title, 400), _clip(stmt_text, 8000), _clip(ddl, 4000), _clip(undo_ddl, 4000), status,
         cost_before, cost_after, ms_before, _clip(rationale, 8000), _clip(approved_by, 128))))


def set_status(db, change_id: int, status: str, ms_after: float | None = None) -> None:
    if ms_after is None:
        db.execute("UPDATE REDB.CHANGES SET STATUS = ? WHERE CHANGE_ID = ?", (status, change_id))
    else:
        db.execute("UPDATE REDB.CHANGES SET STATUS = ?, MS_AFTER = ? WHERE CHANGE_ID = ?",
                   (status, ms_after, change_id))


def current(db) -> list[dict[str, Any]]:
    return db.query(f"SELECT {COLS} FROM REDB.CHANGES ORDER BY CHANGE_ID DESC")


def timeline(db) -> list[dict[str, Any]]:
    return db.query(f"""SELECT {COLS} FROM REDB.CHANGES
        FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-31' ORDER BY CHANGE_ID, SYS_START""")


def as_of(db, ts: str) -> list[dict[str, Any]]:
    return db.query(f"SELECT {COLS} FROM REDB.CHANGES FOR SYSTEM_TIME AS OF TIMESTAMP(CAST(? AS VARCHAR(40))) ORDER BY CHANGE_ID",
                    (ts,))


def rollback(db, change_id: int) -> str:
    rows = db.query("SELECT STATUS, UNDO_DDL FROM REDB.CHANGES WHERE CHANGE_ID = ?", (change_id,))
    if not rows:
        raise ValueError(f"change {change_id} not found")
    status, undo = rows[0]["STATUS"], rows[0]["UNDO_DDL"]
    if status != "APPLIED":
        raise ValueError(f"change {change_id} is {status}, only APPLIED changes can be rolled back")
    stmts = [x.strip() for x in (undo or "").split("\n") if x.strip()]
    bad = [x for x in stmts if not UNDO_OK.match(x)]
    if bad:  # undo text is stored data: only ever run the exact index DDL shapes reDB generates
        raise ValueError(f"refusing to run unexpected undo statement: {bad[0]!r}")
    for stmt in stmts:
        db.execute(stmt)
    set_status(db, change_id, "ROLLED_BACK")
    return undo or ""
