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
