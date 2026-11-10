"""Live checks on the public demo (ASOF_DEMO_LIVE=true, asof/demolive.py), with fake providers and a fake spend counter:
no network, no Db2. The Db2 side (the cap procedure, its race and its grants) is in test_db2_demo_spend.py."""
from __future__ import annotations

import logging
import threading
from datetime import date

import pytest
from fakes import ScriptedLLM, ZeroEmbeddings
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pydantic import ValidationError
from test_api import FakeAssistant, FakeGate

from asof import db, demolive
from asof.api import create_app
from asof.assistant import AssistantAnswer
from asof.config import Settings
from asof.gate import HOLDING_REPLY, Gate, GateResult
from asof.llm import LLMError, LLMResult
from asof.schemas import ExtractionResult

PROXY = ("127.0.0.1", 51000)  # Caddy on the same machine
KEY = "sk-not-a-real-key-demolive-0000"  # under 32 characters after "sk-", so the secret check passes it
RECORDED = {"label": "Moffatt: March booking", "doc_id": "AURELIA-CSP", "as_of": "2026-03-10",
            "question": "My grandmother just died. Can I get the bereavement fare after I travel?",
            "draft": "Yes, you can apply within 90 days.", "draft_checked": "Yes, you can apply within 90 days."}
RECORDED_ASK = {"label": "chat", "doc_id": "AURELIA-CSP", "as_of": "2026-06-02", "question": "Can I bring my cat?",
                "draft": None, "draft_checked": "Yes, for $95 each way."}
NEW = {"question": "Can I take two cats in the cabin?", "draft_answer": "Yes, two cats for $95 in total.",
       "as_of_date": "2026-03-10"}
AS_RECORDED = {"question": RECORDED["question"], "draft_answer": RECORDED["draft"], "as_of_date": RECORDED["as_of"]}


def ip(addr: str) -> dict[str, str]:
    return {"x-forwarded-for": addr}


class FakeSpend:
    """The Db2 counter's contract in memory: claim() admits up to the cap, then raises SQLSTATE 75097."""

    def __init__(self, cap_reached_after: int | None = None, error: str | None = None):
        self.used, self.records, self.limit, self.error = 0, [], cap_reached_after, error
        self.lock = threading.Lock()

    def claim(self, cap):
        with self.lock:
            if self.error:
                raise db.DatabaseError("Db2 is down in this test", self.error)
            if self.used >= min(cap, self.limit if self.limit is not None else cap):
                raise db.DatabaseError("CLAIM_DEMO_CHECK refused: the cap is reached", demolive.CAP_REACHED)
            self.used += 1
            return date(2026, 11, 10), self.used

    def record(self, day, calls, tin, tout):
        self.records.append((day, calls, tin, tout))

    def today(self):
        return {"day": date(2026, 11, 10), "checks": self.used, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0}


class LiveClient:
    """Stands in for the OpenRouter client: one structured call per check, with token counts, or an LLMError."""

    provider, model_name, info = "openrouter", "test/model", "openrouter:test/model"

    def __init__(self, fail: bool = False):
        self.fail, self.calls = fail, 0

    def structured(self, schema, messages, choices=None):
        self.calls += 1
        if self.fail:
            raise LLMError("openrouter:test/model did not answer within 60s")
        return LLMResult(schema.model_validate({"claims": []}), 5, 120, 30, 1)

    def tool_round(self, messages, tools):
        return AIMessage(content="", usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10})

    def run(self, fn):
        return fn()

    @property
    def chat_model(self):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(responses=["Yes, your cat can fly with you."])


class LiveGate:
    """A gate that makes one model call through the metered client, like the real one's first step."""

    def __init__(self, llm, seen):
        self.llm, self.seen = llm, seen

    def check(self, req):
        self.seen.append(req)
        try:
            self.llm.structured(ExtractionResult, [("human", req.draft_answer)])
        except LLMError:
            return GateResult("rid", "ESCALATED", "ERROR_FAIL_CLOSED", HOLDING_REPLY, [], [], None, 3, self.llm.info,
                              ledger_id=7, released=False)
        return GateResult("rid", "PASS", "NO_POLICY_CLAIMS", req.draft_answer, [], [], None, 3, self.llm.info,
                          ledger_id=8)


