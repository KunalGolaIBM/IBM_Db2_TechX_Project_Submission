"""The specialist inbox over HTTP: validation, the reviewer role, and a refused reply shown with its check."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from test_api import FakeAssistant, FakeGate
from test_api_users import ALL, AUDITOR, DIRECTORY, bearer

from asof import api, review
from asof.api import create_app
from asof.config import Settings
from asof.gate import GateResult
from asof.users import APIUser, new_token

REVIEWER = new_token()
MARCH = date(2026, 3, 10)


def _result(reason: str) -> GateResult:
    return GateResult("rid", "PASS" if reason == "ALL_SUPPORTED" else "ESCALATED", reason, "reply", [], [], None, 7,
                      "fake:model", released=False)


@pytest.fixture
def fake_db(monkeypatch):
    monkeypatch.setattr("asof.db.connect", lambda settings, role="app", autocommit=False: type(
        "C", (), {"rollback": lambda self: None, "close": lambda self: None})())
    monkeypatch.setattr("asof.ledger.get_entry", lambda conn, ledger_id, schema="ASOF": {"as_of_date": MARCH})
    monkeypatch.setattr("asof.api.get_embeddings", lambda name: object())


@pytest.fixture
def local(fake_db):
    return TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant()))


@pytest.fixture
def users(fake_db, monkeypatch):
    directory = {**DIRECTORY, REVIEWER: APIUser("rita", frozenset({"reviewer"}))}
    monkeypatch.setattr(api, "authenticate", lambda conn, token, schema="ASOF": directory.get(token))
    return TestClient(create_app(Settings(_env_file=None, asof_auth="users"), gate=FakeGate(), assistant=FakeAssistant()))


def test_the_queue_and_a_held_decision_need_no_model(local, monkeypatch):
    monkeypatch.setattr(review, "queue", lambda conn, schema, limit: {"open": [{"ledger_id": 3}], "answered": [],
                                                                      "counts": {"open": 1}})
    monkeypatch.setattr(review, "detail", lambda connect, emb, ledger_id, schema: {"ledger_id": ledger_id})
    assert local.get("/api/reviews").json()["open"] == [{"ledger_id": 3}]
    assert local.get("/api/reviews/3").json() == {"ledger_id": 3}
    assert local.get("/api/reviews/0").status_code == 422


def test_a_missing_or_unheld_decision_is_a_clear_error(local, monkeypatch):
    def refuse(*a, **k):
        raise review.ReviewError(409, "only a held (ESCALATED) decision goes to a specialist")
    monkeypatch.setattr(review, "detail", refuse)
    r = local.get("/api/reviews/3")
    assert r.status_code == 409 and "held" in r.json()["detail"]


@pytest.mark.parametrize("body", [{}, {"reply": ""}, {"reply": "x" * 3501}, {"reply": "ok", "doc_id": "OTHER"},
                                  {"reply": "ok", "note": "n" * 1001}, {"reply": "a\x00b"}, {"reply": "ok", "extra": 1}])
def test_reply_input_is_validated(local, body):
    assert local.post("/api/reviews/3/resolve", json=body).status_code == 422


def test_a_sent_reply_returns_its_ledger_row_and_check(local, monkeypatch):
    seen = {}

    def resolve(gate, ledger_id, reply, note, doc_id, reviewer):
        seen.update(ledger_id=ledger_id, reply=reply, note=note, doc_id=doc_id, reviewer=reviewer)
        return review.Resolved(9, "a" * 64, "SPECIALIST_CHECKED", reply + " refs", _result("ALL_SUPPORTED"))
    monkeypatch.setattr(review, "resolve", resolve)
    r = local.post("/api/reviews/3/resolve", json={"reply": "  Bereavement fares must be requested before travel. "})
    assert r.status_code == 200
    out = r.json()
    assert (out["escalated_ledger_id"], out["ledger_id"], out["outcome"]) == (3, 9, "SPECIALIST_CHECKED")
    assert out["check"]["sendable"] is True and out["check"]["as_of_date"] == "2026-03-10"
    assert seen == {"ledger_id": 3, "reply": "Bereavement fares must be requested before travel.", "note": None,
                    "doc_id": None, "reviewer": None}  # local mode: no named specialist


def test_a_refused_reply_comes_back_with_the_check_that_refused_it(local, monkeypatch):
    def resolve(*a, **k):
        raise review.ReviewError(409, "1 claim in the reply contradicts the policy", _result("CONTRADICTED"))
    monkeypatch.setattr(review, "resolve", resolve)
    r = local.post("/api/reviews/3/resolve", json={"reply": "You can claim it after travel."})
    assert r.status_code == 409
    body = r.json()
    assert "contradicts" in body["error"]
    assert body["check"]["reason_code"] == "CONTRADICTED" and body["check"]["sendable"] is False


def test_only_a_reviewer_reaches_the_inbox(users, monkeypatch):
    monkeypatch.setattr(review, "queue", lambda conn, schema, limit: {"open": [], "answered": [], "counts": {}})
    monkeypatch.setattr(review, "resolve", lambda gate, ledger_id, reply, note, doc_id, reviewer: review.Resolved(
        9, "a" * 64, "SPECIALIST_CHECKED", reply, _result("ALL_SUPPORTED")) if reviewer == "rita" else None)
    assert users.get("/api/reviews", headers=bearer(AUDITOR)).status_code == 403
    assert users.get("/api/reviews", headers=bearer(ALL)).status_code == 403  # checker, auditor and editor: not reviewer
    assert users.get("/api/reviews", headers=bearer(REVIEWER)).status_code == 200
    r = users.post("/api/reviews/3/resolve", json={"reply": "ok"}, headers=bearer(REVIEWER))
    assert r.status_code == 200 and r.json()["ledger_id"] == 9  # the reviewer's name reached the inbox


def test_policy_terms_drive_the_note_requirement():
    from asof.gate import policy_terms

    assert policy_terms("You can request the bereavement fare after you travel.") == ["bereavement", "fare", "travel"] \
        or "bereavement" in policy_terms("You can request the bereavement fare after you travel.")
    assert policy_terms("It costs $60.")[-1] == "amounts"
    assert policy_terms("Thank you for your patience. I am sorry for your loss.") == []
    r = _result("NO_POLICY_CLAIMS")
    assert review.needs_note(r, "The fee is waived.") and not review.needs_note(r, "Thanks, and sorry for the wait.")
    out = review.check_out(r, MARCH, "The fee is waived.")
    assert out["sendable"] and out["needs_note"] and "fee" in out["note_reason"]
