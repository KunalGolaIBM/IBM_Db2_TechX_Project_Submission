import sqlite3
import os
import re
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.database.db2_connection import db2_manager

logger = logging.getLogger("cloud_loop.database")

class DatabaseSession:
    """
    Unified Database abstraction for Cloud Loop.
    Routes queries to IBM Db2 Enterprise when available;
    transparently falls back to local SQLite with identical schemas
    when Db2 is not yet configured or restricted by local OS policy.
    """
    def __init__(self):
        self.sqlite_path = settings.LOCAL_DB_PATH
        self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Opportunities Table matching CLOUDLOOP.OPPORTUNITIES
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS OPPORTUNITIES (
            ID TEXT PRIMARY KEY,
            KIND TEXT NOT NULL CHECK (KIND IN ('job','internship','event','program','certification')),
            SLUG TEXT UNIQUE NOT NULL,
            TITLE TEXT NOT NULL,
            ORG TEXT NOT NULL,
            LOCATION TEXT,
            MODE TEXT,
            DEADLINE TEXT,
            POSTED TEXT,
            APPLY_URL TEXT NOT NULL,
            SOURCE TEXT NOT NULL DEFAULT 'curated',
            SKILLS TEXT,
            DESCRIPTION TEXT,
            UPDATED_AT TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS IX_OPP_KIND_DEADLINE ON OPPORTUNITIES (KIND, DEADLINE)")

        # Tracking Table matching CLOUDLOOP.TRACKED_OPPORTUNITIES
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS TRACKED_OPPORTUNITIES (
            USER_ID TEXT NOT NULL,
            OPPORTUNITY_ID TEXT NOT NULL,
            STATUS TEXT DEFAULT 'None',
            BOOKMARKED INTEGER DEFAULT 0,
            UPDATED_AT TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (USER_ID, OPPORTUNITY_ID),
            FOREIGN KEY (OPPORTUNITY_ID) REFERENCES OPPORTUNITIES(ID) ON DELETE CASCADE
        )
        """)

        # Newsletter Subscribers Table matching CLOUDLOOP.NEWSLETTER_SUBSCRIBERS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS NEWSLETTER_SUBSCRIBERS (
            EMAIL TEXT PRIMARY KEY,
            CREATED_AT TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Student Profiles Table matching CLOUDLOOP.STUDENT_PROFILES
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS STUDENT_PROFILES (
            USER_ID TEXT PRIMARY KEY,
            EDUCATION TEXT,
            DEGREE TEXT,
            STUDY_YEAR INTEGER DEFAULT 1,
            GRADUATION_BATCH TEXT,
            SKILLS TEXT,
            INTERESTS TEXT,
            PREFERRED_DOMAINS TEXT,
            PREFERRED_LOCATIONS TEXT,
            UPDATED_AT TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Ingestion Runs Table matching CLOUDLOOP.INGESTION_RUNS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS INGESTION_RUNS (
            ID TEXT PRIMARY KEY,
            SOURCE TEXT NOT NULL,
            RECORDS_PROCESSED INTEGER DEFAULT 0,
            RECORDS_INSERTED INTEGER DEFAULT 0,
            RECORDS_UPDATED INTEGER DEFAULT 0,
            RECORDS_REJECTED INTEGER DEFAULT 0,
            STATUS TEXT DEFAULT 'SUCCESS',
            ERROR_SUMMARY TEXT,
            STARTED_AT TEXT DEFAULT CURRENT_TIMESTAMP,
            COMPLETED_AT TEXT
        )
        """)

        # Active Opportunities View matching CLOUDLOOP.V_ACTIVE_OPPORTUNITIES
        cursor.execute("""
        CREATE VIEW IF NOT EXISTS V_ACTIVE_OPPORTUNITIES AS
            SELECT * FROM OPPORTUNITIES WHERE DEADLINE IS NULL OR DEADLINE >= date('now');
        """)

        # Supporting student profiles and ingestion telemetry tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS STUDENT_PROFILES (
            USER_ID TEXT PRIMARY KEY,
            EDUCATION TEXT,
            DEGREE TEXT,
            STUDY_YEAR INTEGER DEFAULT 1,
            GRADUATION_BATCH TEXT,
            SKILLS TEXT,
            INTERESTS TEXT,
            PREFERRED_DOMAINS TEXT,
            PREFERRED_LOCATIONS TEXT,
            UPDATED_AT TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS INGESTION_RUNS (
            ID TEXT PRIMARY KEY,
            SOURCE TEXT NOT NULL,
            RECORDS_PROCESSED INTEGER DEFAULT 0,
            RECORDS_INSERTED INTEGER DEFAULT 0,
            RECORDS_UPDATED INTEGER DEFAULT 0,
            RECORDS_REJECTED INTEGER DEFAULT 0,
            STATUS TEXT DEFAULT 'running',
            ERROR_SUMMARY TEXT,
            STARTED_AT TEXT DEFAULT CURRENT_TIMESTAMP,
            COMPLETED_AT TEXT
        )
        """)

        conn.commit()
        conn.close()

    def _adapt_sql_for_sqlite(self, sql: str) -> str:
        """Adapts Db2 LUW syntax to SQLite when running in local sandbox fallback mode."""
        s = sql.replace("CLOUDLOOP.", "")
        
        # Replace Db2 date arithmetic e.g. (CURRENT DATE + 7 DAYS) -> date('now', '+7 days')
        s = re.sub(r"\(?\s*CURRENT\s+DATE\s*\+\s*(\d+)\s+DAYS\s*\)?", r"date('now', '+\1 days')", s, flags=re.IGNORECASE)
        s = s.replace("CURRENT DATE", "date('now')")
        s = s.replace("CURRENT TIMESTAMP", "datetime('now')")
        
        # Replace Db2 FETCH FIRST n ROWS ONLY [OFFSET m] with SQLite LIMIT n OFFSET m
        fetch_pattern = re.compile(r"OFFSET\s+(\d+|\?)\s+ROWS\s+FETCH\s+FIRST\s+(\d+|\?)\s+ROWS\s+ONLY", re.IGNORECASE)
        match = fetch_pattern.search(s)
        if match:
            offset_val, limit_val = match.groups()
            s = fetch_pattern.sub(f"LIMIT {limit_val} OFFSET {offset_val}", s)
        else:
            fetch_first_pattern = re.compile(r"FETCH\s+FIRST\s+(\d+|\?)\s+ROWS\s+ONLY", re.IGNORECASE)
            s = fetch_first_pattern.sub(r"LIMIT \1", s)

        return s

    def query(self, sql: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        params = params or []
        status = db2_manager.status
        if status["driver_available"] and status["configured"]:
            try:
                return db2_manager.execute_query(sql, params)
            except Exception as e:
                logger.warning(f"Db2 query failed, falling back to local storage: {e}")

        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            adapted_sql = self._adapt_sql_for_sqlite(sql)
            cursor.execute(adapted_sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def execute(self, sql: str, params: List[Any] = None) -> int:
        params = params or []
        status = db2_manager.status
        if status["driver_available"] and status["configured"]:
            try:
                return db2_manager.execute_non_query(sql, params)
            except Exception as e:
                logger.warning(f"Db2 execute failed, falling back to local storage: {e}")

        conn = sqlite3.connect(self.sqlite_path)
        try:
            cursor = conn.cursor()
            adapted_sql = self._adapt_sql_for_sqlite(sql)
            cursor.execute(adapted_sql, params)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

db_session = DatabaseSession()
