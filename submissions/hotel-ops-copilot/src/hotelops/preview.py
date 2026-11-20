"""Dry-run an agent action inside a Db2 transaction, show its effect, then roll it back.

The manager can see *exactly* what an approval would change before approving it.
``SP_APPLY_ACTION`` runs for real (with every guardrail) on a dedicated connection
with autocommit off. We read the affected rows and the knock-on effects (such as
lost sellable inventory) inside the same unit of work, then ``ROLLBACK``. Nothing
is persisted, including the temporal history rows.
"""
from __future__ import annotations

import datetime as dt
import json

import ibm_db

from .config import SCHEMA, load_settings
from .db import OUT_TEXT, Db2

HORIZON_DAYS = 21

RATE_NIGHTS = """
SELECT V.STAY_DATE, RP.RATE, V.ROOMS_IN_SERVICE - V.ROOMS_SOLD AS UNSOLD_ROOMS
  FROM RATE_PLAN RP
  JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = RP.ROOM_TYPE_ID
  JOIN V_ROOM_TYPE_DAY V ON V.ROOM_TYPE_ID = RP.ROOM_TYPE_ID AND V.STAY_DATE = RP.STAY_DATE
 WHERE RT.CODE = ? AND RP.STAY_DATE BETWEEN ? AND ?
 ORDER BY V.STAY_DATE"""

RESERVATION = """
SELECT X.RESERVATION_ID, G.FULL_NAME, RT.CODE AS ROOM_TYPE, X.ROOM_NO, X.CHECK_IN, X.CHECK_OUT, X.SPECIAL_NOTE
  FROM RESERVATIONS X
  JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = X.ROOM_TYPE_ID
  JOIN GUESTS G ON G.GUEST_ID = X.GUEST_ID
 WHERE X.RESERVATION_ID = ?"""

ROOM_INVENTORY = f"""
SELECT V.STAY_DATE, V.ROOM_TYPE_CODE, V.ROOMS_IN_SERVICE, V.ROOMS_SOLD
  FROM V_ROOM_TYPE_DAY V
 WHERE V.ROOM_TYPE_ID = (SELECT ROOM_TYPE_ID FROM ROOMS WHERE ROOM_NO = ?)
   AND V.STAY_DATE BETWEEN CURRENT DATE AND CURRENT DATE + {HORIZON_DAYS - 1} DAYS
 ORDER BY V.STAY_DATE"""

ROOM_GUESTS = f"""
SELECT X.RESERVATION_ID, X.STATUS, X.CHECK_IN, X.CHECK_OUT
  FROM RESERVATIONS X
 WHERE X.ROOM_NO = ? AND X.STATUS IN ('CONFIRMED', 'CHECKED_IN')
   AND X.CHECK_OUT > CURRENT DATE AND X.CHECK_IN < CURRENT DATE + {HORIZON_DAYS} DAYS
 ORDER BY X.CHECK_IN"""


def _snapshot(db: Db2, action_type: str, p: dict) -> dict:
    if action_type == "RATE_CHANGE":
        return {"nights": db.query(RATE_NIGHTS, (p["room_type_code"], p["start_date"], p["end_date"]))}
    if action_type == "ROOM_UPGRADE":
        return {"reservation": db.query(RESERVATION, (int(p["reservation_id"]),))}
    room = p["room_no"]
    return {"room": db.query("SELECT ROOM_NO, STATUS FROM ROOMS WHERE ROOM_NO = ?", (room,)),
            "inventory": db.query(ROOM_INVENTORY, (room,)),
            "tickets": db.scalar("SELECT COUNT(*) FROM MAINTENANCE_TICKETS WHERE ROOM_NO = ?", (room,)),
            "guests": db.query(ROOM_GUESTS, (room,))}


