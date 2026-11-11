"""Trusted context, without a database: the Db2 IDs API users map to, the settings, the pool's per-request switch,
and the API handing each request's user to the pool. tests/test_db2_trusted.py runs it against Db2."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_api import FakeAssistant, FakeGate
from test_api_users import AUDITOR, CHECKER, DIRECTORY, bearer

from asof import api, db, trusted
from asof.config import Settings


@pytest.mark.parametrize("name, authid", [("maria", "API_MARIA"), ("maria.lopez", "API_MARIA_LOPEZ"),
                                          ("ops-1", "API_OPS_1"), ("db2inst1", "API_DB2INST1")])
def test_api_users_get_their_own_prefixed_db2_ids(name, authid):
    assert trusted.authid(name) == authid  # never the owner's or a service account's ID


@pytest.mark.parametrize("address, ok", [("172.17.0.1", True), ("::1", True), ("10.0.0.300", False),
                                         ("172.17.0.1'; DROP", False), ("", False)])
def test_only_an_ip_address_reaches_the_context_ddl(address, ok):
    if ok:
        assert trusted.check_address(address) == address
    else:
        with pytest.raises(trusted.TrustedContextError):
            trusted.check_address(address)


def test_the_setting_needs_per_user_tokens():
    with pytest.raises(ValidationError, match="ASOF_AUTH=users"):
        Settings(_env_file=None, asof_trusted_context=True)
    s = Settings(_env_file=None, asof_auth="users", asof_trusted_context=True)
    assert s.asof_trusted_context and not Settings(_env_file=None).asof_trusted_context
    with pytest.raises(ValidationError):
        Settings(_env_file=None, asof_trusted_context_address="10.0.0.1; x")


class Conn:
    def __init__(self):
        self.closed = False

    def cursor(self):
        return type("Cursor", (), {"execute": lambda self, sql, params=(): None, "fetchall": lambda self: [(1,)],
                                   "close": lambda self: None})()

    def rollback(self):
        pass

    def close(self):
        self.closed = True


@pytest.fixture
def switches(monkeypatch):
    """Fake trusted connections; every switch the pool asks for is recorded, and API_REFUSED is refused."""
    made, log = [], []

    def connect(settings, role="app", autocommit=False, trusted=False):
        assert trusted, "a trusted pool asks for trusted connections"
        made.append(Conn())
        return made[-1]

    def switch_user(conn, authid, settings):
        if authid == "API_REFUSED":
            raise db.DatabaseError("SQL20361N switch refused", sqlstate="42517")
        log.append(authid)

    monkeypatch.setattr(db, "connect", connect)
    monkeypatch.setattr(db, "switch_user", switch_user)
    return made, log


def pool():
    return db.ConnectionPool(Settings(_env_file=None, asof_app_password="app-password-for-tests"), trusted=True)


def test_every_checkout_for_a_user_switches_so_db2_checks_each_request(switches):
    made, log = switches
    p = pool()
    p.connect().close()  # no request user: the runtime user, which a new connection already is
    assert log == []
    token = db.SESSION_USER.set("API_MARIA")
    try:
        p.connect().close()
        p.connect().close()  # the same user again: switched again, so Db2 checks the context's list again
    finally:
        db.SESSION_USER.reset(token)
    p.connect().close()  # back to the runtime user for the next checkout without one
    p.connect().close()  # and no switch when it already is
    assert log == ["API_MARIA", "API_MARIA", "ASOFAPP"] and len(made) == 1


def test_a_refused_switch_closes_the_connection_and_frees_its_slot(switches):
    made, _ = switches
    p = db.ConnectionPool(Settings(_env_file=None, asof_app_password="app-password-for-tests"), trusted=True,
                          max_open=1)
    token = db.SESSION_USER.set("API_REFUSED")
    try:
        with pytest.raises(db.DatabaseError) as err:
            p.connect()
    finally:
        db.SESSION_USER.reset(token)
    assert err.value.sqlstate == "42517" and made[0].closed
    p.connect().close()  # the slot was released: the next request still gets a connection


def test_a_plain_pool_never_switches(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda settings, role="app", autocommit=False: Conn())
    monkeypatch.setattr(db, "switch_user", lambda *a: pytest.fail("a plain pool switched"))
    token = db.SESSION_USER.set("API_MARIA")
    try:
        db.ConnectionPool(Settings(_env_file=None)).connect().close()
    finally:
        db.SESSION_USER.reset(token)


def test_the_api_runs_each_request_as_its_api_user(switches, monkeypatch):
    """The middleware's user reaches the pool inside the (threaded) route, and only for that request."""
    _, log = switches
    monkeypatch.setattr(api, "authenticate", lambda conn, token, schema="ASOF": DIRECTORY.get(token))
    monkeypatch.setattr(api.ledger, "list_entries", lambda conn, schema, limit, offset, decision: [])
    settings = Settings(_env_file=None, asof_auth="users", asof_trusted_context=True,
                        asof_app_password="app-password-for-tests")
    c = TestClient(api.create_app(settings, gate=FakeGate(), assistant=FakeAssistant()))
    assert c.get("/api/ledger", headers=bearer(AUDITOR)).status_code == 200
    assert c.get("/api/ledger", headers=bearer(CHECKER)).status_code == 403  # refused before any switch
    assert log == ["API_ALI", "ASOFAPP"]  # the auditor's route ran as API_ALI, the next token lookup as the runtime user
    assert db.SESSION_USER.get() is None


def test_the_app_builds_a_trusted_pool_only_when_the_setting_is_on(monkeypatch):
    seen, real = [], db.ConnectionPool
    monkeypatch.setattr(api.db, "ConnectionPool", lambda *a, **kw: seen.append(kw.get("trusted")) or real(*a, **kw))
    api.create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant())
    api.create_app(Settings(_env_file=None, asof_auth="users", asof_trusted_context=True), gate=FakeGate(),
                   assistant=FakeAssistant())
    assert seen == [False, True]
