"""The runtime connection pool: reuse, isolation between borrowers, and recovery from dead connections.

Unit tests use fake connections; the last test (marked db2) uses real ones.
"""

from __future__ import annotations

import pytest

from asof import db
from asof.config import Settings


class FakeConn:
    def __init__(self, n: int):
        self.n, self.closed, self.rollbacks, self.dead = n, False, 0, False

    def cursor(self):
        conn = self

        class Cursor:
            def execute(self, sql, params=()):
                if conn.dead or conn.closed:
                    raise RuntimeError("SQL30081N  A communication error has been detected. SQLSTATE=08001")

            def fetchall(self):
                return [(1,)]

            def close(self):
                pass

        return Cursor()

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@pytest.fixture
def opened(monkeypatch):
    made: list[FakeConn] = []

    def fake_connect(settings, role="app", autocommit=False):
        made.append(FakeConn(len(made)))
        return made[-1]

    monkeypatch.setattr(db, "connect", fake_connect)
    return made


def test_a_returned_connection_is_rolled_back_and_reused(opened):
    pool = db.ConnectionPool(Settings(_env_file=None))
    first = pool.connect()
    raw = first.raw
    first.close()
    first.close()  # closing twice is harmless
    second = pool.connect()
    assert second.raw is raw and raw.rollbacks == 1 and pool.opened == 1 and len(opened) == 1
    with pytest.raises(db.DatabaseError, match="already returned"):
        first.cursor()  # the old handle cannot touch the connection someone else now holds


def test_concurrent_borrowers_get_different_connections_and_the_idle_set_is_capped(opened):
    pool = db.ConnectionPool(Settings(_env_file=None), size=2)
    held = [pool.connect() for _ in range(3)]
    assert len({h.raw.n for h in held}) == 3
    raws = [h.raw for h in held]
    for h in held:
        h.close()
    assert [r.closed for r in raws] == [False, False, True]  # the third did not fit and was closed
    pool.close()
    assert all(r.closed for r in raws)


def test_a_dead_idle_connection_is_dropped_and_replaced_not_handed_out(opened):
    pool = db.ConnectionPool(Settings(_env_file=None))
    c = pool.connect()
    c.raw.dead = True  # Db2 restarted while it sat idle
    dead = c.raw
    c.close()
    fresh = pool.connect()
    assert fresh.raw is not dead and dead.closed and pool.opened == 2


@pytest.mark.db2
def test_the_pool_reuses_real_connections_and_survives_one_killed_underneath(settings, test_schema):
    pool = db.ConnectionPool(settings)
    try:
        c = pool.connect()
        db.use_schema(c, test_schema)
        assert db.query(c, "SELECT COUNT(*) FROM POLICY_CLAUSE")[0][0] > 0
        raw = c.raw
        c.close()
        raw.close()  # the server side goes away while the connection is idle in the pool
        c = pool.connect()
        db.use_schema(c, test_schema)  # a new connection: its registers are set again
        assert db.query(c, "SELECT COUNT(*) FROM POLICY_CLAUSE")[0][0] > 0 and pool.opened == 2
        c.close()
    finally:
        pool.close()
