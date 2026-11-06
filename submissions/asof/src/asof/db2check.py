"""One-command check that this Db2 supports every feature AsOf relies on.

    python -m asof.db2check

It creates a throwaway schema (ASOF_CHECK), exercises each feature with real assertions,
prints PASS or FAIL per check, drops everything it created, and exits non-zero on any
failure. It needs the Db2 owner account (DB2_ADMIN_PASSWORD in .env) because it creates
tables, triggers and procedures. It never touches the ASOF schema.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import ibm_db
import ibm_db_dbi

from . import db
from .config import ConfigError, get_settings

S = "ASOF_CHECK"
DIM = 384

DDL_CLAUSE = f"""
CREATE TABLE {S}.CLAUSE (
  CLAUSE_ID   VARCHAR(32)   NOT NULL,
  CLAUSE_TEXT VARCHAR(4000) NOT NULL,
  RULE_JSON   VARCHAR(2000) NOT NULL CONSTRAINT CK_RULE_JSON CHECK (JSON_EXISTS(RULE_JSON, '$')),
  EMBEDDING   VECTOR({DIM}, FLOAT32),
  BUS_START   DATE NOT NULL,
  BUS_END     DATE NOT NULL,
  SYS_START   TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN,
  SYS_END     TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END,
  TRANS_ID    TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID,
  PERIOD BUSINESS_TIME (BUS_START, BUS_END),
  PERIOD SYSTEM_TIME (SYS_START, SYS_END),
  PRIMARY KEY (CLAUSE_ID, BUSINESS_TIME WITHOUT OVERLAPS)
)"""

DDL_LEDGER = f"""
CREATE TABLE {S}.LEDGER (
  ID        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  DECISION  VARCHAR(12) NOT NULL CONSTRAINT CK_DECISION CHECK (DECISION IN ('PASS', 'CORRECTED', 'ESCALATED')),
  PAYLOAD   VARCHAR(400) NOT NULL,
  PREV_HASH CHAR(64) NOT NULL,
  ROW_HASH  CHAR(64) NOT NULL
)"""

DDL_APPEND = f"""
CREATE OR REPLACE PROCEDURE {S}.APPEND (IN P_DECISION VARCHAR(12), IN P_PAYLOAD VARCHAR(400),
                                        OUT P_ID BIGINT, OUT P_HASH CHAR(64))
LANGUAGE SQL MODIFIES SQL DATA
BEGIN
  DECLARE V_PREV CHAR(64);
  SET V_PREV = COALESCE((SELECT ROW_HASH FROM {S}.LEDGER ORDER BY ID DESC FETCH FIRST 1 ROW ONLY), REPEAT('0', 64));
  SET P_HASH = LOWER(HEX(HASH(V_PREV || '|' || P_PAYLOAD, 2)));
  INSERT INTO {S}.LEDGER (DECISION, PAYLOAD, PREV_HASH, ROW_HASH) VALUES (P_DECISION, P_PAYLOAD, V_PREV, P_HASH);
  SET P_ID = IDENTITY_VAL_LOCAL();
END"""

DDL_LIST = f"""
CREATE OR REPLACE PROCEDURE {S}.LIST_LEDGER ()
LANGUAGE SQL READS SQL DATA DYNAMIC RESULT SETS 1
BEGIN
  DECLARE C1 CURSOR WITH RETURN TO CALLER FOR SELECT ID, DECISION, ROW_HASH FROM {S}.LEDGER ORDER BY ID;
  OPEN C1;
