"""API: validation, limits and headers (no Db2), then the Moffatt flow end to end on Db2."""

from __future__ import annotations

from datetime import date

import pytest
from fakes import ScriptedLLM, claims, judge, verdict
from fastapi.testclient import TestClient

from asof.api import create_app
from asof.assistant import AssistantAnswer
from asof.config import Settings
from asof.gate import HOLDING_REPLY, Gate, GateResult
from asof.schemas import RewriteResult

OK = {"question": "Can I get the bereavement fare after I fly?", "draft_answer": "Yes, within 90 days.",
      "as_of_date": "2026-03-10"}


class FakeGate:
    def __init__(self, released=True):
        self.released, self.seen = released, []

    def check(self, req):
        self.seen.append(req)
        return GateResult("rid", "PASS" if self.released else "ESCALATED", "NO_POLICY_CLAIMS",
                          req.draft_answer if self.released else HOLDING_REPLY, [], [], None, 3, "fake:model",
                          ledger_id=1 if self.released else None, released=self.released)


class FakeAssistant:
    def answer(self, question):
        return AssistantAnswer("Yes, retroactively within 90 days.", ["FAQ-01"], 5)


def client(gate=None, rate_limit=30) -> TestClient:
    app = create_app(Settings(_env_file=None), gate=gate or FakeGate(), assistant=FakeAssistant(), rate_limit=rate_limit)
    return TestClient(app)


def test_valid_request_reaches_the_gate():
    gate = FakeGate()
    r = client(gate).post("/api/gate", json=OK)
    assert r.status_code == 200 and r.json()["decision"] == "PASS"
    assert gate.seen[0].as_of == date(2026, 3, 10) and gate.seen[0].doc_id == "AURELIA-CSP"


@pytest.mark.parametrize("change", [
    {"as_of_date": None},
    {"as_of_date": "2019-12-31"},
    {"as_of_date": "next tuesday"},
    {"doc_id": "OTHER-AIRLINE"},
    {"channel": "sms"},
    {"draft_answer": ""},
    {"draft_answer": "é" * 2001},          # 2001 characters but 4002 bytes
    {"question": "hi\x00there"},
    {"unexpected": "field"},
])
def test_invalid_input_is_rejected(change):
    body = {k: v for k, v in {**OK, **change}.items() if v is not None}
    assert client().post("/api/gate", json=body).status_code == 422


