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


def test_the_full_chain_verification_shares_the_rate_limit(monkeypatch):
    from asof import db, ledger

    class Conn:  # what the pool and /healthz need from a connection; verify_chain itself is stubbed
        def cursor(self):
            return type("Cursor", (), {"execute": lambda self, sql, params=(): None,
                                       "fetchall": lambda self: [(1,)], "close": lambda self: None})()

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(db, "connect", lambda settings, role="app", autocommit=False: Conn())
    monkeypatch.setattr(ledger, "verify_chain", lambda conn, schema="ASOF": ledger.ChainStatus("OK", 0, None, ""))
    c = TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant(), rate_limit=2))
    codes = [c.get("/api/chain/verify").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert c.get("/healthz").status_code != 429  # cheap reads stay unlimited


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
    assert remote.post("/api/policy/preview", json=CHANGE).status_code == 403  # a preview is an editor action too


def test_policy_change_token_is_enforced_when_set():
    app = create_app(Settings(_env_file=None, asof_editor_token="s3cret-editor-token"), gate=FakeGate(),
                     assistant=FakeAssistant())
    local = TestClient(app, client=("127.0.0.1", 50000))
    assert local.post("/api/policy/change", json=CHANGE).status_code == 403
    assert local.post("/api/policy/change", json=CHANGE, headers={"X-AsOf-Editor-Token": "wrong"}).status_code == 403
    assert local.post("/api/policy/preview", json=CHANGE).status_code == 403


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
    timeline = c.get("/api/policy/timeline?doc_id=AURELIA-CSP").json()
    assert len(timeline) == 34 and {x["doc_id"] for x in timeline} == {"AURELIA-CSP"}
    assert len(c.get("/api/policy/timeline?doc_id=FERNHOLLOW-FEES").json()) == 18
    assert len(c.get("/api/policy/timeline").json()) == 52
    assert c.get("/api/policy/timeline?doc_id=OTHER").status_code == 422
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


class FakeAsker:
    def __init__(self):
        self.questions: list[str] = []

    def ask(self, question):
        from asof.askledger import AskResult

        self.questions.append(question)
        return AskResult(question=question, status="ANSWERED", answer="2 escalated.", sql="SELECT 1",
                         columns=["N"], rows=[[2]])


@pytest.mark.parametrize("question", ["", "hi", "x" * 501, "bad\x00byte"])
def test_ask_the_ledger_validates_the_question(question):
    asker = FakeAsker()
    app = create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant(), asker=asker)
    assert TestClient(app).post("/api/ledger/ask", json={"question": question}).status_code == 422
    assert asker.questions == []


def test_ask_the_ledger_returns_the_sql_and_rows_with_the_answer():
    asker = FakeAsker()
    app = create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant(), asker=asker)
    r = TestClient(app).post("/api/ledger/ask", json={"question": "How many were escalated?", "extra": 1})
    assert r.status_code == 422  # unknown fields are refused
    r = TestClient(app).post("/api/ledger/ask", json={"question": "How many were escalated?"})
    assert r.status_code == 200 and r.json()["sql"] == "SELECT 1" and r.json()["rows"] == [[2]]


