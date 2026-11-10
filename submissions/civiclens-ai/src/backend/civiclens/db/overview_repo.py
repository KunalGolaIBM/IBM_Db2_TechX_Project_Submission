"""Aggregate queries behind the dashboard overview. Every figure is computed by IBM Db2."""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
from typing import Any

from civiclens.db.connection import Db2Session
from civiclens.domain.investigation_models import GeneratorType, InvestigationStatus, RecommendationStatus
from civiclens.domain.models import Category, ComplaintStatus
from civiclens.domain.overview_models import (
    AgentActivity,
    CategoryCount,
    ComplaintStats,
    InvestigationStats,
    RecommendationStats,
    SeverityCount,
    StatusCount,
    TrendPoint,
)

ACTIVE_INVESTIGATION_STATUSES = (
    InvestigationStatus.OPEN,
    InvestigationStatus.RUNNING,
    InvestigationStatus.PENDING_REVIEW,
)
ACTIVITY_LIMIT = 12


def _ts(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


def _num(value: Any) -> float:
    return float(value) if value is not None else 0.0


def complaint_stats(db: Db2Session, now: dt.datetime, *, trend_days: int = 30) -> ComplaintStats:
    totals = db.fetch_one(
        """
        SELECT COUNT(*) AS TOTAL,
               COALESCE(SUM(CASE WHEN IS_SYNTHETIC = 1 THEN 1 ELSE 0 END), 0) AS SYNTHETIC,
               COALESCE(SUM(CASE WHEN REPORTED_AT >= CAST(? AS TIMESTAMP) THEN 1 ELSE 0 END), 0) AS LAST_7D,
               COALESCE(SUM(CASE WHEN REPORTED_AT >= CAST(? AS TIMESTAMP) THEN 1 ELSE 0 END), 0) AS LAST_30D
        FROM {schema}.COMPLAINTS
        """,
        (_ts(now - timedelta(days=7)), _ts(now - timedelta(days=30))),
    )
    assert totals is not None
    total, synthetic = int(totals["total"]), int(totals["synthetic"])

    by_category = [
        CategoryCount(
            category=Category(r["category"]),
            count=int(r["n"]),
            avg_severity=round(_num(r["avg_severity"]), 2),
            synthetic=int(r["synthetic"]),
        )
        for r in db.fetch_all(
            """
            SELECT CATEGORY, COUNT(*) AS N, AVG(CAST(SEVERITY AS DOUBLE)) AS AVG_SEVERITY,
                   COALESCE(SUM(CASE WHEN IS_SYNTHETIC = 1 THEN 1 ELSE 0 END), 0) AS SYNTHETIC
            FROM {schema}.COMPLAINTS GROUP BY CATEGORY ORDER BY N DESC, CATEGORY
            """
        )
    ]

    status_counts = {r["status"]: int(r["n"]) for r in db.fetch_all(
        "SELECT STATUS, COUNT(*) AS N FROM {schema}.COMPLAINTS GROUP BY STATUS"
    )}  # fmt: skip
    by_status = [StatusCount(status=s, count=status_counts.get(s.value, 0)) for s in ComplaintStatus]

    severity_counts = {int(r["severity"]): int(r["n"]) for r in db.fetch_all(
        "SELECT SEVERITY, COUNT(*) AS N FROM {schema}.COMPLAINTS GROUP BY SEVERITY"
    )}  # fmt: skip
    by_severity = [SeverityCount(severity=s, count=severity_counts.get(s, 0)) for s in range(1, 6)]

    first_day = (now - timedelta(days=trend_days - 1)).date()
    per_day = {
        r["day"]: int(r["n"])
        for r in db.fetch_all(
            """
            SELECT DATE(REPORTED_AT) AS DAY, COUNT(*) AS N FROM {schema}.COMPLAINTS
            WHERE REPORTED_AT >= CAST(? AS TIMESTAMP) GROUP BY DATE(REPORTED_AT) ORDER BY DAY
            """,
            (_ts(dt.datetime.combine(first_day, dt.time.min)),),
        )
    }
    trend = [
        TrendPoint(date=first_day + timedelta(days=i), count=per_day.get(first_day + timedelta(days=i), 0))
        for i in range(trend_days)
    ]

    return ComplaintStats(
        total=total,
        synthetic=synthetic,
        real=total - synthetic,
        last_7d=int(totals["last_7d"]),
        last_30d=int(totals["last_30d"]),
        by_category=by_category,
        by_status=by_status,
        by_severity=by_severity,
        trend_days=trend_days,
        trend=trend,
    )


def investigation_stats(db: Db2Session) -> InvestigationStats:
    counts = {r["status"]: int(r["n"]) for r in db.fetch_all(
        "SELECT STATUS, COUNT(*) AS N FROM {schema}.INVESTIGATIONS GROUP BY STATUS"
    )}  # fmt: skip
    by_status = {s.value: counts.get(s.value, 0) for s in InvestigationStatus}
    return InvestigationStats(
        total=sum(by_status.values()),
        active=sum(by_status[s.value] for s in ACTIVE_INVESTIGATION_STATUSES),
        by_status=by_status,
    )


def recommendation_stats(db: Db2Session) -> RecommendationStats:
    rows = db.fetch_all(
        "SELECT STATUS, GENERATOR_TYPE, COUNT(*) AS N FROM {schema}.RECOMMENDATIONS "
        "GROUP BY STATUS, GENERATOR_TYPE"
    )
    by_status = {s.value: 0 for s in RecommendationStatus}
    by_generator = {g.value: 0 for g in GeneratorType}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + int(r["n"])
        by_generator[r["generator_type"]] = by_generator.get(r["generator_type"], 0) + int(r["n"])
    return RecommendationStats(
        total=sum(by_status.values()),
        pending_review=by_status[RecommendationStatus.PROPOSED.value],
        by_status=by_status,
        by_generator=by_generator,
    )


def recent_agent_activity(db: Db2Session, *, limit: int = ACTIVITY_LIMIT) -> list[AgentActivity]:
    limit = max(1, min(int(limit), 50))
    return [
        AgentActivity(
            audit_id=int(r["audit_id"]),
            investigation_id=int(r["investigation_id"]) if r["investigation_id"] is not None else None,
            action=r["action"],
            tool_name=r["tool_name"],
            success=bool(r["success"]),
            output_summary=(r["output_summary"] or None) and r["output_summary"][:200],
            created_at=r["created_at"],
        )
        for r in db.fetch_all(
            "SELECT AUDIT_ID, INVESTIGATION_ID, ACTION, TOOL_NAME, SUCCESS, OUTPUT_SUMMARY, CREATED_AT "
            "FROM {schema}.AUDIT_LOG WHERE ACTOR_TYPE = 'AGENT' "
            f"ORDER BY AUDIT_ID DESC FETCH FIRST {limit} ROWS ONLY"
        )
    ]
