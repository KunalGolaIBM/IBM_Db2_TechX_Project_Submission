"""The gate when Db2 refuses a release (08_release_rules.sql): held, recorded, never sent (no Db2, no network)."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fakes import ScriptedLLM, ZeroEmbeddings, claims, clause, judge, verdict

from asof import db
from asof import gate as gate_mod
from asof.gate import HOLDING_REPLY, Gate, GateRequest
from asof.ledger import RELEASE_REFUSALS, Appended

JUNE = date(2026, 6, 2)
RETRO = "You can apply for the bereavement discount retroactively within 90 days of ticket issue."
V2_QUOTE = "A retroactive request must be submitted within 90 days of the date the original ticket was issued"


class FakeConn:
    def close(self):
        pass


@pytest.fixture
def world(monkeypatch):
    """Retrieval returns BRV-002 as of the date; each append either raises the next queued error or is captured."""
    state: dict = {"entries": [], "refuse": []}

    def fake_retrieve(conn, vec, as_of, doc_id, k, system_time=None, schema="ASOF"):
        return [clause("BRV-002", as_of)]

    def fake_append(conn, entry, schema="ASOF"):
        state["entries"].append(entry)
        if state["refuse"]:
            raise state["refuse"].pop(0)
        return Appended(len(state["entries"]), "h" * 64, datetime(2026, 11, 10))

    monkeypatch.setattr(gate_mod, "clauses_as_of", fake_retrieve)
    monkeypatch.setattr(gate_mod.ledger, "append", fake_append)
    return state


def supported_check() -> Gate:
    llm = ScriptedLLM(extract=[claims((RETRO, "bereavement", "deadline"))],
                      judge=[judge(verdict(1, "SUPPORTED", "BRV-002", V2_QUOTE))])
    return Gate(llm, ZeroEmbeddings(), connect=FakeConn)


def refusal(state: str) -> db.DatabaseError:
    return db.DatabaseError(f"APPEND_LEDGER failed: SQL0438N Release refused (SQLSTATE={state})", state, -438)


@pytest.mark.parametrize("sqlstate", sorted(RELEASE_REFUSALS))
def test_a_refused_release_is_held_and_the_hold_is_recorded(world, sqlstate):
    world["refuse"] = [refusal(sqlstate)]
    r = supported_check().check(GateRequest("Can I claim it after I fly?", RETRO, JUNE, "AURELIA-CSP", "api"))

    assert (r.decision, r.reason_code, r.final_answer) == ("ESCALATED", "RELEASE_REFUSED", HOLDING_REPLY)
    assert r.released is True and r.ledger_id == 2  # the holding reply goes out, and the hold is in the ledger
    assert sqlstate in (r.error or "")
    first, held = world["entries"]
    assert (first.decision, first.reason_code) == ("PASS", "ALL_SUPPORTED")  # what the check wanted to release
    assert (held.decision, held.reason_code, held.final_answer) == ("ESCALATED", "RELEASE_REFUSED", HOLDING_REPLY)
    assert held.verdicts["release_refused"] == {"decision": "PASS", "reason_code": "ALL_SUPPORTED", "sqlstate": sqlstate,
                                                "detail": RELEASE_REFUSALS[sqlstate]}
    assert held.verdicts["claims"] == first.verdicts["claims"]  # the evidence of what was refused stays on record
    assert RETRO not in held.final_answer


def test_if_the_hold_cannot_be_recorded_either_nothing_is_released(world):
    world["refuse"] = [refusal("75081"), RuntimeError("db down")]
    r = supported_check().check(GateRequest("Can I claim it after I fly?", RETRO, JUNE, "AURELIA-CSP", "api"))
    assert (r.decision, r.reason_code, r.final_answer) == ("ESCALATED", "LEDGER_UNAVAILABLE", HOLDING_REPLY)
    assert r.released is False and r.ledger_id is None


def test_any_other_database_error_is_not_mistaken_for_a_refused_release(world):
    world["refuse"] = [db.DatabaseError("APPEND_LEDGER failed: lock timeout", "40001", -911)]
    r = supported_check().check(GateRequest("Can I claim it after I fly?", RETRO, JUNE, "AURELIA-CSP", "api"))
    assert (r.reason_code, r.released) == ("LEDGER_UNAVAILABLE", False)
    assert len(world["entries"]) == 1  # no second append: only Db2's release rules turn into a recorded hold
