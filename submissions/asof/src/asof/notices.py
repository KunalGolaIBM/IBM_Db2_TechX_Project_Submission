"""Correction notices: telling a customer that an answer they were given no longer holds for their date.

After a policy change, CHANGE_IMPACT marks an answer STALE when the version now in force for the customer's date
is not the one the answer cited. The change-impact agent (impactagent.draft_notices) drafts a correction from the
clause text now in force and runs the full check on it, on the customer's date; ADD_NOTICE stores the notice after
Db2 has checked every claim the caller makes about it (the answer cited the old version, the new version is in
force for that date, the check is a real ledger row for that date that released a claim supported by the new
version). A specialist then approves it (STATUS SENT) or rejects it through DECIDE_NOTICE. AsOf sends nothing
itself: SENT records that a person approved the notice for the customer's channel.

The notice wraps the checked correction in fixed wording that states no policy: what was answered when, for which
date, which clause version applied then and which applies now. Only the correction states policy, and it is the
text the check released.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import ibm_db_dbi

from . import db

MAX_NOTICE_CHARS = 6000
REFERENCES = "\n\nPolicy references:"

# Db2's refusals in ADD_NOTICE and DECIDE_NOTICE, as HTTP statuses.
REFUSALS = {"75060": 409, "75061": 409, "75062": 422, "75063": 409, "75064": 409, "75065": 409, "75066": 404,
            "23505": 409}

SQL_LIST = ("SELECT NOTICE_ID, LEDGER_ID, CLAUSE_ID, CITED_VERSION, CURRENT_VERSION, AS_OF_DATE, CORRECTION_TEXT, "
            "NOTICE_TEXT, CHECK_DECISION, CHECK_LEDGER_ID, AGENT_TRACE, STATUS, REQUESTED_BY, CREATED_AT, DECIDED_AT, "
            "DECIDED_BY, DECIDED_BY_USER FROM CORRECTION_NOTICE "
            "WHERE (CAST(? AS VARCHAR(32)) IS NULL OR CLAUSE_ID = CAST(? AS VARCHAR(32))) "
            "AND (CAST(? AS VARCHAR(12)) IS NULL OR STATUS = CAST(? AS VARCHAR(12))) "
            "ORDER BY NOTICE_ID DESC FETCH FIRST 100 ROWS ONLY")
SQL_OPEN = "SELECT LEDGER_ID, CURRENT_VERSION FROM CORRECTION_NOTICE WHERE CLAUSE_ID = ? AND STATUS IN ('PENDING', 'SENT')"
_KEYS = ("notice_id", "ledger_id", "clause_id", "cited_version", "current_version", "as_of_date", "correction",
         "notice", "check_decision", "check_ledger_id", "agent_trace", "status", "requested_by", "created_at",
         "decided_at", "decided_by", "decided_by_user")


def _day(value: date | datetime) -> str:
    d = value.date() if isinstance(value, datetime) else value
    return f"{d.day} {d.strftime('%B')} {d.year}"


def without_references(answer: str) -> str:
    """The answer as the customer read it, without the "Policy references" line AsOf appends."""
    return answer.split(REFERENCES, 1)[0].strip()


def compose(*, answered_at: datetime, as_of: date, question: str, clause_id: str, clause_title: str, cited: str,
            current: str, current_from: date, correction: str) -> str:
    """The notice: fixed wording around the checked correction. The fixed part states no policy."""
    text = (f"A correction to our reply of {_day(answered_at)}\n\n"
            f"On {_day(answered_at)} we answered your question: \"{question.strip()}\"\n\n"
            f"Our policy for your date, {_day(as_of)}, has changed since then. Our answer relied on {clause_id} "
            f"({clause_title}) version {cited}; version {current} applies to your date now (in effect from "
            f"{_day(current_from)}), so part of that answer no longer holds.\n\n"
            f"What applies to your date now:\n\n{correction.strip()}\n\n"
            f"If you already acted on our earlier reply, reply to this message and a specialist will help.")
    return text[:MAX_NOTICE_CHARS]


def add(conn: ibm_db_dbi.Connection, *, ledger_id: int, clause_id: str, cited: str, current: str, correction: str,
        notice: str, check_decision: str, check_ledger_id: int | None, trace: list[dict[str, Any]],
        requested_by: str | None, schema: str = db.SCHEMA) -> int:
    """Store a drafted notice through ADD_NOTICE (the runtime user holds EXECUTE only). Commits."""
    db.use_schema(conn, schema)
    trace_json = json.dumps(trace[:12], default=str)
    while len(trace_json.encode("utf-8")) > 8000:
        trace = trace[:-1]
        trace_json = json.dumps(trace, default=str)
    cur = conn.cursor()
    try:
        out = cur.callproc("ADD_NOTICE", (int(ledger_id), clause_id, cited, current, correction[:4000],
                                          notice[:MAX_NOTICE_CHARS], check_decision, int(check_ledger_id or 0), trace_json,
                                          requested_by or "", 0))
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "ADD_NOTICE refused the notice") from None
    finally:
        cur.close()
    return int(out[10])


def decide(conn: ibm_db_dbi.Connection, notice_id: int, approve: bool, user: str | None,
           schema: str = db.SCHEMA) -> None:
    """Approve for sending, or reject, through DECIDE_NOTICE. Commits."""
    db.use_schema(conn, schema)
    cur = conn.cursor()
    try:
        cur.callproc("DECIDE_NOTICE", (int(notice_id), 1 if approve else 0, user or ""))
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "DECIDE_NOTICE refused") from None
    finally:
        cur.close()


def list_notices(conn: ibm_db_dbi.Connection, clause_id: str | None = None, status: str | None = None,
                 schema: str = db.SCHEMA) -> list[dict[str, Any]]:
    db.use_schema(conn, schema)
    out = []
    for r in db.query(conn, SQL_LIST, (clause_id, clause_id, status, status)):
        d = dict(zip(_KEYS, r, strict=True))
        d["agent_trace"] = json.loads(d["agent_trace"])
        for k in ("status", "check_decision", "decided_by", "decided_by_user", "requested_by", "clause_id"):
            d[k] = d[k].strip() if isinstance(d[k], str) else d[k]
        out.append(d)
    return out


def open_notices(conn: ibm_db_dbi.Connection, clause_id: str, schema: str = db.SCHEMA) -> set[tuple[int, str]]:
    """(answer, version) pairs that already have a pending or sent notice for this clause."""
    db.use_schema(conn, schema)
    return {(int(r[0]), r[1].strip()) for r in db.query(conn, SQL_OPEN, (clause_id,))}
