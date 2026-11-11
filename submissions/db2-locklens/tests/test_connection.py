import logging

from locklens.config import Settings
from locklens.db.connection import (Db2Connection, build_connection_string, classify_connection_error,
                                    parse_db2_error)
from locklens.errors import Db2ConnectionError, Db2PermissionError, Db2QueryError
from locklens.logging_setup import RedactingFilter

import pytest


def settings(**kw):
    env = {"DB2_PASSWORD": "pw", "DB2_HOST": "db.local", "DB2_DATABASE": "testdb", "DB2_USER": "u"}
    env.update(kw)
    return Settings.from_env(env)


def test_parse_sqlcode_and_state():
    assert parse_db2_error("[IBM] SQL30082N Security processing failed SQLSTATE=08001") == (30082, "08001")
    assert parse_db2_error("no code here") == (None, None)


def test_classification_of_connection_failures():
    assert classify_connection_error(Exception('SQL30082N reason "24" ("USERNAME AND/OR PASSWORD INVALID")')).kind == "invalid_credentials"
    assert classify_connection_error(Exception("SQL1013N The database alias name was not found")).kind == "database_not_found"
    assert classify_connection_error(Exception("SQL30081N A communication error ... Connection refused")).kind == "unreachable"
    assert classify_connection_error(Exception("connection timed out")).kind == "timeout"
    assert classify_connection_error(Exception("weird")).kind == "unknown"


def test_error_messages_do_not_leak_passwords():
    err = classify_connection_error(Exception("failed DATABASE=x;PWD=hunter2;UID=u"))
    assert "hunter2" not in str(err)


def test_connection_string_quotes_special_characters():
    cs = build_connection_string(settings(DB2_PASSWORD="p;w=}x"))
    assert "PWD={p;w=}}x};" in cs and "CONNECTTIMEOUT=15" in cs and "SECURITY" not in cs
    assert "SECURITY=SSL" in build_connection_string(settings(DB2_SECURITY="true"))


def test_redacting_filter_masks_secrets_in_log_records():
    f = RedactingFilter(["hunter2"])
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "conn PWD=abc and hunter2 here", (), None)
    f.filter(rec)
    assert "abc" not in rec.msg and "hunter2" not in rec.msg


class FakeDriver:
    SQL_AUTOCOMMIT_ON = 1

    def __init__(self, connect_error=None, execute_error=None):
        self.connect_error, self.execute_error = connect_error, execute_error
        self.freed, self.closed, self.rows = 0, 0, [{"a": 1}]

    def connect(self, cs, u, p):
        if self.connect_error:
            raise self.connect_error
        return "conn"

    def autocommit(self, c, v): pass
    def active(self, c): return c == "conn"
    def close(self, c): self.closed += 1
    def prepare(self, c, sql): return {"it": iter(self.rows)}

    def execute(self, stmt, params=None):
        if self.execute_error:
            raise self.execute_error
        return True

    def num_fields(self, s): return 1
    def field_name(self, s, i): return "a"
    def fetch_assoc(self, s): return next(s["it"], False)
    def free_stmt(self, s): self.freed += 1
    def num_rows(self, s): return 3


def test_connect_failure_is_classified_not_raw():
    conn = Db2Connection(settings(), FakeDriver(connect_error=Exception("SQL30082N bad")))
    with pytest.raises(Db2ConnectionError) as err:
        conn.connect()
    assert err.value.kind == "invalid_credentials"


def test_query_returns_upper_case_rows_and_frees_statement():
    d = FakeDriver()
    conn = Db2Connection(settings(), d)
    cols, rows = conn.query_with_columns("SELECT 1 FROM T")
    assert cols == ["A"] and rows == [{"A": 1}] and d.freed == 1
    assert conn.execute("UPDATE x SET y = ?", (1,)) == 3 and d.freed == 2
    conn.close()
    assert d.closed == 1 and not conn.is_alive()


def test_permission_and_generic_query_errors_are_typed_and_statement_freed():
    conn = Db2Connection(settings(), FakeDriver(execute_error=Exception("SQL0551N no privilege")))
    with pytest.raises(Db2PermissionError):
        conn.query("SELECT 1 FROM T")
    conn2 = Db2Connection(settings(), FakeDriver(execute_error=Exception("SQL0104N syntax")))
    with pytest.raises(Db2QueryError) as err:
        conn2.query("SELECT")
    assert not isinstance(err.value, Db2PermissionError) and err.value.sqlcode == 104
    assert conn2._driver.freed == 1
