"""The specialist inbox: held decisions, answered by a person, and the answer checked like any other.

    held (ESCALATED) -> a specialist reads the question, the assistant's draft, every claim with the clause
    version it was checked against, and the policy in force on the customer's date -> writes or edits a
    reply -> the full check on the reply (Gate.assess: one pass, no rewrite, nothing recorded) ->
    RESOLVE_ESCALATION appends it as a REVIEWED decision, linked to the held one, in the hash chain

A person may do what the model may not: answer what no clause covers, on their own judgment, with a note
that goes on record. They may not send a reply that contradicts the policy in force on the customer's
date, or one stating a detail the check could not cover: the reply is refused here, and Db2 refuses it
again in RESOLVE_ESCALATION from the verdicts it is asked to record. A reply is recorded only once it is
sent, so the ledger holds what the customer was told, not every draft the specialist tried.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import ibm_db_dbi
from langchain_core.embeddings import Embeddings

from . import db, ledger
from .gate import Gate, GateRequest, GateResult, policy_terms, references
from .redact import redact
from .retriever import clauses_as_of

log = logging.getLogger(__name__)

MAX_REPLY_CHARS = 3500
MIN_NOTE_CHARS = 10
SENDABLE = ("ALL_SUPPORTED", "NO_POLICY_CLAIMS", "NOT_COVERED")  # the reply check's reasons a specialist may send

# Every statement is a literal; names are unqualified (db.use_schema binds the schema).
SQL_OPEN = ("SELECT Q.LEDGER_ID, Q.CREATED_AT, Q.CHANNEL, Q.DOC_ID, Q.AS_OF_DATE, Q.REASON_CODE, L.QUESTION_REDACTED, "
            "MINUTES_BETWEEN(CURRENT TIMESTAMP, Q.CREATED_AT) "
            "FROM V_REVIEW_QUEUE Q JOIN ANSWER_LEDGER L ON L.LEDGER_ID = Q.LEDGER_ID "
            "WHERE Q.STATE = 'OPEN' ORDER BY Q.LEDGER_ID FETCH FIRST ? ROWS ONLY")
SQL_ANSWERED = ("SELECT Q.LEDGER_ID, Q.CREATED_AT, Q.CHANNEL, Q.DOC_ID, Q.AS_OF_DATE, Q.REASON_CODE, L.QUESTION_REDACTED, "
                "MINUTES_BETWEEN(Q.ANSWERED_AT, Q.CREATED_AT), Q.REVIEW_LEDGER_ID, Q.OUTCOME, Q.REVIEWER, Q.ANSWERED_AT "
                "FROM V_REVIEW_QUEUE Q JOIN ANSWER_LEDGER L ON L.LEDGER_ID = Q.LEDGER_ID "
                "WHERE Q.STATE = 'ANSWERED' ORDER BY Q.ANSWERED_AT DESC FETCH FIRST ? ROWS ONLY")
SQL_COUNTS = "SELECT STATE, COUNT(*), MAX(MINUTES_BETWEEN(CURRENT TIMESTAMP, CREATED_AT)) FROM V_REVIEW_QUEUE GROUP BY STATE"
SQL_REVIEW_OF = ("SELECT REVIEW_LEDGER_ID, OUTCOME, REVIEWER, NOTE, CREATED_AT FROM ESCALATION_REVIEW "
                 "WHERE ESCALATED_LEDGER_ID = ?")
SQL_REVIEWED_FOR = ("SELECT ESCALATED_LEDGER_ID, OUTCOME, REVIEWER, NOTE, CREATED_AT FROM ESCALATION_REVIEW "
                    "WHERE REVIEW_LEDGER_ID = ?")

# Db2's refusals in RESOLVE_ESCALATION, as HTTP statuses for the API.
REFUSALS = {"75050": 404, "75051": 409, "75052": 409, "75053": 422, "75054": 403, "75055": 409, "75056": 422,
            "75057": 422, "75030": 403, "23505": 409}


class ReviewError(Exception):
    """A reply the inbox will not send. `check` is the reply's check, for the specialist to read."""

    def __init__(self, status: int, message: str, check: GateResult | None = None):
        super().__init__(message)
        self.status, self.check = status, check


