"""Human-in-the-loop operations performed with the manager (admin) identity."""
from __future__ import annotations

from .config import SCHEMA
from .db import OUT_TEXT, get_db


def list_actions(status: str | None = None, property_id: int | None = None) -> list[dict]:
    sql = ("SELECT ACTION_ID, ACTION_TYPE, STATUS, PAYLOAD, RATIONALE, PROPOSED_BY, PROPOSED_AT, "
           "DECIDED_BY, DECIDED_AT, RESULT_MESSAGE, PROPERTY_ID FROM AGENT_ACTIONS "
           "WHERE STATUS = COALESCE(CAST(? AS VARCHAR(12)), STATUS) "
           "AND PROPERTY_ID = COALESCE(CAST(? AS SMALLINT), PROPERTY_ID)")
    return get_db("admin").query(sql + " ORDER BY ACTION_ID DESC", (status, property_id))


def properties() -> list[dict]:
    """The hotels of the group, as the manager sees them, with tonight's KPIs."""
    return get_db("admin").query(
        "SELECT P.PROPERTY_ID, P.CODE, P.NAME, P.CITY, "
        "(SELECT COUNT(*) FROM ROOMS R WHERE R.PROPERTY_ID = P.PROPERTY_ID) AS ROOMS, "
        "K.OCCUPANCY_PCT, K.ADR, K.REVPAR "
        "FROM PROPERTIES P LEFT JOIN V_DAILY_KPIS K ON K.PROPERTY_ID = P.PROPERTY_ID AND K.STAY_DATE = CURRENT DATE "
        "ORDER BY P.PROPERTY_ID")


def approve(action_id: int, manager: str) -> tuple[str, str]:
    out = get_db("admin").call(f"{SCHEMA}.SP_APPLY_ACTION", int(action_id), manager, " " * 12, OUT_TEXT)
    return out[2], out[3]


def reject(action_id: int, manager: str, reason: str = "Rejected by manager") -> None:
    get_db("admin").call(f"{SCHEMA}.SP_REJECT_ACTION", int(action_id), manager, reason)


def rollback(action_id: int, manager: str) -> tuple[str, str]:
    out = get_db("admin").call(f"{SCHEMA}.SP_ROLLBACK_ACTION", int(action_id), manager, " " * 12, OUT_TEXT)
    return out[2], out[3]


def rate_timeline(room_type_code: str, start_date: str, end_date: str) -> list[dict]:
    """All versions of rates in a date window (current + history) via FOR SYSTEM_TIME."""
    return get_db("admin").query(
        "SELECT RT.CODE, RP.STAY_DATE, RP.RATE, RP.UPDATED_BY, RP.CHANGE_REASON, RP.SOURCE_ACTION_ID, "
        "RP.SYS_START, CASE WHEN RP.SYS_END >= '9999-01-01' THEN NULL ELSE RP.SYS_END END AS SYS_END "
        "FROM RATE_PLAN FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' RP "
        "JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = RP.ROOM_TYPE_ID "
        "WHERE RT.CODE = ? AND RP.STAY_DATE BETWEEN ? AND ? ORDER BY RP.STAY_DATE, RP.SYS_START",
        (room_type_code, start_date, end_date),
    )


def rates_as_of(timestamp: str, start_date: str, end_date: str, property_id: int | None = None) -> list[dict]:
    return get_db("admin").query(
        "SELECT RT.CODE, RP.STAY_DATE, RP.RATE FROM RATE_PLAN FOR SYSTEM_TIME AS OF ? RP "
        "JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = RP.ROOM_TYPE_ID "
        "WHERE RP.STAY_DATE BETWEEN ? AND ? AND RP.PROPERTY_ID = COALESCE(CAST(? AS SMALLINT), RP.PROPERTY_ID) "
        "ORDER BY RT.TIER, RP.STAY_DATE",
        (timestamp, start_date, end_date, property_id),
    )


# --------------------------------------------------------------------------- earned autonomy
def autonomy_policies() -> list[dict]:
    """Current autonomy grants, plus how many actions the AI applied on its own today."""
    rows = get_db("admin").query(
        "SELECT ACTION_TYPE, ENABLED, MAX_CHANGE_PCT, MIN_LEAD_DAYS, MAX_PRIORITY, DAILY_LIMIT, GRANTED_BY, REASON, "
        "SYS_START AS SINCE FROM AUTONOMY_POLICY ORDER BY ACTION_TYPE")
    used = get_db("admin").scalar("SELECT COUNT(*) FROM AGENT_ACTIONS WHERE DECIDED_BY = 'autonomy' "
                                  "AND STATUS = 'APPLIED' AND DATE(DECIDED_AT) = CURRENT DATE")
    for r in rows:
        r["USED_TODAY"] = used
    return rows


def set_autonomy(action_type: str, enabled: bool, manager: str, reason: str, *, max_change_pct=None,
                 min_lead_days=None, max_priority=None, daily_limit=None) -> None:
    """Grant or revoke autonomy (manager identity only; the agent role can only read this table)."""
    get_db("admin").execute(
        "UPDATE AUTONOMY_POLICY SET ENABLED = ?, MAX_CHANGE_PCT = COALESCE(?, MAX_CHANGE_PCT), "
        "MIN_LEAD_DAYS = COALESCE(?, MIN_LEAD_DAYS), MAX_PRIORITY = COALESCE(?, MAX_PRIORITY), "
        "DAILY_LIMIT = COALESCE(?, DAILY_LIMIT), GRANTED_BY = ?, REASON = ? WHERE ACTION_TYPE = ?",
        ("Y" if enabled else "N", max_change_pct, min_lead_days, max_priority, daily_limit, manager[:40],
         reason[:400], action_type))


def autonomy_history() -> list[dict]:
    """Every grant and revocation of trust, reconstructed with Db2 time travel."""
    return get_db("admin").query(
        "SELECT ACTION_TYPE, ENABLED, MAX_CHANGE_PCT, MIN_LEAD_DAYS, MAX_PRIORITY, DAILY_LIMIT, GRANTED_BY, REASON, "
        "SYS_START AS VALID_FROM, CASE WHEN SYS_END >= '9999-01-01' THEN NULL ELSE SYS_END END AS VALID_TO "
        "FROM AUTONOMY_POLICY FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' "
        "ORDER BY SYS_START DESC FETCH FIRST 30 ROWS ONLY")
