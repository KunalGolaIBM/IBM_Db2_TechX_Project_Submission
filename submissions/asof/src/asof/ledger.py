"""The audit ledger: append through APPEND_LEDGER, verify with VERIFY_CHAIN, read and replay.

The runtime user can only CALL the procedures and SELECT; it holds no INSERT, UPDATE or
DELETE on any ledger table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import ibm_db_dbi

from . import db

MAX_VERDICTS_BYTES = 30000
DECISIONS = ("PASS", "CORRECTED", "ESCALATED")


@dataclass(frozen=True)
class LedgerEntry:
    request_id: str
    channel: str
    doc_id: str
    as_of: date
    question_redacted: str
    draft_redacted: str
    final_answer: str
    decision: str
    reason_code: str
    model_info: str
    prompt_version: str
    latency_ms: int
    verdicts: dict[str, Any]


@dataclass(frozen=True)
class Appended:
    ledger_id: int
    row_hash: str
    created_at: datetime


@dataclass(frozen=True)
class ChainStatus:
    status: str
    checked: int
    first_bad: int | None
    detail: str | None


def verdicts_json(verdicts: dict[str, Any]) -> str:
    text = json.dumps(verdicts, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text.encode("utf-8")) > MAX_VERDICTS_BYTES:
        raise ValueError(f"verdicts document exceeds {MAX_VERDICTS_BYTES} bytes")
    return text


def append(conn: ibm_db_dbi.Connection, entry: LedgerEntry, schema: str = db.SCHEMA) -> Appended:
    """Append one decision and commit. Raises DatabaseError if Db2 refuses it."""
    db.use_schema(conn, schema)
    if entry.decision not in DECISIONS:
        raise ValueError(f"unknown decision {entry.decision!r}")
    params = (
        entry.request_id, entry.channel, entry.doc_id, entry.as_of, entry.question_redacted,
        entry.draft_redacted, entry.final_answer, entry.decision, entry.reason_code, entry.model_info,
        entry.prompt_version, int(entry.latency_ms), verdicts_json(entry.verdicts),
        # OUT placeholders: ibm_db sizes output buffers from these, so strings get full width.
        0, " " * 64, datetime(1970, 1, 1),
    )
    cur = conn.cursor()
    try:
        out = cur.callproc("APPEND_LEDGER", params)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "APPEND_LEDGER failed") from None
    finally:
        cur.close()
    return Appended(ledger_id=int(out[13]), row_hash=str(out[14]).strip(), created_at=out[15])


def verify_chain(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> ChainStatus:
    db.use_schema(conn, schema)
    cur = conn.cursor()
    try:
        out = cur.callproc("VERIFY_CHAIN", (" " * 12, 0, 0, " " * 300))  # full-width OUT buffers
    except Exception as exc:  # noqa: BLE001
        raise db.wrap_error(exc, "VERIFY_CHAIN failed") from None
    finally:
        cur.close()
    status, checked, first_bad, detail = out
    return ChainStatus(str(status).strip(), int(checked or 0), int(first_bad) or None, str(detail).strip() or None)


# Every statement below is a literal. Names are unqualified: use_schema() binds the schema.
_ENTRY_KEYS = ("ledger_id", "request_id", "created_at", "channel", "doc_id", "as_of_date", "question_redacted",
               "draft_redacted", "final_answer", "decision", "reason_code", "model_info", "prompt_version",
               "latency_ms", "verdicts_json", "prev_hash", "row_hash")
_CITATION_KEYS = ("pass_no", "claim_no", "claim_text", "area", "verdict", "llm_verdict", "rule_check", "clause_id",
                  "clause_version", "clause_bus_start", "clause_sys_start", "distance", "quoted_span")
_CLAUSE_KEYS = ("clause_id", "version_label", "clause_text", "rule_json", "bus_start", "bus_end", "sys_start",
                "sys_end", "changed_by")

SQL_LIST = ("SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED, "
            "DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION, LATENCY_MS, "
            "VERDICTS_JSON, PREV_HASH, ROW_HASH FROM ANSWER_LEDGER "
            "WHERE (CAST(? AS VARCHAR(12)) IS NULL OR DECISION = CAST(? AS VARCHAR(12))) "
            "ORDER BY LEDGER_ID DESC OFFSET ? ROWS FETCH FIRST ? ROWS ONLY")
SQL_ENTRY = ("SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED, "
             "DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION, LATENCY_MS, "
             "VERDICTS_JSON, PREV_HASH, ROW_HASH FROM ANSWER_LEDGER WHERE LEDGER_ID = ?")
SQL_CITATIONS = ("SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, "
                 "CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN "
                 "FROM CLAIM_CITATION WHERE LEDGER_ID = ? ORDER BY PASS_NO, CLAIM_NO")
SQL_CLAUSE_USED = ("SELECT CLAUSE_ID, VERSION_LABEL, CLAUSE_TEXT, RULE_JSON, BUS_START, BUS_END, SYS_START, SYS_END, "
                   "CHANGED_BY FROM POLICY_CLAUSE FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' "
                   "WHERE CLAUSE_ID = ? AND BUS_START = ? AND SYS_START = ?")
SQL_CLAUSE_THEN = ("SELECT CLAUSE_ID, VERSION_LABEL, CLAUSE_TEXT, RULE_JSON, BUS_START, BUS_END, SYS_START, SYS_END, "
                   "CHANGED_BY FROM POLICY_CLAUSE FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ? "
                   "WHERE CLAUSE_ID = ?")
SQL_CLAUSE_NOW = ("SELECT CLAUSE_ID, VERSION_LABEL, CLAUSE_TEXT, RULE_JSON, BUS_START, BUS_END, SYS_START, SYS_END, "
                  "CHANGED_BY FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? WHERE CLAUSE_ID = ?")


def _entry(row: tuple) -> dict[str, Any]:
    out = dict(zip(_ENTRY_KEYS, row, strict=True))
    out["verdicts"] = json.loads(out.pop("verdicts_json"))
    for k in ("request_id", "prev_hash", "row_hash"):
        out[k] = out[k].strip()
    return out


def list_entries(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA, limit: int = 50, offset: int = 0,
                 decision: str | None = None) -> list[dict[str, Any]]:
    if decision is not None and decision not in DECISIONS:
        raise ValueError("unknown decision")
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_LIST, (decision, decision, offset, limit))
    return [_entry(r) for r in rows]


def get_entry(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_ENTRY, (ledger_id,))
    if not rows:
        return None
    entry = _entry(rows[0])
    entry["citations"] = [dict(zip(_CITATION_KEYS, r, strict=True)) for r in db.query(conn, SQL_CITATIONS, (ledger_id,))]
    return entry


def replay(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    """For each clause a decision cited: the exact row it used, what the database held for
    that customer date at decision time (FOR SYSTEM_TIME AS OF), and what applies today."""
    entry = get_entry(conn, ledger_id, schema)
    if entry is None:
        return None
    def one(rows: list[tuple]) -> dict[str, Any] | None:
        if not rows:
            return None
        row = dict(zip(_CLAUSE_KEYS, rows[0], strict=True))
        row["rule"] = json.loads(row.pop("rule_json"))
        row["changed_by"] = row["changed_by"].strip()
        return row

    seen: set[str] = set()
    clauses = []
    for c in entry["citations"]:
        cid = c["clause_id"]
        if cid is None or cid in seen:
            continue
        seen.add(cid)
        used = one(db.query(conn, SQL_CLAUSE_USED, (cid, c["clause_bus_start"], c["clause_sys_start"])))
        then = one(db.query(conn, SQL_CLAUSE_THEN, (entry["created_at"], entry["as_of_date"], cid)))
        now = one(db.query(conn, SQL_CLAUSE_NOW, (entry["as_of_date"], cid)))
        changed = now is None or used is None or (now["version_label"], now["clause_text"]) != (used["version_label"], used["clause_text"])
        clauses.append({"clause_id": cid, "used": used, "held_at_decision": then, "in_force_now": now,
                        "status": "CHANGED_SINCE_DECISION" if changed else "UNCHANGED"})
    return {"ledger_id": ledger_id, "created_at": entry["created_at"], "as_of_date": entry["as_of_date"],
            "decision": entry["decision"], "clauses": clauses}
