"""The customer chat demo (ui/chat.html): served under the same strict CSP, renders API text as text only, and every
suggested question is one replay mode can answer for its booking's date."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from test_api import FakeAssistant, FakeGate

from asof import replay
from asof.api import create_app
from asof.config import Settings

UI = Path(__file__).resolve().parents[1] / "src" / "asof" / "ui"


def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant()))


def test_the_chat_page_is_served_under_the_strict_csp_and_linked_from_the_console():
    c = client()
    r = c.get("/ui/chat.html")
    assert r.status_code == 200 and "Aurelia Air" in r.text
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp
    assert c.get("/chat", follow_redirects=False).headers["location"] == "/ui/chat.html"
    assert 'href="chat.html"' in (UI / "index.html").read_text(encoding="utf-8")


def test_the_page_has_no_inline_script_style_or_handlers():
    page = (UI / "chat.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", page) and "<style" not in page
    assert not re.search(r"\sstyle=|\son[a-z]+=", page)


def test_api_text_is_only_ever_set_as_text():
    js = (UI / "chat.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js and "outerHTML" not in js and "insertAdjacentHTML" not in js
    assert "eval(" not in js and "new Function" not in js
    assert "textContent" in js


def test_every_booking_suggests_questions_replay_mode_has_for_that_date():
    bookings = replay.load_scenarios()["chat"]["bookings"]
    assert len({b["ref"] for b in bookings}) == len(bookings) >= 3
    recorded = {(c["question"], c["as_of"]) for c in replay.Recording.load().scenarios["checks"] if c["draft"] is None}
    decisions = {}
    for b in bookings:
        date.fromisoformat(b["booked"])
        for q in b["questions"]:
            assert (q, b["booked"]) in recorded, f"{b['ref']}: not recorded; python -m asof.replay record --only chat"
            decisions[b["ref"]] = next(c["decision"] for c in replay.Recording.load().scenarios["checks"]
                                       if c["question"] == q and c["as_of"] == b["booked"] and c["draft"] is None)
    assert {"PASS", "CORRECTED", "ESCALATED"} <= set(decisions.values())  # the demo shows all three outcomes
