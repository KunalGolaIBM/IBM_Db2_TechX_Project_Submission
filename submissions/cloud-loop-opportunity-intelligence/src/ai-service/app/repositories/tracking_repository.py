import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.database.session import db_session
from app.database.db2_connection import db2_manager
from app.repositories.opportunity_repository import opportunity_repo

logger = logging.getLogger("cloud_loop.repository.tracking")

class TrackingRepository:
    def get_user_tracking(self, user_id: str) -> List[Dict[str, Any]]:
        sql = """
            SELECT t.USER_ID, t.OPPORTUNITY_ID, t.STATUS, t.BOOKMARKED, t.UPDATED_AT
            FROM CLOUDLOOP.TRACKED_OPPORTUNITIES t
            WHERE t.USER_ID = ?
            ORDER BY t.UPDATED_AT DESC
        """
        rows = db_session.query(sql, [user_id])
        items = []
        for r in rows:
            opp_id = r.get("OPPORTUNITY_ID") or r.get("opportunity_id")
            opp = opportunity_repo.get_by_id(opp_id)
            items.append({
                "user_id": r.get("USER_ID") or r.get("user_id"),
                "opportunity_id": opp_id,
                "status": r.get("STATUS") or r.get("status") or "None",
                "bookmarked": bool(r.get("BOOKMARKED") or r.get("bookmarked")),
                "updated_at": str(r.get("UPDATED_AT") or r.get("updated_at") or ""),
                "opportunity": opp,
            })
        return items

    def set_tracking(self, user_id: str, opportunity_id: str, status: str, bookmarked: bool) -> bool:
        # Check if opportunity exists
        opp = opportunity_repo.get_by_id(opportunity_id)
        if not opp:
            logger.warning(f"Attempted to track non-existent opportunity {opportunity_id}")
            return False

        b_val = 1 if bookmarked else 0
        status_info = db2_manager.status

        if status_info["driver_available"] and status_info["configured"]:
            # Native Db2 MERGE upsert statement
            sql_merge = """
                MERGE INTO CLOUDLOOP.TRACKED_OPPORTUNITIES AS target
                USING (VALUES (?, ?, ?, ?)) AS source (USER_ID, OPPORTUNITY_ID, STATUS, BOOKMARKED)
                ON (target.USER_ID = source.USER_ID AND target.OPPORTUNITY_ID = source.OPPORTUNITY_ID)
                WHEN MATCHED THEN
                  UPDATE SET STATUS = source.STATUS, BOOKMARKED = source.BOOKMARKED, UPDATED_AT = CURRENT TIMESTAMP
                WHEN NOT MATCHED THEN
                  INSERT (USER_ID, OPPORTUNITY_ID, STATUS, BOOKMARKED, UPDATED_AT)
                  VALUES (source.USER_ID, source.OPPORTUNITY_ID, source.STATUS, source.BOOKMARKED, CURRENT TIMESTAMP)
            """
            try:
                db_session.execute(sql_merge, [user_id, opportunity_id, status, b_val])
                return True
            except Exception as e:
                logger.warning(f"Db2 MERGE failed, trying fallback: {e}")

        # Local SQLite / fallback upsert
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql_sqlite = """
            INSERT INTO TRACKED_OPPORTUNITIES (USER_ID, OPPORTUNITY_ID, STATUS, BOOKMARKED, UPDATED_AT)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(USER_ID, OPPORTUNITY_ID) DO UPDATE SET
                STATUS = excluded.STATUS,
                BOOKMARKED = excluded.BOOKMARKED,
                UPDATED_AT = excluded.UPDATED_AT
        """
        db_session.execute(sql_sqlite, [user_id, opportunity_id, status, b_val, now])
        return True

    def get_counts(self, user_id: str) -> Dict[str, int]:
        sql = """
            SELECT STATUS, COUNT(*) as CNT
            FROM CLOUDLOOP.TRACKED_OPPORTUNITIES
            WHERE USER_ID = ?
            GROUP BY STATUS
        """
        rows = db_session.query(sql, [user_id])
        counts = {"None": 0, "Saved": 0, "Applied": 0, "Interviewing": 0, "Accepted": 0, "Rejected": 0}
        for r in rows:
            st = r.get("STATUS") or r.get("status") or "None"
            cnt = int(r.get("CNT") or r.get("cnt") or 0)
            counts[st] = cnt
        return counts

tracking_repo = TrackingRepository()