def _impact(action_type: str, before: dict, after: dict) -> dict:
    """Summarise the difference between the two snapshots, with warnings for the manager."""
    warnings: list[str] = []
    if action_type == "RATE_CHANGE":
        rows = []
        for b, a in zip(before["nights"], after["nights"], strict=True):
            delta = float(a["RATE"]) - float(b["RATE"])
            rows.append({"STAY_DATE": b["STAY_DATE"], "RATE_BEFORE": b["RATE"], "RATE_AFTER": a["RATE"],
                         "CHANGE_PCT": round(100 * delta / float(b["RATE"]), 1), "UNSOLD_ROOMS": b["UNSOLD_ROOMS"],
                         "REVENUE_DELTA_IF_SOLD": round(delta * b["UNSOLD_ROOMS"])})
        total = sum(r["REVENUE_DELTA_IF_SOLD"] for r in rows)
        unsold = sum(r["UNSOLD_ROOMS"] for r in rows)
        summary = (f"{len(rows)} night(s) repriced; existing bookings keep their rate. If the {unsold} unsold "
                   f"rooms sell at the new rate: INR {total:+,.0f} vs the current rate.")
        old = sum(float(r["RATE_BEFORE"]) for r in rows) / max(len(rows), 1)
        new = sum(float(r["RATE_AFTER"]) for r in rows) / max(len(rows), 1)
        if new < old:
            summary += (f" A cut pays off only if it sells at least {100 * (old / new - 1):.0f}% more rooms "
                        "than the current rate would.")
        if any(r["UNSOLD_ROOMS"] == 0 for r in rows):
            warnings.append("Some nights are already sold out for this room type - the new rate has no effect there.")
        return {"summary": summary, "rows": rows, "warnings": warnings}

    if action_type == "ROOM_UPGRADE":
        b, a = before["reservation"][0], after["reservation"][0]
        rows = [{"FIELD": k, "BEFORE": b[k], "AFTER": a[k]} for k in ("ROOM_TYPE", "ROOM_NO", "SPECIAL_NOTE")
                if b[k] != a[k]]
        return {"summary": f"{b['FULL_NAME']} (#{b['RESERVATION_ID']}, {b['CHECK_IN']} to {b['CHECK_OUT']}) moves "
                           f"from {b['ROOM_TYPE']} room {b['ROOM_NO']} to {a['ROOM_TYPE']} room {a['ROOM_NO']}.",
                "rows": rows, "warnings": warnings}

    # MAINTENANCE
    status_b, status_a = before["room"][0]["STATUS"], after["room"][0]["STATUS"]
    rows = []
    for b, a in zip(before["inventory"], after["inventory"], strict=True):
        if a["ROOMS_IN_SERVICE"] != b["ROOMS_IN_SERVICE"] or a["ROOMS_SOLD"] > a["ROOMS_IN_SERVICE"]:
            rows.append({"STAY_DATE": a["STAY_DATE"], "ROOM_TYPE": a["ROOM_TYPE_CODE"],
                         "SELLABLE_BEFORE": b["ROOMS_IN_SERVICE"], "SELLABLE_AFTER": a["ROOMS_IN_SERVICE"],
                         "SOLD": a["ROOMS_SOLD"],
                         "OVERSOLD_BY": max(0, a["ROOMS_SOLD"] - a["ROOMS_IN_SERVICE"])})
    oversold = [r for r in rows if r["OVERSOLD_BY"] > 0]
    if oversold:  # show the nights that matter; the rest only lose one unsold room
        rows = oversold
    if oversold:
        nights = ", ".join(str(r["STAY_DATE"]) for r in oversold)
        warnings.append(f"Taking the room out of order leaves {oversold[0]['ROOM_TYPE']} OVERSOLD on {nights}. "
                        "Plan re-rooming or upgrades before approving, or raise the ticket without blocking the room.")
    if status_a == "OUT_OF_ORDER" and before["guests"]:
        warnings.append(f"{len(before['guests'])} active/upcoming reservation(s) are assigned to this room and "
                        "will need to be moved.")
    summary = (f"New ticket ({before['tickets']} -> {after['tickets']} for this room); room status "
               f"{status_b} -> {status_a}.")
    return {"summary": summary, "rows": rows, "guests": before["guests"], "warnings": warnings}


def preview_action(action_id: int) -> dict:
    """Run SP_APPLY_ACTION for real inside a transaction, diff the result, and roll back."""
    s = load_settings().db2
    db = Db2(s.conn_str(s.admin_user, s.admin_password), "preview")
    try:
        action = db.query("SELECT ACTION_TYPE, PAYLOAD, STATUS, PROPOSED_AT FROM AGENT_ACTIONS WHERE ACTION_ID = ?",
                          (int(action_id),))
        if not action:
            raise ValueError(f"action #{action_id} not found")
        action_type, payload = action[0]["ACTION_TYPE"], json.loads(action[0]["PAYLOAD"])
        if action[0]["STATUS"] != "PENDING":
            raise ValueError(f"action #{action_id} is {action[0]['STATUS']}, only PENDING actions can be previewed")
        from .provenance import stale_evidence

        freshness = stale_evidence(db, action_type, payload, action[0]["PROPOSED_AT"])
        ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        try:
            before = _snapshot(db, action_type, payload)
            out = db.call(f"{SCHEMA}.SP_APPLY_ACTION", int(action_id), "dry-run", " " * 12, OUT_TEXT)
            status, message = out[2], out[3]
            after = _snapshot(db, action_type, payload) if status == "APPLIED" else before
        finally:
            ibm_db.rollback(db.conn)  # nothing is persisted, including temporal history rows
        result = {"action_id": int(action_id), "action_type": action_type, "status": status, "message": message,
                  "rolled_back_at": dt.datetime.now().isoformat(timespec="seconds")}
        if status == "APPLIED":
            result.update(_impact(action_type, before, after))
        else:
            result.update({"summary": f"Db2 guardrails would refuse this action: {message}", "rows": [],
                           "warnings": []})
        result["warnings"] = freshness["warnings"] + result["warnings"]  # stale evidence first
        result["stale_changes"] = freshness["changes"]
        return result
    finally:
        db.close()
