"""LangChain tools that give the agents controlled access to IBM Db2.

Every tool:
  * runs its SQL on the least-privileged ``agent`` connection (role HOTELOPS_AGENT),
  * is timed and written to AGENT_STEPS through RunContext,
  * returns compact JSON text, or an "ERROR: ..." string the LLM can react to.
"""
from __future__ import annotations

import functools
import json
import time
from collections.abc import Callable

from langchain_core.tools import BaseTool, tool

from .audit import RunContext
from .config import SCHEMA, load_settings
from .costguard import check_cost
from .db import OUT_TEXT, Db2, Db2Error, get_db, vector_literal
from .sqlguard import UnsafeSqlError, validate_select

MAX_TOOL_CHARS = 9000


def _shrink(obj):
    """Halve the longest list inside ``obj`` (in place); return False when nothing is left to shrink."""
    lists = []

    def walk(x):
        if isinstance(x, list):
            lists.append(x)
            for v in x:
                walk(v)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)

    walk(obj)
    longest = max(lists, key=len, default=None)
    if not longest or len(longest) <= 1:
        return False
    del longest[max(1, len(longest) // 2):]
    return True


def _dump(obj) -> str:
    """Serialise a tool result; oversized results stay *valid JSON* by trimming rows, never mid-string."""
    text = json.dumps(obj, default=str, ensure_ascii=False)
    if len(text) <= MAX_TOOL_CHARS:
        return text
    obj = json.loads(text)  # deep copy with plain types
    while len(text) > MAX_TOOL_CHARS and _shrink(obj):
        wrapped = {"_truncated": "result trimmed to fit; refine the query or aggregate", "result": obj}
        text = json.dumps(wrapped, ensure_ascii=False)
    if len(text) > MAX_TOOL_CHARS:  # a single huge value: fall back to a plain cut
        text = text[:MAX_TOOL_CHARS] + " ... [truncated - refine the query or aggregate]"
    return text


def _audited(ctx: RunContext, fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        ok = True
        try:
            result = fn(*args, **kwargs)
        except (Db2Error, UnsafeSqlError, ValueError) as exc:
            ok = False
            result = f"ERROR: {exc}"
        latency = int((time.perf_counter() - t0) * 1000)
        ctx.step(fn.__name__, kwargs or list(args), result, ok, latency)
        return result

    return wrapper


@functools.lru_cache(maxsize=1)
def key_columns_card() -> str:
    """Exact column lists of the most-used objects, from SYSCAT, so the LLM does not guess names."""
    try:
        rows = get_db("agent").query(
            "SELECT TABNAME, LISTAGG(COLNAME, ', ') WITHIN GROUP (ORDER BY COLNO) AS COLS FROM SYSCAT.COLUMNS "
            "WHERE TABSCHEMA = ? AND TABNAME IN ('V_DAILY_KPIS', 'V_ROOM_TYPE_DAY', 'RESERVATIONS', 'ROOM_TYPES', "
            "'GUEST_REVIEWS', 'MAINTENANCE_TICKETS') AND HIDDEN <> 'I' AND COLNAME NOT IN ('EMBEDDING') "
            "GROUP BY TABNAME ORDER BY TABNAME", (SCHEMA,))
    except Db2Error:
        return ""
    lines = [f"- {r['TABNAME']}({r['COLS']})" for r in rows]
    return "\n".join(["Exact columns (from the Db2 catalog):", *lines])


@functools.lru_cache(maxsize=1)
def schema_card() -> str:
    """Compact description of HOTELOPS tables/views built from the Db2 catalog (incl. COMMENTs)."""
    db = get_db("agent")
    tables = db.query(
        "SELECT TABNAME, TYPE, REMARKS FROM SYSCAT.TABLES WHERE TABSCHEMA = ? "
        "AND TABNAME NOT LIKE 'AGENT_%' AND TABNAME NOT LIKE '%_HISTORY' ORDER BY TYPE, TABNAME",
        (SCHEMA,),
    )
    cols = db.query(
        "SELECT TABNAME, COLNAME, TYPENAME, LENGTH, SCALE, REMARKS FROM SYSCAT.COLUMNS "
        "WHERE TABSCHEMA = ? AND HIDDEN <> 'I' ORDER BY TABNAME, COLNO",
        (SCHEMA,),
    )
    by_table: dict[str, list[str]] = {}
    for c in cols:
        if c["COLNAME"] in ("EMBEDDING", "SYS_START", "SYS_END") and c["TABNAME"] != "RATE_PLAN":
            continue
        t = c["TYPENAME"]
        if t in ("VARCHAR", "CHARACTER"):
            t = f"{t}({c['LENGTH']})"
        elif t == "DECIMAL":
            t = f"DECIMAL({c['LENGTH']},{c['SCALE']})"
        note = f" -- {c['REMARKS']}" if c.get("REMARKS") else ""
        by_table.setdefault(c["TABNAME"], []).append(f"{c['COLNAME']} {t}{note}")
    lines = [f"Schema {SCHEMA} (IBM Db2). Tables (T) and views (V):"]
    for t in tables:
        name = t["TABNAME"]
        lines.append(f"\n{t['TYPE'].strip()} {name}: {t.get('REMARKS') or ''}")
        lines.extend(f"  - {c}" for c in by_table.get(name, []))
    return "\n".join(lines)


def build_tools(ctx: RunContext, db: Db2 | None = None) -> dict[str, BaseTool]:
    """Create the tool set bound to one run context."""
    settings = load_settings()
    agent_db = db or get_db("agent")

    # ------------------------------------------------------------------ read
    def describe_schema() -> str:
        """Return the Db2 schema card: every table/view, its columns, types and business meaning."""
        return schema_card()

    def run_sql(query: str) -> str:
        """Run ONE read-only Db2 SQL query (SELECT or WITH) and return up to 200 rows as JSON.

        Args:
            query: A single Db2 SELECT statement. Use Db2 syntax: FETCH FIRST n ROWS ONLY,
                CURRENT DATE, CURRENT DATE + 7 DAYS, DAYNAME(d), VARCHAR_FORMAT(ts, 'YYYY-MM-DD').
        """
        safe = validate_select(query, settings.sql_row_limit)
        cost = check_cost(safe)  # Db2 EXPLAIN estimate; refuses runaway queries before they run
        rows = agent_db.query(safe, max_rows=settings.sql_row_limit)
        return _dump({"row_count": len(rows), "est_cost_timerons": round(cost), "rows": rows})

    def occupancy_outlook(days_ahead: int = 14, room_type_code: str = "") -> str:
        """Forward-looking occupancy and pricing per stay date and room type.

        Args:
            days_ahead: Number of future nights to include, starting today (1-90).
            room_type_code: Optional room type code filter (STD, DLX, PRM, FAM, JST, STE).
        """
        days = max(1, min(int(days_ahead), 90))
        sql = (
            "SELECT V.STAY_DATE, V.DAY_NAME, V.ROOM_TYPE_CODE, V.ROOMS_IN_SERVICE, V.ROOMS_SOLD, "
            "DECIMAL(100.0 * V.ROOMS_SOLD / NULLIF(V.ROOMS_IN_SERVICE, 0), 5, 1) AS OCC_PCT, "
            "V.CURRENT_SELL_RATE, RT.FLOOR_RATE, RT.CEILING_RATE "
            "FROM V_ROOM_TYPE_DAY V JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = V.ROOM_TYPE_ID "
            "WHERE V.STAY_DATE BETWEEN CURRENT DATE AND CURRENT DATE + ? DAYS "
        )
        params: list = [days - 1]
        if room_type_code:
            sql += "AND V.ROOM_TYPE_CODE = ? "
            params.append(room_type_code.upper())
        sql += "ORDER BY V.STAY_DATE, RT.TIER"
        return _dump(agent_db.query(sql, params))

    def search_reviews(query: str, days: int = 90, max_rating: int = 5, k: int = 8) -> str:
        """Semantic search over guest reviews using Db2 VECTOR_DISTANCE (cosine) on stored embeddings.

        Args:
            query: What to look for, in natural language (e.g. "noisy air conditioning").
            days: Only reviews from the last N days.
            max_rating: Only reviews with RATING <= this value (use 3 to focus on complaints).
            k: Number of reviews to return (1-25).
        """
        from .embeddings import embed_query

        vec = vector_literal(embed_query(query))
        rows = agent_db.query(
            "WITH C AS ("
            "  SELECT C.REVIEW_ID, C.CHUNK_TEXT, "
            "         VECTOR_DISTANCE(C.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS D "
            "  FROM REVIEW_CHUNKS C JOIN GUEST_REVIEWS R ON R.REVIEW_ID = C.REVIEW_ID "
            "  WHERE R.CREATED_AT >= CURRENT DATE - ? DAYS AND R.RATING <= ?), "
            "B AS (SELECT C.*, ROW_NUMBER() OVER (PARTITION BY REVIEW_ID ORDER BY D) AS RN FROM C) "
            "SELECT R.REVIEW_ID, R.CREATED_AT, R.RATING, R.ROOM_NO, RM.FLOOR_NO, "
            "B.CHUNK_TEXT AS MATCHED_SENTENCE, DECIMAL(B.D, 6, 4) AS DISTANCE, R.REVIEW_TEXT "
            "FROM B JOIN GUEST_REVIEWS R ON R.REVIEW_ID = B.REVIEW_ID "
            "LEFT JOIN ROOMS RM ON RM.ROOM_NO = R.ROOM_NO "
            "WHERE B.RN = 1 ORDER BY B.D FETCH FIRST ? ROWS ONLY",
            (vec, int(days), int(max_rating), max(1, min(int(k), 25))),
        )
        return _dump(rows)

    def review_hotspots(query: str, days: int = 30, max_distance: float = 0.35) -> str:
        """Find WHERE a complaint theme is concentrated: counts semantically matching reviews per room and floor.

        Args:
            query: The theme, e.g. "air conditioning noise" or "no hot water".
            days: Look-back window in days.
            max_distance: Cosine distance cut-off on the best-matching sentence (0.30 strict - 0.45 loose).
        """
        from .embeddings import embed_query

        vec = vector_literal(embed_query(query))
        rows = agent_db.query(
            "WITH B AS ("
            "  SELECT C.REVIEW_ID, MIN(VECTOR_DISTANCE(C.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE)) AS D "
            "  FROM REVIEW_CHUNKS C GROUP BY C.REVIEW_ID), "
            "M AS ("
            "  SELECT R.ROOM_NO, RM.FLOOR_NO, R.RATING, R.CREATED_AT FROM B "
            "  JOIN GUEST_REVIEWS R ON R.REVIEW_ID = B.REVIEW_ID "
            "  LEFT JOIN ROOMS RM ON RM.ROOM_NO = R.ROOM_NO "
            "  WHERE R.CREATED_AT >= CURRENT DATE - ? DAYS AND B.D <= ?) "
            "SELECT ROOM_NO, FLOOR_NO, COUNT(*) AS MATCHING_REVIEWS, DECIMAL(AVG(RATING * 1.0), 3, 2) AS AVG_RATING, "
            "MAX(CREATED_AT) AS LATEST FROM M GROUP BY ROLLUP(FLOOR_NO, ROOM_NO) "
            "ORDER BY MATCHING_REVIEWS DESC, ROOM_NO FETCH FIRST 15 ROWS ONLY",
            (vec, int(days), float(max_distance)),
        )
        return _dump({"note": "rows with ROOM_NO null are floor subtotals; both null = grand total",
                      "rows": rows})

    def complaint_radar(days: int = 30) -> str:
        """Overview of ALL complaint themes at once (AC, hot water, Wi-Fi, check-in, noise, value, housekeeping,
        food, staff), classified inside Db2 by vector similarity, with top rooms, floors and whether each theme
        is LOCALISED to a room (likely equipment) or SYSTEMIC (process issue). Start with this tool.

        Args:
            days: Look-back window in days.
        """
        from .radar import complaint_radar as radar

        return _dump(radar(agent_db, days))

    def search_policies(query: str, k: int = 3) -> str:
        """Search the hotel's operations policy handbook (stored in Db2 via IBM langchain-db2) by meaning.
        Use before proposing an action and cite the returned policy_id in the rationale.

        Args:
            query: The situation, e.g. "upgrade a platinum guest" or "AC complaints in a fully booked room type".
            k: Number of policies to return (1-6).
        """
        from .knowledge import search_policies as kb_search

        return _dump(kb_search(query, k))

    def rate_history(room_type_code: str, stay_date: str) -> str:
        """Every version of the sell rate for one room type and night, using Db2 system-period time travel.

        Args:
            room_type_code: STD, DLX, PRM, FAM, JST or STE.
            stay_date: Night in YYYY-MM-DD format.
        """
        rows = agent_db.query(
            "SELECT RP.RATE, RP.UPDATED_BY, RP.CHANGE_REASON, RP.SOURCE_ACTION_ID, RP.SYS_START AS VALID_FROM, "
            "CASE WHEN RP.SYS_END >= '9999-01-01' THEN NULL ELSE RP.SYS_END END AS VALID_TO "
            "FROM RATE_PLAN FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' RP "
            "JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = RP.ROOM_TYPE_ID "
            "WHERE RT.CODE = ? AND RP.STAY_DATE = ? ORDER BY RP.SYS_START",
            (room_type_code.upper(), stay_date),
        )
        return _dump(rows)

    def promotion_on(room_type_code: str, stay_date: str, as_known_at: str = "") -> str:
        """Discount for a room type on a stay date, from the BITEMPORAL table PROMOTIONS (Db2 BUSINESS_TIME +
        SYSTEM_TIME). Shows the offer in force and every version ever recorded for that night, so you can
        tell what a guest was quoted before a later correction.

        Args:
            room_type_code: STD, DLX, PRM, FAM, JST or STE.
            stay_date: Night in YYYY-MM-DD format (business time).
            as_known_at: Optional timestamp 'YYYY-MM-DD HH:MM:SS': what the hotel's records said at that moment.
        """
        code, night = room_type_code.upper(), stay_date
        cols = ("P.PROMO_ID, P.NAME, P.DISCOUNT_PCT, P.VALID_FROM, P.VALID_TO, P.UPDATED_BY, P.CHANGE_REASON, "
                "P.SYS_START AS RECORDED_AT")
        if as_known_at:
            in_force = agent_db.query(
                f"SELECT {cols} FROM PROMOTIONS FOR SYSTEM_TIME AS OF CAST(? AS TIMESTAMP) "
                "FOR BUSINESS_TIME AS OF CAST(? AS DATE) P JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = P.ROOM_TYPE_ID "
                "WHERE RT.CODE = ?", (as_known_at, night, code))
        else:
            in_force = agent_db.query(
                f"SELECT {cols} FROM PROMOTIONS FOR BUSINESS_TIME AS OF CAST(? AS DATE) P "
                "JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = P.ROOM_TYPE_ID WHERE RT.CODE = ?", (night, code))
        versions = agent_db.query(
            f"SELECT {cols}, CASE WHEN P.SYS_END >= '9999-01-01' THEN NULL ELSE P.SYS_END END AS SUPERSEDED_AT "
            "FROM PROMOTIONS FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' "
            "FOR BUSINESS_TIME AS OF CAST(? AS DATE) P "
            "JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = P.ROOM_TYPE_ID WHERE RT.CODE = ? ORDER BY P.SYS_START",
            (night, code))
        return _dump({"room_type": code, "stay_date": night, "as_known_at": as_known_at or "now",
                      "in_force": in_force, "all_recorded_versions": versions})

    def what_changed(hours: int = 24) -> str:
        """Change feed from Db2 time travel: rate, reservation and room-status changes in the last N hours,
        each with before/after values, who changed it, why, and the agent action that caused it.

        Args:
            hours: Look-back window in hours (1-720). Use 24 for "since yesterday".
        """
        from .changefeed import change_feed

        return _dump(change_feed(agent_db, hours))

    def find_upgrade_candidates(days_ahead: int = 3) -> str:
        """Loyalty guests (GOLD/PLATINUM) arriving soon, with the number of free higher-tier rooms for their stay.

        Args:
            days_ahead: Arrivals from today up to this many days ahead.
        """
        rows = agent_db.query(
            "SELECT X.RESERVATION_ID, G.FULL_NAME, G.LOYALTY_TIER, X.CHECK_IN, X.CHECK_OUT, "
            "RT.CODE AS BOOKED_TYPE, X.SPECIAL_NOTE, UT.CODE AS UPGRADE_TO, UT.TIER AS UPGRADE_TIER, "
            "COUNT(R.ROOM_NO) AS FREE_ROOMS_FOR_WHOLE_STAY, "
            "(SELECT COUNT(*) FROM RESERVATIONS P WHERE P.GUEST_ID = G.GUEST_ID "
            "   AND P.STATUS = 'CHECKED_OUT') AS PAST_STAYS "
            "FROM RESERVATIONS X "
            "JOIN GUESTS G ON G.GUEST_ID = X.GUEST_ID "
            "JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = X.ROOM_TYPE_ID "
            "JOIN ROOM_TYPES UT ON UT.TIER > RT.TIER "
            "JOIN ROOMS R ON R.ROOM_TYPE_ID = UT.ROOM_TYPE_ID AND R.STATUS = 'IN_SERVICE' "
            "WHERE X.STATUS = 'CONFIRMED' AND X.CHECK_IN BETWEEN CURRENT DATE AND CURRENT DATE + ? DAYS "
            "AND G.LOYALTY_TIER IN ('GOLD', 'PLATINUM') "
            "AND NOT EXISTS (SELECT 1 FROM RESERVATIONS O WHERE O.ROOM_NO = R.ROOM_NO "
            "   AND O.STATUS IN ('CONFIRMED', 'CHECKED_IN') "
            "   AND O.CHECK_IN < X.CHECK_OUT AND O.CHECK_OUT > X.CHECK_IN) "
            "GROUP BY X.RESERVATION_ID, G.GUEST_ID, G.FULL_NAME, G.LOYALTY_TIER, X.CHECK_IN, X.CHECK_OUT, "
            "RT.CODE, X.SPECIAL_NOTE, UT.CODE, UT.TIER "
            "ORDER BY CASE G.LOYALTY_TIER WHEN 'PLATINUM' THEN 0 ELSE 1 END, X.CHECK_IN, X.RESERVATION_ID, UT.TIER "
            "FETCH FIRST 30 ROWS ONLY",
            (int(days_ahead),),
        )
        return _dump({"note": "one row per (reservation, possible upgrade room type) with free rooms",
                      "rows": rows})

    def list_actions(status: str = "PENDING") -> str:
        """List agent actions in the approval queue.

        Args:
            status: PENDING, APPLIED, REJECTED, ROLLED_BACK, FAILED or ALL.
        """
        sql = ("SELECT ACTION_ID, ACTION_TYPE, PAYLOAD, STATUS, PROPOSED_AT, RESULT_MESSAGE FROM AGENT_ACTIONS ")
        params: tuple = ()
        if status.upper() != "ALL":
            sql += "WHERE STATUS = ? "
            params = (status.upper(),)
        sql += "ORDER BY ACTION_ID DESC FETCH FIRST 20 ROWS ONLY"
        return _dump(agent_db.query(sql, params))

    # --------------------------------------------------------------- propose
    def _propose(action_type: str, payload: dict, rationale: str) -> str:
        out = agent_db.call(f"{SCHEMA}.SP_PROPOSE_ACTION", ctx.run_id, action_type,
                            json.dumps(payload), rationale[:2000], 0, OUT_TEXT)
        action_id, message = (out[4] or None), out[5]
        ctx.emit(type="proposal", action_id=action_id, action_type=action_type, payload=payload, message=message)
        return _dump({"action_id": action_id, "result": message})

    def propose_rate_change(room_type_code: str, start_date: str, end_date: str, new_rate: float,
                            rationale: str) -> str:
        """Queue a rate change for manager approval (NOT applied until a human approves).

        Args:
            room_type_code: STD, DLX, PRM, FAM, JST or STE.
            start_date: First night (YYYY-MM-DD), today or later.
            end_date: Last night (YYYY-MM-DD), inclusive.
            new_rate: New nightly sell rate in INR; must stay inside the room type's floor/ceiling band
                and within 35% of the current rate.
            rationale: Evidence-based reason citing the numbers you looked at.
        """
        return _propose("RATE_CHANGE", {"room_type_code": room_type_code.upper(), "start_date": start_date,
                                        "end_date": end_date, "new_rate": round(float(new_rate), 2)}, rationale)

    def propose_room_upgrade(reservation_id: int, to_room_type_code: str, rationale: str) -> str:
        """Queue a complimentary room upgrade for manager approval.

        Args:
            reservation_id: The reservation to upgrade.
            to_room_type_code: Target room type code (must be a higher tier with a free room).
            rationale: Why this guest deserves the upgrade.
        """
        return _propose("ROOM_UPGRADE", {"reservation_id": int(reservation_id),
                                         "to_room_type_code": to_room_type_code.upper()}, rationale)

    def propose_maintenance(room_no: str, category: str, priority: str, description: str,
                            take_out_of_order: bool, rationale: str) -> str:
        """Queue a maintenance work order (optionally taking the room out of order) for manager approval.

        Args:
            room_no: Room number, e.g. "307".
            category: HVAC, PLUMBING, ELECTRICAL, NETWORK, HOUSEKEEPING or GENERAL.
            priority: LOW, MEDIUM, HIGH or URGENT.
            description: What engineering should inspect or fix.
            take_out_of_order: True to block the room from sale until fixed.
            rationale: Evidence (e.g. review IDs and counts) supporting the ticket.
        """
        return _propose("MAINTENANCE", {"room_no": str(room_no), "category": category.upper(),
                                        "priority": priority.upper(), "description": description[:900],
                                        "take_out_of_order": bool(take_out_of_order)}, rationale)

    fns = [describe_schema, run_sql, occupancy_outlook, search_reviews, review_hotspots, complaint_radar,
           search_policies,
           rate_history, promotion_on,
           what_changed, find_upgrade_candidates, list_actions,
           propose_rate_change, propose_room_upgrade, propose_maintenance]
    tools: dict[str, BaseTool] = {}
    for fn in fns:
        tools[fn.__name__] = tool(_audited(ctx, fn), parse_docstring=True)
    return tools


AGENT_TOOLSETS = {
    "analyst": ["describe_schema", "run_sql", "occupancy_outlook", "rate_history", "promotion_on", "what_changed"],
    "reviews": ["complaint_radar", "search_reviews", "review_hotspots", "run_sql"],
    "operations": ["occupancy_outlook", "find_upgrade_candidates", "complaint_radar", "review_hotspots",
                   "search_reviews", "search_policies",
                   "rate_history", "promotion_on", "what_changed", "run_sql", "list_actions",
                   "propose_rate_change", "propose_room_upgrade",
                   "propose_maintenance"],
}
