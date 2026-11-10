"""Decision provenance: why did the AI propose this, and is its evidence still true?

Approvals can wait for hours, and the hotel keeps changing: someone reprices, a guest books,
a room goes out of order. Using Db2 system-period temporal tables, this module compares the
data **as of the moment the AI proposed** an action (``FOR SYSTEM_TIME AS OF PROPOSED_AT``)
with the data now, and lists the evidence the agent gathered for it (from AGENT_STEPS).
Read-only: nothing here changes data.
"""
from __future__ import annotations

import json

from .db import Db2, get_db

RATE_THEN_NOW = """
SELECT N.STAY_DATE, T.RATE AS RATE_WHEN_PROPOSED, N.RATE AS RATE_NOW, N.UPDATED_BY AS CHANGED_BY,
       N.CHANGE_REASON, N.SYS_START AS CHANGED_AT
  FROM RATE_PLAN FOR SYSTEM_TIME AS OF CAST(? AS TIMESTAMP(12)) T
  JOIN RATE_PLAN N ON N.ROOM_TYPE_ID = T.ROOM_TYPE_ID AND N.STAY_DATE = T.STAY_DATE
  JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = N.ROOM_TYPE_ID
 WHERE RT.CODE = ? AND N.STAY_DATE BETWEEN ? AND ? AND T.RATE <> N.RATE
 ORDER BY N.STAY_DATE"""

NEW_BOOKINGS = """
SELECT COUNT(*) FROM RESERVATIONS X JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = X.ROOM_TYPE_ID
 WHERE RT.CODE = ? AND X.BOOKED_AT > CAST(? AS TIMESTAMP) AND X.BOOKED_AT <= CURRENT TIMESTAMP
   AND X.STATUS NOT IN ('CANCELLED', 'NO_SHOW')
   AND X.CHECK_IN <= ? AND X.CHECK_OUT > ?"""

RES_THEN_NOW = """
SELECT T.ROOM_TYPE_ID AS TYPE_THEN, N.ROOM_TYPE_ID AS TYPE_NOW, T.ROOM_NO AS ROOM_THEN, N.ROOM_NO AS ROOM_NOW,
       T.STATUS AS STATUS_THEN, N.STATUS AS STATUS_NOW, N.SYS_START AS CHANGED_AT
  FROM RESERVATIONS FOR SYSTEM_TIME AS OF CAST(? AS TIMESTAMP(12)) T
  JOIN RESERVATIONS N ON N.RESERVATION_ID = T.RESERVATION_ID
 WHERE N.RESERVATION_ID = ?"""

ROOM_THEN_NOW = """
SELECT T.STATUS AS STATUS_THEN, N.STATUS AS STATUS_NOW, N.SYS_START AS CHANGED_AT
  FROM ROOMS FOR SYSTEM_TIME AS OF CAST(? AS TIMESTAMP(12)) T JOIN ROOMS N ON N.ROOM_NO = T.ROOM_NO
 WHERE N.ROOM_NO = ?"""


def stale_evidence(db: Db2, action_type: str, payload: dict, proposed_at) -> dict:
    """What changed in Db2 between the proposal and now, for the data this action depends on."""
    at = str(proposed_at)
    changes: list[dict] = []
    warnings: list[str] = []
    if action_type == "RATE_CHANGE":
        code, start, end = payload["room_type_code"], payload["start_date"], payload["end_date"]
        changes = db.query(RATE_THEN_NOW, (at, code, start, end))
        if changes:
            who = ", ".join(sorted({str(c["CHANGED_BY"]) for c in changes}))
            warnings.append(f"Stale evidence: {len(changes)} night(s) of {code} were repriced after the AI proposed "
                            f"this (by {who}). It reasoned from rates that no longer apply.")
        booked = db.scalar(NEW_BOOKINGS, (code, at, end, start)) or 0
        if booked:
            warnings.append(f"Demand changed: {booked} new {code} booking(s) for these nights since the proposal.")
    elif action_type == "ROOM_UPGRADE":
        rows = db.query(RES_THEN_NOW, (at, int(payload["reservation_id"])))
        changes = [r for r in rows if (r["TYPE_THEN"], r["ROOM_THEN"], r["STATUS_THEN"])
                   != (r["TYPE_NOW"], r["ROOM_NOW"], r["STATUS_NOW"])]
        if changes:
            warnings.append("Stale evidence: the reservation changed after the AI proposed this upgrade "
                            f"(status {changes[0]['STATUS_THEN']} -> {changes[0]['STATUS_NOW']}, "
                            f"room {changes[0]['ROOM_THEN']} -> {changes[0]['ROOM_NOW']}).")
    elif action_type == "MAINTENANCE":
        room = str(payload["room_no"])
        rows = db.query(ROOM_THEN_NOW, (at, room))
        changes = [r for r in rows if r["STATUS_THEN"] != r["STATUS_NOW"]]
        if changes:
            warnings.append(f"Stale evidence: room {room} went from {changes[0]['STATUS_THEN']} to "
                            f"{changes[0]['STATUS_NOW']} after the proposal.")
        tickets = db.scalar("SELECT COUNT(*) FROM MAINTENANCE_TICKETS WHERE ROOM_NO = ? AND CREATED_AT > "
                            "CAST(? AS TIMESTAMP) AND STATUS IN ('OPEN', 'IN_PROGRESS')", (room, at)) or 0
        if tickets:
            warnings.append(f"Possible duplicate: {tickets} open ticket(s) were raised for room {room} since.")
    return {"proposed_at": at, "changes": changes, "warnings": warnings, "fresh": not warnings}


def provenance(action_id: int, db: Db2 | None = None) -> dict:
    """Question, rationale, evidence (the agent's tool calls) and evidence freshness for one action."""
    db = db or get_db("admin")
    rows = db.query("SELECT A.ACTION_ID, A.ACTION_TYPE, A.PAYLOAD, A.RATIONALE, A.PROPOSED_AT, A.RUN_ID, "
                    "R.USER_QUESTION, R.MODEL FROM AGENT_ACTIONS A LEFT JOIN AGENT_RUNS R ON R.RUN_ID = A.RUN_ID "
                    "WHERE A.ACTION_ID = ?", (int(action_id),))
    if not rows:
        raise ValueError(f"action #{action_id} not found")
    a = rows[0]
    steps = db.query("SELECT AGENT, TOOL_NAME, OK, LATENCY_MS, SUBSTR(TOOL_INPUT, 1, 400) AS INPUT, "
                     "SUBSTR(TOOL_OUTPUT, 1, 300) AS OUTPUT FROM AGENT_STEPS WHERE RUN_ID = ? "
                     "AND TOOL_NAME NOT LIKE 'propose%' ORDER BY STEP_ID", (a["RUN_ID"],)) if a["RUN_ID"] else []
    return {"action_id": a["ACTION_ID"], "question": a["USER_QUESTION"], "model": a["MODEL"],
            "rationale": a["RATIONALE"], "evidence": steps,
            "freshness": stale_evidence(db, a["ACTION_TYPE"], json.loads(a["PAYLOAD"]), a["PROPOSED_AT"])}