def test_the_optional_api_token_guards_every_api_route_but_not_health_or_the_ui():
    app = create_app(Settings(_env_file=None, asof_api_token="a-long-test-token-0123"), gate=FakeGate(),
                     assistant=FakeAssistant())
    c = TestClient(app)
    assert c.post("/api/gate", json=OK).status_code == 401
    assert c.get("/api/ledger").status_code == 401
    assert c.post("/api/gate", json=OK, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.post("/api/gate", json=OK, headers={"Authorization": "Basic t0ken"}).status_code == 401
    assert c.post("/api/gate", json=OK, headers={"Authorization": "Bearer a-long-test-token-0123"}).status_code == 200
    assert c.get("/healthz").status_code == 200 and c.get("/ui/").status_code == 200
    assert c.post("/api/gate", json=OK).headers["www-authenticate"] == "Bearer"


def test_tokens_with_unusual_characters_are_refused_not_crashed():
    from asof.api import token_matches

    assert token_matches("abc", "abc") and not token_matches("abd", "abc") and not token_matches(None, "abc")
    assert not token_matches("\u00e9t\u00e9", "abc")  # str compare_digest would raise on non-ASCII
    for bad in ("short", "has a space in it ok", "t\u00f6ken-with-umlaut-1234"):
        with pytest.raises(ValueError):
            Settings(_env_file=None, asof_api_token=bad)


def test_a_foreign_host_header_is_refused_so_dns_rebinding_cannot_reach_the_api():
    c = client()
    assert c.get("/healthz", headers={"host": "attacker.example"}).status_code == 400
    assert c.get("/healthz", headers={"host": "127.0.0.1:8000"}).status_code == 200


def test_a_chunked_body_over_the_cap_is_refused_without_a_content_length():
    def chunks():
        for _ in range(80):
            yield b"x" * 1024  # 80 KB, streamed: no Content-Length header at all

    r = client().post("/api/gate", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_health_says_plainly_when_no_model_is_configured():
    no_key = TestClient(create_app(Settings(_env_file=None, llm_provider="openrouter", openrouter_api_key=""),
                                   gate=FakeGate(), assistant=FakeAssistant())).get("/healthz").json()
    assert no_key["llm_ready"] is False and no_key["status"] == "degraded"
    placeholder = Settings(_env_file=None, llm_provider="openrouter", openrouter_api_key="sk-or-v1-your-key-here")
    assert placeholder.llm_ready is False
    assert Settings(_env_file=None, llm_provider="ollama").llm_ready is True


def test_a_check_without_a_model_gets_a_plain_503_not_a_server_error():
    app = create_app(Settings(_env_file=None, llm_provider="openrouter", openrouter_api_key=""))
    r = TestClient(app).post("/api/gate", json=OK)
    assert r.status_code == 503 and "OPENROUTER_API_KEY" in r.json()["detail"] and "/" not in r.json()["detail"].split(".env")[0]


def test_the_app_starts_and_serves_policy_screens_without_a_model():
    app = create_app(Settings(_env_file=None, llm_provider="openrouter", openrouter_api_key=""))
    with TestClient(app) as c:  # runs the lifespan, as uvicorn does
        assert c.get("/healthz").json()["llm_ready"] is False
        assert c.post("/api/gate", json=OK).status_code == 503


def test_health_names_replay_mode_and_the_model_the_outputs_were_recorded_from():
    body = TestClient(create_app(Settings(_env_file=None, llm_provider="replay"), gate=FakeGate(),
                                 assistant=FakeAssistant())).get("/healthz").json()
    assert body["replay"] is True and body["llm_ready"] is True and body["llm"] == "replay:recorded outputs"
    assert body["replay_model"].startswith("openrouter:")  # the UI banner names it
    assert TestClient(create_app(Settings(_env_file=None, llm_provider="ollama"), gate=FakeGate(),
                                 assistant=FakeAssistant())).get("/healthz").json()["replay"] is False


def test_a_receipt_is_checked_against_the_ledger_and_validated(monkeypatch):
    from asof import ledger

    seen = {}

    def fake_check(conn, ledger_id, row_hash, schema="ASOF"):
        seen.update(ledger_id=ledger_id, row_hash=row_hash)
        return ledger.ReceiptCheck(ledger_id, True, False, ledger.ChainStatus("OK", 9, None, "ok"))

    monkeypatch.setattr(ledger, "check_receipt", fake_check)
    monkeypatch.setattr("asof.db.connect", lambda settings, role="app", autocommit=False: type(
        "C", (), {"rollback": lambda self: None, "close": lambda self: None})())
    c = client()
    good = {"ledger_id": 7, "row_hash": "ab" * 32}
    body = c.post("/api/ledger/receipt", json=good).json()
    assert body["verdict"] == "REWRITTEN" and body["chain_status"] == "OK" and seen == good
    for bad in ({**good, "row_hash": "zz" * 32}, {**good, "row_hash": "ab"}, {**good, "ledger_id": 0},
                {**good, "extra": 1}):
        assert c.post("/api/ledger/receipt", json=bad).status_code == 422


def test_every_check_response_carries_its_receipt():
    assert "row_hash" in client().post("/api/gate", json=OK).json()


@pytest.mark.parametrize(("found", "matches", "chain", "verdict"), [
    (True, True, "OK", "INTACT"), (True, False, "OK", "REWRITTEN"), (False, False, "OK", "MISSING"),
    (True, True, "BROKEN", "CHAIN_BROKEN")])
def test_receipt_verdicts(found, matches, chain, verdict):
    from asof import ledger

    assert ledger.ReceiptCheck(1, found, matches, ledger.ChainStatus(chain, 1, None, None)).verdict == verdict


def test_the_evidence_pack_downloads_as_a_file_and_shares_the_rate_limit(monkeypatch):
    from asof import ledger

    monkeypatch.setattr(ledger, "evidence", lambda conn, ledger_id, schema="ASOF":
                        None if ledger_id == 404 else {"asof_evidence": 1, "ledger_entry": {"ledger_id": ledger_id}})
    monkeypatch.setattr("asof.db.connect", lambda settings, role="app", autocommit=False: type(
        "C", (), {"rollback": lambda self: None, "close": lambda self: None})())
    c = client(rate_limit=2)
    r = c.get("/api/ledger/7/evidence")
    assert r.status_code == 200 and r.json()["ledger_entry"]["ledger_id"] == 7
    assert r.headers["content-disposition"] == 'attachment; filename="asof-evidence-7.json"'
    assert c.get("/api/ledger/404/evidence").status_code == 404
    assert c.get("/api/ledger/7/evidence").status_code == 429


def test_a_replay_miss_is_explained_not_reported_as_a_broken_model():
    from asof.replay import MISS, ReplayMiss

    class MissingAssistant:
        def answer(self, question):
            raise ReplayMiss(MISS)

    app = create_app(Settings(_env_file=None), gate=FakeGate(), assistant=MissingAssistant())
    r = TestClient(app).post("/api/assistant/ask", json={"question": "Can I bring my bike?", "as_of_date": "2026-05-05"})
    assert r.status_code == 503 and "decision" not in r.json()  # the UI shows this as an error, not as a result
    assert r.json()["error"].startswith("Replay mode has recorded model outputs only for the built-in scenarios")

