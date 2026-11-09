import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.database.session import db_session
from backend.app.repositories.opportunity_repository import opportunity_repo

logger = logging.getLogger("cloud_loop.repository.tracking")

class TrackingRepository:
    def get_user_tracking(self, user_id: str) -> List[Dict[str, Any]]:
        sql = """
            SELECT t.*, o.TITLE, o.ORGANIZATION, o.OPPORTUNITY_TYPE, o.CATEGORY,
                   o.APPLICATION_URL, o.DEADLINE, o.LOCATION
            FROM USER_OPPORTUNITY_TRACKING t
            LEFT JOIN OPPORTUNITIES o ON t.OPPORTUNITY_ID = o.ID
            WHERE t.USER_ID = ?
            ORDER BY t.UPDATED_AT DESC
        """
        rows = db_session.query(sql, [user_id])
        items = []
        for r in rows:
            opp = opportunity_repo.get_by_id(r.get("OPPORTUNITY_ID") or r.get("opportunity_id"))
            items.append({
                "user_id": r.get("USER_ID") or r.get("user_id"),
                "opportunity_id": r.get("OPPORTUNITY_ID") or r.get("opportunity_id"),
                "application_status": r.get("APPLICATION_STATUS") or r.get("application_status") or "saved",
                "bookmarked": bool(r.get("BOOKMARKED") or r.get("bookmarked")),
                "updated_at": r.get("UPDATED_AT") or r.get("updated_at"),
                "opportunity": opp,
            })
        return items

    def set_tracking(self, user_id: str, opportunity_id: str, status: str, bookmarked: bool) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        # Ensure opportunity exists
        opp = opportunity_repo.get_by_id(opportunity_id)
        if not opp:
            logger.warning(f"Attempted to track non-existent opportunity {opportunity_id}")
            return False

        # SQLite/Db2 upsert pattern
        sql_check = "SELECT 1 FROM USER_OPPORTUNITY_TRACKING WHERE USER_ID = ? AND OPPORTUNITY_ID = ?"
        exists = db_session.query(sql_check, [user_id, opportunity_id])

        if exists:
            sql_update = """
                UPDATE USER_OPPORTUNITY_TRACKING SET
                    APPLICATION_STATUS = ?,
                    BOOKMARKED = ?,
                    UPDATED_AT = ?
                WHERE USER_ID = ? AND OPPORTUNITY_ID = ?
            """
            db_session.execute(sql_update, [status, 1 if bookmarked else 0, now, user_id, opportunity_id])
        else:
            sql_insert = """
                INSERT INTO USER_OPPORTUNITY_TRACKING (
                    USER_ID, OPPORTUNITY_ID, APPLICATION_STATUS, BOOKMARKED, UPDATED_AT
                ) VALUES (?, ?, ?, ?, ?)
            """
            db_session.execute(sql_insert, [user_id, opportunity_id, status, 1 if bookmarked else 0, now])

        return True

    def get_counts(self, user_id: str) -> Dict[str, int]:
        sql = """
            SELECT APPLICATION_STATUS, COUNT(*) as cnt
            FROM USER_OPPORTUNITY_TRACKING
            WHERE USER_ID = ?
            GROUP BY APPLICATION_STATUS
        """
        rows = db_session.query(sql, [user_id])
        counts = {"saved": 0, "applied": 0, "under_review": 0, "not_interested": 0}
        for r in rows:
            st = (r.get("APPLICATION_STATUS") or r.get("application_status") or "").lower()
            cnt = r.get("CNT") or r.get("cnt") or 0
            if st in counts:
                counts[st] = cnt
        return counts

tracking_repo = TrackingRepository()

