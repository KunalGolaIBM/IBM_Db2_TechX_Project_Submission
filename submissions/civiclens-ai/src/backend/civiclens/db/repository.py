"""Data-access functions for CivicLens. Every query is static SQL with bound parameters.

Optional filters are composed only from fixed SQL fragments defined in this module;
user- or model-supplied values are always passed as parameters, never as SQL text.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from civiclens.db.connection import Db2Session
from civiclens.domain import geo, text
from civiclens.domain.models import (
    Category,
    Complaint,
    ComplaintCreate,
    ComplaintStatus,
    DuplicateCandidate,
    Hotspot,
)

MAX_LIST_LIMIT = 200
MAX_HOTSPOT_LIMIT = 100

_COMPLAINT_COLUMNS = (
    "COMPLAINT_ID, EXTERNAL_REF, CATEGORY, TITLE, DESCRIPTION, LATITUDE, LONGITUDE, "
    "GEO_CELL, WARD, SEVERITY, STATUS, SOURCE, DUPLICATE_OF, IS_SYNTHETIC, "
    "REPORTED_AT, CREATED_AT"
)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ts(value: datetime) -> str:
    """Format a naive-UTC datetime for CAST(? AS TIMESTAMP)."""
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


def _num(value: Any) -> float:
    return float(Decimal(str(value))) if value is not None else 0.0


def _row_to_complaint(row: dict[str, Any]) -> Complaint:
    return Complaint(
        complaint_id=int(row["complaint_id"]),
        external_ref=row["external_ref"],
        category=Category(row["category"]),
        title=row["title"],
        description=row["description"],
        latitude=_num(row["latitude"]),
        longitude=_num(row["longitude"]),
        geo_cell=row["geo_cell"],
        ward=row["ward"],
        severity=int(row["severity"]),
        status=ComplaintStatus(row["status"]),
        source=row["source"],
        duplicate_of=int(row["duplicate_of"]) if row["duplicate_of"] is not None else None,
        is_synthetic=bool(row["is_synthetic"]),
        reported_at=row["reported_at"],
        created_at=row["created_at"],
    )


# --------------------------------------------------------------------------- complaints
def insert_complaint(db: Db2Session, data: ComplaintCreate) -> int:
    reported_at = data.reported_at or utcnow()
    row = db.fetch_one(
        """
        SELECT COMPLAINT_ID FROM FINAL TABLE (
            INSERT INTO {schema}.COMPLAINTS
                (EXTERNAL_REF, CATEGORY, TITLE, DESCRIPTION, LATITUDE, LONGITUDE, GEO_CELL,
                 WARD, SEVERITY, SOURCE, TEXT_FINGERPRINT, IS_SYNTHETIC, REPORTED_AT)
            VALUES (?, ?, ?, ?, CAST(? AS DECIMAL(9,6)), CAST(? AS DECIMAL(9,6)), ?,
                    ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP))
        )
        """,
        (
            data.external_ref,
            data.category.value,
            data.title,
            data.description,
            f"{data.latitude:.6f}",
            f"{data.longitude:.6f}",
            geo.geo_cell(data.latitude, data.longitude),
            data.ward,
            data.severity,
            data.source,
            text.fingerprint(data.category.value, data.title, data.description),
            1 if data.is_synthetic else 0,
            _ts(reported_at),
        ),
    )
    if row is None:  # pragma: no cover - FINAL TABLE always returns the new row
        raise RuntimeError("Insert did not return a COMPLAINT_ID")
    return int(row["complaint_id"])


def get_complaint(db: Db2Session, complaint_id: int) -> Complaint | None:
    row = db.fetch_one(
        f"SELECT {_COMPLAINT_COLUMNS} FROM {{schema}}.COMPLAINTS WHERE COMPLAINT_ID = ?",
        (complaint_id,),
    )
    return _row_to_complaint(row) if row else None


def list_complaints(
    db: Db2Session,
    *,
    category: Category | None = None,
    status: ComplaintStatus | None = None,
    ward: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    synthetic: bool | None = None,
    geo_cell: str | None = None,
    limit: int = 50,
) -> list[Complaint]:
    clauses: list[str] = []
    params: list[Any] = []
    if category is not None:
        clauses.append("CATEGORY = ?")
        params.append(category.value)
    if status is not None:
        clauses.append("STATUS = ?")
        params.append(status.value)
    if ward:
        clauses.append("WARD = ?")
        params.append(ward)
    if since is not None:
        clauses.append("REPORTED_AT >= CAST(? AS TIMESTAMP)")
        params.append(_ts(since))
    if until is not None:
        clauses.append("REPORTED_AT < CAST(? AS TIMESTAMP)")
        params.append(_ts(until))
    if geo_cell:
        clauses.append("GEO_CELL = ?")
        params.append(geo_cell)
    if synthetic is not None:
        clauses.append("IS_SYNTHETIC = ?")
        params.append(1 if synthetic else 0)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = max(1, min(int(limit), MAX_LIST_LIMIT))  # int literal, bounded
    rows = db.fetch_all(
        f"SELECT {_COMPLAINT_COLUMNS} FROM {{schema}}.COMPLAINTS {where} "
        f"ORDER BY REPORTED_AT DESC, COMPLAINT_ID DESC FETCH FIRST {limit} ROWS ONLY",
        params,
    )
    return [_row_to_complaint(r) for r in rows]


def find_duplicate_candidates(
    db: Db2Session,
    *,
    category: Category,
    title: str,
    description: str,
    latitude: float,
    longitude: float,
    reported_at: datetime | None = None,
    radius_m: float = 250.0,
    window_days: int = 14,
    exclude_id: int | None = None,
    min_score: float = 0.35,
    limit: int = 5,
) -> list[DuplicateCandidate]:
    """Spatial + temporal candidates computed in Db2, re-ranked by text similarity.

    Db2 does the heavy lifting: an index-friendly bounding box, then an exact
    great-circle (haversine) distance computed in SQL.
    """
    reported_at = reported_at or utcnow()
    min_lat, max_lat, min_lon, max_lon = geo.bounding_box(latitude, longitude, radius_m)
    window = timedelta(days=window_days)
    rows = db.fetch_all(
        """
        WITH NEARBY AS (
            SELECT COMPLAINT_ID, TITLE, DESCRIPTION, TEXT_FINGERPRINT,
                   2 * 6371000 * ASIN(SQRT(
                       POWER(SIN(RADIANS(CAST(LATITUDE AS DOUBLE) - CAST(? AS DOUBLE)) / 2), 2)
                     + COS(RADIANS(CAST(? AS DOUBLE))) * COS(RADIANS(CAST(LATITUDE AS DOUBLE)))
                     * POWER(SIN(RADIANS(CAST(LONGITUDE AS DOUBLE) - CAST(? AS DOUBLE)) / 2), 2)
                   )) AS DISTANCE_M
            FROM {schema}.COMPLAINTS
            WHERE CATEGORY = ?
              AND STATUS <> 'DUPLICATE'
              AND LATITUDE  BETWEEN CAST(? AS DECIMAL(9,6)) AND CAST(? AS DECIMAL(9,6))
              AND LONGITUDE BETWEEN CAST(? AS DECIMAL(9,6)) AND CAST(? AS DECIMAL(9,6))
              AND REPORTED_AT BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)
              AND COMPLAINT_ID <> ?
        )
        SELECT COMPLAINT_ID, TITLE, DESCRIPTION, TEXT_FINGERPRINT, DISTANCE_M
        FROM NEARBY WHERE DISTANCE_M <= CAST(? AS DOUBLE)
        ORDER BY DISTANCE_M FETCH FIRST 50 ROWS ONLY
        """,
        (
            f"{latitude:.6f}",
            f"{latitude:.6f}",
            f"{longitude:.6f}",
            category.value,
            f"{min_lat:.6f}",
            f"{max_lat:.6f}",
            f"{min_lon:.6f}",
            f"{max_lon:.6f}",
            _ts(reported_at - window),
            _ts(reported_at + window),
            exclude_id if exclude_id is not None else -1,
            str(radius_m),
        ),
    )
    query_fp = text.fingerprint(category.value, title, description)
    query_text = f"{title} {description}"
    candidates: list[DuplicateCandidate] = []
    for r in rows:
        sim = (
            1.0
            if r["text_fingerprint"] == query_fp
            else text.jaccard(query_text, f"{r['title']} {r['description']}")
        )
        distance = _num(r["distance_m"])
        score = text.duplicate_score(distance, radius_m, sim)
        if score >= min_score:
            candidates.append(
                DuplicateCandidate(
                    complaint_id=int(r["complaint_id"]),
                    title=r["title"],
                    distance_m=round(distance, 1),
                    text_similarity=round(sim, 4),
                    score=score,
                )
            )
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[: max(1, min(limit, 20))]


def hotspots(
    db: Db2Session,
    *,
    since: datetime,
    until: datetime | None = None,
    category: Category | None = None,
    min_count: int = 3,
    limit: int = 20,
) -> list[Hotspot]:
    """Geo-cell x category aggregation over a time window, computed in Db2."""
    until = until or utcnow()
    params: list[Any] = [_ts(since), _ts(until)]
    category_clause = ""
    if category is not None:
        category_clause = "AND CATEGORY = ?"
        params.append(category.value)
    params.append(max(1, int(min_count)))
    limit = max(1, min(int(limit), MAX_HOTSPOT_LIMIT))
    rows = db.fetch_all(
        f"""
        SELECT GEO_CELL, CATEGORY,
               COUNT(*) AS COMPLAINT_COUNT,
               AVG(CAST(SEVERITY AS DOUBLE)) AS AVG_SEVERITY,
               AVG(CAST(LATITUDE AS DOUBLE)) AS CENTER_LATITUDE,
               AVG(CAST(LONGITUDE AS DOUBLE)) AS CENTER_LONGITUDE,
               MIN(REPORTED_AT) AS FIRST_REPORTED_AT,
               MAX(REPORTED_AT) AS LAST_REPORTED_AT
        FROM {{schema}}.COMPLAINTS
        WHERE REPORTED_AT >= CAST(? AS TIMESTAMP)
          AND REPORTED_AT <  CAST(? AS TIMESTAMP)
          AND STATUS <> 'DUPLICATE'
          {category_clause}
        GROUP BY GEO_CELL, CATEGORY
        HAVING COUNT(*) >= ?
        ORDER BY COMPLAINT_COUNT DESC, AVG_SEVERITY DESC
        FETCH FIRST {limit} ROWS ONLY
        """,
        params,
    )
    return [
        Hotspot(
            geo_cell=r["geo_cell"],
            category=Category(r["category"]),
            complaint_count=int(r["complaint_count"]),
            avg_severity=round(_num(r["avg_severity"]), 2),
            center_latitude=round(_num(r["center_latitude"]), 6),
            center_longitude=round(_num(r["center_longitude"]), 6),
            first_reported_at=r["first_reported_at"],
            last_reported_at=r["last_reported_at"],
        )
        for r in rows
    ]


# --------------------------------------------------------------------------- investigations & audit
def create_investigation(db: Db2Session, *, title: str, question: str, created_by: str) -> int:
    row = db.fetch_one(
        """
        SELECT INVESTIGATION_ID FROM FINAL TABLE (
            INSERT INTO {schema}.INVESTIGATIONS (TITLE, QUESTION, CREATED_BY) VALUES (?, ?, ?)
        )
        """,
        (title[:200], question[:2000], created_by[:64]),
    )
    assert row is not None
    return int(row["investigation_id"])


def write_audit(
    db: Db2Session,
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    investigation_id: int | None = None,
    tool_name: str | None = None,
    input_payload: dict[str, Any] | None = None,
    output_summary: str | None = None,
    success: bool = True,
) -> int:
    row = db.fetch_one(
        """
        SELECT AUDIT_ID FROM FINAL TABLE (
            INSERT INTO {schema}.AUDIT_LOG
                (INVESTIGATION_ID, ACTOR_TYPE, ACTOR_ID, ACTION, TOOL_NAME,
                 INPUT_JSON, OUTPUT_SUMMARY, SUCCESS)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        )
        """,
        (
            investigation_id,
            actor_type,
            actor_id[:64],
            action[:64],
            tool_name,
            json.dumps(input_payload, default=str)[:4000] if input_payload is not None else None,
            output_summary[:4000] if output_summary else None,
            1 if success else 0,
        ),
    )
    assert row is not None
    return int(row["audit_id"])


def list_audit(db: Db2Session, *, investigation_id: int, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    return db.fetch_all(
        "SELECT AUDIT_ID, ACTOR_TYPE, ACTOR_ID, ACTION, TOOL_NAME, INPUT_JSON, OUTPUT_SUMMARY, "
        "SUCCESS, CREATED_AT FROM {schema}.AUDIT_LOG WHERE INVESTIGATION_ID = ? "
        f"ORDER BY AUDIT_ID FETCH FIRST {limit} ROWS ONLY",
        (investigation_id,),
    )
