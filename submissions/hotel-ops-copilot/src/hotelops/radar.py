"""Complaint radar: classify every recent complaint sentence into themes, inside Db2.

One SQL statement:
  1. builds a small in-query table of theme "anchor" vectors (VALUES + VECTOR(?, 384, FLOAT32)),
  2. computes VECTOR_DISTANCE between every review sentence and every anchor (CROSS JOIN),
  3. assigns each sentence to its nearest theme if it is close enough (ROW_NUMBER() OVER),
  4. aggregates by theme, floor and room in one pass with GROUP BY GROUPING SETS.

No keywords, no extra model: the agents (and the dashboard) see every complaint theme at
once, and whether it is LOCALISED (one room: probably equipment) or SYSTEMIC (a process issue).
The 0.32 cosine cut-off was calibrated on the data: complaint sentences sit at 0.10-0.29 from
their theme anchor, the closest unrelated (positive) sentences at 0.33+.
"""
from __future__ import annotations

from functools import lru_cache

from .db import Db2, vector_literal

THEME_ANCHORS = {
    "Air conditioning": "The air conditioning in the room was noisy or not working properly.",
    "Hot water / shower": "The shower had no hot water.",
    "Wi-Fi / internet": "The Wi-Fi internet connection was slow and unreliable.",
    "Check-in / arrival": "Check-in at reception was slow and we had to wait a long time.",
    "Outside noise": "Noise from traffic outside kept us awake at night.",
    "Value for money": "The room was too expensive and not good value for money.",
    "Housekeeping": "The room was not cleaned on time and towels were not changed.",
    "Breakfast / food": "The breakfast and restaurant food were disappointing.",
    "Staff attitude": "The staff were rude and unhelpful.",
}
MAX_DISTANCE = 0.32
LOCALISED_SHARE = 0.6  # 1-2 rooms hold >= 60% of a theme's reviews -> treat as an equipment fault


@lru_cache(maxsize=1)
def _anchor_params() -> tuple:
    from .embeddings import embed_documents

    vectors = embed_documents(list(THEME_ANCHORS.values()))
    return tuple(x for name, v in zip(THEME_ANCHORS, vectors, strict=True) for x in (name, vector_literal(v)))


def _sql() -> str:
    values = ", ".join(["(CAST(? AS VARCHAR(40)), VECTOR(?, 384, FLOAT32))"] * len(THEME_ANCHORS))
    return f"""
WITH T (THEME, TV) AS (VALUES {values}),
     C AS (SELECT C.CHUNK_ID, C.REVIEW_ID, T.THEME,
                  VECTOR_DISTANCE(C.EMBEDDING, T.TV, COSINE) AS D
             FROM REVIEW_CHUNKS C
             JOIN GUEST_REVIEWS R ON R.REVIEW_ID = C.REVIEW_ID
            CROSS JOIN T
            WHERE R.CREATED_AT >= CURRENT DATE - ? DAYS AND R.RATING <= ?),
     B AS (SELECT C.*, ROW_NUMBER() OVER (PARTITION BY C.CHUNK_ID ORDER BY C.D) AS RN FROM C),
     M AS (SELECT DISTINCT B.REVIEW_ID, B.THEME FROM B WHERE B.RN = 1 AND B.D <= ?)
SELECT M.THEME, RM.FLOOR_NO, R.ROOM_NO, COUNT(*) AS REVIEWS,
       DECIMAL(AVG(R.RATING * 1.0), 3, 2) AS AVG_RATING, MAX(R.CREATED_AT) AS LATEST,
       GROUPING(RM.FLOOR_NO) AS G_FLOOR, GROUPING(R.ROOM_NO) AS G_ROOM
  FROM M
  JOIN GUEST_REVIEWS R ON R.REVIEW_ID = M.REVIEW_ID
  LEFT JOIN ROOMS RM ON RM.ROOM_NO = R.ROOM_NO
 GROUP BY GROUPING SETS ((M.THEME), (M.THEME, RM.FLOOR_NO), (M.THEME, RM.FLOOR_NO, R.ROOM_NO))"""


def complaint_radar(db: Db2, days: int = 30, max_rating: int = 3) -> dict:
    """Every complaint theme in the window with its volume, floors, top rooms and a LOCALISED/SYSTEMIC call."""
    rows = db.query(_sql(), (*_anchor_params(), max(1, int(days)), int(max_rating), MAX_DISTANCE))
    themes: dict[str, dict] = {}
    for r in rows:
        if r["G_FLOOR"] == 1:  # theme total
            themes.setdefault(r["THEME"], {})["total"] = r
    out = []
    for name, info in themes.items():
        total = info["total"]["REVIEWS"]
        floors = sorted(({"FLOOR_NO": r["FLOOR_NO"], "REVIEWS": r["REVIEWS"]} for r in rows
                         if r["THEME"] == name and r["G_FLOOR"] == 0 and r["G_ROOM"] == 1),
                        key=lambda f: -f["REVIEWS"])
        rooms = sorted(({"ROOM_NO": r["ROOM_NO"], "REVIEWS": r["REVIEWS"], "AVG_RATING": r["AVG_RATING"]}
                        for r in rows if r["THEME"] == name and r["G_ROOM"] == 0),
                       key=lambda x: (-x["REVIEWS"], x["ROOM_NO"]))
        hot = [r for r in rooms[:3] if r["REVIEWS"] >= 2]  # rooms with repeated complaints
        localised = bool(hot) and sum(r["REVIEWS"] for r in hot) / total >= LOCALISED_SHARE and len(hot) <= 2
        room_list = ", ".join(f"{r['ROOM_NO']} ({r['REVIEWS']})" for r in hot)
        out.append({
            "THEME": name, "REVIEWS": total, "AVG_RATING": info["total"]["AVG_RATING"],
            "LATEST": info["total"]["LATEST"],
            "PATTERN": "LOCALISED" if localised else "SYSTEMIC",
            "HINT": (f"{sum(r['REVIEWS'] for r in hot)} of {total} in room(s) {room_list}: inspect those rooms"
                     if localised else "spread across rooms/floors: a process or property-wide issue"),
            "TOP_ROOMS": rooms[:3], "FLOORS": floors,
        })
    out.sort(key=lambda t: -t["REVIEWS"])
    silent = [t for t in THEME_ANCHORS if t not in themes]
    return {"window_days": int(days), "max_rating": int(max_rating), "themes": out, "no_complaints_about": silent}
