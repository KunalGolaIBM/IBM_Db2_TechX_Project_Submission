"""Drop AsOf into an existing LangChain app.

    from langchain_core.runnables import RunnablePassthrough
    from asof import as_runnable

    chain = RunnablePassthrough.assign(draft=assistant_prompt | llm | StrOutputParser()) | as_runnable()
    chain.invoke({"question": "Can I get a bereavement fare after I travel?", "as_of": booking_date})

One chain serves every customer: the runnable takes a dict with the assistant's "draft", the
customer's "question" (the check tests the premises a draft states against it) and "as_of", the
customer's date as the calling system knows it (a date or an ISO string). A plain string is taken
as the draft, with the question and date given when the runnable was built. A call with no date
anywhere is refused: the date is never guessed. It returns the checked answer (the draft with
policy references, a corrected answer, or a holding reply), and every decision is recorded in the
Db2 ledger. Pass output="result" to get the full GateResult instead of text.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from langchain_core.runnables import RunnableLambda

from . import db
from .anchor import AnchorLog
from .config import Settings, get_settings
from .embeddings import get_embeddings
from .gate import Gate, GateRequest, GateResult
from .llm import build_llm


def build_gate(settings: Settings | None = None, schema: str = db.SCHEMA) -> Gate:
    settings = settings or get_settings()
    settings.require("asof_app_password")
    return Gate(build_llm(settings), get_embeddings(settings.embedding_model),
                connect=db.ConnectionPool(settings, "app").connect, schema=schema,
                anchors=AnchorLog.from_settings(settings, schema))  # every write to a ledger is anchored


def as_runnable(*, as_of: date | None = None, doc_id: str = "AURELIA-CSP", question: str = "", channel: str = "api",
                output: Literal["text", "result"] = "text", gate: Gate | None = None) -> RunnableLambda[Any, Any]:
    """`as_of` and `question` are defaults for calls that pass only a draft; a dict input overrides them."""
    checker = gate or build_gate()

    def run(value: Any) -> str | GateResult:
        if isinstance(value, str):
            draft, q, day = value, question, as_of
        elif isinstance(value, dict) and isinstance(value.get("draft"), str):
            draft, q, day = value["draft"], value.get("question", question), value.get("as_of", as_of)
        else:
            raise TypeError("as_runnable expects the draft as a string or {'draft': ..., 'question': ..., 'as_of': ...}")
        if day is None:
            raise ValueError("AsOf needs the customer's date: pass 'as_of' in the input or to as_runnable()")
        from .api import GateIn  # the API's own input model: byte limits, date range, allowed doc_id and channel

        checked = GateIn.model_validate({"question": q or "(question not provided)", "draft_answer": draft,
                                         "as_of_date": day, "doc_id": doc_id, "channel": channel})
        result = checker.check(GateRequest(checked.question, checked.draft_answer, checked.as_of_date, checked.doc_id,
                                           checked.channel))
        return result if output == "result" else result.final_answer

    return RunnableLambda(run, name="AsOfCheck")
