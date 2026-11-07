"""Per-user API authentication (ASOF_AUTH=users): personal tokens, roles per route, the user in the record."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_api import OK, FakeAssistant, FakeGate

from asof import api
from asof.api import create_app, required_role
from asof.config import Settings
from asof.users import APIUser, new_token

CHECKER, AUDITOR, EDITOR, ALL = (new_token() for _ in range(4))
DIRECTORY = {CHECKER: APIUser("cara", frozenset({"checker"})), AUDITOR: APIUser("ali", frozenset({"auditor"})),
             EDITOR: APIUser("eve", frozenset({"editor"})),
             ALL: APIUser("root.ops", frozenset({"checker", "auditor", "editor"}))}


@pytest.fixture
def users_client(monkeypatch):
    """The app in users mode, with the Db2 lookup replaced by a directory of four users."""
    seen = []
    monkeypatch.setattr(api, "authenticate", lambda conn, token, schema="ASOF": seen.append(token) or DIRECTORY.get(token))
    monkeypatch.setattr("asof.db.connect", lambda settings, role="app", autocommit=False: type(
        "C", (), {"rollback": lambda self: None, "close": lambda self: None})())
    gate = FakeGate()
    app = create_app(Settings(_env_file=None, asof_auth="users", asof_api_token="a-shared-token-not-used-0"),
                     gate=gate, assistant=FakeAssistant())
    c = TestClient(app)
    c.gate, c.seen = gate, seen
    return c


def bearer(token):
    return {"authorization": f"Bearer {token}"}


def test_no_or_unknown_token_is_401_and_health_stays_open(users_client, monkeypatch):
    monkeypatch.setattr("asof.db.query", lambda conn, sql, params=(): [(1,)])
    assert users_client.post("/api/gate", json=OK).status_code == 401
    r = users_client.post("/api/gate", json=OK, headers=bearer(new_token()))
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert users_client.post("/api/gate", json=OK, headers=bearer("a-shared-token-not-used-0")).status_code == 401
    h = users_client.get("/healthz")
    assert h.status_code == 200 and h.json()["auth"] == "users"


def test_a_checker_can_check_but_not_read_the_ledger(users_client):
    r = users_client.post("/api/gate", json=OK, headers=bearer(CHECKER))
    assert r.status_code == 200
    assert users_client.gate.seen[-1].requested_by == "cara"  # recorded with the decision
    r = users_client.get("/api/ledger", headers=bearer(CHECKER))
    assert r.status_code == 403 and "auditor" in r.json()["error"]


def test_an_auditor_cannot_submit_drafts_or_change_policy(users_client):
    assert users_client.post("/api/gate", json=OK, headers=bearer(AUDITOR)).status_code == 403
    body = {"clause_id": "PET-001", "effective_from": "2026-12-01", "clause_text": "x" * 30, "rule": {},
            "change_note": "test"}
    assert users_client.post("/api/policy/change", json=body, headers=bearer(AUDITOR)).status_code == 403


def test_an_editor_is_not_limited_to_localhost(users_client, monkeypatch):
    """The editor role replaces the localhost rule and the shared editor token; the editor's name goes into
    the clause's change note."""
    notes = []
    monkeypatch.setattr(api.policy, "apply_change", lambda conn, body, emb, schema: notes.append(body.change_note) or {})
    monkeypatch.setattr(api.policy, "change_impact", lambda conn, clause_id, schema: [])
    monkeypatch.setattr(api, "get_embeddings", lambda name: None)
    body = {"clause_id": "PET-001", "effective_from": "2026-12-01", "version_label": "v2",
            "clause_text": "The pet fee is $125 each way.", "rule": {"pet_fee_usd": 125}, "change_note": "fee rise"}
    r = users_client.post("/api/policy/change", json=body, headers={**bearer(EDITOR), "x-forwarded-for": "10.0.0.9"})
    assert r.status_code == 200, r.text
    assert notes == ["[eve] fee rise"]


def test_whoami_and_policy_reads_need_only_a_signed_in_user(users_client):
    me = users_client.get("/api/whoami", headers=bearer(ALL)).json()
    assert me == {"auth": "users", "user": "root.ops", "roles": ["auditor", "checker", "editor"]}
    assert users_client.get("/api/whoami").status_code == 401


def test_the_rate_limit_counts_per_user_not_per_address(monkeypatch):
    monkeypatch.setattr(api, "authenticate", lambda conn, token, schema="ASOF": DIRECTORY.get(token))
    monkeypatch.setattr("asof.db.connect", lambda settings, role="app", autocommit=False: type(
        "C", (), {"rollback": lambda self: None, "close": lambda self: None})())
    c = TestClient(create_app(Settings(_env_file=None, asof_auth="users"), gate=FakeGate(), assistant=FakeAssistant(),
                              rate_limit=1))
    assert c.post("/api/gate", json=OK, headers=bearer(CHECKER)).status_code == 200
    assert c.post("/api/gate", json=OK, headers=bearer(CHECKER)).status_code == 429
    assert c.post("/api/gate", json=OK, headers=bearer(ALL)).status_code == 200  # same address, another user


@pytest.mark.parametrize("method, path, role", [
    ("POST", "/api/gate", "checker"), ("POST", "/api/assistant/ask", "checker"),
    ("POST", "/api/policy/change", "editor"), ("POST", "/api/policy/preview", "editor"),
    ("POST", "/api/impact/PET-001/suggestions", "editor"), ("POST", "/api/suggestions/3/decision", "editor"),
    ("GET", "/api/ledger", "auditor"), ("GET", "/api/ledger/4/evidence", "auditor"), ("POST", "/api/ledger/ask", "auditor"),
    ("POST", "/api/ledger/receipt", "auditor"), ("GET", "/api/chain/anchors", "auditor"), ("GET", "/api/analytics", "auditor"),
    ("GET", "/api/policy/timeline", None), ("GET", "/api/whoami", None),
    ("GET", "/api/some-future-route", "auditor"),   # not open by accident
])
def test_every_route_needs_its_role(method, path, role):
    assert required_role(method, path) == role


def test_local_mode_is_unchanged():
    c = TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant()))
    assert c.post("/api/gate", json=OK).status_code == 200
    assert c.get("/api/whoami").json() == {"auth": "local", "user": None, "roles": None}
