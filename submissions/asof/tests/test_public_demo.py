"""The public demo (ASOF_PUBLIC_DEMO=true): replay mode only, no model keys, and nothing that changes policy or sends
anything, even though every request reaches the app from its own reverse proxy on localhost."""
from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_api import FakeAssistant, FakeGate

from asof import intake
from asof.api import create_app
from asof.config import Settings

PROXY = ("127.0.0.1", 51000)   # Caddy on the same machine: the peer every demo request comes from
CHANGE = {"clause_id": "PET-001", "effective_from": "2026-12-01", "version_label": "v2",
          "clause_text": "Small cats and dogs may travel in the cabin. The pet fee is $125 each way.",
          "rule": {"pet_fee_usd": 125}, "change_note": "a test change"}
REPLY = {"reply": "Yes, as long as you ask before you fly."}


def demo_settings(**extra) -> Settings:
    return Settings(_env_file=None, asof_public_demo=True, llm_provider="replay", **extra)


@pytest.fixture
def demo(monkeypatch):
    def no_db(*_a, **_k):
        raise AssertionError("a refused action must not reach Db2")
    monkeypatch.setattr("asof.db.connect", no_db)
    app = create_app(demo_settings(), gate=FakeGate(), assistant=FakeAssistant(), rate_limit=50, read_limit=50)
    return TestClient(app, client=PROXY, raise_server_exceptions=False)


def test_off_by_default():
    assert Settings(_env_file=None).asof_public_demo is False


def test_the_demo_runs_in_replay_mode_only():
    with pytest.raises(ValidationError, match="replay mode only"):
        Settings(_env_file=None, asof_public_demo=True, llm_provider="openrouter")


@pytest.mark.parametrize("key", ["openrouter_api_key", "watsonx_api_key", "openai_compat_api_key", "embedding_api_key"])
def test_the_demo_refuses_to_hold_model_keys(key):
    with pytest.raises(ValidationError, match="holds no model keys"):
        demo_settings(**{key: "sk-not-a-real-key-0000000000"})


@pytest.mark.parametrize(("method", "path", "body"), [
    ("post", "/api/policy/change", CHANGE),
    ("post", "/api/policy/drafts/1/decision", {"approve": True, "accept": [1]}),
    ("post", "/api/policy/drafts/1/decision", {"approve": False}),
    ("post", "/api/reviews/12/resolve", REPLY),
    ("post", "/api/notices/draft", {"clause_id": "PET-001"}),
    ("post", "/api/notices/1/decision", {"approve": True}),
    ("post", "/api/impact/PET-001/suggestions", None),
    ("post", "/api/suggestions/1/decision", {"approve": True}),
])
def test_every_write_is_refused_even_from_the_local_proxy(demo, method, path, body):
    r = getattr(demo, method)(path, json=body) if body is not None else getattr(demo, method)(path)
    assert r.status_code == 403
    assert r.json()["detail"].startswith("Disabled in the public demo: ")
    assert "quickstart" in r.json()["detail"]


def test_only_the_built_in_sample_can_be_uploaded(demo):
    r = demo.post("/api/policy/drafts?doc_id=AURELIA-CSP&name=mine.pdf", content=b"%PDF-1.4 not the sample",
                  headers={"content-type": "application/pdf"})
    assert r.status_code == 403 and "Use the sample works" in r.json()["detail"]


def test_the_sample_upload_is_not_refused(demo, monkeypatch):
    seen = []
    monkeypatch.setattr(intake, "read_pdf", lambda data, name: seen.append(data) or (_ for _ in ()).throw(
        intake.IntakeError("stop here: past the demo check")))
    r = demo.post("/api/policy/drafts?doc_id=AURELIA-CSP&name=sample.pdf", content=intake.SAMPLE_PDF.read_bytes(),
                  headers={"content-type": "application/pdf"})
    assert r.status_code == 422 and seen == [intake.SAMPLE_PDF.read_bytes()]


@pytest.mark.parametrize(("path", "body"), [
    ("/api/reviews/12/check", REPLY),
    ("/api/policy/preview", CHANGE),
    ("/api/policy/drafts/1/decision", {"approve": True, "accept": [1], "preview": True}),
])
def test_checks_and_previews_are_not_refused(demo, path, body):
    r = demo.post(path, json=body)
    assert r.status_code != 403, r.text


def test_outside_the_demo_local_writes_are_unchanged(monkeypatch):
    monkeypatch.setattr("asof.db.connect", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("reached Db2")))
    c = TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant()), client=PROXY,
                   raise_server_exceptions=False)
    r = c.post("/api/notices/1/decision", json={"approve": True})
    assert r.status_code == 500  # past every check, into Db2: local mode trusts localhost as before


def test_rate_limits_follow_the_forwarded_address(monkeypatch):
    monkeypatch.setattr("asof.db.connect", lambda *a, **k: None)
    c = TestClient(create_app(demo_settings(), gate=FakeGate(), assistant=FakeAssistant(), rate_limit=2, read_limit=50),
                   client=PROXY, raise_server_exceptions=False)
    one, two = {"x-forwarded-for": "203.0.113.7"}, {"x-forwarded-for": "198.51.100.9"}
    codes = [c.post("/api/policy/change", json=CHANGE, headers=one).status_code for _ in range(3)]
    assert codes == [403, 403, 429]
    assert c.post("/api/policy/change", json=CHANGE, headers=two).status_code == 403   # another visitor is not limited
    # what a client claims comes first; the entry Caddy sets is the last one, and that is the one counted
    spoof = {"x-forwarded-for": "198.51.100.9, 203.0.113.7"}
    assert c.post("/api/policy/change", json=CHANGE, headers=spoof).status_code == 429


def test_reads_are_limited_per_address_in_the_demo(monkeypatch):
    monkeypatch.setattr("asof.db.connect", lambda *a, **k: None)
    c = TestClient(create_app(demo_settings(), gate=FakeGate(), assistant=FakeAssistant(), read_limit=2),
                   client=PROXY, raise_server_exceptions=False)
    ip = {"x-forwarded-for": "203.0.113.7"}
    codes = [c.get("/api/whoami", headers=ip).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def _db_down(*_a, **_k):
    from asof import db
    raise db.DatabaseError("Db2 is down in this test", "08001")


@pytest.mark.parametrize(("demo_on", "notice"), [(True, "Public demo: the built-in scenarios replay recorded model outputs "
                                                  "while Db2 runs live. To check your own answers, run AsOf locally with "
                                                  "./quickstart.sh."), (False, None)])
def test_the_pages_get_the_public_demo_notice_only_in_the_demo(monkeypatch, demo_on, notice):
    monkeypatch.setattr("asof.db.connect", _db_down)
    settings = demo_settings() if demo_on else Settings(_env_file=None, llm_provider="replay")
    body = TestClient(create_app(settings, gate=FakeGate(), assistant=FakeAssistant())).get("/healthz").json()
    assert body["public_demo"] is demo_on and body["public_demo_notice"] == notice


def test_both_pages_show_the_servers_notice_instead_of_the_key_advice():
    ui = pathlib.Path(__file__).resolve().parents[1] / "src" / "asof" / "ui"
    assert "body.public_demo_notice ||" in (ui / "app.js").read_text()
    chat = (ui / "chat.js").read_text()
    assert "health.public_demo_notice" in chat and "state.notice ||" in chat