class LiveAssistant:
    def __init__(self, llm, seen):
        self.llm, self.seen = llm, seen

    def answer(self, question):
        self.seen.append(question)
        return AssistantAnswer("Yes, your cat can fly with you.", ["FAQ-07"], 4)


def demo_settings(**extra) -> Settings:
    return Settings(_env_file=None, asof_public_demo=True, llm_provider="replay", asof_demo_live=True, **extra)


def make_live(spend=None, client=None, per_minute=3, per_day=20, cap=400, available=True, seen=None, asked=None,
              clock=None, today=None) -> demolive.LiveChecks:
    seen = [] if seen is None else seen
    asked = [] if asked is None else asked
    kw = {k: v for k, v in (("clock", clock), ("today", today)) if v is not None}
    return demolive.LiveChecks(model="openrouter:test/model", cap=cap, per_minute=per_minute, per_day=per_day,
                               available=available, client=lambda: client or LiveClient(), spend=spend or FakeSpend(),
                               gate=lambda m: LiveGate(m, seen), assistant=lambda m: LiveAssistant(m, asked),
                               recorded=demolive.RecordedInputs([RECORDED, RECORDED_ASK]), **kw)


@pytest.fixture
def no_db(monkeypatch):
    """No Db2: /healthz reports it down; everything else under test must not need it (the spend counter is faked)."""
    def down(*_a, **_k):
        raise db.DatabaseError("no Db2 in this test", "08001")
    monkeypatch.setattr("asof.db.connect", down)


def app_with(live, replay_gate=None, rate_limit=60) -> TestClient:
    app = create_app(demo_settings(), gate=replay_gate or FakeGate(), assistant=FakeAssistant(), rate_limit=rate_limit,
                     read_limit=200, live=live)
    return TestClient(app, client=PROXY, raise_server_exceptions=False)


# ---------- 1. explicit opt-in, OpenRouter only, key from the environment only ----------
def test_live_is_off_by_default():
    s = Settings(_env_file=None)
    assert s.asof_demo_live is False and (s.asof_demo_live_daily_cap, s.asof_demo_live_per_minute,
                                          s.asof_demo_live_per_day) == (400, 3, 20)


