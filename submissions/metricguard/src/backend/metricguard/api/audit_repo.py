"""Read/write access to METRICGUARD.QUERY_AUDIT_LOG.

Stage 2: the API reads and writes this table through the least-privilege audit account
(DB2_AUDIT_USER: INSERT + SELECT on this table only). All values travel as parameter markers.
"""

from __future__ import annotations

import json
from typing import Any

from metricguard.db import Db2Client

S = "METRICGUARD"

_SUMMARY_COLS = (
    "REQUEST_ID, CREATED_AT, QUESTION, STATUS, METRIC_REFS, RESULT_ROW_COUNT, TOTAL_MS, PLANNER, EXECUTION_MODE"
)
_DETAIL_COLS = (
    "REQUEST_ID, CREATED_AT, API_VERSION, QUESTION, STATUS, STATUS_REASON, PLANNER, METRIC_REFS, PLAN_JSON, "
    "SQL_TEXT, SQL_PARAMS_JSON, SQL_HASH, VERIFICATION_JSON, RESULT_PREVIEW_JSON, RESULT_ROW_COUNT, TOTAL_MS, "
    "PLANNING_MS, VALIDATION_MS, EXECUTION_MS, VERIFICATION_MS, ERROR_CODE, ERROR_MESSAGE, EXECUTION_MODE, "
    "PLANNER_MODEL, METRIC_DEFS_JSON, ANSWER_SUMMARY"
)


def _refs(value: str | None) -> list[str]:
    return [r for r in (value or "").split(",") if r]


def _loads(value: Any) -> Any:
    return json.loads(value) if value else None


def insert(db: Db2Client, record: dict[str, Any]) -> None:
    cols = [
        "REQUEST_ID", "QUESTION", "STATUS", "STATUS_REASON", "METRIC_REFS", "PLANNER", "PLAN_JSON", "SQL_TEXT",
        "SQL_PARAMS_JSON", "SQL_HASH", "VERIFICATION_JSON", "RESULT_ROW_COUNT", "RESULT_PREVIEW_JSON", "TOTAL_MS",
        "PLANNING_MS", "VALIDATION_MS", "EXECUTION_MS", "VERIFICATION_MS", "ERROR_CODE", "ERROR_MESSAGE",
        "API_VERSION", "EXECUTION_MODE", "PLANNER_MODEL", "METRIC_DEFS_JSON", "ANSWER_SUMMARY",
    ]
    if record.get("created_at"):
        cols.append("CREATED_AT")
    values = [record.get(c.lower()) for c in cols]
    marks = ", ".join("?" for _ in cols)
    db.execute(f"INSERT INTO {S}.QUERY_AUDIT_LOG ({', '.join(cols)}) VALUES ({marks})", values)


def list_summaries(db: Db2Client, *, limit: int, offset: int, status: str | None) -> tuple[list[dict], int]:
    where, params = ("WHERE STATUS = ?", [status]) if status else ("", [])
    total = db.scalar(f"SELECT COUNT(*) FROM {S}.QUERY_AUDIT_LOG {where}", params)
    res = db.query(
        f"SELECT {_SUMMARY_COLS} FROM {S}.QUERY_AUDIT_LOG {where} ORDER BY CREATED_AT DESC, REQUEST_ID "
        f"OFFSET {int(offset)} ROWS FETCH FIRST {int(limit)} ROWS ONLY",
        params,
    )
    items = [
        {
            "request_id": r[0].strip(), "created_at": r[1], "question": r[2], "status": r[3],
            "metric_refs": _refs(r[4]), "row_count": r[5], "total_ms": r[6], "planner": r[7],
            "execution_mode": r[8],
        }
        for r in res.rows
    ]
    return items, int(total or 0)


def get_detail(db: Db2Client, request_id: str) -> dict[str, Any] | None:
    res = db.query(f"SELECT {_DETAIL_COLS} FROM {S}.QUERY_AUDIT_LOG WHERE REQUEST_ID = ?", (request_id,))
    if not res.rows:
        return None
    r = dict(zip([c.strip() for c in _DETAIL_COLS.split(",")], res.rows[0]))
    sql = None
    if r["SQL_TEXT"]:
        sql = {"text": r["SQL_TEXT"], "parameters": _loads(r["SQL_PARAMS_JSON"]) or [], "sql_hash": (r["SQL_HASH"] or "").strip()}
    error = None
    if r["ERROR_CODE"]:
        error = {"code": r["ERROR_CODE"], "message": r["ERROR_MESSAGE"] or ""}
    return {
        "request_id": r["REQUEST_ID"].strip(), "created_at": r["CREATED_AT"], "api_version": r["API_VERSION"],
        "question": r["QUESTION"], "status": r["STATUS"], "status_reason": r["STATUS_REASON"],
        "planner": r["PLANNER"], "metric_refs": _refs(r["METRIC_REFS"]), "plan": _loads(r["PLAN_JSON"]),
        "sql": sql, "verification": _loads(r["VERIFICATION_JSON"]), "result_preview": _loads(r["RESULT_PREVIEW_JSON"]),
        "row_count": r["RESULT_ROW_COUNT"],
        "timing": {"total_ms": r["TOTAL_MS"], "planning_ms": r["PLANNING_MS"], "validation_ms": r["VALIDATION_MS"],
                   "execution_ms": r["EXECUTION_MS"], "verification_ms": r["VERIFICATION_MS"]},
        "error": error,
        "execution_mode": r["EXECUTION_MODE"], "planner_model": r["PLANNER_MODEL"],
        "metric_definitions": _loads(r["METRIC_DEFS_JSON"]) or [], "answer_summary": r["ANSWER_SUMMARY"],
    }
