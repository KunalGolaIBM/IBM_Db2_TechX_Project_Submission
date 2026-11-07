"""as_runnable(): AsOf as a step in someone else's LangChain chain, validated like the API."""

from __future__ import annotations

from datetime import date

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from asof.integration import as_runnable


class RecordingGate:
    def __init__(self):
        self.requests = []

    def check(self, req):
        self.requests.append(req)

        class Result:
            final_answer = "checked: " + req.draft_answer

        return Result()


def test_it_chains_after_an_assistant_and_returns_what_asof_releases():
    gate = RecordingGate()
    chain = RunnableLambda(lambda q: "The overdraft fee is $25.") | as_runnable(
        as_of=date(2026, 8, 3), doc_id="FERNHOLLOW-FEES", question="Overdraft fee?", gate=gate)
    assert chain.invoke("anything") == "checked: The overdraft fee is $25."
    assert (gate.requests[0].doc_id, gate.requests[0].as_of) == ("FERNHOLLOW-FEES", date(2026, 8, 3))


@pytest.mark.parametrize("kwargs, draft", [
    ({"doc_id": "SOMEONE-ELSE"}, "fine"),
    ({"as_of": date(2019, 1, 1)}, "fine"),
    ({}, "x" * 4001),
    ({}, "bad\x00byte"),
])
def test_bad_input_is_refused_before_any_check(kwargs, draft):
    gate = RecordingGate()
    step = as_runnable(**({"as_of": date(2026, 3, 10), "gate": gate} | kwargs))
    with pytest.raises(ValidationError):
        step.invoke(draft)
    assert gate.requests == []


def test_one_chain_serves_every_customer_with_their_own_question_and_date():
    """The assistant's draft joins the input dict; the question and the date travel with each call."""
    from langchain_core.runnables import RunnablePassthrough

    gate = RecordingGate()
    assistant = RunnableLambda(lambda d: f"Answer to: {d['question']}")
    chain = RunnablePassthrough.assign(draft=assistant) | as_runnable(gate=gate)
    chain.invoke({"question": "Bereavement fare after travel?", "as_of": date(2026, 3, 10)})
    chain.invoke({"question": "Bereavement fare after travel?", "as_of": "2026-06-02"})
    assert [(r.as_of, r.question, r.draft_answer) for r in gate.requests] == [
        (date(2026, 3, 10), "Bereavement fare after travel?", "Answer to: Bereavement fare after travel?"),
        (date(2026, 6, 2), "Bereavement fare after travel?", "Answer to: Bereavement fare after travel?")]


def test_a_call_without_any_date_is_refused_not_guessed():
    gate = RecordingGate()
    with pytest.raises(ValueError, match="customer's date"):
        as_runnable(gate=gate).invoke({"draft": "Bags are $40.", "question": "Bag fee?"})
    assert gate.requests == []
