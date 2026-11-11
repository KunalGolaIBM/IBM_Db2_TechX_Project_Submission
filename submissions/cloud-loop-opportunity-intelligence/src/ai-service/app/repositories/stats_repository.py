import logging
from typing import Dict, Any
from app.database.session import db_session

logger = logging.getLogger("cloud_loop.repository.stats")

class StatsRepository:
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Retrieves SQL aggregates using CLOUDLOOP.V_ACTIVE_OPPORTUNITIES:
        1. Opportunity counts grouped by kind
        2. Count of opportunities closing within next 7 days
        3. Total active opportunities
        """
        # 1. Counts per kind
        sql_kinds = """
            SELECT KIND, COUNT(*) as CNT
            FROM CLOUDLOOP.V_ACTIVE_OPPORTUNITIES
            WHERE SOURCE != 'synthetic-demo'
            GROUP BY KIND
        """
        kind_rows = db_session.query(sql_kinds)
        counts_per_kind = {
            "job": 0,
            "internship": 0,
            "event": 0,
            "program": 0,
            "certification": 0,
        }
        total_active = 0
        for r in kind_rows:
            k = (r.get("KIND") or r.get("kind") or "").lower()
            cnt = int(r.get("CNT") or r.get("cnt") or 0)
            if k in counts_per_kind:
                counts_per_kind[k] = cnt
            total_active += cnt

        # 2. Closing within 7 days
        sql_closing = """
            SELECT COUNT(*) as CNT
            FROM CLOUDLOOP.V_ACTIVE_OPPORTUNITIES
            WHERE SOURCE != 'synthetic-demo'
              AND DEADLINE IS NOT NULL
              AND DEADLINE >= CURRENT DATE
              AND DEADLINE <= (CURRENT DATE + 7 DAYS)
        """
        closing_rows = db_session.query(sql_closing)
        closing_soon = int(closing_rows[0].get("CNT") or closing_rows[0].get("cnt") or 0) if closing_rows else 0

        return {
            "counts_per_kind": counts_per_kind,
            "closing_within_7_days": closing_soon,
            "total_active": total_active,
        }

stats_repo = StatsRepository()
