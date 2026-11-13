"""The audit ledger: append through APPEND_LEDGER, verify with VERIFY_CHAIN, read and replay.

The runtime user can only CALL the procedures and SELECT; it holds no INSERT, UPDATE or
DELETE on any ledger table.
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import ibm_db_dbi

from . import db

if TYPE_CHECKING:
    from .anchor import AnchorLog

MAX_VERDICTS_BYTES = 30000
DECISIONS = ("PASS", "CORRECTED", "ESCALATED", "REVIEWED")  # REVIEWED: only RESOLVE_ESCALATION writes it
# Db2's release rules (08_release_rules.sql): the ledger refuses a PASS or CORRECTED row whose released claims are not
# each SUPPORTED by a clause version in force on the customer's date and quoted from its text. 75003 (too many
# claims) is APPEND_LEDGER_ROW's own limit, which the trigger repeats for direct inserts.
RELEASE_REFUSALS = {
    "75080": "a released claim is not SUPPORTED by a cited clause",
    "75081": "a released claim cites a clause version not in force on the customer's date",
    "75082": "a released claim's quote is not in the cited clause version's text",
    "75083": "the claims do not match the decision (draft check for a PASS, re-check for a CORRECTED answer)",
}


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
    """Append one decision and commit. Raises DatabaseError if Db2 refuses it (a release Db2 will not back raises
    one whose sqlstate is in RELEASE_REFUSALS)."""
    db.use_schema(conn, schema)
    if entry.decision not in DECISIONS[:3]:  # a REVIEWED row goes through review.resolve, never through here
        raise ValueError(f"unknown decision {entry.decision!r}")
    params = (
        entry.request_id, entry.channel, entry.doc_id, entry.as_of, entry.question_redacted,
        entry.draft_redacted, entry.final_answer, entry.decision, entry.reason_code, entry.model_info,
        entry.prompt_version, int(entry.latency_ms), verdicts_json(entry.verdicts),
        # OUT placeholders at full width. ibm_db 3.3.0 returns the whole value even from a shorter placeholder.
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


@dataclass(frozen=True)
class CheckpointStatus:
    status: str
    checked: int               # rows recomputed: the checkpoint row and every row after it
    first_bad: int | None
    detail: str | None
    from_id: int               # the first row recomputed (the previous checkpoint's row, or 1)
    checkpoint_id: int | None  # the checkpoint this run wrote; None when the chain is broken or empty


def verify_from_checkpoint(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA, full: bool = False,
                           requested_by: str | None = None) -> CheckpointStatus:
    """VERIFY_CHAIN_FROM_CHECKPOINT: verify from the latest checkpoint (from the first row with full=True) and record
    the new one. Commits. Rows before the checkpoint are not recomputed: only VERIFY_CHAIN re-checks those."""
    db.use_schema(conn, schema)
    cur = conn.cursor()
    try:
        out = cur.callproc("VERIFY_CHAIN_FROM_CHECKPOINT",
                           (1 if full else 0, (requested_by or "")[:40], " " * 12, 0, 0, " " * 300, 0, 0))
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "VERIFY_CHAIN_FROM_CHECKPOINT failed") from None
    finally:
        cur.close()
    status, checked, first_bad, detail, from_id, checkpoint_id = out[2:]
    return CheckpointStatus(str(status).strip(), int(checked or 0), int(first_bad) or None, str(detail).strip() or None,
                            int(from_id or 0), int(checkpoint_id) or None)


SQL_CHECKPOINTS = ("SELECT CHECKPOINT_ID, LEDGER_ID, ROW_HASH, FROM_LEDGER_ID, ROWS_CHECKED, KIND, VERIFIED_AT, "
                   "VERIFIED_BY, REQUESTED_BY FROM CHAIN_CHECKPOINT ORDER BY CHECKPOINT_ID DESC FETCH FIRST ? ROWS ONLY")
_CHECKPOINT_KEYS = ("checkpoint_id", "ledger_id", "row_hash", "from_ledger_id", "rows_checked", "kind", "verified_at",
                    "verified_by", "requested_by")


def checkpoints(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA, limit: int = 20) -> list[dict[str, Any]]:
    """The latest verified positions, newest first."""
    db.use_schema(conn, schema)
    out = []
    for r in db.query(conn, SQL_CHECKPOINTS, (int(limit),)):
        d = dict(zip(_CHECKPOINT_KEYS, r, strict=True))
        d.update({k: d[k].strip() for k in ("row_hash", "kind", "verified_by") if isinstance(d[k], str)})
        out.append(d)
    return out


SQL_ROW_HASH = "SELECT ROW_HASH FROM ANSWER_LEDGER WHERE LEDGER_ID = ?"


@dataclass(frozen=True)
class ReceiptCheck:
    ledger_id: int
    found: bool
    matches: bool
    chain: ChainStatus

    @property
    def verdict(self) -> str:
        if not self.found:
            return "MISSING"
        if not self.matches:
            return "MISMATCH"  # rewritten, reset, or a receipt from another ledger: Db2 cannot tell which
        return "INTACT" if self.chain.status == "OK" else "CHAIN_BROKEN"


def check_receipt(conn: ibm_db_dbi.Connection, ledger_id: int, row_hash: str, schema: str = db.SCHEMA) -> ReceiptCheck:
    """Compare a receipt (the row hash a caller kept from the check's response) with the ledger now.

    VERIFY_CHAIN proves the rows agree with each other. It cannot tell that an owner who dropped the
    triggers rebuilt the whole chain consistently, because every hash would agree again. A hash kept
    outside Db2 can: the rebuilt row no longer matches it. A MISMATCH says only that this ledger's row
    with that ID is not the one the receipt was issued for: rewritten, lost to a demo ledger reset (IDs
    restart), or the receipt came from another ledger or was mistyped. MISSING: no row with that ID.
    """
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_ROW_HASH, (ledger_id,))
    stored = rows[0][0].strip() if rows else None
    matches = stored is not None and hmac.compare_digest(stored.encode(), row_hash.strip().lower().encode())
    return ReceiptCheck(ledger_id, stored is not None, matches, verify_chain(conn, schema))


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
            "ORDER BY LEDGER_ID DESC OFFSET ? ROWS FETCH FIRST ? ROWS ONLY")
# A separate statement for the filtered page (not "? IS NULL OR DECISION = ?"), so Db2 can plan it on
# IX_LEDGER_DECISION instead of one plan that has to serve both shapes.
SQL_LIST_BY_DECISION = ("SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED, "
                        "DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION, LATENCY_MS, "
                        "VERDICTS_JSON, PREV_HASH, ROW_HASH FROM ANSWER_LEDGER WHERE DECISION = ? "
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


def uncovered_claims(verdicts: dict[str, Any]) -> list[str]:
    """The claims no clause in force covered, in the last check that ran: what a NOT_COVERED hold is about.

    The reason code alone says only that some claim was uncovered; the ledger and the inbox name it."""
    claims = [c for c in verdicts.get("claims") or [] if isinstance(c, dict)]
    last = max((c.get("pass", 1) for c in claims), default=1)
    return [str(c.get("text", "")) for c in claims if c.get("pass", 1) == last and c.get("verdict") == "NOT_COVERED"]


def _entry(row: tuple[Any, ...]) -> dict[str, Any]:
    out = dict(zip(_ENTRY_KEYS, row, strict=True))
    out["verdicts"] = json.loads(out.pop("verdicts_json"))
    out["uncovered"] = uncovered_claims(out["verdicts"])
    for k in ("request_id", "prev_hash", "row_hash"):
        out[k] = out[k].strip()
    return out


def list_entries(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA, limit: int = 50, offset: int = 0,
                 decision: str | None = None) -> list[dict[str, Any]]:
    if decision is not None and decision not in DECISIONS:
        raise ValueError("unknown decision")
    db.use_schema(conn, schema)
    rows = (db.query(conn, SQL_LIST_BY_DECISION, (decision, offset, limit)) if decision
            else db.query(conn, SQL_LIST, (offset, limit)))
    return [_entry(r) for r in rows]


def get_entry(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_ENTRY, (ledger_id,))
    if not rows:
        return None
    entry = _entry(rows[0])
    entry["citations"] = [dict(zip(_CITATION_KEYS, r, strict=True)) for r in db.query(conn, SQL_CITATIONS, (ledger_id,))]
    entry["stored_by"] = stored_by(conn, ledger_id, schema)
    return entry


# Set by Db2 on insert (trigger ANSWER_LEDGER_SESSION_AUDIT, 13_trusted_context.sql), outside ROW_HASH.
SQL_STORED_BY = "SELECT STORED_BY, STORED_ROLES, STORED_CONTEXT FROM ANSWER_LEDGER WHERE LEDGER_ID = ?"


def stored_by(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    """Who Db2 says stored a ledger row: the session user, the roles it acted under, the trusted context it came
    through. None for a row stored before Db2 recorded this. Not covered by the row hash or VERIFY_CHAIN."""
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_STORED_BY, (ledger_id,))
    if not rows or rows[0][0] is None:
        return None
    user, roles, context = rows[0]
    return {"user": user.strip(), "roles": [r for r in (roles or "").split(",") if r],
            "trusted_context": context.strip() if context else None, "in_row_hash": False}


def replay(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    """For each clause a decision cited: the exact row it used, what the database held for
    that customer date at decision time (FOR SYSTEM_TIME AS OF), and what applies today."""
    entry = get_entry(conn, ledger_id, schema)
    if entry is None:
        return None
    def one(rows: list[tuple[Any, ...]]) -> dict[str, Any] | None:
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
        changed = (now is None or used is None
                   or (now["version_label"], now["clause_text"]) != (used["version_label"], used["clause_text"]))
        clauses.append({"clause_id": cid, "used": used, "held_at_decision": then, "in_force_now": now,
                        "status": "CHANGED_SINCE_DECISION" if changed else "UNCHANGED"})
    return {"ledger_id": ledger_id, "created_at": entry["created_at"], "as_of_date": entry["as_of_date"],
            "decision": entry["decision"], "clauses": clauses}


EVIDENCE_FORMAT = 1


def evidence(conn: ibm_db_dbi.Connection, ledger_id: int, schema: str = db.SCHEMA,
             anchors: AnchorLog | None = None) -> dict[str, Any] | None:
    """Everything needed to account for one answer in a dispute, in one document.

    The decision as recorded (question and draft redacted, the answer released, every claim with its
    verdict and the clause version it was checked against), the replay of each cited clause (the row
    used, what Db2 held at that moment, what applies today), the whole chain's verification, and the
    row hash to match against the receipt the caller kept. Read as the runtime user, which sees the
    ledger text unmasked.
    """
    entry = get_entry(conn, ledger_id, schema)
    if entry is None:
        return None
    chain = verify_chain(conn, schema)
    anchor = None
    if anchors is not None:
        from .anchor import verify as verify_anchors

        a = verify_anchors(anchors, conn, schema)
        anchor = {**a.as_dict(), "covers_this_row": a.status == "OK" and (a.covered_through or 0) >= ledger_id}
    return {
        "asof_evidence": EVIDENCE_FORMAT,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ledger_entry": entry,
        "replay": replay(conn, ledger_id, schema),
        "chain": {"status": chain.status, "rows_checked": chain.checked, "first_bad_ledger_id": chain.first_bad,
                  "detail": chain.detail},
        "receipt": {"ledger_id": ledger_id, "row_hash": entry["row_hash"], "prev_hash": entry["prev_hash"],
                    "check_with": "POST /api/ledger/receipt with the row hash the caller kept"},
        "anchor": anchor or {"status": "OFF", "detail": "no ASOF_ANCHOR_KEY: chain-head anchoring is off"},
        "notes": ["Questions and drafts were redacted (emails, phone numbers, card and booking numbers, person names) "
                  "before storage.",
                  "Clause versions are Db2 business-time periods; replay uses FOR SYSTEM_TIME AS OF the decision time.",
                  "Chain status covers the whole ledger at generation time. A matching receipt, or an anchor at or "
                  "after this row, also rules out a ledger rebuilt consistently after the decision.",
                  "ledger_entry.stored_by is the Db2 session that stored the row (session user, roles, trusted "
                  "context), set by a trigger on insert; it is not part of the row hash, so the chain check does "
                  "not cover it."],
    }