END"""

AS_OF_VECTOR_SQL = (
    "SELECT c.CLAUSE_ID, c.CLAUSE_TEXT, "
    f"VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, {DIM}, FLOAT32), COSINE) AS DIST "
    f"FROM {S}.CLAUSE FOR BUSINESS_TIME AS OF ? AS c ORDER BY DIST FETCH FIRST 5 ROWS ONLY"
)

V1_TEXT = "Bereavement fares must be requested before travel."
V2_TEXT = "Bereavement fares may be requested retroactively within 90 days."


def _vec(seed: int) -> str:
    rng = random.Random(seed)
    v = [rng.uniform(-1, 1) for _ in range(DIM)]
    n = sum(x * x for x in v) ** 0.5
    return db.vector_literal([x / n for x in v])


@dataclass
class Ctx:
    conn: ibm_db_dbi.Connection
    state: dict = field(default_factory=dict)

    def q(self, sql: str, params: tuple = ()) -> list[tuple]:
        return db.query(self.conn, sql, params)

    def x(self, sql: str, params: tuple = ()) -> int:
        return db.execute(self.conn, sql, params)

    def call(self, proc: str, params: tuple) -> tuple:
        cur = self.conn.cursor()
        try:
            return tuple(cur.callproc(proc, params))
        except Exception as exc:  # noqa: BLE001
            raise db.wrap_error(exc, f"CALL {proc} failed") from None
        finally:
            cur.close()

    def call_rows(self, proc: str, params: tuple) -> list[tuple]:
        cur = self.conn.cursor()
        try:
            cur.callproc(proc, params)
            return list(cur.fetchall())
        except Exception as exc:  # noqa: BLE001
            raise db.wrap_error(exc, f"CALL {proc} failed") from None
        finally:
            cur.close()

    def expect_sqlstate(self, sql: str, params: tuple, states: tuple[str, ...]) -> str:
        try:
            self.x(sql, params)
        except db.DatabaseError as exc:
            assert exc.sqlstate in states, f"failed with SQLSTATE {exc.sqlstate}, expected {states}"
            return f"rejected with SQLSTATE {exc.sqlstate}"
        raise AssertionError("statement succeeded but should have been rejected")


def check_version(c: Ctx) -> str:
    info = ibm_db.server_info(c.conn.conn_handler)
    major, minor, mod = (int(p) for p in info.DBMS_VER.split("."))
    assert (major, minor, mod // 100) >= (12, 1, 2), f"{info.DBMS_VER} is older than 12.1.2 (needed for VECTOR)"
    return f"{info.DBMS_NAME} {info.DBMS_VER}"


def check_create_clause(c: Ctx) -> str:
    c.x(DDL_CLAUSE)
    c.conn.commit()  # DDL is transactional in Db2; commit so later rollbacks keep it
    return "BUSINESS_TIME + SYSTEM_TIME periods, VECTOR(384, FLOAT32), JSON check, WITHOUT OVERLAPS key"


def check_history(c: Ctx) -> str:
    c.x(f"CREATE TABLE {S}.CLAUSE_HIST LIKE {S}.CLAUSE")
    c.x(f"ALTER TABLE {S}.CLAUSE ADD VERSIONING USE HISTORY TABLE {S}.CLAUSE_HIST")
    c.conn.commit()
    return "history table created with LIKE, system versioning on"


def check_insert_vectors(c: Ctx) -> str:
    rows = [
        ("BRV-002", V1_TEXT, json.dumps({"retroactive_allowed": False, "request_window_days": 0}), _vec(1), "2026-01-01", "9999-12-31"),
        ("BAG-001", "The first checked bag costs $35.", json.dumps({"first_bag_fee_usd": 35}), _vec(2), "2026-01-01", "9999-12-31"),
    ]
    for r in rows:
        c.x(f"INSERT INTO {S}.CLAUSE (CLAUSE_ID, CLAUSE_TEXT, RULE_JSON, EMBEDDING, BUS_START, BUS_END) "
            f"VALUES (?, ?, ?, VECTOR(?, {DIM}, FLOAT32), ?, ?)", r)
    c.conn.commit()
    return "2 rows inserted with the embedding bound as a parameter"


def check_json_constraint(c: Ctx) -> str:
    out = c.expect_sqlstate(
        f"INSERT INTO {S}.CLAUSE (CLAUSE_ID, CLAUSE_TEXT, RULE_JSON, BUS_START, BUS_END) VALUES (?, ?, ?, ?, ?)",
        ("BAD-001", "x", '{"unterminated": 1', "2026-01-01", "2026-02-01"), ("23513",))
    c.conn.rollback()
    return f"malformed RULE_JSON {out}"


def check_portion_update(c: Ctx) -> str:
    c.state["t_before"] = c.q("SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1")[0][0]
    time.sleep(1.1)
    c.x(f"UPDATE {S}.CLAUSE FOR PORTION OF BUSINESS_TIME FROM ? TO ? "
        f"SET CLAUSE_TEXT = ?, RULE_JSON = ?, EMBEDDING = VECTOR(?, {DIM}, FLOAT32) WHERE CLAUSE_ID = ?",
        ("2026-05-01", "9999-12-31", V2_TEXT, json.dumps({"retroactive_allowed": True, "request_window_days": 90}), _vec(3), "BRV-002"))
    c.conn.commit()
    rows = c.q(f"SELECT BUS_START, BUS_END, CLAUSE_TEXT FROM {S}.CLAUSE WHERE CLAUSE_ID = ? ORDER BY BUS_START", ("BRV-002",))
    assert [(r[0], r[1]) for r in rows] == [(date(2026, 1, 1), date(2026, 5, 1)), (date(2026, 5, 1), date(9999, 12, 31))], rows
    assert rows[0][2] == V1_TEXT and rows[1][2] == V2_TEXT
    return "one row became v1 [2026-01-01, 2026-05-01) and v2 [2026-05-01, open)"


def check_history_row(c: Ctx) -> str:
    rows = c.q(f"SELECT CLAUSE_ID, BUS_END, CLAUSE_TEXT, EMBEDDING IS NOT NULL FROM {S}.CLAUSE_HIST")
    assert rows == [("BRV-002", date(9999, 12, 31), V1_TEXT, True)], rows
    return "pre-update row, including its VECTOR, moved to the history table"


def check_asof_v1(c: Ctx) -> str:
    rows = c.q(AS_OF_VECTOR_SQL, (_vec(1), "2026-03-10"))
    assert rows[0][0] == "BRV-002" and rows[0][1] == V1_TEXT and abs(rows[0][2]) < 1e-5, rows[0]
    return f"2026-03-10 -> v1, nearest first (cosine distance {rows[0][2]:.4f})"


def check_asof_v2(c: Ctx) -> str:
    rows = c.q(AS_OF_VECTOR_SQL, (_vec(1), "2026-06-02"))
    brv = [r for r in rows if r[0] == "BRV-002"]
    assert len(brv) == 1 and brv[0][1] == V2_TEXT, rows
    return "2026-06-02 -> v2 from the same query"


def check_boundary(c: Ctx) -> str:
    sql = f"SELECT CLAUSE_TEXT FROM {S}.CLAUSE FOR BUSINESS_TIME AS OF ? WHERE CLAUSE_ID = ?"
    before = c.q(sql, ("2026-04-30", "BRV-002"))
    on = c.q(sql, ("2026-05-01", "BRV-002"))
    assert before == [(V1_TEXT,)] and on == [(V2_TEXT,)], (before, on)
    return "2026-04-30 -> v1, 2026-05-01 -> v2 (end date is exclusive)"


def check_system_time(c: Ctx) -> str:
    rows = c.q(f"SELECT CLAUSE_TEXT FROM {S}.CLAUSE FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ? WHERE CLAUSE_ID = ?",
               (c.state["t_before"], "2026-06-02", "BRV-002"))
    assert rows == [(V1_TEXT,)], rows
    return "replay: before the change, the database said v1 applied on 2026-06-02"


def check_system_time_vector(c: Ctx) -> str:
    rows = c.q(f"SELECT c.CLAUSE_ID, VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, {DIM}, FLOAT32), COSINE) AS DIST "
               f"FROM {S}.CLAUSE FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ? AS c ORDER BY DIST FETCH FIRST 2 ROWS ONLY",
               (_vec(1), c.state["t_before"], "2026-06-02"))
    assert rows[0][0] == "BRV-002" and abs(rows[0][1]) < 1e-5, rows
    return "SYSTEM_TIME + BUSINESS_TIME + VECTOR_DISTANCE in one query"


def check_json_value(c: Ctx) -> str:
    rows = c.q(f"SELECT BUS_START, JSON_VALUE(RULE_JSON, '$.request_window_days' RETURNING INTEGER), "
               f"JSON_VALUE(RULE_JSON, '$.retroactive_allowed') FROM {S}.CLAUSE WHERE CLAUSE_ID = ? ORDER BY BUS_START", ("BRV-002",))
    assert [(r[1], r[2]) for r in rows] == [(0, "false"), (90, "true")], rows
    return "typed INTEGER and boolean ('true'/'false') extraction"


def check_json_table(c: Ctx) -> str:
    rows = c.q(f"SELECT j.DAYS FROM {S}.CLAUSE c, JSON_TABLE(c.RULE_JSON, 'strict $' COLUMNS (DAYS INTEGER PATH '$.request_window_days') "
               f"ERROR ON ERROR) AS j WHERE c.CLAUSE_ID = ? ORDER BY j.DAYS", ("BRV-002",))
    assert rows == [(0,), (90,)], rows
    return "rule parameters as relational columns"


def check_json_exists(c: Ctx) -> str:
    rows = c.q(f"SELECT CLAUSE_ID FROM {S}.CLAUSE WHERE JSON_EXISTS(RULE_JSON, '$.first_bag_fee_usd')")
    assert rows == [("BAG-001",)], rows
    return "filter rows by rule parameter presence"


def check_sha256_unicode(c: Ctx) -> str:
    s = "ledger|2026-03-10|café"
    got = c.q("SELECT LOWER(HEX(HASH(CAST(? AS VARCHAR(200) CCSID UNICODE), 2))) FROM SYSIBM.SYSDUMMY1", (s,))[0][0]
    assert got == hashlib.sha256(s.encode("utf-8")).hexdigest(), got
    return "HASH(expr, 2) equals Python SHA-256 for UTF-8 text"


def check_sha256_param(c: Ctx) -> str:
    s = "prev|PASS|payload"
    got = c.q("SELECT LOWER(HEX(HASH(?, 2))) FROM SYSIBM.SYSDUMMY1", (s,))[0][0]
    assert got == hashlib.sha256(s.encode("utf-8")).hexdigest(), got
    return "HASH(?, 2) on a bound parameter"


def check_ledger_table(c: Ctx) -> str:
    c.x(DDL_LEDGER)
    c.x(f"CREATE TRIGGER {S}.LEDGER_NO_UPDATE BEFORE UPDATE ON {S}.LEDGER FOR EACH ROW "
        "SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'Ledger rows are append-only'")
    c.x(f"CREATE TRIGGER {S}.LEDGER_NO_DELETE BEFORE DELETE ON {S}.LEDGER FOR EACH ROW "
        "SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'Ledger rows are append-only'")
    c.conn.commit()
    return "identity key, CHECK constraint, BEFORE UPDATE and BEFORE DELETE triggers"


def check_check_constraint(c: Ctx) -> str:
    out = c.expect_sqlstate(f"INSERT INTO {S}.LEDGER (DECISION, PAYLOAD, PREV_HASH, ROW_HASH) VALUES (?, ?, ?, ?)",
                            ("MAYBE", "x", "0" * 64, "0" * 64), ("23513",))
    c.conn.rollback()
    return f"DECISION outside the enum {out}"


def check_procedure(c: Ctx) -> str:
    c.x(DDL_APPEND)
    c.x(DDL_LIST)
    c.conn.commit()
    return "SQL PL procedures with OUT parameters and a dynamic result set"


def check_hash_chain(c: Ctx) -> str:
    _, _, id1, h1 = c.call(f"{S}.APPEND", ("PASS", "first", 0, ""))
    _, _, id2, h2 = c.call(f"{S}.APPEND", ("ESCALATED", "second", 0, ""))
    c.conn.commit()
    zero = "0" * 64
    assert h1 == hashlib.sha256(f"{zero}|first".encode()).hexdigest()
    assert h2 == hashlib.sha256(f"{h1}|second".encode()).hexdigest()
    assert id2 == id1 + 1
    return "each row hash covers the previous row hash, computed inside Db2"


def check_trigger_update(c: Ctx) -> str:
    out = c.expect_sqlstate(f"UPDATE {S}.LEDGER SET PAYLOAD = ?", ("tampered",), ("75001",))
    c.conn.rollback()
    return f"UPDATE {out}"


def check_trigger_delete(c: Ctx) -> str:
    out = c.expect_sqlstate(f"DELETE FROM {S}.LEDGER WHERE ID > ?", (0,), ("75001",))
    c.conn.rollback()
    return f"DELETE {out}"


def check_result_set(c: Ctx) -> str:
    rows = c.call_rows(f"{S}.LIST_LEDGER", ())
    assert [r[1] for r in rows] == ["PASS", "ESCALATED"], rows
    return "CALL returns rows to the Python driver"


def check_vector_serialize(c: Ctx) -> str:
    text = c.q(f"SELECT VECTOR_SERIALIZE(EMBEDDING) FROM {S}.CLAUSE WHERE CLAUSE_ID = ?", ("BAG-001",))[0][0]
    values = json.loads(text)
    assert len(values) == DIM
    return f"VECTOR read back as {DIM} floats"


def check_injection_text(c: Ctx) -> str:
    payload = "'); DROP TABLE ASOF_CHECK.CLAUSE; --"
    c.call(f"{S}.APPEND", ("PASS", payload, 0, ""))
    c.conn.commit()
    stored = c.q(f"SELECT PAYLOAD FROM {S}.LEDGER ORDER BY ID DESC FETCH FIRST 1 ROW ONLY")[0][0]
    still_there = c.q(f"SELECT COUNT(*) FROM {S}.CLAUSE")[0][0]
    assert stored == payload and still_there > 0
    return "SQL in a parameter is stored as plain text"


CHECKS: list[tuple[str, Callable[[Ctx], str]]] = [
    ("Db2 version supports VECTOR", check_version),
    ("Bitemporal table with VECTOR column", check_create_clause),
    ("System versioning with history table", check_history),
    ("Insert embeddings as parameters", check_insert_vectors),
    ("JSON check constraint", check_json_constraint),
    ("FOR PORTION OF BUSINESS_TIME update", check_portion_update),
    ("History keeps old version and vector", check_history_row),
    ("As-of date + vector search (March)", check_asof_v1),
    ("As-of date + vector search (June)", check_asof_v2),
    ("Version boundary is exact", check_boundary),
    ("FOR SYSTEM_TIME AS OF replay", check_system_time),
    ("Replay + vector search", check_system_time_vector),
    ("JSON_VALUE", check_json_value),
    ("JSON_TABLE", check_json_table),
    ("JSON_EXISTS", check_json_exists),
    ("SHA-256 in SQL (Unicode)", check_sha256_unicode),
    ("SHA-256 on a parameter", check_sha256_param),
    ("Append-only ledger table and triggers", check_ledger_table),
    ("CHECK constraint on decision", check_check_constraint),
    ("SQL PL stored procedures", check_procedure),
    ("Hash chain via stored procedure", check_hash_chain),
    ("Trigger blocks UPDATE", check_trigger_update),
    ("Trigger blocks DELETE", check_trigger_delete),
    ("Procedure result set", check_result_set),
    ("VECTOR_SERIALIZE", check_vector_serialize),
    ("SQL injection stored as text", check_injection_text),
]

CLEANUP = [
    f"DROP PROCEDURE {S}.APPEND",
    f"DROP PROCEDURE {S}.LIST_LEDGER",
    f"DROP TRIGGER {S}.LEDGER_NO_UPDATE",
    f"DROP TRIGGER {S}.LEDGER_NO_DELETE",
    f"DROP TABLE {S}.LEDGER",
    f"ALTER TABLE {S}.CLAUSE DROP VERSIONING",
    f"DROP TABLE {S}.CLAUSE_HIST",
    f"DROP TABLE {S}.CLAUSE",
    f"DROP SCHEMA {S} RESTRICT",
]


def _cleanup(conn: ibm_db_dbi.Connection) -> None:
    """Drop everything the check created. Missing objects are fine; each step stands alone."""
    for stmt in CLEANUP:
        try:
            db.execute(conn, stmt)
            conn.commit()
        except db.DatabaseError:
            conn.rollback()


def run() -> int:
    settings = get_settings()
    try:
        conn = db.connect(settings, "admin")
    except (ConfigError, db.DatabaseError) as exc:
        print(f"FAIL  cannot start: {exc}")
        return 2
    ctx = Ctx(conn)
    results: list[tuple[str, bool, str]] = []
    try:
        _cleanup(conn)  # leftovers from an interrupted earlier run
        for name, fn in CHECKS:
            try:
                detail = fn(ctx)
                results.append((name, True, detail))
            except Exception as exc:  # noqa: BLE001 - one failing check must not stop the rest
                conn.rollback()
                results.append((name, False, str(exc) or type(exc).__name__))
            mark = "PASS" if results[-1][1] else "FAIL"
            print(f"{mark}  {name}: {results[-1][2]}", flush=True)
    finally:
        _cleanup(conn)
        leftover = db.query(conn, "SELECT COUNT(*) FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?", (S,))[0][0]
        conn.close()
    passed = sum(ok for _, ok, _ in results)
    cleanup = f"Schema {S} was removed." if leftover == 0 else f"WARNING: schema {S} is still present."
    print(f"\n{passed}/{len(results)} Db2 feature checks passed. {cleanup}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run())
