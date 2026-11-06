"""The Langflow component, without a server: what it sends, what it passes on, and what it refuses.

Runs in the Langflow virtualenv (langflow/requirements-langflow.txt); skipped anywhere lfx is not installed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("lfx")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "components"))

from asof_policy import asof_check  # noqa: E402
from asof_policy.asof_check import AsOfCheckComponent  # noqa: E402


class Reply:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


def component(**over):
    c = AsOfCheckComponent()
    values = {"draft_answer": "The overdraft fee is $35.", "question": "Overdraft fee?", "as_of_date": "2026-08-03",
              "doc_id": "FERNHOLLOW-FEES", "api_url": "http://127.0.0.1:8000", "api_token": "", "timeout_s": 30}
    values.update(over)
    for k, v in values.items():
        setattr(c, k, v)
    return c


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers})
        return calls_reply[0]

    calls_reply = [Reply(200, {"decision": "CORRECTED", "reason_code": "CORRECTED_FROM_CLAUSES", "released": True,
                               "ledger_id": 7, "final_answer": "The overdraft fee is $25.", "claims": []})]
    monkeypatch.setattr(asof_check.httpx, "post", fake_post)
    return calls, calls_reply


def test_it_sends_the_check_and_passes_on_only_what_asof_released(sent):
    calls, _ = sent
    c = component()
    assert c.checked_answer().text == "The overdraft fee is $25."
    assert c.verdicts().data["decision"] == "CORRECTED"
    assert len(calls) == 1  # both outputs share one check
    assert calls[0]["url"] == "http://127.0.0.1:8000/api/gate"
    assert calls[0]["json"]["doc_id"] == "FERNHOLLOW-FEES" and calls[0]["json"]["as_of_date"] == "2026-08-03"
    assert "authorization" not in calls[0]["headers"]


def test_a_held_answer_becomes_the_holding_reply_and_the_token_is_sent(sent):
    calls, reply = sent
    reply[0] = Reply(503, {"decision": "ESCALATED", "reason_code": "NOT_COVERED", "released": False, "ledger_id": 8,
                           "final_answer": "A specialist will confirm this for you.", "claims": []})
    c = component(api_token="a-long-test-token-0123")  # noqa: S106 - a fake token for the header check
    assert c.checked_answer().text == "A specialist will confirm this for you."
    assert calls[0]["headers"]["authorization"] == "Bearer a-long-test-token-0123"


@pytest.mark.parametrize("over, message", [
    ({"as_of_date": "next tuesday"}, "ISO date"),
    ({"api_url": "file:///etc/passwd"}, "http"),
    ({"api_url": "http://host/path"}, "no path"),
    ({"doc_id": "SOMEONE-ELSE"}, "doc_id"),
])
def test_bad_settings_are_refused_before_any_request(sent, over, message):
    calls, _ = sent
    with pytest.raises(ValueError, match=message):
        component(**over).checked_answer()
    assert calls == []


def test_an_error_from_asof_is_raised_not_passed_on(sent):
    _, reply = sent
    reply[0] = Reply(401, {"error": "this AsOf server needs an API token"})
    with pytest.raises(ValueError, match="HTTP 401"):
        component().checked_answer()
