"""One-command check that this Db2 supports every feature AsOf relies on.

    python -m asof.db2check

It creates a throwaway schema (ASOF_CHECK), exercises each feature with real assertions
(every statement is a literal; the schema is bound with SET CURRENT SCHEMA = ?),
prints PASS or FAIL per check, drops everything it created, and exits non-zero on any
failure. It needs the Db2 owner account (DB2_USER / DB2_PASSWORD in .env) because it creates
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
from typing import Any

import ibm_db
import ibm_db_dbi

from . import db
from .config import ConfigError, get_settings

S = "ASOF_CHECK"
DIM = 384

DDL_CLAUSE = """
CREATE TABLE CLAUSE (
  CLAUSE_ID   VARCHAR(32)   NOT NULL,
  CLAUSE_TEXT VARCHAR(4000) NOT NULL,
  RULE_JSON   VARCHAR(2000) NOT NULL CONSTRAINT CK_RULE_JSON CHECK (JSON_EXISTS(RULE_JSON, '$')),
  EMBEDDING   VECTOR(384, FLOAT32),
  BUS_START   DATE NOT NULL,
  BUS_END     DATE NOT NULL,
  SYS_START   TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN,
  SYS_END     TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END,
  TRANS_ID    TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID,
  PERIOD BUSINESS_TIME (BUS_START, BUS_END),
  PERIOD SYSTEM_TIME (SYS_START, SYS_END),
  PRIMARY KEY (CLAUSE_ID, BUSINESS_TIME WITHOUT OVERLAPS)
)"""

DDL_LEDGER = """
CREATE TABLE LEDGER (
  ID        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  DECISION  VARCHAR(12) NOT NULL CONSTRAINT CK_DECISION CHECK (DECISION IN ('PASS', 'CORRECTED', 'ESCALATED')),
  PAYLOAD   VARCHAR(400) NOT NULL,
  PREV_HASH CHAR(64) NOT NULL,
  ROW_HASH  CHAR(64) NOT NULL
)"""

DDL_APPEND = """
CREATE OR REPLACE PROCEDURE APPEND (IN P_DECISION VARCHAR(12), IN P_PAYLOAD VARCHAR(400),
                                        OUT P_ID BIGINT, OUT P_HASH CHAR(64))
LANGUAGE SQL MODIFIES SQL DATA
BEGIN
  DECLARE V_PREV CHAR(64);
  SET V_PREV = COALESCE((SELECT ROW_HASH FROM LEDGER ORDER BY ID DESC FETCH FIRST 1 ROW ONLY), REPEAT('0', 64));
  SET P_HASH = LOWER(HEX(HASH(V_PREV || '|' || P_PAYLOAD, 2)));
  INSERT INTO LEDGER (DECISION, PAYLOAD, PREV_HASH, ROW_HASH) VALUES (P_DECISION, P_PAYLOAD, V_PREV, P_HASH);
  SET P_ID = IDENTITY_VAL_LOCAL();
END"""

DDL_LIST = """
CREATE OR REPLACE PROCEDURE LIST_LEDGER ()
LANGUAGE SQL READS SQL DATA DYNAMIC RESULT SETS 1
BEGIN
  DECLARE C1 CURSOR WITH RETURN TO CALLER FOR SELECT ID, DECISION, ROW_HASH FROM LEDGER ORDER BY ID;
  OPEN C1;
