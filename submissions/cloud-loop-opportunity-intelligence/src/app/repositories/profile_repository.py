import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from backend.app.database.session import db_session

logger = logging.getLogger("cloud_loop.repository.profile")

class ProfileRepository:
    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(row)

        def _parse_list(val):
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return [s.strip() for s in val.split(",") if s.strip()]
            return list(val) if val else []

        return {
            "user_id": d.get("USER_ID") or d.get("user_id"),
            "education": d.get("EDUCATION") or d.get("education"),
            "degree": d.get("DEGREE") or d.get("degree"),
            "study_year": d.get("STUDY_YEAR") or d.get("study_year") or 1,
            "graduation_batch": d.get("GRADUATION_BATCH") or d.get("graduation_batch"),
            "skills": _parse_list(d.get("SKILLS") or d.get("skills")),
            "interests": _parse_list(d.get("INTERESTS") or d.get("interests")),
            "preferred_domains": _parse_list(d.get("PREFERRED_DOMAINS") or d.get("preferred_domains")),
            "preferred_locations": _parse_list(d.get("PREFERRED_LOCATIONS") or d.get("preferred_locations")),
            "updated_at": d.get("UPDATED_AT") or d.get("updated_at"),
        }

    def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM STUDENT_PROFILES WHERE USER_ID = ?"
        rows = db_session.query(sql, [user_id])
        return self._row_to_dict(rows[0]) if rows else None

    def upsert(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        skills_str = json.dumps(data.get("skills") or [])
        interests_str = json.dumps(data.get("interests") or [])
        domains_str = json.dumps(data.get("preferred_domains") or [])
        locations_str = json.dumps(data.get("preferred_locations") or [])

        existing = self.get_by_user_id(user_id)
        if existing:
            sql = """
                UPDATE STUDENT_PROFILES SET
                    EDUCATION = ?,
                    DEGREE = ?,
                    STUDY_YEAR = ?,
                    GRADUATION_BATCH = ?,
                    SKILLS = ?,
                    INTERESTS = ?,
                    PREFERRED_DOMAINS = ?,
                    PREFERRED_LOCATIONS = ?,
                    UPDATED_AT = ?
                WHERE USER_ID = ?
            """
            params = [
                data.get("education"),
                data.get("degree"),
                data.get("study_year", 1),
                data.get("graduation_batch"),
                skills_str,
                interests_str,
                domains_str,
                locations_str,
                now,
                user_id,
            ]
            db_session.execute(sql, params)
        else:
            sql = """
                INSERT INTO STUDENT_PROFILES (
                    USER_ID, EDUCATION, DEGREE, STUDY_YEAR, GRADUATION_BATCH,
                    SKILLS, INTERESTS, PREFERRED_DOMAINS, PREFERRED_LOCATIONS, UPDATED_AT
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                user_id,
                data.get("education"),
                data.get("degree"),
                data.get("study_year", 1),
                data.get("graduation_batch"),
                skills_str,
                interests_str,
                domains_str,
                locations_str,
                now,
            ]
            db_session.execute(sql, params)

        return self.get_by_user_id(user_id)

profile_repo = ProfileRepository()