def test_oversized_body_is_rejected():
    r = client().post("/api/gate", content=b"{" + b" " * 70_000 + b"}", headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_rate_limit_applies_to_llm_endpoints():
    c = client(rate_limit=2)
    codes = [c.post("/api/gate", json=OK).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_unrecorded_decision_is_not_released():
    r = client(FakeGate(released=False)).post("/api/gate", json=OK)
    assert r.status_code == 503 and r.json()["final_answer"] == HOLDING_REPLY and r.json()["released"] is False


def test_security_headers():
    h = client().post("/api/gate", json=OK).headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and h["cache-control"] == "no-store"


def test_assistant_endpoint_checks_the_draft():
    gate = FakeGate()
    r = client(gate).post("/api/assistant/ask", json={"question": "Bereavement after travel?", "as_of_date": "2026-03-10"})
    assert r.status_code == 200 and r.json()["assistant"]["faq_ids"] == ["FAQ-01"]
    assert gate.seen[0].draft_answer == "Yes, retroactively within 90 days."


@pytest.mark.parametrize("path", ["/api/ledger/0", "/api/ledger/-1", "/api/ledger/abc", "/api/ledger?limit=500"])
def test_ledger_paths_are_validated(path):
    assert client().get(path).status_code == 422


# ---- end to end on Db2 (scripted LLM, real retrieval, real ledger) -------------------------

V1_QUOTE = "A bereavement fare cannot be applied retroactively once any part of the journey has been flown"
RETRO = "You can apply for the bereavement discount retroactively within 90 days of ticket issue."


@pytest.mark.db2
def test_moffatt_flow_through_the_api(settings, embeddings, test_schema, app_conn):
    from asof import db

    rewrite = "Bereavement fares must be requested before travel begins and cannot be applied after you have flown."
    llm = ScriptedLLM(
        extract=[claims((RETRO, "bereavement", "deadline")),
                 claims(("Bereavement fares must be requested before travel begins.", "bereavement", "procedure"))],
        judge=[judge(verdict(1, "CONTRADICTED", "BRV-002", V1_QUOTE)),
               judge(verdict(1, "SUPPORTED", "BRV-002", "Bereavement fares must be requested before travel begins"))],
        rewrite=[RewriteResult(answer=rewrite)],
    )
    gate = Gate(llm, embeddings, lambda: db.connect(settings, "app"), test_schema)
    app = create_app(settings, gate=gate, assistant=FakeAssistant(), schema=test_schema)
    with TestClient(app) as c:
        r = c.post("/api/assistant/ask", json={"question": "Can I get the bereavement fare after I fly?",
                                               "as_of_date": "2026-03-10"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decision"] == "CORRECTED" and body["final_answer"].startswith(rewrite)
        first = body["claims"][0]
        assert (first["clause_id"], first["clause_version"], first["verdict"]) == ("BRV-002", "v1", "CONTRADICTED")

        entry = c.get(f"/api/ledger/{body['ledger_id']}").json()
        assert entry["decision"] == "CORRECTED" and entry["as_of_date"] == "2026-03-10"
        assert [(x["pass_no"], x["verdict"]) for x in entry["citations"]] == [(1, "CONTRADICTED"), (2, "SUPPORTED")]

        assert c.get("/api/chain/verify").json()["status"] == "OK"
        replay = c.get(f"/api/ledger/{body['ledger_id']}/replay").json()
        assert replay["clauses"][0]["used"]["version_label"] == "v1"
        assert c.get("/healthz").json()["db2"] == "ok"

    db.use_schema(app_conn, test_schema)
    with pytest.raises(db.DatabaseError) as err:  # and the app user still cannot touch the row
        db.execute(app_conn, "UPDATE ANSWER_LEDGER SET DECISION = 'PASS' WHERE LEDGER_ID = ?",
                   (body["ledger_id"],))
    assert err.value.sqlstate == "42501"


# ---- UI and policy endpoints -----------------------------------------------------------------

def test_ui_is_served_with_a_strict_csp():
    c = client()
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/ui/"
    page = c.get("/ui/")
    assert page.status_code == 200 and "<title>AsOf</title>" in page.text
    csp = page.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert c.get("/ui/app.js").status_code == 200


CHANGE = {"clause_id": "PET-001", "effective_from": "2026-12-01", "version_label": "v2",
          "clause_text": "Small cats and dogs may travel in the cabin. The pet fee is $125 each way.",
          "rule": {"pet_fee_usd": 125}, "change_note": "Pet fee rises"}


def test_policy_change_is_refused_from_a_remote_client():
    app = create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant())
    remote = TestClient(app, client=("203.0.113.7", 50000))
    assert remote.post("/api/policy/change", json=CHANGE).status_code == 403


def test_policy_change_token_is_enforced_when_set():
    app = create_app(Settings(_env_file=None, asof_editor_token="s3cret-token"), gate=FakeGate(), assistant=FakeAssistant())
    local = TestClient(app, client=("127.0.0.1", 50000))
    assert local.post("/api/policy/change", json=CHANGE).status_code == 403
    assert local.post("/api/policy/change", json=CHANGE, headers={"X-AsOf-Editor-Token": "wrong"}).status_code == 403


@pytest.mark.parametrize("change", [
    {"rule": {"nested": {"deep": 1}}}, {"version_label": "latest"}, {"clause_id": "PET-1"},
    {"effective_from": "2019-01-01"}, {"clause_text": "short"},
])
def test_policy_change_input_is_validated(change):
    local = TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant()),
                       client=("127.0.0.1", 50000))
    assert local.post("/api/policy/change", json={**CHANGE, **change}).status_code == 422


@pytest.mark.db2
def test_policy_endpoints_on_db2(settings, embeddings, test_schema):
    app = create_app(settings, gate=FakeGate(), assistant=FakeAssistant(), schema=test_schema)
    c = TestClient(app, client=("127.0.0.1", 50000))
    timeline = c.get("/api/policy/timeline").json()
    assert len(timeline) == 34
    brv = next(x for x in timeline if x["clause_id"] == "BRV-002")
    assert [v["params"]["retroactive_allowed"] for v in brv["versions"]] == ["false", "true"]
    assert c.get("/api/policy/clauses/BRV-002/history").status_code == 200
    assert c.get("/api/policy/clauses/ZZZ-999/history").status_code == 404
    impact = c.get("/api/impact/BAG-001").json()
    assert any(r["kind"] == "PUBLISHED" and r["ref_id"] == "PA-BAG-001" for r in impact)
    assert "decisions" in c.get("/api/analytics").json()
    reused = c.post("/api/policy/change", json={**CHANGE, "clause_id": "BAG-001", "version_label": "v1",
                                                 "rule": {"first_bag_fee_usd": 45}})
    assert reused.status_code == 422 and "already in use" in reused.json()["detail"]


def test_configuration_errors_do_not_reveal_server_paths():
    from asof.config import ConfigError

    class Broken(FakeGate):
        def check(self, req):
            raise ConfigError("Missing required setting(s): OPENROUTER_API_KEY. Set them in /home/x/.env")

    r = client(Broken()).post("/api/gate", json=OK)
    assert r.status_code == 500
    assert ".env" not in r.text and "/home" not in r.text and "OPENROUTER" not in r.text
