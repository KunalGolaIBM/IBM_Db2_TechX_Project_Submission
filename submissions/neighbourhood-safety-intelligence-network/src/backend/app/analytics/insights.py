"""Response-time and hotspot analytics.

In DATABASE_MODE=db2 every metric is computed inside IBM Db2 with native SQL: CTEs,
SECONDS_BETWEEN, MEDIAN, PERCENTILE_CONT ... WITHIN GROUP, RANK() OVER and HOUR(). Other
databases (SQLite for tests and local development) use an equivalent Python path, and the
test suite checks that both produce the same numbers.
"""
import datetime
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.entities import Incident, IncidentStatusHistory

ACTIVE_STATUSES = ("reported", "acknowledged", "responder_en_route", "on_scene", "resolving")
CLOSED_STATUSES = ("resolved", "false_alarm")
# Time-to-acknowledge targets from the responder SOP (seconds).
ACK_TARGET_SECONDS = {"P1_CRITICAL": 120, "P2_HIGH": 900, "P3_MODERATE": 3600, "P4_ADVISORY": 86400}
GENERIC_LOCATIONS = ("Current Device GPS Coordinates", "Current GPS Location")
WINDOW_DAYS = 30


@dataclass
class PriorityResponse:
    priority: str
    incidents: int
    acknowledged: int
    avg_ack_minutes: Optional[float]
    median_ack_minutes: Optional[float]
    p90_ack_minutes: Optional[float]
    avg_resolve_minutes: Optional[float]
    ack_target_minutes: float


@dataclass
class Hotspot:
    rank: int
    location: str
    incidents: int
    open_incidents: int
    last_reported: datetime.datetime


def _minutes(seconds: Optional[float]) -> Optional[float]:
    return None if seconds is None else round(float(seconds) / 60.0, 2)


# ---------------------------------------------------------------------------------------------
# Db2-native SQL
# ---------------------------------------------------------------------------------------------
DB2_RESPONSE_TIMES = """
WITH first_ack AS (
    SELECT incident_id, MIN(created_at) AS ack_at
    FROM incident_status_history
    WHERE status = 'acknowledged'
    GROUP BY incident_id
), first_close AS (
    SELECT incident_id, MIN(created_at) AS closed_at
    FROM incident_status_history
    WHERE status IN ('resolved', 'false_alarm')
    GROUP BY incident_id
)
SELECT i.priority,
       COUNT(*)                                                    AS incidents,
       COUNT(a.ack_at)                                             AS acknowledged,
       AVG(DOUBLE(SECONDS_BETWEEN(a.ack_at, i.created_at)))        AS avg_ack_s,
       MEDIAN(DOUBLE(SECONDS_BETWEEN(a.ack_at, i.created_at)))     AS median_ack_s,
       PERCENTILE_CONT(0.9) WITHIN GROUP
           (ORDER BY DOUBLE(SECONDS_BETWEEN(a.ack_at, i.created_at))) AS p90_ack_s,
       AVG(DOUBLE(SECONDS_BETWEEN(c.closed_at, i.created_at)))     AS avg_resolve_s
FROM incidents i
LEFT JOIN first_ack a   ON a.incident_id = i.id
LEFT JOIN first_close c ON c.incident_id = i.id
WHERE i.created_at >= :since
GROUP BY i.priority
ORDER BY i.priority
"""

DB2_OVERALL_ACK = """
SELECT AVG(DOUBLE(SECONDS_BETWEEN(a.ack_at, i.created_at)))
FROM incidents i
JOIN (SELECT incident_id, MIN(created_at) AS ack_at
      FROM incident_status_history WHERE status = 'acknowledged' GROUP BY incident_id) a
  ON a.incident_id = i.id
WHERE i.created_at >= :since
"""

DB2_HOTSPOTS = """
SELECT RANK() OVER (ORDER BY COUNT(*) DESC)                                         AS hotspot_rank,
       location_address,
       COUNT(*)                                                                     AS incidents,
       SUM(CASE WHEN status IN ('reported', 'acknowledged', 'responder_en_route',
                                'on_scene', 'resolving') THEN 1 ELSE 0 END)         AS open_incidents,
       MAX(created_at)                                                              AS last_reported
FROM incidents
WHERE created_at >= :since
  AND location_address IS NOT NULL
  AND location_address NOT IN ('Current Device GPS Coordinates', 'Current GPS Location')
GROUP BY location_address
ORDER BY hotspot_rank, last_reported DESC
FETCH FIRST 5 ROWS ONLY
"""

DB2_BY_HOUR = """
SELECT HOUR(created_at) AS hour_of_day, COUNT(*) AS incidents
FROM incidents
WHERE created_at >= :since
GROUP BY HOUR(created_at)
ORDER BY hour_of_day
"""

DB2_SLA_BREACHES = """
SELECT COUNT(*)
FROM incidents i
WHERE i.status = 'reported'
  AND SECONDS_BETWEEN(CAST(:now AS TIMESTAMP), i.created_at) >
      CASE i.priority WHEN 'P1_CRITICAL' THEN 120
                      WHEN 'P2_HIGH'     THEN 900
                      WHEN 'P3_MODERATE' THEN 3600
                      ELSE 86400 END
"""


