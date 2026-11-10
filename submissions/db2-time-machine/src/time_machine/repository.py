"""Repositories: the investigators' only view of the data.

``Db2Repository`` talks to IBM Db2. ``time_machine.memory_repo.MemoryRepository`` is a
pure-Python test double with the same interface (used by the unit tests only).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Protocol

from .db import Db2Gateway
from .models import MetricPoint, fmt_ts, money, parse_ts
from . import temporal_sql as q
from .temporal_sql import ORDER_ITEMS, TrackedTable


class Repository(Protocol):  # pragma: no cover - interface description
    table: TrackedTable
    def now(self) -> datetime: ...
    def products(self) -> list[dict]: ...
    def last_snapshot(self, product_id: Optional[int]) -> Optional[dict]: ...
    def metric_as_of(self, product_id: Optional[int], ts: datetime) -> MetricPoint: ...
    def versions(self, product_id: Optional[int], start: datetime, end: datetime) -> tuple[list[dict], str]: ...
    def delete_log(self, start: datetime, end: datetime) -> tuple[list[dict], str]: ...
    def temporal_tables(self) -> list[dict]: ...
    def write_audit(self, entry: dict) -> None: ...
    def list_audit(self, run_id: str) -> list[dict]: ...
    def save_report(self, report: dict) -> None: ...
    def list_reports(self, limit: int = 20) -> list[dict]: ...
    def get_report(self, run_id: str) -> Optional[dict]: ...


class Db2Repository:
    table = ORDER_ITEMS

    def __init__(self, gateway: Db2Gateway):
        self.db = gateway

    # -- reads (guarded) -------------------------------------------------
    def now(self) -> datetime:
        rows = self.db.read(q.NOW_SQL)
        return parse_ts(list(rows[0].values())[0])

    def products(self) -> list[dict]:
        return self.db.read(q.PRODUCTS_SQL)

    def last_snapshot(self, product_id: Optional[int]) -> Optional[dict]:
        rows = self.db.read(q.snapshot_sql(product_id))
        if not rows:
            return None
        return {"ts": parse_ts(rows[0]["snapshot_ts"]), "revenue": money(rows[0]["revenue"]),
                "product_id": rows[0]["product_id"]}

    def metric_as_of(self, product_id: Optional[int], ts: datetime) -> MetricPoint:
        sql = q.metric_as_of_sql(self.table, product_id, ts)
        row = self.db.read(sql)[0]
        return MetricPoint(ts, money(row["revenue"]), int(row["row_count"]), sql)

    def versions(self, product_id, start, end):
        sql = q.versions_sql(self.table, product_id, start, end)
        return self.db.read(sql), sql

    def delete_log(self, start, end):
        sql = q.delete_log_sql(start, end)
        try:
            return self.db.read(sql), sql
        except Exception:  # log table is optional; deletions are still detected from history
            return [], sql

    def temporal_tables(self) -> list[dict]:
        return self.db.read(q.TEMPORAL_TABLES_SQL)

    # -- fixed writers ---------------------------------------------------
    def write_audit(self, e: dict) -> None:
        self.db.execute(
            "INSERT INTO AUDIT_LOG (RUN_ID, SEQ, AGENT, ACTION, SQL_TEXT, ROW_COUNT, LATENCY_MS, OUTCOME, DETAIL) "
            "VALUES (:run_id, :seq, :agent, :action, :sql_text, :row_count, :latency_ms, :outcome, :detail)",
            {"run_id": e["run_id"], "seq": e["seq"], "agent": e["agent"], "action": e["action"],
             "sql_text": (e.get("sql") or "")[:1800] or None, "row_count": e.get("rows"),
             "latency_ms": e.get("ms"), "outcome": e.get("outcome", "ok"),
             "detail": (e.get("detail") or "")[:800] or None})

    def list_audit(self, run_id: str) -> list[dict]:
        rows = self.db.read(
            "SELECT SEQ, AGENT, ACTION, SQL_TEXT, ROW_COUNT, LATENCY_MS, OUTCOME, DETAIL, "
            "VARCHAR_FORMAT(CREATED_AT, 'YYYY-MM-DD HH24:MI:SS.FF3') AS CREATED_AT "
            f"FROM AUDIT_LOG WHERE RUN_ID = '{_safe_id(run_id)}' ORDER BY SEQ")
        return rows

    def save_report(self, r: dict) -> None:
        self.db.execute(
            "INSERT INTO INCIDENT_REPORTS (RUN_ID, QUESTION, PRODUCT_NAME, STATUS, ROOT_CAUSE, ACTOR, "
            "IMPACT, REPORT_JSON) VALUES (:run_id, :question, :product, :status, :root, :actor, :impact, :json)",
            {"run_id": r["run_id"], "question": r["question"][:500], "product": r.get("product_name"),
             "status": r["verdict"]["status"], "root": r["verdict"].get("pattern"),
             "actor": (r.get("root_cause") or {}).get("actor"),
             "impact": str((r.get("root_cause") or {}).get("impact", "0")),
             "json": json.dumps(r, default=str)})

    def list_reports(self, limit: int = 20) -> list[dict]:
        return self.db.read(
            "SELECT RUN_ID, QUESTION, PRODUCT_NAME, STATUS, ROOT_CAUSE, ACTOR, IMPACT, "
            "VARCHAR_FORMAT(CREATED_AT, 'YYYY-MM-DD HH24:MI:SS') AS CREATED_AT "
            f"FROM INCIDENT_REPORTS ORDER BY CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY")

    def get_report(self, run_id: str) -> Optional[dict]:
        rows = self.db.read(f"SELECT REPORT_JSON FROM INCIDENT_REPORTS WHERE RUN_ID = '{_safe_id(run_id)}'")
        return json.loads(rows[0]["report_json"]) if rows else None

    # -- time-travel curve for the UI -------------------------------------
    def curve(self, product_id: Optional[int], start: datetime, end: datetime, points: int = 20) -> list[dict]:
        step = (end - start) / max(points - 1, 1)
        out = []
        for i in range(points):
            ts = start + step * i
            m = self.metric_as_of(product_id, ts)
            out.append({"ts": fmt_ts(ts), "revenue": str(m.revenue)})
        return out


def _safe_id(value: str) -> str:
    if not value or not all(c.isalnum() or c in "-_" for c in value):
        raise ValueError("invalid id")
    return value
