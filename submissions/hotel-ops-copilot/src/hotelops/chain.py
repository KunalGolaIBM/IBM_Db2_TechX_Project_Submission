"""Hotel chain: prove that Db2 keeps each AI agent inside its own hotel.

The demo database holds one hotel (Saltwater Bay, Goa). ``isolation_check`` briefly adds a second hotel of
the group, with a room type that reuses the code ``STD``, a room, a rate, a booking and a review, then looks
at it through the agent's own Db2 login:

* the agent does not see the other hotel's rows anywhere: tables, history tables, the KPI view;
* SP_PROPOSE_ACTION, called as the agent, rejects actions on the other hotel's room and booking, and the
  agent's ``STD`` means its own hotel's Standard room;
* adding the hotel to the agent's row in AGENT_SCOPE (a manager-only table) makes it visible, so the scope
  table, not the application, decides.

Everything it created is deleted again, including the row versions Db2 wrote to the history tables. Used by
``verify.py`` and ``tests/test_db2_integration.py``. No LLM is needed.
"""
from __future__ import annotations

import datetime as dt
import json

import ibm_db

from hotelops.config import SCHEMA, load_settings
from hotelops.db import OUT_TEXT, Db2, Db2Error

PROPERTY = 2
ROOM_TYPE = 90
ROOM = "K101"
RESERVATION = 990001
REVIEW = 990001


def _own(role: str) -> Db2:
    s = load_settings().db2
    user, pw = (s.admin_user, s.admin_password) if role == "admin" else (s.agent_user, s.agent_password)
    return Db2(s.conn_str(user, pw), f"chain-{role}")


def _add_second_hotel(admin: Db2, today: dt.date) -> None:
    admin.execute("INSERT INTO PROPERTIES (PROPERTY_ID, CODE, NAME, CITY) VALUES (?, 'KOCHI', 'Backwater House', "
                  "'Kochi')", (PROPERTY,))
    admin.execute("INSERT INTO ROOM_TYPES (ROOM_TYPE_ID, CODE, NAME, TIER, BASE_RATE, FLOOR_RATE, CEILING_RATE, "
                  "MAX_OCCUPANCY, PROPERTY_ID) VALUES (?, 'STD', 'Lagoon Standard', 1, 4000, 3000, 6000, 2, ?)",
                  (ROOM_TYPE, PROPERTY))
    admin.execute("INSERT INTO ROOMS (ROOM_NO, ROOM_TYPE_ID, FLOOR_NO, PROPERTY_ID) VALUES (?, ?, 1, ?)",
                  (ROOM, ROOM_TYPE, PROPERTY))
    admin.execute("INSERT INTO RATE_PLAN (ROOM_TYPE_ID, STAY_DATE, RATE, PROPERTY_ID) VALUES (?, ?, 4000, ?)",
                  (ROOM_TYPE, (today + dt.timedelta(days=10)).isoformat(), PROPERTY))
    admin.execute("INSERT INTO RESERVATIONS (RESERVATION_ID, GUEST_ID, ROOM_TYPE_ID, ROOM_NO, CHECK_IN, CHECK_OUT, "
                  "CHANNEL, STATUS, NIGHTLY_RATE, TOTAL_AMOUNT, BOOKED_AT, PROPERTY_ID) "
                  "VALUES (?, 1, ?, ?, ?, ?, 'DIRECT', 'CONFIRMED', 4000, 8000, CURRENT TIMESTAMP, ?)",
                  (RESERVATION, ROOM_TYPE, ROOM, today.isoformat(), (today + dt.timedelta(days=2)).isoformat(),
                   PROPERTY))
    admin.execute("INSERT INTO GUEST_REVIEWS (REVIEW_ID, RESERVATION_ID, ROOM_NO, SOURCE, RATING, REVIEW_TEXT, "
                  "CREATED_AT, PROPERTY_ID) VALUES (?, ?, ?, 'DIRECT', 2, 'Kochi: the boat transfer was late.', "
                  "?, ?)", (REVIEW, RESERVATION, ROOM, today.isoformat(), PROPERTY))


def _remove_second_hotel(admin: Db2) -> None:
    for sql in (
        "DELETE FROM GUEST_REVIEWS WHERE PROPERTY_ID = ?",
        "DELETE FROM AGENT_ACTIONS WHERE PROPERTY_ID = ?",
        "DELETE FROM RESERVATIONS WHERE PROPERTY_ID = ?",
        "DELETE FROM RATE_PLAN WHERE PROPERTY_ID = ?",
        "DELETE FROM ROOMS WHERE PROPERTY_ID = ?",
        "DELETE FROM ROOM_TYPES WHERE PROPERTY_ID = ?",
        "DELETE FROM AGENT_SCOPE WHERE PROPERTY_ID = ?",
        "DELETE FROM PROPERTIES WHERE PROPERTY_ID = ?",
        # deleting from a system-period temporal table writes the old rows to its history table
        "DELETE FROM RESERVATIONS_HISTORY WHERE PROPERTY_ID = ?",
        "DELETE FROM RATE_PLAN_HISTORY WHERE PROPERTY_ID = ?",
        "DELETE FROM ROOMS_HISTORY WHERE PROPERTY_ID = ?",
    ):
        try:
            admin.execute(sql, (PROPERTY,))
        except Db2Error:
            pass


