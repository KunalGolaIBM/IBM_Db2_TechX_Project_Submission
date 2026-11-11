"""A scriptable fake ``ibm_db_dbi`` for adapter tests (no Db2, no network).

``script`` is an ordered list of ``(needle, outcome)``: the FIRST needle found
in an executed statement decides the result. ``outcome`` is either an
exception instance (raised) or ``{"columns": [...], "rows": [...]}``.
"""

from __future__ import annotations

import sys
import types
import uuid

import pytest

from app.core.config import Settings


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self._conn = conn
        self.description = None
        self.lastrowid = 7
        self._rows: list[tuple] = []

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        for needle, outcome in self._conn.script:
            if needle in sql:
                if isinstance(outcome, BaseException):
                    raise outcome
                self.description = [(c,) for c in outcome["columns"]]
                self._rows = list(outcome["rows"])
                return
        self.description = None
        self._rows = []

    def fetchmany(self, n):
        out, self._rows = self._rows[:n], self._rows[n:]
        return out

    def fetchall(self):
        out, self._rows = self._rows, []
        return out


class FakeConnection:
    def __init__(self, script):
        self.script = script
        self.executed: list[tuple] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True

    def statements(self) -> list[str]:
        return [sql for sql, _ in self.executed]


def install_fake_dbi(monkeypatch) -> types.SimpleNamespace:
    ctl = types.SimpleNamespace(script=[], connections=[], connect_error=None)

    def connect(dsn, user, password):
        if ctl.connect_error:
            raise ctl.connect_error
        conn = FakeConnection(ctl.script)
        ctl.connections.append(conn)
        return conn

    module = types.ModuleType("ibm_db_dbi")
    module.connect = connect
    monkeypatch.setitem(sys.modules, "ibm_db_dbi", module)
    monkeypatch.setitem(sys.modules, "ibm_db", types.ModuleType("ibm_db"))
    return ctl


def real_settings(**overrides) -> Settings:
    base = dict(
        _env_file=None,
        adapter_mode="real",
        db2_ro_password="pw-" + uuid.uuid4().hex,  # throwaway, per run
        sql_max_rows=3,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def dbi(monkeypatch):
    return install_fake_dbi(monkeypatch)
