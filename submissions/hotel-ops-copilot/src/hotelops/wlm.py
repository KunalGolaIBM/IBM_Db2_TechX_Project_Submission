"""Db2 workload management for the AI login: prove that Db2 itself caps what the agent's queries may cost.

03_security.sql puts every connection of the agent identity in workload HOTELOPS_AGENT_WL with thresholds:
estimated cost above 25,000 timerons, more than 1,000 rows returned (bulk extraction), or more than 30 s of
run time stop the activity with SQL4712N. A threshold-violations event monitor records each stop in
HOTELOPS.AGENT_THRESHOLD_VIOLATIONS. These limits apply to the agent's own credentials, so they hold even
if the application's SQL guard and EXPLAIN check are bypassed. The manager login is not in the workload.
"""
from __future__ import annotations

import re

from hotelops.config import SCHEMA, load_settings
from hotelops.db import Db2, Db2Error

THRESHOLDS = ("HOTELOPS_AGENT_MAX_COST", "HOTELOPS_AGENT_MAX_ROWS", "HOTELOPS_AGENT_MAX_TIME")
VIOLATIONS = f"{SCHEMA}.AGENT_THRESHOLD_VIOLATIONS"


def _own(role: str) -> Db2:
    s = load_settings().db2
    user, pw = (s.admin_user, s.admin_password) if role == "admin" else (s.agent_user, s.agent_password)
    return Db2(s.conn_str(user, pw), f"wlm-{role}")


def _attempt(db: Db2, sql: str) -> tuple[bool, str]:
    try:
        rows = db.query(sql)
        return True, f"{len(rows)} row(s)"
    except Db2Error as exc:
        m = re.search(r'SQL\d{4,5}N.*?threshold "(\w+)"', str(exc))
        return False, (f"SQL4712N {m.group(1)}" if m else str(exc)[:120])


def violations(admin: Db2) -> int:
    admin.execute("FLUSH EVENT MONITOR HOTELOPS_AGENT_VIOLATIONS BUFFER")
    return admin.scalar(f"SELECT COUNT(*) FROM {VIOLATIONS}")


def workload_check() -> dict:
    """Run a normal, a runaway and a bulk-extraction query on the agent's own login; nothing is written."""
    admin, agent = _own("admin"), _own("agent")
    try:
        defined = admin.query("SELECT THRESHOLDNAME, MAXVALUE FROM SYSCAT.THRESHOLDS WHERE THRESHOLDNAME IN "
                              f"({', '.join('?' * len(THRESHOLDS))}) ORDER BY THRESHOLDNAME", THRESHOLDS)
        before = violations(admin)
        result = {
            "thresholds": {r["THRESHOLDNAME"]: float(r["MAXVALUE"]) for r in defined},
            "normal": _attempt(agent, "SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE"),
            "runaway": _attempt(agent, "SELECT COUNT(*) FROM RESERVATIONS A, RESERVATIONS B, RESERVATIONS C"),
            "bulk": _attempt(agent, "SELECT RESERVATION_ID, GUEST_ID, CHECK_IN FROM RESERVATIONS"),
            "manager_bulk": _attempt(admin, "SELECT RESERVATION_ID FROM RESERVATIONS FETCH FIRST 1500 ROWS ONLY"),
        }
        result["violations_logged"] = violations(admin) - before
        return result
    finally:
        agent.close()
        admin.close()