def _propose_rolled_back(agent: Db2, action_type: str, payload: dict) -> tuple[int, str, int | None]:
    """Call SP_PROPOSE_ACTION as the agent inside a transaction that is rolled back."""
    ibm_db.autocommit(agent.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        out = agent.call(f"{SCHEMA}.SP_PROPOSE_ACTION", "chain-check", action_type, json.dumps(payload),
                         "property isolation check", 0, OUT_TEXT)
        action_id, msg = int(out[4] or 0), str(out[5])
        prop = agent.scalar("SELECT PROPERTY_ID FROM AGENT_ACTIONS WHERE ACTION_ID = ?", (action_id,)) \
            if action_id else None
    finally:
        ibm_db.rollback(agent.conn)
        ibm_db.autocommit(agent.conn, ibm_db.SQL_AUTOCOMMIT_ON)
    return action_id, msg, prop


def isolation_check() -> dict:
    """Run the check on dedicated connections and return what each identity saw. Leaves no trace."""
    from hotelops.nights import pick_nights

    admin, agent = _own("admin"), _own("agent")
    agent_user = load_settings().db2.agent_user.upper()
    today = dt.date.fromisoformat(str(admin.scalar("VALUES CURRENT DATE")))
    seen: dict = {}
    _remove_second_hotel(admin)  # in case an earlier run was interrupted
    try:
        own = pick_nights(agent, "STD", 10)  # the agent's own Standard room: a night priced inside its band
        _add_second_hotel(admin, today)
        seen |= {
            "admin_properties": admin.scalar("SELECT COUNT(*) FROM PROPERTIES"),
            "agent_properties": agent.scalar("SELECT COUNT(*) FROM PROPERTIES"),
            "agent_other_rows": sum(agent.scalar(sql, (PROPERTY,)) for sql in (
                "SELECT COUNT(*) FROM ROOM_TYPES WHERE PROPERTY_ID = ?",
                "SELECT COUNT(*) FROM ROOMS WHERE PROPERTY_ID = ?",
                "SELECT COUNT(*) FROM RATE_PLAN WHERE PROPERTY_ID = ?",
                "SELECT COUNT(*) FROM RESERVATIONS WHERE PROPERTY_ID = ?",
                "SELECT COUNT(*) FROM GUEST_REVIEWS WHERE PROPERTY_ID = ?",
                "SELECT COUNT(*) FROM RATE_PLAN FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' "
                "WHERE PROPERTY_ID = ?",
            )),
            "admin_other_rows": admin.scalar("SELECT COUNT(*) FROM ROOMS WHERE PROPERTY_ID = ?", (PROPERTY,)),
            "agent_std_types": agent.scalar("SELECT COUNT(*) FROM ROOM_TYPES WHERE CODE = 'STD'"),
            "admin_std_types": admin.scalar("SELECT COUNT(*) FROM ROOM_TYPES WHERE CODE = 'STD'"),
            "agent_kpi_rows_today": agent.scalar("SELECT COUNT(*) FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE"),
            "admin_kpi_rows_today": admin.scalar("SELECT COUNT(*) FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE"),
        }
        _, seen["ticket_other_room"], _ = _propose_rolled_back(
            agent, "MAINTENANCE", {"room_no": ROOM, "category": "GENERAL", "priority": "LOW",
                                   "description": "chain check", "take_out_of_order": False})
        _, seen["upgrade_other_booking"], _ = _propose_rolled_back(
            agent, "ROOM_UPGRADE", {"reservation_id": RESERVATION, "to_room_type_code": "STE"})
        aid, msg, prop = _propose_rolled_back(
            agent, "RATE_CHANGE", {"room_type_code": "STD", "start_date": own.night, "end_date": own.night,
                                   "new_rate": round(own.rate, 2)})
        seen["std_proposal"], seen["std_proposal_property"] = (msg if not aid else "PENDING"), prop

        admin.execute("INSERT INTO AGENT_SCOPE (AUTH_ID, PROPERTY_ID, GRANTED_BY) VALUES (?, ?, 'chain-check')",
                      (agent_user, PROPERTY))
        seen["agent_properties_after_grant"] = agent.scalar("SELECT COUNT(*) FROM PROPERTIES")
        seen["agent_sees_other_room_after_grant"] = agent.scalar(
            "SELECT COUNT(*) FROM ROOMS WHERE ROOM_NO = ?", (ROOM,))
        admin.execute("DELETE FROM AGENT_SCOPE WHERE AUTH_ID = ? AND PROPERTY_ID = ?", (agent_user, PROPERTY))
        seen["agent_sees_other_room_after_revoke"] = agent.scalar(
            "SELECT COUNT(*) FROM ROOMS WHERE ROOM_NO = ?", (ROOM,))
        try:
            agent.execute("INSERT INTO AGENT_SCOPE (AUTH_ID, PROPERTY_ID) VALUES (?, ?)", (agent_user, PROPERTY))
            seen["agent_can_widen_scope"] = True
        except Db2Error:
            seen["agent_can_widen_scope"] = False
    finally:
        _remove_second_hotel(admin)
        seen_after = admin.scalar("SELECT COUNT(*) FROM PROPERTIES WHERE PROPERTY_ID = ?", (PROPERTY,)) + \
            admin.scalar("SELECT COUNT(*) FROM RATE_PLAN_HISTORY WHERE PROPERTY_ID = ?", (PROPERTY,))
        admin.close()
        agent.close()
    seen["left_behind"] = seen_after
    return seen
