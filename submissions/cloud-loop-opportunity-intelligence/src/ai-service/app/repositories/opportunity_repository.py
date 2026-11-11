import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from app.database.session import db_session

logger = logging.getLogger("cloud_loop.repository.opportunity")

class OpportunityRepository:
    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(row)
        skills_raw = d.get("SKILLS") or d.get("skills")
        skills_list = []
        if isinstance(skills_raw, str):
            try:
                parsed = json.loads(skills_raw)
                if isinstance(parsed, list):
                    skills_list = [s.strip() for s in parsed if s]
                else:
                    skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]
            except Exception:
                skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]
        elif isinstance(skills_raw, list):
            skills_list = [str(s).strip() for s in skills_raw if s]

        return {
            "id": d.get("ID") or d.get("id"),
            "kind": d.get("KIND") or d.get("kind") or "job",
            "slug": d.get("SLUG") or d.get("slug"),
            "title": d.get("TITLE") or d.get("title"),
            "org": d.get("ORG") or d.get("org") or d.get("ORGANIZATION") or d.get("organization"),
            "location": d.get("LOCATION") or d.get("location") or "India / Remote",
            "mode": d.get("MODE") or d.get("mode") or d.get("LOCATION_TYPE") or d.get("location_type") or "onsite",
            "deadline": str(d.get("DEADLINE") or d.get("deadline") or "") or None,
            "posted": str(d.get("POSTED") or d.get("posted") or "") or None,
            "apply_url": d.get("APPLY_URL") or d.get("apply_url") or d.get("APPLICATION_URL") or d.get("application_url") or "#",
            "source": d.get("SOURCE") or d.get("source") or "curated",
            "skills": skills_list,
            "description": d.get("DESCRIPTION") or d.get("description"),
            "updated_at": str(d.get("UPDATED_AT") or d.get("updated_at") or ""),
        }

    def get_by_id(self, opp_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM CLOUDLOOP.OPPORTUNITIES WHERE ID = ?"
        rows = db_session.query(sql, [opp_id])
        return self._row_to_dict(rows[0]) if rows else None

    def get_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM CLOUDLOOP.OPPORTUNITIES WHERE SLUG = ?"
        rows = db_session.query(sql, [slug])
        return self._row_to_dict(rows[0]) if rows else None

    def list_opportunities(
        self,
        kind: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        include_synthetic: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where_clauses = []
        params = []

        if not include_synthetic:
            where_clauses.append("SOURCE != 'synthetic-demo'")

        if kind and kind.lower() != "all":
            where_clauses.append("LOWER(KIND) = LOWER(?)")
            params.append(kind)

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            where_clauses.append("(LOWER(TITLE) LIKE ? OR LOWER(ORG) LIKE ? OR LOWER(SKILLS) LIKE ? OR LOWER(DESCRIPTION) LIKE ?)")
            params.extend([term, term, term, term])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Total count query
        count_sql = f"SELECT COUNT(*) as CNT FROM CLOUDLOOP.OPPORTUNITIES {where_sql}"
        count_rows = db_session.query(count_sql, params)
        total = int(count_rows[0].get("CNT") or count_rows[0].get("cnt") or 0) if count_rows else 0

        # Parameterized pagination: OFFSET ? ROWS FETCH FIRST ? ROWS ONLY
        offset = max(0, (page - 1) * limit)
        fetch_sql = f"""
            SELECT * FROM CLOUDLOOP.OPPORTUNITIES
            {where_sql}
            ORDER BY UPDATED_AT DESC
            OFFSET ? ROWS FETCH FIRST ? ROWS ONLY
        """
        rows = db_session.query(fetch_sql, params + [offset, limit])
        items = [self._row_to_dict(r) for r in rows]
        return items, total

    def count(self) -> int:
        rows = db_session.query("SELECT COUNT(*) as CNT FROM CLOUDLOOP.OPPORTUNITIES WHERE SOURCE != 'synthetic-demo'")
        return int(rows[0].get("CNT") or rows[0].get("cnt") or 0) if rows else 0

    def create(self, data: Dict[str, Any]) -> str:
        return self.upsert(data)

    def update(self, opp_id: str, data: Dict[str, Any]) -> str:
        return self.upsert({**data, "id": opp_id})

    def upsert(self, data: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        opp_id = data.get("id") or data.get("slug")
        slug = data.get("slug") or opp_id
        kind = data.get("kind") or data.get("opportunity_type") or "job"
        title = data.get("title") or "Opportunity"
        org = data.get("org") or data.get("organization") or "Partner"
        location = data.get("location") or "India / Remote"
        mode = data.get("mode") or data.get("location_type") or "onsite"
        deadline = data.get("deadline") or None
        posted = data.get("posted") or None
        apply_url = data.get("apply_url") or data.get("application_url") or "#"
        source = data.get("source") or "curated"

        skills = data.get("skills") or []
        if isinstance(skills, list):
            skills_str = ", ".join(skills)
        else:
            skills_str = str(skills)

        description = data.get("description") or f"{title} at {org}."

        existing = self.get_by_id(opp_id)
        if existing:
            sql = """
                UPDATE CLOUDLOOP.OPPORTUNITIES SET
                    KIND = ?, SLUG = ?, TITLE = ?, ORG = ?, LOCATION = ?, MODE = ?,
                    DEADLINE = ?, POSTED = ?, APPLY_URL = ?, SOURCE = ?, SKILLS = ?,
                    DESCRIPTION = ?, UPDATED_AT = ?
                WHERE ID = ?
            """
            params = [
                kind, slug, title, org, location, mode,
                deadline, posted, apply_url, source, skills_str,
                description, now, opp_id
            ]
            db_session.execute(sql, params)
        else:
            sql = """
                INSERT INTO CLOUDLOOP.OPPORTUNITIES (
                    ID, KIND, SLUG, TITLE, ORG, LOCATION, MODE,
                    DEADLINE, POSTED, APPLY_URL, SOURCE, SKILLS,
                    DESCRIPTION, UPDATED_AT
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                opp_id, kind, slug, title, org, location, mode,
                deadline, posted, apply_url, source, skills_str,
                description, now
            ]
            db_session.execute(sql, params)

        return opp_id

opportunity_repo = OpportunityRepository()