def _db2_metrics(db: Session, since: datetime.datetime, now: datetime.datetime) -> Dict:
    params = {"since": since}
    priorities = [
        PriorityResponse(
            priority=r[0], incidents=int(r[1]), acknowledged=int(r[2]),
            avg_ack_minutes=_minutes(r[3]), median_ack_minutes=_minutes(r[4]), p90_ack_minutes=_minutes(r[5]),
            avg_resolve_minutes=_minutes(r[6]), ack_target_minutes=ACK_TARGET_SECONDS.get(r[0], 86400) / 60,
        )
        for r in db.execute(text(DB2_RESPONSE_TIMES), params)
    ]
    overall = db.execute(text(DB2_OVERALL_ACK), params).scalar()
    hotspots = [Hotspot(rank=int(r[0]), location=r[1], incidents=int(r[2]), open_incidents=int(r[3]),
                        last_reported=r[4]) for r in db.execute(text(DB2_HOTSPOTS), params)]
    by_hour = {int(r[0]): int(r[1]) for r in db.execute(text(DB2_BY_HOUR), params)}
    breaches = int(db.execute(text(DB2_SLA_BREACHES), {"now": now}).scalar() or 0)
    return {"priorities": priorities, "overall_ack_s": overall, "hotspots": hotspots,
            "by_hour": by_hour, "sla_breaches": breaches}


# ---------------------------------------------------------------------------------------------
# Portable path (SQLite / PostgreSQL): same metrics, computed in Python
# ---------------------------------------------------------------------------------------------
def _percentile_cont(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _python_metrics(db: Session, since: datetime.datetime, now: datetime.datetime) -> Dict:
    incidents = db.query(Incident).filter(Incident.created_at >= since).all()
    ids = [i.id for i in incidents]
    first: Dict[str, Dict[int, datetime.datetime]] = {"ack": {}, "close": {}}
    if ids:
        for h in db.query(IncidentStatusHistory).filter(IncidentStatusHistory.incident_id.in_(ids)):
            kind = "ack" if h.status == "acknowledged" else "close" if h.status in CLOSED_STATUSES else None
            if kind and (h.incident_id not in first[kind] or h.created_at < first[kind][h.incident_id]):
                first[kind][h.incident_id] = h.created_at

    groups: Dict[str, List[Incident]] = defaultdict(list)
    for inc in incidents:
        groups[inc.priority].append(inc)

    def secs(a: Dict[int, datetime.datetime], inc: Incident) -> Optional[float]:
        t = a.get(inc.id)
        return None if t is None else (t - inc.created_at).total_seconds()

    priorities, all_ack = [], []
    for prio in sorted(groups):
        ack = [s for s in (secs(first["ack"], i) for i in groups[prio]) if s is not None]
        res = [s for s in (secs(first["close"], i) for i in groups[prio]) if s is not None]
        all_ack.extend(ack)
        priorities.append(PriorityResponse(
            priority=prio, incidents=len(groups[prio]), acknowledged=len(ack),
            avg_ack_minutes=_minutes(statistics.fmean(ack)) if ack else None,
            median_ack_minutes=_minutes(statistics.median(ack)) if ack else None,
            p90_ack_minutes=_minutes(_percentile_cont(ack, 0.9)),
            avg_resolve_minutes=_minutes(statistics.fmean(res)) if res else None,
            ack_target_minutes=ACK_TARGET_SECONDS.get(prio, 86400) / 60,
        ))

    located = [i for i in incidents if i.location_address and i.location_address not in GENERIC_LOCATIONS]
    counts = Counter(i.location_address for i in located)
    ordered = sorted(counts, key=lambda loc: (-counts[loc],
                                              -max(i.created_at for i in located if i.location_address == loc).timestamp()))
    hotspots, rank, prev = [], 0, None
    for pos, loc in enumerate(ordered, start=1):
        if counts[loc] != prev:
            rank, prev = pos, counts[loc]
        mine = [i for i in located if i.location_address == loc]
        hotspots.append(Hotspot(rank=rank, location=loc, incidents=counts[loc],
                                open_incidents=sum(i.status in ACTIVE_STATUSES for i in mine),
                                last_reported=max(i.created_at for i in mine)))
    breaches = sum(1 for i in incidents if i.status == "reported"
                   and (now - i.created_at).total_seconds() > ACK_TARGET_SECONDS.get(i.priority, 86400))
    return {"priorities": priorities, "overall_ack_s": statistics.fmean(all_ack) if all_ack else None,
            "hotspots": hotspots[:5], "by_hour": dict(sorted(Counter(i.created_at.hour for i in incidents).items())),
            "sla_breaches": breaches}


def compute_insights(db: Session, now: Optional[datetime.datetime] = None) -> Dict:
    now = now or datetime.datetime.utcnow()
    since = now - datetime.timedelta(days=WINDOW_DAYS)
    use_db2 = settings.DATABASE_MODE == "db2"
    m = _db2_metrics(db, since, now) if use_db2 else _python_metrics(db, since, now)
    return {
        "analytics_engine": "IBM Db2 SQL (MEDIAN, PERCENTILE_CONT, RANK OVER)" if use_db2 else "Python (portable mode)",
        "window_days": WINDOW_DAYS,
        "average_response_time_minutes": _minutes(m["overall_ack_s"]),
        "response_times": [asdict(p) for p in m["priorities"]],
        "hotspots": [asdict(h) for h in m["hotspots"]],
        "incidents_by_hour": m["by_hour"],
        "sla_breaches": m["sla_breaches"],
    }