@dataclass(frozen=True)
class Resolved:
    ledger_id: int
    row_hash: str
    outcome: str
    final_answer: str
    check: GateResult


def _strip(v: Any) -> Any:
    return v.strip() if isinstance(v, str) else v


def queue(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA, limit: int = 50) -> dict[str, Any]:
    """Held decisions waiting for a specialist (oldest first) and the latest answered ones, as the runtime user."""
    db.use_schema(conn, schema)
    keys = ("ledger_id", "created_at", "channel", "doc_id", "as_of_date", "reason_code", "question")
    open_items = [dict(zip((*keys, "waiting_minutes"), map(_strip, r), strict=True))
                  for r in db.query(conn, SQL_OPEN, (limit,))]
    answered = [dict(zip((*keys, "minutes_to_answer", "review_ledger_id", "outcome", "reviewer", "answered_at"),
                         map(_strip, r), strict=True)) for r in db.query(conn, SQL_ANSWERED, (limit,))]
    counts = {r[0].strip(): {"count": int(r[1]), "oldest_minutes": int(r[2] or 0)} for r in db.query(conn, SQL_COUNTS)}
    return {"open": open_items, "answered": answered,
            "counts": {"open": counts.get("OPEN", {}).get("count", 0),
                       "answered": counts.get("ANSWERED", {}).get("count", 0),
                       "oldest_open_minutes": counts.get("OPEN", {}).get("oldest_minutes", 0)}}


def review_of(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    """The specialist's answer to a held decision, if it has one."""
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_REVIEW_OF, (ledger_id,))
    if not rows:
        return None
    return dict(zip(("review_ledger_id", "outcome", "reviewer", "note", "answered_at"), map(_strip, rows[0]),
                    strict=True))


def reviewed_for(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    """For a REVIEWED ledger row: the held decision it answered."""
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_REVIEWED_FOR, (ledger_id,))
    if not rows:
        return None
    return dict(zip(("escalated_ledger_id", "outcome", "reviewer", "note", "answered_at"), map(_strip, rows[0]),
                    strict=True))


def held_entry(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any]:
    """The held decision, or a ReviewError if there is none or it was not held."""
    entry = ledger.get_entry(conn, ledger_id, schema)
    if entry is None:
        raise ReviewError(404, "no such ledger entry")
    if entry["decision"].strip() != "ESCALATED":
        raise ReviewError(409, "only a held (ESCALATED) decision goes to a specialist")
    return entry


def detail(connect: Callable[[], ibm_db_dbi.Connection], embeddings: Embeddings, ledger_id: int,
           schema: str = db.SCHEMA) -> dict[str, Any]:
    """Everything the specialist reads before answering: the held decision with its claims, each cited clause as
    it was used and as it applies now, the clauses in force on the customer's date nearest the question, and the
    answer if one was sent. Needs no language model."""
    conn = connect()
    try:
        entry = held_entry(conn, ledger_id, schema)
        replayed = ledger.replay(conn, ledger_id, schema) or {"clauses": []}
        answered = review_of(conn, ledger_id, schema)
        vector = embeddings.embed_query(entry["question_redacted"])
        nearest = clauses_as_of(conn, vector, entry["as_of_date"], entry["doc_id"].strip(), 4, schema=schema)
    finally:
        conn.close()
    verdicts = entry["verdicts"]
    claims = [c for c in verdicts.get("claims", []) if isinstance(c, dict)]
    return {
        "ledger_id": ledger_id, "created_at": entry["created_at"], "channel": entry["channel"].strip(),
        "doc_id": entry["doc_id"].strip(), "as_of_date": entry["as_of_date"], "reason_code": entry["reason_code"].strip(),
        "question": entry["question_redacted"], "draft": entry["draft_redacted"], "holding_reply": entry["final_answer"],
        "rewrite": verdicts.get("rewrite"), "claims": claims, "unchecked": verdicts.get("unchecked") or [],
        "requested_by": verdicts.get("requested_by"), "route": verdicts.get("route"),
        "cited": replayed["clauses"],
        "in_force": [{"clause_id": c.clause_id, "title": c.title, "version": c.version_label, "from": c.bus_start,
                      "to": c.bus_end, "text": c.clause_text, "distance": round(c.distance, 4)} for c in nearest],
        "answered": answered,
    }


