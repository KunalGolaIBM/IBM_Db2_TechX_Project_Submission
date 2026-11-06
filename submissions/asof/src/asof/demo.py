"""Record a handful of real decisions so the UI has history to show.

    python -m asof.demo

Asks the naive demo assistant each question below for the given customer date, checks its
draft with the gate (real LLM, real Db2), and records the decision in the ASOF ledger. The
two pet questions (November and December trips) are what the change-impact screen uses
after the "pet fee to $125 from 1 Dec 2026" preset. The bank drafts below are checked as written
(the demo assistant only knows the airline), against Fernhollow Bank's fee schedule.
"""

from __future__ import annotations

import sys
from datetime import date

from . import db
from .assistant import DemoAssistant
from .config import ConfigError, get_settings
from .embeddings import get_embeddings
from .gate import Gate, GateRequest
from .llm import LLMError, build_llm

MOFFATT = "My grandmother just died. Can I get the bereavement fare after I travel?"
PETS = "Can my cat fly in the cabin with me, and what does it cost?"
SCENARIOS = [
    (MOFFATT, date(2026, 3, 10)),
    (MOFFATT, date(2026, 6, 2)),
    ("How much is the first checked bag?", date(2026, 7, 15)),
    ("Can I transfer my ticket to a friend?", date(2026, 4, 1)),
    (PETS, date(2026, 11, 20)),
    (PETS, date(2026, 12, 15)),
    ("Can my 12-year-old fly alone?", date(2026, 8, 1)),
]
REFUND = "I was charged an overdraft fee yesterday. Will you refund it?"
BANK_DRAFTS = [  # (question, a bank assistant's draft, customer date)
    (REFUND, "Yes, don't worry: overdraft fees are refunded automatically within a few days.", date(2026, 3, 15)),
    (REFUND, "Overdraft fees are not refunded automatically, but you can ask us for a courtesy refund of up to two "
             "overdraft fees in any 12-month period, within 60 days of the date the fee was charged.", date(2026, 9, 10)),
    ("How much is the overdraft fee?", "The overdraft fee is $35 for each item we pay.", date(2026, 8, 3)),
]


def main() -> int:
    settings = get_settings()
    try:
        llm = build_llm(settings)
        emb = get_embeddings(settings.embedding_model)
        connect = lambda: db.connect(settings, "app")  # noqa: E731
        assistant, gate = DemoAssistant(llm, emb, connect), Gate(llm, emb, connect)
        for question, as_of in SCENARIOS:
            draft = assistant.answer(question)
            r = gate.check(GateRequest(question, draft.text, as_of, "AURELIA-CSP", "demo"))
            print(f"#{r.ledger_id}  {as_of}  {r.decision:<9} {r.reason_code:<24} {question}")
        for question, draft_text, as_of in BANK_DRAFTS:
            r = gate.check(GateRequest(question, draft_text, as_of, "FERNHOLLOW-FEES", "demo"))
            print(f"#{r.ledger_id}  {as_of}  {r.decision:<9} {r.reason_code:<24} {question} (bank)")
    except (ConfigError, LLMError, db.DatabaseError) as exc:
        print(f"Demo failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
