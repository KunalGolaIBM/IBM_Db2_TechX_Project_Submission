"""
CivicConnect – IBM Db2 Repository Layer
All database read/write operations for complaints, departments, audit logs,
and analytics using ibm_db (native) and ibm_db_dbi (DB-API 2.0).
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Optional
import ibm_db

from db.db2_setup import get_ibm_db_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Department repository
# ---------------------------------------------------------------------------

DEFAULT_DEPARTMENTS = [
    ("DEPT-SAN",   "Sanitation Department",        "Solid waste management and garbage clearance.",            1),
    ("DEPT-PWD",   "Public Works Department",       "Road repairs, civic infrastructure and pavements.",       1),
    ("DEPT-ELEC",  "Electricity Department",        "Streetlight maintenance and public illumination.",        1),
    ("DEPT-WATER", "Water Supply Department",       "Pipeline leak repairs and municipal water pressure.",     1),
    ("DEPT-DRAIN", "Drainage Department",           "Stormwater drains, sewer lines and monsoon relief.",      1),
    ("DEPT-ADMIN", "Municipal Administration",      "General civic oversight and multi-department queries.",   1),
]


def seed_departments():
    """Insert default departments if DEPARTMENTS table is empty."""
    conn = get_ibm_db_connection()
    try:
        stmt = ibm_db.exec_immediate(
            conn, "SELECT COUNT(*) AS CNT FROM CIVICCONNECT.DEPARTMENTS"
        )
        row = ibm_db.fetch_assoc(stmt)
        if row and int(row["CNT"]) == 0:
            for dept_id, name, desc, active in DEFAULT_DEPARTMENTS:
                sql = """
                    INSERT INTO CIVICCONNECT.DEPARTMENTS
                        (DEPARTMENT_ID, NAME, DESCRIPTION, ACTIVE)
                    VALUES (?, ?, ?, ?)
                """
                s = ibm_db.prepare(conn, sql)
                ibm_db.execute(s, (dept_id, name, desc, active))
            print("[Db2] Default departments seeded.")
    finally:
        ibm_db.close(conn)


def fetch_all_departments() -> list[dict]:
    conn = get_ibm_db_connection()
    results = []
    try:
        stmt = ibm_db.exec_immediate(
            conn,
            "SELECT DEPARTMENT_ID, NAME, DESCRIPTION, ACTIVE FROM CIVICCONNECT.DEPARTMENTS WHERE ACTIVE = 1 ORDER BY NAME"
        )
        row = ibm_db.fetch_assoc(stmt)
        while row:
            results.append(dict(row))
            row = ibm_db.fetch_assoc(stmt)
    finally:
        ibm_db.close(conn)
    return results


# ---------------------------------------------------------------------------
# Complaint repository
# ---------------------------------------------------------------------------

def insert_complaint(data: dict) -> dict:
    """Persist a new complaint record to IBM Db2."""
    conn = get_ibm_db_connection()
    try:
        doc_id = data.get("id") or _new_id()
        now = _now_iso()
        keywords_str = json.dumps(data.get("ai_keywords", []))

        sql = """
            INSERT INTO CIVICCONNECT.COMPLAINTS (
                ID, COMPLAINT_ID, USER_ID, CITIZEN_NAME, CITIZEN_EMAIL,
                TITLE, DESCRIPTION, CATEGORY, DEPARTMENT_ID, DEPARTMENT_NAME,
                LOCATION, LANDMARK, IMAGE_URL, PRIORITY, STATUS,
                AI_SUMMARY, AI_KEYWORDS, CREATED_AT, UPDATED_AT
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        s = ibm_db.prepare(conn, sql)
        ibm_db.execute(s, (
            doc_id,
            data["complaint_id"],
            data["user_id"],
            data.get("citizen_name", ""),
            data.get("citizen_email", ""),
            data["title"],
            data["description"],
            data.get("category", ""),
            data.get("department_id", ""),
            data.get("department_name", ""),
            data["location"],
            data.get("landmark", ""),
            data.get("image_url", ""),
            data.get("priority", "medium"),
            data.get("status", "Submitted"),
            data.get("ai_summary", ""),
            keywords_str,
            now,
            now,
        ))
        return {**data, "id": doc_id, "created_at": now, "updated_at": now}
    finally:
        ibm_db.close(conn)


def fetch_all_complaints(limit: int = 500) -> list[dict]:
    """Fetch all complaints ordered by creation time (latest first)."""
    conn = get_ibm_db_connection()
    results = []
    try:
        sql = f"""
            SELECT ID, COMPLAINT_ID, USER_ID, CITIZEN_NAME, TITLE, CATEGORY,
                   DEPARTMENT_NAME, LOCATION, PRIORITY, STATUS, AI_SUMMARY,
                   CREATED_AT, UPDATED_AT
            FROM CIVICCONNECT.COMPLAINTS
            ORDER BY CREATED_AT DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        stmt = ibm_db.exec_immediate(conn, sql)
        row = ibm_db.fetch_assoc(stmt)
        while row:
            results.append(dict(row))
            row = ibm_db.fetch_assoc(stmt)
    finally:
        ibm_db.close(conn)
    return results


def fetch_complaints_by_category(category: str) -> list[dict]:
    conn = get_ibm_db_connection()
    results = []
    try:
        sql = """
            SELECT ID, COMPLAINT_ID, TITLE, STATUS, PRIORITY, CREATED_AT
            FROM CIVICCONNECT.COMPLAINTS
            WHERE CATEGORY = ?
            ORDER BY CREATED_AT DESC
        """
        s = ibm_db.prepare(conn, sql)
        ibm_db.execute(s, (category,))
        row = ibm_db.fetch_assoc(s)
        while row:
            results.append(dict(row))
            row = ibm_db.fetch_assoc(s)
    finally:
        ibm_db.close(conn)
    return results


def update_complaint_status(complaint_id: str, new_status: str, note: str, updated_by: str, updated_by_uid: str, role: str):
    """Update complaint status and record audit log entry."""
    conn = get_ibm_db_connection()
    try:
        # Fetch current status
        s = ibm_db.prepare(conn, "SELECT STATUS FROM CIVICCONNECT.COMPLAINTS WHERE COMPLAINT_ID = ?")
        ibm_db.execute(s, (complaint_id,))
        row = ibm_db.fetch_assoc(s)
        prev_status = row["STATUS"] if row else "Unknown"

        now = _now_iso()

        # Update complaint
        upd = ibm_db.prepare(
            conn,
            "UPDATE CIVICCONNECT.COMPLAINTS SET STATUS = ?, UPDATED_AT = ? WHERE COMPLAINT_ID = ?"
        )
        ibm_db.execute(upd, (new_status, now, complaint_id))

        # Audit log
        log_sql = """
            INSERT INTO CIVICCONNECT.COMPLAINT_UPDATES
                (ID, COMPLAINT_ID, PREVIOUS_STATUS, NEW_STATUS, UPDATED_BY, UPDATED_BY_UID, ROLE, NOTE, CREATED_AT)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        ls = ibm_db.prepare(conn, log_sql)
        ibm_db.execute(ls, (_new_id(), complaint_id, prev_status, new_status, updated_by, updated_by_uid, role, note, now))
    finally:
        ibm_db.close(conn)


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------

def get_category_summary() -> list[dict]:
    """Aggregate complaint counts grouped by category for analytics dashboard."""
    conn = get_ibm_db_connection()
    results = []
    try:
        sql = """
            SELECT
                CATEGORY,
                COUNT(*)                                            AS TOTAL,
                SUM(CASE WHEN STATUS = 'Resolved'  THEN 1 ELSE 0 END) AS RESOLVED,
                SUM(CASE WHEN STATUS != 'Resolved' THEN 1 ELSE 0 END) AS PENDING,
                AVG(CASE
                    WHEN RESOLVED_AT IS NOT NULL
                    THEN (TIMESTAMPDIFF(8, CHAR(RESOLVED_AT - CREATED_AT)))
                    ELSE NULL END)                                  AS AVG_RESOLUTION_HRS
            FROM CIVICCONNECT.COMPLAINTS
            GROUP BY CATEGORY
            ORDER BY TOTAL DESC
        """
        stmt = ibm_db.exec_immediate(conn, sql)
        row = ibm_db.fetch_assoc(stmt)
        while row:
            results.append(dict(row))
            row = ibm_db.fetch_assoc(stmt)
    finally:
        ibm_db.close(conn)
    return results


def get_department_workload() -> list[dict]:
    """Return open complaint counts per department (used for load balancing)."""
    conn = get_ibm_db_connection()
    results = []
    try:
        sql = """
            SELECT
                COALESCE(DEPARTMENT_NAME, 'Unassigned') AS DEPARTMENT,
                COUNT(*) AS OPEN_COUNT
            FROM CIVICCONNECT.COMPLAINTS
            WHERE STATUS NOT IN ('Resolved', 'Rejected')
            GROUP BY DEPARTMENT_NAME
            ORDER BY OPEN_COUNT DESC
        """
        stmt = ibm_db.exec_immediate(conn, sql)
        row = ibm_db.fetch_assoc(stmt)
        while row:
            results.append(dict(row))
            row = ibm_db.fetch_assoc(stmt)
    finally:
        ibm_db.close(conn)
    return results
