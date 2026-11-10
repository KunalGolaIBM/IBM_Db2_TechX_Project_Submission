"""Exercises Db2Gateway / Db2Repository code paths (parameter conversion, guard, writers, readers)
through a SQLite-backed stand-in for the ``ibm_db_dbi`` DB-API module. This checks our Python code, not Db2 itself."""
import json
import re
import sqlite3
import sys
import types

import pytest

from time_machine.config import Settings
from time_machine.db import Db2Gateway, _to_qmark
from time_machine.repository import Db2Repository
from time_machine.sql_guard import UnsafeSQL


class _Conn:
    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.create_function("VARCHAR_FORMAT", 2, lambda v, f: v)

    def cursor(self):
        outer = self

        class Cur:
            def __init__(self):
                self.c = outer.db.cursor()

            def execute(self, sql, params=()):
                if sql.strip().upper().startswith("SET CURRENT SCHEMA"):
                    return
                sql = re.sub(r"FETCH FIRST (\d+) ROWS ONLY", r"LIMIT \1", sql)
                self.c.execute(sql, params)

            @property
            def description(self):
                return self.c.description

            def fetchall(self):
                return self.c.fetchall()

            def close(self):
                self.c.close()

        return Cur()

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def close(self):
        self.db.close()


@pytest.fixture()
def gateway(monkeypatch, tmp_path):
    conn = _Conn()
    shim = types.SimpleNamespace(connect=lambda *a, **k: conn)
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", shim)
    gw = Db2Gateway(Settings(db_password="x"))
    script = tmp_path / "schema.sql"
    script.write_text("""
-- comment only block
--#
CREATE TABLE PRODUCTS (PRODUCT_ID INTEGER, NAME TEXT, CATEGORY TEXT)
--#
CREATE TABLE AUDIT_LOG (LOG_ID INTEGER PRIMARY KEY AUTOINCREMENT, RUN_ID TEXT, SEQ INTEGER, AGENT TEXT, ACTION TEXT,
  SQL_TEXT TEXT, ROW_COUNT INTEGER, LATENCY_MS REAL, OUTCOME TEXT DEFAULT 'ok', DETAIL TEXT, CREATED_AT TEXT DEFAULT CURRENT_TIMESTAMP)
--#
CREATE TABLE INCIDENT_REPORTS (RUN_ID TEXT PRIMARY KEY, QUESTION TEXT, PRODUCT_NAME TEXT, STATUS TEXT, ROOT_CAUSE TEXT,
  ACTOR TEXT, IMPACT TEXT, CREATED_AT TEXT DEFAULT CURRENT_TIMESTAMP, REPORT_JSON TEXT)
""")
    assert gw.run_script(script) == 3
    return gw


def test_named_to_qmark_conversion_keeps_timestamp_colons():
    sql, args = _to_qmark("SELECT 1 WHERE A = :a AND B = ':x' AND TS = '10:00:00' AND C = :c", {"a": 1, "c": 2})
    assert sql.count("?") == 2 and args == (1, 2) and "':x'" in sql and "10:00:00" in sql


def test_read_is_guarded(gateway):
    with pytest.raises(UnsafeSQL):
        gateway.read("DELETE FROM PRODUCTS")
    with pytest.raises(UnsafeSQL):
        gateway.read("SELECT * FROM PASSWORDS")


def test_writers_and_readers_round_trip(gateway):
    gateway.execute("INSERT INTO PRODUCTS VALUES (:a, :b, :c)", {"a": 1, "b": "Aurora Laptop", "c": "Computers"})
    repo = Db2Repository(gateway)
    assert repo.products() == [{"product_id": 1, "name": "Aurora Laptop", "category": "Computers"}]

    repo.write_audit({"run_id": "abc123", "seq": 1, "agent": "detective", "action": "scope", "sql": "SELECT 1",
                      "rows": 3, "ms": 4.2, "outcome": "ok", "detail": "x" * 5000})
    rows = repo.list_audit("abc123")
    assert rows[0]["agent"] == "detective" and len(rows[0]["detail"]) == 800  # long details are truncated

    report = {"run_id": "abc123", "question": "why?", "product_name": "Aurora Laptop",
              "verdict": {"status": "confirmed", "pattern": "price_change"},
              "root_cause": {"actor": "nightly_batch", "impact": "-9450.00"}}
    repo.save_report(report)
    assert repo.get_report("abc123") == json.loads(json.dumps(report))
    assert repo.list_reports()[0]["status"] == "confirmed"
    assert repo.get_report("nope") is None


def test_run_id_cannot_inject(gateway):
    with pytest.raises(ValueError):
        Db2Repository(gateway).list_audit("x' OR '1'='1")


def test_failed_statement_is_rolled_back_and_reported(gateway, tmp_path):
    bad = tmp_path / "bad.sql"
    bad.write_text("CREATE TABLE T1 (A INTEGER)\n--#\nTHIS IS NOT SQL\n")
    with pytest.raises(RuntimeError, match="statement failed"):
        gateway.run_script(bad)
    assert gateway.run_script(bad, ignore_errors=True) == 0  # table already exists, junk ignored
