"""Change feed built on Db2 system-period temporal tables.

"What changed since yesterday?" is answered by pairing each row version that
started inside the window with the version it replaced. The previous version
is the one whose SYS_END equals the new version's SYS_START, because Db2 closes
the old row and opens the new one with the same transaction timestamp. No
triggers or audit tables are needed: Db2 keeps the history itself.
"""
from __future__ import annotations

from .db import Db2

ALL_TIME = "FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30'"

RATE_CHANGES = f"""
SELECT RT.CODE AS ROOM_TYPE, V.UPDATED_BY, V.CHANGE_REASON, V.SOURCE_ACTION_ID,
       MIN(V.STAY_DATE) AS FIRST_NIGHT, MAX(V.STAY_DATE) AS LAST_NIGHT, COUNT(*) AS NIGHTS,
       DECIMAL(AVG(P.RATE), 10, 0) AS AVG_RATE_BEFORE, DECIMAL(AVG(V.RATE), 10, 0) AS AVG_RATE_AFTER,
       MIN(V.SYS_START) AS CHANGED_AT
  FROM RATE_PLAN {ALL_TIME} V
  JOIN RATE_PLAN {ALL_TIME} P
    ON P.ROOM_TYPE_ID = V.ROOM_TYPE_ID AND P.STAY_DATE = V.STAY_DATE AND P.SYS_END = V.SYS_START
  JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = V.ROOM_TYPE_ID
 WHERE V.SYS_START >= CURRENT TIMESTAMP - ? HOURS
 GROUP BY RT.CODE, RT.TIER, V.UPDATED_BY, V.CHANGE_REASON, V.SOURCE_ACTION_ID, V.SYS_START
 ORDER BY CHANGED_AT DESC, RT.TIER
 FETCH FIRST 50 ROWS ONLY"""

RESERVATION_CHANGES = f"""
SELECT V.RESERVATION_ID, P.STATUS AS STATUS_BEFORE, V.STATUS AS STATUS_AFTER,
       PT.CODE AS ROOM_TYPE_BEFORE, VT.CODE AS ROOM_TYPE_AFTER,
       P.ROOM_NO AS ROOM_BEFORE, V.ROOM_NO AS ROOM_AFTER, V.SYS_START AS CHANGED_AT
  FROM RESERVATIONS {ALL_TIME} V
  JOIN RESERVATIONS {ALL_TIME} P ON P.RESERVATION_ID = V.RESERVATION_ID AND P.SYS_END = V.SYS_START
  JOIN ROOM_TYPES PT ON PT.ROOM_TYPE_ID = P.ROOM_TYPE_ID
  JOIN ROOM_TYPES VT ON VT.ROOM_TYPE_ID = V.ROOM_TYPE_ID
 WHERE V.SYS_START >= CURRENT TIMESTAMP - ? HOURS
 ORDER BY V.SYS_START DESC
 FETCH FIRST 30 ROWS ONLY"""

ROOM_CHANGES = f"""
SELECT V.ROOM_NO, P.STATUS AS STATUS_BEFORE, V.STATUS AS STATUS_AFTER, V.SYS_START AS CHANGED_AT
  FROM ROOMS {ALL_TIME} V
  JOIN ROOMS {ALL_TIME} P ON P.ROOM_NO = V.ROOM_NO AND P.SYS_END = V.SYS_START
 WHERE V.SYS_START >= CURRENT TIMESTAMP - ? HOURS
 ORDER BY V.SYS_START DESC
 FETCH FIRST 30 ROWS ONLY"""

NEW_BOOKINGS = """
SELECT RT.CODE AS ROOM_TYPE, COUNT(*) AS NEW_BOOKINGS, DECIMAL(SUM(X.TOTAL_AMOUNT), 12, 0) AS VALUE_INR
  FROM RESERVATIONS X JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = X.ROOM_TYPE_ID
 WHERE X.BOOKED_AT >= CURRENT TIMESTAMP - ? HOURS
 GROUP BY RT.CODE, RT.TIER ORDER BY RT.TIER"""


def change_feed(db: Db2, hours: int = 24) -> dict:
    """Return everything that changed in the last ``hours`` hours, reconstructed from Db2 history."""
    hours = max(1, min(int(hours), 24 * 30))
    return {
        "window_hours": hours,
        "rate_changes": db.query(RATE_CHANGES, (hours,)),
        "reservation_changes": db.query(RESERVATION_CHANGES, (hours,)),
        "room_status_changes": db.query(ROOM_CHANGES, (hours,)),
        "new_bookings_by_room_type": db.query(NEW_BOOKINGS, (hours,)),
    }