def _request(entry: dict[str, Any], reply: str, doc_id: str, reviewer: str | None) -> GateRequest:
    return GateRequest(entry["question_redacted"], reply, entry["as_of_date"], doc_id, entry["channel"].strip(), reviewer)


def _validate(reply: str, doc_id: str, entry: dict[str, Any]) -> str:
    reply = reply.strip()
    if not reply:
        raise ReviewError(422, "the reply is empty")
    if len(reply) > MAX_REPLY_CHARS:
        raise ReviewError(422, f"the reply is longer than {MAX_REPLY_CHARS} characters")
    if doc_id != entry["doc_id"].strip() and entry["reason_code"].strip() != "ROUTE_UNCERTAIN":
        raise ReviewError(422, "the reply must be checked against the held decision's policy document")
    return reply


def check_reply(gate: Gate, ledger_id: int, reply: str, doc_id: str | None = None,
                reviewer: str | None = None) -> GateResult:
    """The full check of a reply on the customer's date, recording nothing (the specialist's "Check" button)."""
    conn = gate.connect()
    try:
        entry = held_entry(conn, ledger_id, gate.schema)
    finally:
        conn.close()
    doc = doc_id or entry["doc_id"].strip()
    reply = _validate(reply, doc, entry)
    return assess(gate, _request(entry, reply, doc, reviewer))


def policy_sentences(text: str) -> list[str]:
    """The sentences of `text` that state something a policy decides."""
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]
    return [x for x in sentences if policy_terms(x)]


def assess(gate: Gate, req: GateRequest) -> GateResult:
    """The reply's check: the full check graph, once, recording nothing. If extraction found no claim in a reply that
    talks policy, its policy sentences are judged as claims of their own (Gate.assess_sentences), so a contradiction
    the extractor missed is still refused, not merely sent on a note."""
    result = gate.assess(req)
    if result.reason_code == "NO_POLICY_CLAIMS" and policy_terms(req.draft_answer):
        sentences = policy_sentences(req.draft_answer)
        if sentences:
            log.info("extraction found no claim in a reply that talks policy; judging %d sentence(s) as written",
                     len(sentences))
            return gate.assess_sentences(req, sentences)
    return result


def final_text(reply: str, result: GateResult) -> str:
    """What the customer is sent: the reply, with references to every clause a claim of it is supported by."""
    supported = [c for c in result.claims if c.verdict == "SUPPORTED"]
    return reply + references(supported)


def resolve(gate: Gate, ledger_id: int, reply: str, note: str | None = None, doc_id: str | None = None,
            reviewer: str | None = None) -> Resolved:
    """Check the reply and, if it may be sent, append it to the ledger through RESOLVE_ESCALATION. Commits."""
    conn = gate.connect()
    try:
        entry = held_entry(conn, ledger_id, gate.schema)
        if review_of(conn, ledger_id, gate.schema) is not None:
            raise ReviewError(409, "a specialist has already answered this decision")
    finally:
        conn.close()
    doc = doc_id or entry["doc_id"].strip()
    reply = _validate(reply, doc, entry)
    note = (note or "").strip()[:1000] or None
    req = _request(entry, reply, doc, reviewer)
    result = assess(gate, req)
    if result.reason_code not in SENDABLE:
        raise ReviewError(409, refusal(result), result)
    if needs_note(result, reply) and len(note or "") < MIN_NOTE_CHARS:
        raise ReviewError(422, note_reason(result, reply), result)
    redactions = result.redactions or {"question": {}, "draft": {}}
    verdicts = gate.verdicts(req, result, redactions.get("question", {}), redactions.get("draft", {}))
    verdicts["review"] = {"of_ledger_id": ledger_id, "reviewer": reviewer, "note": note,
                          "check_reason": result.reason_code, "on_judgment": needs_note(result, reply)}
    final = final_text(reply, result)
    params = (ledger_id, str(uuid.uuid4()), doc, redact(reply).text[:4000], redact(final).text[:4000],
              result.reason_code, note or "", reviewer or "", result.model_info[:200], gate.domain(doc).prompt_version,
              int(result.latency_ms), ledger.verdicts_json(verdicts), 0, " " * 64, " " * 40)
    conn = gate.connect()
    try:
        db.use_schema(conn, gate.schema)
        cur = conn.cursor()
        try:
            out = cur.callproc("RESOLVE_ESCALATION", params)
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            err = db.wrap_error(exc, "RESOLVE_ESCALATION refused the reply")
            status = REFUSALS.get(err.sqlstate or "")
            if status is None:
                raise err from None
            raise ReviewError(status, str(err).split(": ", 1)[-1], result) from None
        finally:
            cur.close()
    finally:
        conn.close()
    new_id, row_hash, outcome = int(out[12]), str(out[13]).strip(), str(out[14]).strip()
    gate.anchor(new_id, row_hash)
    log.info("held decision %s answered by %s as ledger row %s (%s)", ledger_id, reviewer or "a local user", new_id,
             outcome)
    return Resolved(new_id, row_hash, outcome, final, result)