END"""

AS_OF_VECTOR_SQL = (
    "SELECT c.CLAUSE_ID, c.CLAUSE_TEXT, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM CLAUSE FOR BUSINESS_TIME AS OF ? AS c ORDER BY DIST FETCH FIRST 5 ROWS ONLY"
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
    state: dict[str, Any] = field(default_factory=dict)

    def q(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        return db.query(self.conn, sql, params)

    def x(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        return db.execute(self.conn, sql, params)

    def call(self, proc: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
        cur = self.conn.cursor()
        try:
            return tuple(cur.callproc(proc, params))
        except Exception as exc:  # noqa: BLE001
            raise db.wrap_error(exc, f"CALL {proc} failed") from None
        finally:
            cur.close()

    def call_rows(self, proc: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        cur = self.conn.cursor()
        try:
            cur.callproc(proc, params)
            return list(cur.fetchall())
        except Exception as exc:  # noqa: BLE001
            raise db.wrap_error(exc, f"CALL {proc} failed") from None
        finally:
            cur.close()

    def expect_sqlstate(self, sql: str, params: tuple[Any, ...], states: tuple[str, ...]) -> str:
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
    c.x("CREATE TABLE CLAUSE_HIST LIKE CLAUSE")
    c.x("ALTER TABLE CLAUSE ADD VERSIONING USE HISTORY TABLE CLAUSE_HIST")
    c.conn.commit()
    return "history table created with LIKE, system versioning on"


def check_insert_vectors(c: Ctx) -> str:
    rows = [
        ("BRV-002", V1_TEXT, json.dumps({"retroactive_allowed": False, "request_window_days": 0}), _vec(1),
         "2026-01-01", "9999-12-31"),
        ("BAG-001", "The first checked bag costs $35.", json.dumps({"first_bag_fee_usd": 35}), _vec(2),
         "2026-01-01", "9999-12-31"),
    ]
    for r in rows:
        c.x("INSERT INTO CLAUSE (CLAUSE_ID, CLAUSE_TEXT, RULE_JSON, EMBEDDING, BUS_START, BUS_END) "
            "VALUES (?, ?, ?, VECTOR(?, 384, FLOAT32), ?, ?)", r)
    c.conn.commit()
    return "2 rows inserted with the embedding bound as a parameter"


def check_json_constraint(c: Ctx) -> str:
    out = c.expect_sqlstate(
        "INSERT INTO CLAUSE (CLAUSE_ID, CLAUSE_TEXT, RULE_JSON, BUS_START, BUS_END) VALUES (?, ?, ?, ?, ?)",
        ("BAD-001", "x", '{"unterminated": 1', "2026-01-01", "2026-02-01"), ("23513",))
    c.conn.rollback()
    return f"malformed RULE_JSON {out}"


def check_portion_update(c: Ctx) -> str:
    c.state["t_before"] = c.q("SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1")[0][0]
    time.sleep(1.1)
    c.x("UPDATE CLAUSE FOR PORTION OF BUSINESS_TIME FROM ? TO ? "
        "SET CLAUSE_TEXT = ?, RULE_JSON = ?, EMBEDDING = VECTOR(?, 384, FLOAT32) WHERE CLAUSE_ID = ?",
        ("2026-05-01", "9999-12-31", V2_TEXT, json.dumps({"retroactive_allowed": True, "request_window_days": 90}),
         _vec(3), "BRV-002"))
    c.conn.commit()
    rows = c.q("SELECT BUS_START, BUS_END, CLAUSE_TEXT FROM CLAUSE WHERE CLAUSE_ID = ? ORDER BY BUS_START", ("BRV-002",))
    assert [(r[0], r[1]) for r in rows] == [(date(2026, 1, 1), date(2026, 5, 1)), (date(2026, 5, 1), date(9999, 12, 31))], rows
    assert rows[0][2] == V1_TEXT and rows[1][2] == V2_TEXT
    return "one row became v1 [2026-01-01, 2026-05-01) and v2 [2026-05-01, open)"


def check_history_row(c: Ctx) -> str:
    rows = c.q("SELECT CLAUSE_ID, BUS_END, CLAUSE_TEXT, EMBEDDING IS NOT NULL FROM CLAUSE_HIST")
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
    sql = "SELECT CLAUSE_TEXT FROM CLAUSE FOR BUSINESS_TIME AS OF ? WHERE CLAUSE_ID = ?"
    before = c.q(sql, ("2026-04-30", "BRV-002"))
    on = c.q(sql, ("2026-05-01", "BRV-002"))
    assert before == [(V1_TEXT,)] and on == [(V2_TEXT,)], (before, on)
    return "2026-04-30 -> v1, 2026-05-01 -> v2 (end date is exclusive)"


def check_system_time(c: Ctx) -> str:
    rows = c.q("SELECT CLAUSE_TEXT FROM CLAUSE FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ? WHERE CLAUSE_ID = ?",
               (c.state["t_before"], "2026-06-02", "BRV-002"))
    assert rows == [(V1_TEXT,)], rows
    return "replay: before the change, the database said v1 applied on 2026-06-02"


def check_system_time_vector(c: Ctx) -> str:
    rows = c.q("SELECT c.CLAUSE_ID, VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
               "FROM CLAUSE FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ? AS c ORDER BY DIST FETCH FIRST 2 ROWS ONLY",
               (_vec(1), c.state["t_before"], "2026-06-02"))
    assert rows[0][0] == "BRV-002" and abs(rows[0][1]) < 1e-5, rows
    return "SYSTEM_TIME + BUSINESS_TIME + VECTOR_DISTANCE in one query"


def check_json_value(c: Ctx) -> str:
    rows = c.q("SELECT BUS_START, JSON_VALUE(RULE_JSON, '$.request_window_days' RETURNING INTEGER), "
               "JSON_VALUE(RULE_JSON, '$.retroactive_allowed') FROM CLAUSE WHERE CLAUSE_ID = ? ORDER BY BUS_START", ("BRV-002",))
    assert [(r[1], r[2]) for r in rows] == [(0, "false"), (90, "true")], rows
    return "typed INTEGER and boolean ('true'/'false') extraction"


def check_json_table(c: Ctx) -> str:
    rows = c.q("SELECT j.DAYS FROM CLAUSE c, "
               "JSON_TABLE(c.RULE_JSON, 'strict $' COLUMNS (DAYS INTEGER PATH '$.request_window_days') "
               "ERROR ON ERROR) AS j WHERE c.CLAUSE_ID = ? ORDER BY j.DAYS", ("BRV-002",))
    assert rows == [(0,), (90,)], rows
    return "rule parameters as relational columns"


def check_json_exists(c: Ctx) -> str:
    rows = c.q("SELECT CLAUSE_ID FROM CLAUSE WHERE JSON_EXISTS(RULE_JSON, '$.first_bag_fee_usd')")
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
    c.x("CREATE TRIGGER LEDGER_NO_UPDATE BEFORE UPDATE ON LEDGER FOR EACH ROW "
        "SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'Ledger rows are append-only'")
    c.x("CREATE TRIGGER LEDGER_NO_DELETE BEFORE DELETE ON LEDGER FOR EACH ROW "
        "SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'Ledger rows are append-only'")
    c.conn.commit()
    return "identity key, CHECK constraint, BEFORE UPDATE and BEFORE DELETE triggers"


def check_check_constraint(c: Ctx) -> str:
    out = c.expect_sqlstate("INSERT INTO LEDGER (DECISION, PAYLOAD, PREV_HASH, ROW_HASH) VALUES (?, ?, ?, ?)",
                            ("MAYBE", "x", "0" * 64, "0" * 64), ("23513",))
    c.conn.rollback()
    return f"DECISION outside the enum {out}"


def check_procedure(c: Ctx) -> str:
    c.x(DDL_APPEND)
    c.x(DDL_LIST)
    c.conn.commit()
    return "SQL PL procedures with OUT parameters and a dynamic result set"


def check_hash_chain(c: Ctx) -> str:
    _, _, id1, h1 = c.call("APPEND", ("PASS", "first", 0, ""))
    _, _, id2, h2 = c.call("APPEND", ("ESCALATED", "second", 0, ""))
    c.conn.commit()
    zero = "0" * 64
    assert h1 == hashlib.sha256(f"{zero}|first".encode()).hexdigest()
    assert h2 == hashlib.sha256(f"{h1}|second".encode()).hexdigest()
    assert id2 == id1 + 1
    return "each row hash covers the previous row hash, computed inside Db2"


def check_trigger_update(c: Ctx) -> str:
    out = c.expect_sqlstate("UPDATE LEDGER SET PAYLOAD = ?", ("tampered",), ("75001",))
    c.conn.rollback()
    return f"UPDATE {out}"


def check_trigger_delete(c: Ctx) -> str:
    out = c.expect_sqlstate("DELETE FROM LEDGER WHERE ID > ?", (0,), ("75001",))
    c.conn.rollback()
    return f"DELETE {out}"


def check_result_set(c: Ctx) -> str:
    rows = c.call_rows("LIST_LEDGER", ())
    assert [r[1] for r in rows] == ["PASS", "ESCALATED"], rows
    return "CALL returns rows to the Python driver"


def check_vector_serialize(c: Ctx) -> str:
    text = c.q("SELECT VECTOR_SERIALIZE(EMBEDDING) FROM CLAUSE WHERE CLAUSE_ID = ?", ("BAG-001",))[0][0]
    values = json.loads(text)
    assert len(values) == DIM
    return "VECTOR read back as 384 floats"


def check_vector_index(c: Ctx) -> str:
    # A 384-dim FLOAT32 key is 1,536 bytes, more than a 4K page allows, so the index needs a
    # 32K tablespace. These are the same shared storage objects AsOf's setup creates.
    for kind, name, ddl in (
        ("BUFFERPOOLS", "ASOF_BP32K", "CREATE BUFFERPOOL ASOF_BP32K SIZE AUTOMATIC PAGESIZE 32K"),
        ("TABLESPACES", "ASOF_TS32K", "CREATE TABLESPACE ASOF_TS32K PAGESIZE 32K MANAGED BY AUTOMATIC STORAGE "
                                      "BUFFERPOOL ASOF_BP32K"),
    ):
        exists = c.q("SELECT COUNT(*) FROM SYSCAT.BUFFERPOOLS WHERE BPNAME = ?", (name,)) if kind == "BUFFERPOOLS" \
            else c.q("SELECT COUNT(*) FROM SYSCAT.TABLESPACES WHERE TBSPACE = ?", (name,))
        if exists[0][0] == 0:
            c.x(ddl)
            c.conn.commit()
    c.x("CREATE TABLE VEC (ID INT NOT NULL PRIMARY KEY, EMBEDDING VECTOR(384, FLOAT32) NOT NULL) IN ASOF_TS32K")
    c.conn.commit()
    for i in range(20):
        c.x("INSERT INTO VEC (ID, EMBEDDING) VALUES (?, VECTOR(?, 384, FLOAT32))", (i, _vec(1000 + i)))
    c.conn.commit()
    c.x("CREATE VECTOR INDEX VEC_ANN ON VEC (EMBEDDING) WITH DISTANCE COSINE")
    c.conn.commit()
    kind = c.q("SELECT INDEXTYPE FROM SYSCAT.INDEXES WHERE INDSCHEMA = CURRENT SCHEMA AND INDNAME = 'VEC_ANN'")[0][0]
    assert kind.strip() == "VANN", f"index type {kind!r}"
    exact = [r[0] for r in c.q("SELECT ID FROM VEC ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) "
                               "FETCH EXACT FIRST 3 ROWS ONLY", (_vec(1005),))]
    approx = c.q("SELECT ID FROM VEC ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) "
                 "FETCH APPROX FIRST 3 ROWS ONLY", (_vec(1005),))
    assert exact[0] == 5 and len(approx) == 3
    return "CREATE VECTOR INDEX (type VANN) in a 32K tablespace; FETCH EXACT and FETCH APPROX both answer"


def check_indb_ai_functions(c: Ctx) -> str:
    # Db2 12.1.5 adds CREATE EXTERNAL MODEL, TO_EMBEDDING and TEXT_GENERATION. Calling them with a
    # model that does not exist must fail with "undefined name" (42704), not "unknown function".
    for fn in ("VALUES TO_EMBEDDING(CAST('x' AS VARCHAR(10)) USING ASOF_CHECK.NO_SUCH_MODEL)",
               "VALUES TEXT_GENERATION(CAST('x' AS VARCHAR(10)) USING ASOF_CHECK.NO_SUCH_MODEL)"):
        try:
            c.q(fn)
        except db.DatabaseError as exc:
            assert exc.sqlstate == "42704", f"{fn.split('(')[0]} failed with SQLSTATE {exc.sqlstate}"
            continue
        raise AssertionError("a call to a missing model succeeded")
    c.q("SELECT COUNT(*) FROM SYSCAT.EXTERNALMODELS")
    return "TO_EMBEDDING, TEXT_GENERATION and SYSCAT.EXTERNALMODELS present (setup registers the model)"


def check_injection_text(c: Ctx) -> str:
    payload = "'); DROP TABLE ASOF_CHECK.CLAUSE; --"
    c.call("APPEND", ("PASS", payload, 0, ""))
    c.conn.commit()
    stored = c.q("SELECT PAYLOAD FROM LEDGER ORDER BY ID DESC FETCH FIRST 1 ROW ONLY")[0][0]
    still_there = c.q("SELECT COUNT(*) FROM CLAUSE")[0][0]
    assert stored == payload and still_there > 0
    return "SQL in a parameter is stored as plain text"


def check_column_mask(c: Ctx) -> str:
    # RCAC needs SECURED triggers on the table (else SQL20469N reason code 37); both need SECADM.
    c.x("ALTER TRIGGER LEDGER_NO_UPDATE SECURED")
    c.x("ALTER TRIGGER LEDGER_NO_DELETE SECURED")
    c.x("CREATE OR REPLACE MASK M_PAYLOAD ON LEDGER FOR COLUMN PAYLOAD RETURN CASE "
        "WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') = 1 THEN PAYLOAD ELSE '[masked]' END ENABLE")
    c.x("ALTER TABLE LEDGER ACTIVATE COLUMN ACCESS CONTROL")
    c.conn.commit()
    shown = {r[0] for r in c.q("SELECT PAYLOAD FROM LEDGER")}
    assert shown == {"[masked]"}, shown  # the owner holds no ASOF_TEXT_READER role
    counted = c.q("SELECT COUNT(*) FROM LEDGER WHERE PAYLOAD = ?", ("first",))[0][0]
    assert counted == 1, counted  # masks apply to values returned, not to predicates
    return "owner reads '[masked]'; predicates still see the real value (why Ask the ledger refuses them)"


DDL_PARTITIONED = """
CREATE TABLE PLEDGER (
  ID         BIGINT        NOT NULL PRIMARY KEY,
  CREATED_AT TIMESTAMP(12) NOT NULL,
  DECISION   VARCHAR(12)   NOT NULL,
  LATENCY_MS INTEGER       NOT NULL
) PARTITION BY RANGE (CREATED_AT) (
    PARTITION P_BEFORE STARTING MINVALUE ENDING '2026-01-01-00.00.00' EXCLUSIVE,
    STARTING '2026-01-01-00.00.00' ENDING '2027-01-01-00.00.00' EXCLUSIVE EVERY 1 MONTH,
    PARTITION P_AFTER STARTING '2027-01-01-00.00.00' ENDING MAXVALUE)"""
DDL_MQT = """
CREATE TABLE PSTATS AS (SELECT DECISION, COUNT(*) AS DECISIONS, SUM(BIGINT(LATENCY_MS)) AS LATENCY_SUM
                        FROM PLEDGER GROUP BY DECISION)
  DATA INITIALLY DEFERRED REFRESH IMMEDIATE ENABLE QUERY OPTIMIZATION MAINTAINED BY SYSTEM"""


def check_range_partitions(c: Ctx) -> str:
    c.x(DDL_PARTITIONED)
    rows = [(1, "2025-06-01-00.00.00", "PASS", 40), (2, "2026-03-15-12.00.00", "PASS", 60),
            (3, "2026-03-20-08.00.00", "ESCALATED", 7), (4, "2031-01-01-00.00.00", "PASS", 5)]
    for r in rows:
        c.x("INSERT INTO PLEDGER (ID, CREATED_AT, DECISION, LATENCY_MS) VALUES (?, ?, ?, ?)", r)
    c.conn.commit()
    parts = c.q("SELECT COUNT(*) FROM SYSCAT.DATAPARTITIONS WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = 'PLEDGER'")[0][0]
    assert parts == 14, parts
    where = c.q("SELECT ID, DATAPARTITIONNUM(CREATED_AT) FROM PLEDGER ORDER BY ID")
    assert where[1][1] == where[2][1] and len({p for _, p in where}) == 3, where
    return "12 monthly partitions plus two open-ended ones; March rows share a partition, 2025 and 2031 have their own"


def check_mqt_refresh_immediate(c: Ctx) -> str:
    c.x(DDL_MQT)
    c.conn.commit()
    c.expect_sqlstate("INSERT INTO PLEDGER (ID, CREATED_AT, DECISION, LATENCY_MS) VALUES (?, ?, ?, ?)",
                      (5, "2026-04-01-00.00.00", "PASS", 1), ("57007",))  # pending until refreshed
    c.conn.rollback()
    c.x("REFRESH TABLE PSTATS")
    c.conn.commit()
    c.x("INSERT INTO PLEDGER (ID, CREATED_AT, DECISION, LATENCY_MS) VALUES (?, ?, ?, ?)", (5, "2026-04-01-00.00.00", "PASS", 1))
    c.conn.commit()
    got = c.q("SELECT DECISION, DECISIONS, LATENCY_SUM FROM PSTATS ORDER BY DECISION")
    assert [tuple(r) for r in got] == [("ESCALATED", 1, 7), ("PASS", 4, 106)], got
    return "inserts refused until REFRESH TABLE (SQL0668N); then Db2 updates the MQT in the insert's own transaction"


def check_mqt_over_masked_table(c: Ctx) -> str:
    # LEDGER has column access control (check_column_mask): an MQT over it gets row access control with no
    # permission, so it hides every row until one is created.
    c.x("CREATE TABLE LSTATS AS (SELECT DECISION, COUNT(*) AS N FROM LEDGER GROUP BY DECISION) "
        "DATA INITIALLY DEFERRED REFRESH IMMEDIATE")
    c.x("REFRESH TABLE LSTATS")
    c.conn.commit()
    hidden = c.q("SELECT COUNT(*) FROM LSTATS")[0][0]
    c.x("CREATE OR REPLACE PERMISSION P_LSTATS ON LSTATS FOR ROWS WHERE 1 = 1 ENFORCED FOR ALL ACCESS ENABLE")
    c.conn.commit()
    shown = c.q("SELECT COUNT(*) FROM LSTATS")[0][0]
    assert hidden == 0 and shown == 2, (hidden, shown)
    return "0 rows visible until a row permission is created, then 2 (why AsOf gives each MQT one)"


def check_one_open_row_per_key(c: Ctx) -> str:
    # CORRECTION_NOTICE's rule: at most one open (PENDING or SENT) notice per answer and version, any number of
    # rejected ones. A generated column is non-null only while open; the unique index skips the null keys.
    c.x("CREATE TABLE NOTICE (ID BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY, ANSWER BIGINT NOT NULL, "
        "STATUS VARCHAR(12) NOT NULL DEFAULT 'PENDING', OPEN_KEY VARCHAR(40) GENERATED ALWAYS AS "
        "(CASE WHEN STATUS IN ('PENDING', 'SENT') THEN RTRIM(CHAR(ANSWER)) END))")
    c.x("CREATE UNIQUE INDEX UX_NOTICE ON NOTICE (OPEN_KEY) EXCLUDE NULL KEYS")
    c.conn.commit()
    c.x("INSERT INTO NOTICE (ANSWER) VALUES (7)")
    refused = c.expect_sqlstate("INSERT INTO NOTICE (ANSWER) VALUES (7)", (), ("23505",))
    c.conn.rollback()
    c.x("INSERT INTO NOTICE (ANSWER) VALUES (7)")
    c.x("UPDATE NOTICE SET STATUS = 'REJECTED' WHERE ANSWER = 7")
    c.x("INSERT INTO NOTICE (ANSWER) VALUES (7)")  # a rejected one makes way
    c.x("UPDATE NOTICE SET STATUS = 'REJECTED' WHERE ANSWER = 7 AND STATUS = 'PENDING'")
    c.x("INSERT INTO NOTICE (ANSWER) VALUES (7)")
    rows = c.q("SELECT STATUS, COUNT(*) FROM NOTICE GROUP BY STATUS ORDER BY STATUS")
    c.conn.commit()
    assert [(r[0].strip(), r[1]) for r in rows] == [("PENDING", 1), ("REJECTED", 2)], rows
    return f"a second open row {refused}; two rejected rows and one open row coexist (CORRECTION_NOTICE's rule)"


def check_nearest_per_group(c: Ctx) -> str:
    # The router's vote: ROW_NUMBER() OVER (PARTITION BY ...) over the as-of + vector query, in one statement.
    rows = c.q("SELECT R.GRP, R.CLAUSE_ID FROM (SELECT D.GRP, D.CLAUSE_ID, ROW_NUMBER() OVER (PARTITION BY D.GRP "
               "ORDER BY D.DIST) AS RN FROM (SELECT SUBSTR(c.CLAUSE_ID, 1, 3) AS GRP, c.CLAUSE_ID, "
               "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
               "FROM CLAUSE FOR BUSINESS_TIME AS OF ? AS c) D) R WHERE R.RN = 1 ORDER BY R.GRP",
               (_vec(1), date(2026, 3, 10)))
    assert rows and all(r[1].startswith(r[0]) for r in rows), rows
    return f"nearest clause per group, as of 2026-03-10, in one statement ({len(rows)} group{'s' if len(rows) != 1 else ''})"


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
    ("Native vector index (VANN)", check_vector_index),
    ("In-database AI functions (12.1.5)", check_indb_ai_functions),
    ("SQL injection stored as text", check_injection_text),
    ("Column mask (RCAC) with SECURED triggers", check_column_mask),
    ("Monthly range partitions", check_range_partitions),
    ("REFRESH IMMEDIATE materialized query table", check_mqt_refresh_immediate),
    ("MQT over a masked table needs a row permission", check_mqt_over_masked_table),
    ("One open row per key (generated column, EXCLUDE NULL KEYS)", check_one_open_row_per_key),
    ("Nearest row per group with a window function over the as-of + vector query", check_nearest_per_group),
]

CLEANUP = [
    "DROP TABLE NOTICE",
    "DROP TABLE LSTATS",
    "DROP TABLE PSTATS",
    "DROP TABLE PLEDGER",
    "DROP TABLE VEC",
    "DROP PROCEDURE APPEND",
    "DROP PROCEDURE LIST_LEDGER",
    "DROP TRIGGER LEDGER_NO_UPDATE",
    "DROP TRIGGER LEDGER_NO_DELETE",
    "DROP TABLE LEDGER",
    "ALTER TABLE CLAUSE DROP VERSIONING",
    "DROP TABLE CLAUSE_HIST",
    "DROP TABLE CLAUSE",
    f"DROP SCHEMA {db.ident(S)} RESTRICT",
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
    db.use_schema(conn, S)  # every statement below is a literal with unqualified names
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
