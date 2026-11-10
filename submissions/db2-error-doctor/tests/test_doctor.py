"""Offline tests: no Db2, no model download. Db2 is replaced by a recording fake."""

from types import SimpleNamespace

import pytest

import db
import doctor
from config import ConfigError, Settings, _identifier, load_settings
from kb import InputError, clean_input, entry_text, load_entries, parse_sqlcode

KB_COLUMNS = ("sqlcode", "sqlstate", "title", "cause", "fix", "example_sql")


def make_settings(**overrides):
    values = dict(
        host="localhost", port=50000, database="testdb", user="db2inst1", password="pw",
        security=False, vector_table="DOCTOR_KB_VECTORS", kb_table="DOCTOR_KB",
        log_table="DOCTOR_QUERY_LOG", embedding_model="m", llm_provider="none",
        ollama_model="llama3.2", ollama_base_url="http://localhost:11434",
    )
    values.update(overrides)
    return Settings(**values)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._row = None

    def execute(self, sql, params=()):
        self.conn.executed.append((sql, tuple(params)))
        self._row = None
        if "WHERE SQLCODE = ?" in sql:
            entry = self.conn.kb.get(params[0])
            if entry:
                self._row = tuple(entry.get(k) for k in KB_COLUMNS)

    def executemany(self, sql, rows):
        self.conn.executed.append((sql, tuple(rows)))

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConn:
    def __init__(self):
        self.kb = {e["sqlcode"]: e for e in load_entries()}
        self.executed = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class FakeStore:
    def __init__(self, code):
        self.code = code
        self.calls = 0

    def similarity_search_with_score(self, query, k=3):
        self.calls += 1
        return [(SimpleNamespace(metadata={"sqlcode": self.code}), 0.1234)]


@pytest.mark.parametrize(
    "text, expected",
    [
        ('SQL0204N "DB2INST1.ORDERS" is an undefined name. SQLSTATE=42704', "-204"),
        ("ibm_db_dbi::ProgrammingError: SQLCODE=-803, SQLSTATE=23505", "-803"),
        ("[IBM][CLI Driver] SQL30082N Security processing failed", "-30082"),
        ("sqlcode: -911", "-911"),
        ("SQLCODE=100", "100"),
        ("my insert keeps saying the key already exists", None),
    ],
)
def test_parse_sqlcode(text, expected):
    assert parse_sqlcode(text) == expected


def test_knowledge_base_is_well_formed():
    entries = load_entries()
    assert len(entries) >= 30
    assert len({e["sqlcode"] for e in entries}) == len(entries)
    assert "SQLCODE -204" in entry_text(next(e for e in entries if e["sqlcode"] == "-204"))


@pytest.mark.parametrize("bad", ["", "  ", "ab", "x" * 2001, None])
def test_clean_input_rejects_bad_text(bad):
    with pytest.raises(InputError):
        clean_input(bad)


def test_clean_input_strips_control_characters():
    assert clean_input("  SQL0204N\x00\x1b bad  ") == "SQL0204N bad"


@pytest.mark.parametrize("bad", ["LOG; DROP TABLE X", "1ABC", "a-b", ""])
def test_table_names_are_allow_listed(bad):
    with pytest.raises(ConfigError):
        _identifier("DOCTOR_LOG_TABLE", bad)


def test_missing_password_is_a_config_error(monkeypatch):
    monkeypatch.setattr("config.load_dotenv", lambda: None)
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    with pytest.raises(ConfigError):
        load_settings()


def test_dsn_adds_ssl_only_when_enabled():
    assert "SECURITY=SSL" not in make_settings().dsn
    assert "SECURITY=SSL" in make_settings(security=True).dsn


def test_exact_match_skips_vector_search_and_logs():
    conn, store = FakeConn(), FakeStore("-803")
    result = doctor.diagnose(conn, make_settings(), store, "SQL0204N TABLE1 is an undefined name")
    assert result.match_type == "exact"
    assert result.matches[0]["sqlcode"] == "-204"
    assert store.calls == 0
    log_sql, log_params = conn.executed[-1]
    assert "INSERT INTO DOCTOR_QUERY_LOG" in log_sql
    assert log_params[1:4] == ("-204", "-204", "exact")


def test_vector_fallback_when_no_code_in_text():
    conn, store = FakeConn(), FakeStore("-803")
    result = doctor.diagnose(conn, make_settings(), store, "insert says the key already exists")
    assert result.match_type == "vector"
    assert result.matches[0]["sqlcode"] == "-803"
    assert result.matches[0]["distance"] == 0.1234
    assert "Db2 vector search" in doctor.format_diagnosis(result)


def test_user_text_is_never_concatenated_into_sql():
    conn = FakeConn()
    hostile = "x'; DROP TABLE DOCTOR_KB; -- SQL0204N"
    doctor.diagnose(conn, make_settings(), FakeStore("-204"), hostile)
    assert all("DROP TABLE" not in sql for sql, _ in conn.executed)
    assert any(hostile in params for _, params in conn.executed)


def test_llm_failure_does_not_break_diagnosis():
    def boom(error, matches):
        raise RuntimeError("model offline")

    result = doctor.diagnose(
        FakeConn(), make_settings(), FakeStore("-204"), "SQLCODE=-911", explain=boom
    )
    assert result.match_type == "exact"
    assert "unavailable" in result.explanation


def test_replace_kb_uses_parameter_markers():
    conn = FakeConn()
    assert db.replace_kb(conn, make_settings(), load_entries()) == len(conn.kb)
    assert conn.executed[-1][0].count("?") == 6
    assert conn.commits == 1