def needs_note(result: GateResult, reply: str) -> bool:
    """A reply goes out on the specialist's judgment, with their note, when no clause covers part of it, or when it
    talks policy (fees, refunds, eligibility, amounts) and still no claim of it was judged (assess judges its policy
    sentences when extraction finds none, so this is the last resort: a person vouches for it)."""
    return result.reason_code == "NOT_COVERED" or (result.reason_code == "NO_POLICY_CLAIMS" and bool(policy_terms(reply)))


def note_reason(result: GateResult, reply: str) -> str:
    if result.reason_code == "NOT_COVERED":
        return ("No clause in force on the customer's date covers part of this reply. Add a note that explains your "
                "judgment; it goes on record with the reply.")
    terms = ", ".join(policy_terms(reply)[:5])
    return (f"The check found no policy claim in this reply, but it talks about {terms}. Add a note that explains "
            "your judgment; it goes on record with the reply.")


def refusal(result: GateResult) -> str:
    """Why a reply cannot be sent, in the specialist's terms."""
    reason = result.reason_code
    if reason == "CONTRADICTED":
        n = sum(c.verdict == "CONTRADICTED" for c in result.claims)
        return (f"{n} claim{'s' if n != 1 else ''} in the reply contradict{'s' if n == 1 else ''} the policy in force on "
                "the customer's date. Revise the reply; nothing was sent.")
    if reason == "UNCHECKED_DETAILS":
        return (f"The reply states {', '.join(result.unchecked) or 'details'} that the check could not tie to a claim. "
                "State each one as a sentence of its own, or remove it.")
    if reason == "TOO_MANY_CLAIMS":
        return "The reply makes more than 8 policy claims. Shorten it."
    if reason == "ERROR_FAIL_CLOSED" and "replay mode" in (result.error or ""):
        return ("Replay mode has recorded model outputs only for the built-in replies, so this reply cannot be checked "
                "and nothing was sent. Use a suggested reply, or configure a live model.")
    if reason == "ERROR_FAIL_CLOSED":
        return "The check could not complete (the language model or Db2 is unavailable), so nothing was sent. Try again."
    return f"The reply was not sent ({reason})."


def check_out(result: GateResult, as_of: date, reply: str = "") -> dict[str, Any]:
    """The reply's check for the API: claims with their verdicts and clause versions."""
    claims = []
    for c in result.claims:
        cl = c.clause
        claims.append({"claim_no": c.claim_no, "text": c.text, "area": c.area, "verdict": c.verdict,
                       "llm_verdict": c.llm_verdict, "rule_check": c.rule_check, "rule_details": c.rule_details,
                       "clause_id": cl.clause_id if cl else None, "clause_version": cl.version_label if cl else None,
                       "effective_from": cl.bus_start if cl else None, "effective_to": cl.bus_end if cl else None,
                       "clause_text": cl.clause_text if cl else None, "quoted_span": c.quoted_span, "reason": c.reason})
    sendable = result.reason_code in SENDABLE
    note = sendable and needs_note(result, reply)
    return {"as_of_date": as_of, "reason_code": result.reason_code, "sendable": sendable, "needs_note": note,
            "note_reason": note_reason(result, reply) if note else None,
            "message": None if sendable else refusal(result),
            "unchecked": result.unchecked, "claims": claims, "latency_ms": result.latency_ms, "model": result.model_info}
