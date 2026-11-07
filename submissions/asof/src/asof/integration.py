"""Drop AsOf into an existing LangChain app.

    from asof import as_runnable
    chain = assistant_prompt | llm | StrOutputParser() | as_runnable(as_of=booking_date)

The runnable takes the assistant's draft (a string, or a dict with "draft" and optionally
"question") and returns the checked answer: the draft with policy references (PASS), a
corrected answer (CORRECTED), or a holding reply (ESCALATED). Every decision is recorded in
the Db2 ledger. Pass output="result" to get the full GateResult instead of text.
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


def as_runnable(*, as_of: date, doc_id: str = "AURELIA-CSP", question: str = "", channel: str = "api",
                output: Literal["text", "result"] = "text", gate: Gate | None = None) -> RunnableLambda:
    checker = gate or build_gate()

    def run(value: Any) -> str | GateResult:
        if isinstance(value, str):
            draft, q = value, question
        elif isinstance(value, dict) and isinstance(value.get("draft"), str):
            draft, q = value["draft"], value.get("question", question)
        else:
            raise TypeError("as_runnable expects the draft as a string or {'draft': ..., 'question': ...}")
        from .api import GateIn  # the API's own input model: byte limits, date range, allowed doc_id and channel

        checked = GateIn(question=q or "(question not provided)", draft_answer=draft, as_of_date=as_of,
                         doc_id=doc_id, channel=channel)
        result = checker.check(GateRequest(checked.question, checked.draft_answer, checked.as_of_date, checked.doc_id,
                                           checked.channel))
        return result if output == "result" else result.final_answer

    return RunnableLambda(run, name="AsOfCheck")
