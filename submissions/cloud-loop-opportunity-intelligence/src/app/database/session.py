import sqlite3
import os
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.database.db2_connection import db2_manager

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

        # Idempotent schema initialization
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS OPPORTUNITIES (
            ID TEXT PRIMARY KEY,
            SLUG TEXT UNIQUE NOT NULL,
            TITLE TEXT NOT NULL,
            ORGANIZATION TEXT NOT NULL,
            OPPORTUNITY_TYPE TEXT NOT NULL,
            CATEGORY TEXT NOT NULL,
            DESCRIPTION TEXT,
            LOCATION TEXT,
            LOCATION_TYPE TEXT,
            SKILLS TEXT,
            ELIGIBILITY TEXT,
            DEADLINE TEXT,
            APPLICATION_URL TEXT NOT NULL,
            SOURCE_NAME TEXT DEFAULT 'CloudLoop Scraper',
            SOURCE_URL TEXT,
            VERIFICATION_STATUS TEXT DEFAULT 'verified',
            FETCHED_AT TEXT,
            CREATED_AT TEXT,
            UPDATED_AT TEXT
        )
        """)

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
            UPDATED_AT TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS USER_OPPORTUNITY_TRACKING (
            USER_ID TEXT NOT NULL,
            OPPORTUNITY_ID TEXT NOT NULL,
            APPLICATION_STATUS TEXT DEFAULT 'saved',
            BOOKMARKED INTEGER DEFAULT 1,
            UPDATED_AT TEXT,
            PRIMARY KEY (USER_ID, OPPORTUNITY_ID),
            FOREIGN KEY (OPPORTUNITY_ID) REFERENCES OPPORTUNITIES(ID) ON DELETE CASCADE
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
            STARTED_AT TEXT,
            COMPLETED_AT TEXT
        )
        """)

        conn.commit()
        conn.close()

    def query(self, sql: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        params = params or []
        # Try Db2 first if driver and config are available
        status = db2_manager.status
        if status["driver_available"] and status["configured"]:
            try:
                return db2_manager.execute_query(sql, params)
            except Exception as e:
                logger.warning(f"Db2 query failed, falling back to local storage: {e}")

        # Local storage execution
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
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
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

db_session = DatabaseSession()

