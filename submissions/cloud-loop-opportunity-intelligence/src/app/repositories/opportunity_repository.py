import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from backend.app.database.session import db_session

logger = logging.getLogger("cloud_loop.repository.opportunity")

class OpportunityRepository:
    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(row)
        # Parse skills if stringified JSON
        skills_raw = d.get("SKILLS") or d.get("skills")
        if isinstance(skills_raw, str):
            try:
                d["skills"] = json.loads(skills_raw)
            except Exception:
                d["skills"] = [s.strip() for s in skills_raw.split(",") if s.strip()]
        elif not skills_raw:
            d["skills"] = []
        else:
            d["skills"] = list(skills_raw)

        # Normalize key casing
        return {
            "id": d.get("ID") or d.get("id"),
            "slug": d.get("SLUG") or d.get("slug"),
            "title": d.get("TITLE") or d.get("title"),
            "organization": d.get("ORGANIZATION") or d.get("organization"),
            "opportunity_type": d.get("OPPORTUNITY_TYPE") or d.get("opportunity_type"),
            "category": d.get("CATEGORY") or d.get("category"),
            "description": d.get("DESCRIPTION") or d.get("description"),
            "location": d.get("LOCATION") or d.get("location"),
            "location_type": d.get("LOCATION_TYPE") or d.get("location_type"),
            "skills": d["skills"],
            "eligibility": d.get("ELIGIBILITY") or d.get("eligibility"),
            "deadline": d.get("DEADLINE") or d.get("deadline"),
            "application_url": d.get("APPLICATION_URL") or d.get("application_url"),
            "source_name": d.get("SOURCE_NAME") or d.get("source_name"),
            "source_url": d.get("SOURCE_URL") or d.get("source_url"),
            "verification_status": d.get("VERIFICATION_STATUS") or d.get("verification_status") or "verified",
            "fetched_at": d.get("FETCHED_AT") or d.get("fetched_at"),
            "created_at": d.get("CREATED_AT") or d.get("created_at"),
            "updated_at": d.get("UPDATED_AT") or d.get("updated_at"),
        }

    def get_by_id(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM OPPORTUNITIES WHERE ID = ?"
        rows = db_session.query(sql, [opportunity_id])
        return self._row_to_dict(rows[0]) if rows else None

    def get_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM OPPORTUNITIES WHERE SLUG = ?"
        rows = db_session.query(sql, [slug])
        return self._row_to_dict(rows[0]) if rows else None

    def list_opportunities(
        self,
        opp_type: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> (List[Dict[str, Any]], int):
        where_clauses = []
        params = []

        if opp_type and opp_type.lower() != "all":
            where_clauses.append("LOWER(OPPORTUNITY_TYPE) = LOWER(?)")
            params.append(opp_type)

        if category and category.lower() != "all":
            where_clauses.append("LOWER(CATEGORY) = LOWER(?)")
            params.append(category)

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            where_clauses.append("(LOWER(TITLE) LIKE ? OR LOWER(ORGANIZATION) LIKE ? OR LOWER(DESCRIPTION) LIKE ?)")
            params.extend([term, term, term])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Total count query
        count_sql = f"SELECT COUNT(*) as cnt FROM OPPORTUNITIES {where_sql}"
        count_rows = db_session.query(count_sql, params)
        total = count_rows[0].get("CNT") or count_rows[0].get("cnt") or 0

        # Paginated fetch
        offset = (page - 1) * limit
        fetch_sql = f"""
            SELECT * FROM OPPORTUNITIES
            {where_sql}
            ORDER BY ROWID DESC
            LIMIT ? OFFSET ?
        """
        rows = db_session.query(fetch_sql, params + [limit, offset])
        items = [self._row_to_dict(r) for r in rows]
        return items, total

    def upsert(self, data: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc).isoformat()
        skills_str = json.dumps(data.get("skills") or [])
        opp_id = data.get("id") or data.get("slug")

        # Check existing
        existing = self.get_by_id(opp_id)
        if existing:
            sql = """
                UPDATE OPPORTUNITIES SET
                    TITLE = ?,
                    ORGANIZATION = ?,
                    OPPORTUNITY_TYPE = ?,
                    CATEGORY = ?,
                    DESCRIPTION = ?,
                    LOCATION = ?,
                    LOCATION_TYPE = ?,
                    SKILLS = ?,
                    ELIGIBILITY = ?,
                    DEADLINE = ?,
                    APPLICATION_URL = ?,
                    SOURCE_NAME = ?,
                    SOURCE_URL = ?,
                    VERIFICATION_STATUS = ?,
                    UPDATED_AT = ?
                WHERE ID = ?
            """
            params = [
                data.get("title"),
                data.get("organization"),
                data.get("opportunity_type"),
                data.get("category"),
                data.get("description"),
                data.get("location"),
                data.get("location_type"),
                skills_str,
                data.get("eligibility"),
                data.get("deadline"),
                data.get("application_url"),
                data.get("source_name") or "CloudLoop Indexer",
                data.get("source_url"),
                data.get("verification_status") or "verified",
                now,
                opp_id,
            ]
            db_session.execute(sql, params)
            return opp_id
        else:
            sql = """
                INSERT INTO OPPORTUNITIES (
                    ID, SLUG, TITLE, ORGANIZATION, OPPORTUNITY_TYPE, CATEGORY,
                    DESCRIPTION, LOCATION, LOCATION_TYPE, SKILLS, ELIGIBILITY,
                    DEADLINE, APPLICATION_URL, SOURCE_NAME, SOURCE_URL,
                    VERIFICATION_STATUS, FETCHED_AT, CREATED_AT, UPDATED_AT
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                opp_id,
                data.get("slug") or opp_id,
                data.get("title"),
                data.get("organization"),
                data.get("opportunity_type"),
                data.get("category"),
                data.get("description"),
                data.get("location"),
                data.get("location_type"),
                skills_str,
                data.get("eligibility"),
                data.get("deadline"),
                data.get("application_url"),
                data.get("source_name") or "CloudLoop Indexer",
                data.get("source_url"),
                data.get("verification_status") or "verified",
                now,
                now,
                now,
            ]
            db_session.execute(sql, params)
            return opp_id

opportunity_repo = OpportunityRepository()