def test_the_demo_still_refuses_a_key_without_the_opt_in(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    with pytest.raises(ValidationError, match="holds no model keys"):
        Settings(_env_file=None, asof_public_demo=True, llm_provider="replay", openrouter_api_key=KEY)


def test_with_the_opt_in_an_openrouter_key_from_the_environment_is_accepted(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    s = demo_settings()
    assert s.openrouter_api_key is not None and s.openrouter_api_key.get_secret_value() == KEY
    assert s.llm_provider == "replay"  # the built-in scenarios still replay
    assert s.embedding_key is None and not s.indb_embeddings_wanted  # the demo key never becomes Db2's embedding key


def test_with_the_opt_in_a_key_from_dotenv_is_refused(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(f"ASOF_PUBLIC_DEMO=true\nLLM_PROVIDER=replay\nASOF_DEMO_LIVE=true\nOPENROUTER_API_KEY={KEY}\n")
    with pytest.raises(ValidationError, match="process environment only") as err:
        Settings(_env_file=env)
    assert KEY not in str(err.value)


@pytest.mark.parametrize("key", ["watsonx_api_key", "openai_compat_api_key", "embedding_api_key"])
def test_with_the_opt_in_every_other_model_key_is_still_refused(key):
    with pytest.raises(ValidationError, match="holds no model keys but OPENROUTER_API_KEY"):
        demo_settings(**{key: "sk-not-a-real-key-0000000000"})


def test_the_opt_in_keeps_replay_as_the_provider():
    with pytest.raises(ValidationError, match="replay mode only"):
        Settings(_env_file=None, asof_public_demo=True, llm_provider="openrouter", asof_demo_live=True)


def test_the_opt_in_is_for_the_public_demo_only():
    with pytest.raises(ValidationError, match="for the public demo only"):
        Settings(_env_file=None, asof_demo_live=True)


@pytest.mark.parametrize(("field", "value"), [("asof_demo_live_daily_cap", 0), ("asof_demo_live_per_minute", 0),
                                              ("asof_demo_live_per_day", 0), ("asof_demo_live_daily_cap", 100001)])
def test_limits_are_bounded(field, value):
    with pytest.raises(ValidationError):
        demo_settings(**{field: value})


def test_without_a_key_live_checks_are_unavailable_and_new_input_is_refused(no_db):
    c = TestClient(create_app(demo_settings(), gate=FakeGate(), assistant=FakeAssistant()), client=PROXY,
                   raise_server_exceptions=False)
    r = c.post("/api/gate", json=NEW, headers=ip("203.0.113.7"))
    assert r.status_code == 503 and r.json()["reason"] == "unavailable"
    h = c.get("/healthz").json()
    assert h["live_checks"] == "unavailable" and "not available" in h["public_demo_notice"]


# ---------- routing: recorded inputs replay, anything else goes live ----------
def test_every_shipped_recorded_input_replays_and_fits_the_live_limits():
    from asof.replay import Recording

    checks = Recording.load().scenarios["checks"]
    rec = demolive.RecordedInputs.shipped()
    assert len(rec) == len(checks) > 10
    for c in checks:
        on = date.fromisoformat(c["as_of"])
        assert rec.gate(c["doc_id"], c["question"], c["draft_checked"], on), c["label"]
        assert rec.ask(c["doc_id"], c["question"], on) == (c["draft"] is None), c["label"]
        demolive.LiveGateIn(question=c["question"], draft_answer=c["draft_checked"])  # never refused for length


def test_one_changed_character_is_a_new_input():
    rec = demolive.RecordedInputs([RECORDED])
    on = date(2026, 3, 10)
    assert rec.gate("AURELIA-CSP", RECORDED["question"], RECORDED["draft"], on)
    assert not rec.gate("AURELIA-CSP", RECORDED["question"], RECORDED["draft"] + " ", on)
    assert not rec.gate("AURELIA-CSP", RECORDED["question"], RECORDED["draft"], date(2026, 3, 11))
    assert not rec.gate("FERNHOLLOW-FEES", RECORDED["question"], RECORDED["draft"], on)


def test_a_recorded_input_replays_and_spends_nothing(no_db):
    spend, replay = FakeSpend(), FakeGate()
    seen: list = []
    c = app_with(make_live(spend=spend, seen=seen), replay)
    r = c.post("/api/gate", json=AS_RECORDED, headers=ip("203.0.113.7"))
    assert r.status_code == 200 and len(replay.seen) == 1 and seen == [] and spend.used == 0


def test_a_new_input_is_checked_live_and_its_usage_recorded(no_db):
    spend, replay = FakeSpend(), FakeGate()
    seen: list = []
    c = app_with(make_live(spend=spend, seen=seen), replay)
    r = c.post("/api/gate", json=NEW, headers=ip("203.0.113.7"))
    assert r.status_code == 200, r.text
    assert r.json()["model"] == "openrouter:test/model" and replay.seen == [] and len(seen) == 1
    assert spend.used == 1 and spend.records == [(date(2026, 11, 10), 1, 120, 30)]


def test_the_demo_assistant_answers_a_new_question_live_and_a_recorded_one_from_the_recording(no_db):
    asked: list = []
    seen: list = []
    spend = FakeSpend()
    c = app_with(make_live(spend=spend, seen=seen, asked=asked))
    new = c.post("/api/assistant/ask", json={"question": "Can my dog fly with me?", "as_of_date": "2026-06-02"},
                 headers=ip("203.0.113.7"))
    assert new.status_code == 200 and asked == ["Can my dog fly with me?"] and len(seen) == 1 and spend.used == 1
    old = c.post("/api/assistant/ask", json={"question": RECORDED_ASK["question"], "as_of_date": "2026-06-02"},
                 headers=ip("203.0.113.7"))
    assert old.status_code == 200 and old.json()["assistant"]["draft"] == "Yes, retroactively within 90 days."  # replay's
    assert len(asked) == 1 and spend.used == 1


# ---------- 4. input limits, before anything runs ----------
@pytest.mark.parametrize(("path", "body"), [
    ("/api/gate", {**NEW, "question": "q" * (demolive.LIVE_QUESTION_MAX + 1)}),
    ("/api/gate", {**NEW, "draft_answer": "d" * (demolive.LIVE_DRAFT_MAX + 1)}),
    ("/api/assistant/ask", {"question": "q" * (demolive.LIVE_QUESTION_MAX + 1), "as_of_date": "2026-03-10"}),
])
def test_input_over_the_live_limits_is_refused_before_anything_runs(no_db, path, body):
    spend, replay = FakeSpend(), FakeGate()
    seen: list = []
    c = app_with(make_live(spend=spend, seen=seen), replay)
    r = c.post(path, json=body, headers=ip("203.0.113.7"))
    assert r.status_code == 422 and "at most" in str(r.json()["detail"])
    assert spend.used == 0 and seen == [] and replay.seen == []


def test_input_at_the_live_limits_is_accepted(no_db):
    c = app_with(make_live())
    body = {**NEW, "question": "q" * demolive.LIVE_QUESTION_MAX, "draft_answer": "d" * demolive.LIVE_DRAFT_MAX}
    assert c.post("/api/gate", json=body, headers=ip("203.0.113.7")).status_code == 200


# ---------- 2. the daily cap (Db2's answer, faked here) ----------
def test_at_the_cap_new_input_is_refused_with_the_reason_and_built_ins_still_replay(no_db):
    spend, replay = FakeSpend(cap_reached_after=1), FakeGate()
    seen: list = []
    c = app_with(make_live(spend=spend, seen=seen, cap=1), replay)
    assert c.post("/api/gate", json=NEW, headers=ip("203.0.113.7")).status_code == 200
    r = c.post("/api/gate", json={**NEW, "draft_answer": "Two cats are free."}, headers=ip("198.51.100.9"))
    assert r.status_code == 503 and r.json()["reason"] == "cap" and r.json()["live_checks"] == "paused"
    assert "limit of 1 live checks" in r.json()["error"] and "Nothing was checked or sent" in r.json()["error"]
    assert "decision" not in r.json() and int(r.headers["retry-after"]) > 0
    assert len(seen) == 1  # the refused one never reached a gate
    assert c.post("/api/gate", json=AS_RECORDED, headers=ip("198.51.100.9")).status_code == 200  # replays
    h = c.get("/healthz").json()
    assert h["live_checks"] == "paused" and "used up" in h["public_demo_notice"] and "still replay" in h["public_demo_notice"]


def test_a_cap_refusal_from_db2_is_remembered_until_the_next_utc_day(no_db):
    day = [date(2026, 11, 10)]
    spend = FakeSpend(cap_reached_after=0)
    live = make_live(spend=spend, today=lambda: day[0])
    with pytest.raises(demolive.LiveRefused):
        live.admit("203.0.113.7")
    calls = []
    spend.claim = lambda cap: calls.append(cap)  # type: ignore[method-assign]
    with pytest.raises(demolive.LiveRefused) as err:
        live.admit("203.0.113.7")
    assert err.value.reason == "cap" and calls == []  # refused without asking Db2 again
    day[0] = date(2026, 11, 11)
    spend.claim = lambda cap: (day[0], 1)  # type: ignore[method-assign]
    assert live.admit("203.0.113.7").used == 1


def test_when_the_spend_counter_fails_no_live_check_starts(no_db):
    seen: list = []
    c = app_with(make_live(spend=FakeSpend(error="08001"), seen=seen))
    r = c.post("/api/gate", json=NEW, headers=ip("203.0.113.7"))
    assert r.status_code == 503 and r.json()["reason"] == "spend_counter" and seen == []


# ---------- 3. per-visitor limits ----------
def test_live_checks_are_limited_per_visitor_per_minute(no_db):
    spend = FakeSpend()
    c = app_with(make_live(spend=spend, per_minute=2))
    one, two = ip("203.0.113.7"), ip("198.51.100.9")
    codes = [c.post("/api/gate", json={**NEW, "draft_answer": f"Yes, {i} cats."}, headers=one).status_code
             for i in range(3)]
    assert codes == [200, 200, 429] and spend.used == 2  # the refused one never reached Db2
    assert c.post("/api/gate", json=NEW, headers=two).status_code == 200
    spoof = ip("203.0.113.99, 203.0.113.7")  # what the client claims comes first; the proxy's entry counts
    r = c.post("/api/gate", json=NEW, headers=spoof)
    assert r.status_code == 429 and r.json()["reason"] == "visitor_minute"
    assert c.post("/api/gate", json=AS_RECORDED, headers=one).status_code == 200  # built-ins are not live checks


def test_live_checks_are_limited_per_visitor_per_utc_day(no_db):
    t = [0.0]
    day = [date(2026, 11, 10)]
    live = make_live(per_minute=10, per_day=2, clock=lambda: t[0], today=lambda: day[0])
    for _ in range(2):
        with live.check("203.0.113.7"):
            t[0] += 61
    with pytest.raises(demolive.LiveRefused) as err:
        live.admit("203.0.113.7")
    assert (err.value.status, err.value.reason) == (429, "visitor_day")
    assert live.status("203.0.113.7")["reason"] == "visitor_day" and live.status("198.51.100.9")["state"] == "on"
    day[0] = date(2026, 11, 11)
    assert live.admit("203.0.113.7").used == 3


def test_ipv6_visitors_are_counted_by_their_64():
    assert demolive.visitor_key("2001:db8:1:2:aaaa::1") == demolive.visitor_key("2001:db8:1:2:ffff::9") == \
        "2001:db8:1:2::/64"
    assert demolive.visitor_key("2001:db8:1:3::1") != demolive.visitor_key("2001:db8:1:2::1")
    assert demolive.visitor_key("::ffff:203.0.113.7") == "203.0.113.7"
    assert demolive.visitor_key("203.0.113.7") == "203.0.113.7"
    assert demolive.visitor_key("proxy") == "proxy"


def test_a_refusal_after_the_visitor_layer_gives_the_visitors_slot_back(no_db):
    live = make_live(spend=FakeSpend(error="08001"), per_minute=1, per_day=1)
    for _ in range(3):
        with pytest.raises(demolive.LiveRefused) as err:
            live.admit("203.0.113.7")
        assert err.value.reason == "spend_counter"  # never "visitor_*": nothing was admitted
    assert live.visitors.used_today("203.0.113.7") == 0


# ---------- 5. fail closed: concurrency, provider failures, the pause ----------
def test_at_most_a_few_live_checks_run_at_once():
    live = make_live(per_minute=60, per_day=60)
    held = [live.admit(f"203.0.113.{i}") for i in range(demolive.LIVE_SLOTS)]
    with pytest.raises(demolive.LiveRefused) as err:
        live.admit("198.51.100.9")
    assert (err.value.status, err.value.reason) == (503, "busy")
    live.finish(held[0])
    assert live.admit("198.51.100.9").used == demolive.LIVE_SLOTS + 1


def test_a_provider_failure_mid_check_is_held_and_three_in_a_row_pause_live_checks(no_db):
    spend, replay = FakeSpend(), FakeGate()
    c = app_with(make_live(spend=spend, client=LiveClient(fail=True)), replay)
    for i in range(demolive.PAUSE_AFTER):
        r = c.post("/api/gate", json={**NEW, "draft_answer": f"Yes, {i} cats."}, headers=ip(f"203.0.113.{i}"))
        assert r.status_code == 503 and r.json()["decision"] == "ESCALATED"
        assert r.json()["final_answer"] == HOLDING_REPLY and r.json()["released"] is False
    r = c.post("/api/gate", json=NEW, headers=ip("198.51.100.9"))
    assert r.status_code == 503 and r.json()["reason"] == "provider" and "decision" not in r.json()
    assert spend.used == demolive.PAUSE_AFTER  # the paused one never reached Db2
    assert [rec[1] for rec in spend.records] == [1] * demolive.PAUSE_AFTER
    h = c.get("/healthz").json()
    assert h["live_checks"] == "paused" and "model provider failed" in h["public_demo_notice"]
    assert c.post("/api/gate", json=AS_RECORDED, headers=ip("198.51.100.9")).status_code == 200
    assert len(replay.seen) == 1


def test_the_pause_ends_and_a_success_resets_the_count():
    t = [0.0]
    p = demolive.Pause(after=2, seconds=100, clock=lambda: t[0])
    p.note(failed=True)
    p.note(failed=False)
    p.note(failed=True)
    assert p.remaining_s() == 0
    p.note(failed=True)
    assert p.remaining_s() == 100
    t[0] = 100.5
    assert p.remaining_s() == 0


def test_with_the_real_gate_a_provider_error_holds_the_draft_and_releases_nothing():
    """The real check graph on a provider that fails: the draft is never released, the holding reply goes out."""
    def no_ledger():
        raise db.DatabaseError("no Db2 in this test", "08001")

    live = demolive.LiveChecks(
        model="openrouter:test/model", cap=5, per_minute=5, per_day=5, available=True, client=lambda: LiveClient(fail=True),
        spend=FakeSpend(), gate=lambda m: Gate(m, ZeroEmbeddings(), no_ledger), assistant=lambda m: None,
        recorded=demolive.RecordedInputs([]))
    from asof.gate import GateRequest

    with live.check("203.0.113.7") as s:
        r = s.gate.check(GateRequest(NEW["question"], NEW["draft_answer"], date(2026, 3, 10), "AURELIA-CSP"))
    assert r.decision == "ESCALATED" and r.released is False and r.final_answer == HOLDING_REPLY
    assert s.meter is not None and s.meter.failures == 1


# ---------- the meter ----------
def test_the_meter_counts_calls_tokens_and_failures():
    m = demolive.Meter(LiveClient())
    m.structured(ExtractionResult, [("human", "x")])
    m.tool_round([], [])
    m.chat_model.invoke("hello")
    assert (m.calls, m.input_tokens, m.output_tokens, m.failures) == (3, 127, 33, 0)
    bad = demolive.Meter(ScriptedLLM(extract=[LLMError("down")]))
    with pytest.raises(LLMError):
        bad.structured(ExtractionResult, [("human", "x")])
    assert (bad.calls, bad.failures) == (1, 1)


def test_the_live_client_has_no_local_fallback(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    s = demo_settings(llm_fallback="ollama")
    live = demolive.LiveChecks.from_settings(s, lambda: None, "ASOF", lambda m: None, lambda m: None)
    client = live.client()
    assert client.info == f"openrouter:{s.openrouter_model}" and not hasattr(client, "fallback")


# ---------- 6. the banner and the key ----------
def test_the_banner_says_live_and_never_mentions_the_key(monkeypatch, caplog, no_db):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    caplog.set_level(logging.DEBUG)
    app = create_app(demo_settings(), gate=FakeGate(), assistant=FakeAssistant())
    c = TestClient(app, client=PROXY, raise_server_exceptions=False)
    r = c.get("/healthz")
    h = r.json()
    assert h["live_checks"] == "on" and h["replay"] is True and h["live_model"].startswith("openrouter:")
    assert "checked live by" in h["public_demo_notice"] and "0 of 400" in h["public_demo_notice"]
    assert KEY not in r.text and "key" not in r.text.lower().replace("monkey", "")
    assert KEY not in caplog.text


def test_the_pages_refresh_the_banner_and_show_why_a_live_check_was_refused():
    import pathlib

    ui = pathlib.Path(__file__).resolve().parents[1] / "src" / "asof" / "ui"
    app = (ui / "app.js").read_text()
    assert 'textContent = body.public_demo_notice' in app and "if (health.live) status();" in app
    assert "body.live_checks" in app
    chat = (ui / "chat.js").read_text()
    assert "data.error" in chat and "Array.isArray(data.detail)" in chat
    assert 'maxlength="500"' in (ui / "chat.html").read_text() and demolive.LIVE_QUESTION_MAX == 500


def test_outside_live_mode_the_demo_is_unchanged(no_db):
    c = TestClient(create_app(Settings(_env_file=None, asof_public_demo=True, llm_provider="replay"), gate=FakeGate(),
                              assistant=FakeAssistant()), client=PROXY, raise_server_exceptions=False)
    long_draft = {**NEW, "draft_answer": "d" * (demolive.LIVE_DRAFT_MAX + 1)}
    assert c.post("/api/gate", json=long_draft).status_code == 200  # the replay gate; no live limits apply
    h = c.get("/healthz").json()
    assert h["live_checks"] is None and h["live_model"] is None
