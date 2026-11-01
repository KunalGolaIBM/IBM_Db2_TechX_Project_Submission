"""
Repository layer providing CRUD operations and business logic for IBM Db2.
"""

from typing import List, Dict, Any, Optional
from internscrap.db.connection import get_db_connection


class Db2Repository:
    """Repository handling all database interactions with IBM Db2."""

    def __init__(self, conn=None):
        self.conn = conn or get_db_connection()

    def get_or_create_company(self, name: str, website: str = "", location: str = "", 
                              industry: str = "Technology", tier: str = "Mid") -> int:
        """Finds an existing company or creates a new one in Db2."""
        find_sql = "SELECT ID FROM COMPANIES WHERE NAME = ?"
        rows = self.conn.execute(find_sql, (name,))
        if rows:
            return rows[0]["ID"]

        insert_sql = """
        INSERT INTO COMPANIES (NAME, WEBSITE, LOCATION, INDUSTRY, TIER)
        VALUES (?, ?, ?, ?, ?)
        """
        self.conn.execute_non_query(insert_sql, (name, website, location, industry, tier))
        rows = self.conn.execute(find_sql, (name,))
        return rows[0]["ID"]

    def get_or_create_skill(self, name: str, category: str = "General") -> int:
        """Finds or creates a technical skill."""
        normalized_name = name.strip()
        find_sql = "SELECT ID FROM SKILLS WHERE UPPER(NAME) = UPPER(?)"
        rows = self.conn.execute(find_sql, (normalized_name,))
        if rows:
            return rows[0]["ID"]

        insert_sql = "INSERT INTO SKILLS (NAME, CATEGORY) VALUES (?, ?)"
        self.conn.execute_non_query(insert_sql, (normalized_name, category))
        rows = self.conn.execute(find_sql, (normalized_name,))
        return rows[0]["ID"]

    def upsert_internship(self, data: Dict[str, Any]) -> int:
        """
        Inserts or updates an internship listing in Db2.
        Links associated technical skills.
        """
        company_id = self.get_or_create_company(
            name=data["company"],
            website=data.get("website", ""),
            location=data.get("company_location", ""),
            industry=data.get("industry", "Technology"),
            tier=data.get("tier", "Mid")
        )

        source = data.get("source", "Direct")
        external_id = data.get("external_id") or str(hash(f"{data['title']}_{data['company']}"))

        # Check if already exists
        check_sql = "SELECT ID FROM INTERNSHIPS WHERE SOURCE = ? AND EXTERNAL_ID = ?"
        existing = self.conn.execute(check_sql, (source, external_id))

        if existing:
            internship_id = existing[0]["ID"]
            update_sql = """
            UPDATE INTERNSHIPS 
            SET TITLE = ?, LOCATION = ?, IS_REMOTE = ?, 
                STIPEND_MIN = ?, STIPEND_MAX = ?, APPLY_URL = ?, DEADLINE = ?
            WHERE ID = ?
            """
            self.conn.execute_non_query(update_sql, (
                data["title"],
                data.get("location", "Remote"),
                1 if data.get("is_remote", True) else 0,
                data.get("stipend_min"),
                data.get("stipend_max"),
                data["apply_url"],
                data.get("deadline"),
                internship_id
            ))
        else:
            insert_sql = """
            INSERT INTO INTERNSHIPS (
                TITLE, COMPANY_ID, LOCATION, IS_REMOTE, STIPEND_MIN, STIPEND_MAX,
                CURRENCY, APPLY_URL, SOURCE, EXTERNAL_ID, DEADLINE, STATUS
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
            """
            self.conn.execute_non_query(insert_sql, (
                data["title"],
                company_id,
                data.get("location", "Remote"),
                1 if data.get("is_remote", True) else 0,
                data.get("stipend_min"),
                data.get("stipend_max"),
                data.get("currency", "USD"),
                data["apply_url"],
                source,
                external_id,
                data.get("deadline")
            ))
            res = self.conn.execute(check_sql, (source, external_id))
            internship_id = res[0]["ID"]

        # Link skills
        skills = data.get("skills", [])
        for skill_name in skills:
            skill_id = self.get_or_create_skill(skill_name)
            # Insert if not already linked
            link_sql = """
            INSERT OR IGNORE INTO INTERNSHIP_SKILLS (INTERNSHIP_ID, SKILL_ID) 
            VALUES (?, ?)
            """ if not self.conn.is_native_db2 else """
            MERGE INTO INTERNSHIP_SKILLS target
            USING (VALUES (?, ?)) AS src (INTERNSHIP_ID, SKILL_ID)
            ON target.INTERNSHIP_ID = src.INTERNSHIP_ID AND target.SKILL_ID = src.SKILL_ID
            WHEN NOT MATCHED THEN INSERT (INTERNSHIP_ID, SKILL_ID) VALUES (src.INTERNSHIP_ID, src.SKILL_ID)
            """
            try:
                self.conn.execute_non_query(link_sql, (internship_id, skill_id))
            except Exception:
                pass

        return internship_id

    def list_internships(self, remote_only: bool = False, keyword: Optional[str] = None, 
                          limit: int = 20) -> List[Dict[str, Any]]:
        """Queries active internships with company name and skills."""
        query = """
        SELECT 
            i.ID,
            i.TITLE,
            c.NAME AS COMPANY,
            i.LOCATION,
            i.IS_REMOTE,
            i.STIPEND_MIN,
            i.STIPEND_MAX,
            i.CURRENCY,
            i.DEADLINE,
            i.APPLY_URL,
            i.SOURCE
        FROM INTERNSHIPS i
        JOIN COMPANIES c ON i.COMPANY_ID = c.ID
        WHERE i.STATUS = 'ACTIVE'
        """
        params = []
        if remote_only:
            query += " AND i.IS_REMOTE = 1"
        if keyword:
            query += " AND (UPPER(i.TITLE) LIKE UPPER(?) OR UPPER(c.NAME) LIKE UPPER(?))"
            kw = f"%{keyword}%"
            params.extend([kw, kw])

        query += " ORDER BY i.POSTED_DATE DESC, i.ID DESC"
        if limit > 0:
            query += f" LIMIT {limit}" if not self.conn.is_native_db2 else f" FETCH FIRST {limit} ROWS ONLY"

        rows = self.conn.execute(query, tuple(params))

        # Attach skills to each row
        for row in rows:
            skill_sql = """
            SELECT s.NAME FROM SKILLS s
            JOIN INTERNSHIP_SKILLS isk ON s.ID = isk.SKILL_ID
            WHERE isk.INTERNSHIP_ID = ?
            """
            s_rows = self.conn.execute(skill_sql, (row["ID"],))
            row["SKILLS"] = [s["NAME"] for s in s_rows]

        return rows

    def get_internship_by_id(self, internship_id: int) -> Optional[Dict[str, Any]]:
        """Fetches full details of a single internship."""
        query = """
        SELECT 
            i.ID, i.TITLE, c.NAME AS COMPANY, c.TIER AS COMPANY_TIER,
            i.LOCATION, i.IS_REMOTE, i.STIPEND_MIN, i.STIPEND_MAX,
            i.CURRENCY, i.APPLY_URL, i.SOURCE, i.DEADLINE, i.STATUS
        FROM INTERNSHIPS i
        JOIN COMPANIES c ON i.COMPANY_ID = c.ID
        WHERE i.ID = ?
        """
        rows = self.conn.execute(query, (internship_id,))
        if not rows:
            return None
        item = rows[0]
        skill_sql = """
        SELECT s.NAME FROM SKILLS s
        JOIN INTERNSHIP_SKILLS isk ON s.ID = isk.SKILL_ID
        WHERE isk.INTERNSHIP_ID = ?
        """
        s_rows = self.conn.execute(skill_sql, (internship_id,))
        item["SKILLS"] = [s["NAME"] for s in s_rows]
        return item

    def track_application(self, internship_id: int, status: str = "APPLIED", 
                          notes: str = "", applied_date: Optional[str] = None, 
                          follow_up_date: Optional[str] = None) -> bool:
        """Records or updates a user's internship application in Db2."""
        check_sql = "SELECT ID FROM APPLICATIONS WHERE INTERNSHIP_ID = ? AND USER_IDENTIFIER = 'local_user'"
        existing = self.conn.execute(check_sql, (internship_id,))

        if existing:
            update_sql = """
            UPDATE APPLICATIONS
            SET STATUS = ?, NOTES = ?, APPLIED_DATE = COALESCE(?, APPLIED_DATE),
                FOLLOW_UP_DATE = ?, UPDATED_AT = CURRENT_TIMESTAMP
            WHERE ID = ?
            """
            self.conn.execute_non_query(update_sql, (
                status, notes, applied_date, follow_up_date, existing[0]["ID"]
            ))
        else:
            insert_sql = """
            INSERT INTO APPLICATIONS (
                INTERNSHIP_ID, USER_IDENTIFIER, STATUS, APPLIED_DATE, FOLLOW_UP_DATE, NOTES
            ) VALUES (?, 'local_user', ?, COALESCE(?, DATE('now')), ?, ?)
            """ if not self.conn.is_native_db2 else """
            INSERT INTO APPLICATIONS (
                INTERNSHIP_ID, USER_IDENTIFIER, STATUS, APPLIED_DATE, FOLLOW_UP_DATE, NOTES
            ) VALUES (?, 'local_user', ?, COALESCE(?, CURRENT DATE), ?, ?)
            """
            self.conn.execute_non_query(insert_sql, (
                internship_id, status, applied_date, follow_up_date, notes
            ))
        return True

    def list_applications(self) -> List[Dict[str, Any]]:
        """Queries tracked applications joined with internship and company info."""
        query = """
        SELECT 
            a.ID AS APPLICATION_ID,
            i.ID AS INTERNSHIP_ID,
            c.NAME AS COMPANY,
            i.TITLE AS ROLE,
            a.STATUS,
            a.APPLIED_DATE,
            a.FOLLOW_UP_DATE,
            a.NOTES
        FROM APPLICATIONS a
        JOIN INTERNSHIPS i ON a.INTERNSHIP_ID = i.ID
        JOIN COMPANIES c ON i.COMPANY_ID = c.ID
        WHERE a.USER_IDENTIFIER = 'local_user'
        ORDER BY a.UPDATED_AT DESC
        """
        return self.conn.execute(query)

    def get_analytics(self) -> Dict[str, Any]:
        """Fetches aggregated statistics using Db2 views or equivalent queries."""
        funnel_sql = "SELECT * FROM V_APPLICATION_FUNNEL"
        skills_sql = """
        SELECT 
            s.NAME AS SKILL_NAME, 
            COUNT(isk.INTERNSHIP_ID) AS LISTING_COUNT
        FROM SKILLS s
        JOIN INTERNSHIP_SKILLS isk ON s.ID = isk.SKILL_ID
        JOIN INTERNSHIPS i ON isk.INTERNSHIP_ID = i.ID
        WHERE i.STATUS = 'ACTIVE'
        GROUP BY s.NAME
        ORDER BY LISTING_COUNT DESC
        """
        if self.conn.is_native_db2:
            skills_sql += " FETCH FIRST 10 ROWS ONLY"
        else:
            skills_sql += " LIMIT 10"

        funnel_rows = self.conn.execute(funnel_sql)
        skills_rows = self.conn.execute(skills_sql)

        total_internships = self.conn.execute("SELECT COUNT(*) AS TOTAL FROM INTERNSHIPS")[0]["TOTAL"]
        total_companies = self.conn.execute("SELECT COUNT(*) AS TOTAL FROM COMPANIES")[0]["TOTAL"]

        return {
            "total_internships": total_internships,
            "total_companies": total_companies,
            "funnel": funnel_rows,
            "top_skills": skills_rows
        }
