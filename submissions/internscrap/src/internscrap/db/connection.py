"""
Database connection manager for InternScrap.
Connects natively to IBM Db2 using the official `ibm_db` driver.
Provides transparent fallback simulation when running offline or during testing.
"""

import sys
import sqlite3
from typing import Optional, Any, Dict, List
from internscrap.config import (
    DB_BACKEND,
    DB2_HOST,
    DB2_PORT,
    DB2_DATABASE,
    get_db2_connection_string
)

# Attempt to import ibm_db
try:
    import ibm_db
    IBM_DB_AVAILABLE = True
except ImportError:
    IBM_DB_AVAILABLE = False


class Db2ConnectionWrapper:
    """Wrapper around the native IBM Db2 connection object."""

    def __init__(self, conn):
        self.conn = conn
        self.is_native_db2 = True

    def execute(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Executes a SQL query and returns results as a list of dicts."""
        if params:
            stmt = ibm_db.prepare(self.conn, sql)
            # ibm_db parameters are bound 1-indexed or passed directly to execute
            ibm_db.execute(stmt, params)
        else:
            stmt = ibm_db.exec_immediate(self.conn, sql)

        results = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            # Normalize keys to uppercase for Db2 convention
            normalized_row = {k.upper(): v for k, v in row.items()}
            results.append(normalized_row)
            row = ibm_db.fetch_assoc(stmt)
        return results

    def execute_non_query(self, sql: str, params: tuple = ()) -> int:
        """Executes DDL or DML statements (INSERT, UPDATE, DELETE)."""
        if params:
            stmt = ibm_db.prepare(self.conn, sql)
            ibm_db.execute(stmt, params)
            return ibm_db.num_rows(stmt)
        else:
            stmt = ibm_db.exec_immediate(self.conn, sql)
            return ibm_db.num_rows(stmt)

    def close(self):
        if self.conn:
            ibm_db.close(self.conn)
            self.conn = None


class SimulatedDb2Connection:
    """
    Simulated IBM Db2 connection using SQLite for offline development & tests.
    Translates Db2 data types and provides identical method signatures.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.is_native_db2 = False
        self._init_sqlite_schema()

    def _init_sqlite_schema(self):
        cur = self.conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS COMPANIES (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            NAME TEXT NOT NULL UNIQUE,
            WEBSITE TEXT,
            LOCATION TEXT,
            INDUSTRY TEXT DEFAULT 'Technology',
            TIER TEXT DEFAULT 'Mid',
            CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS INTERNSHIPS (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            TITLE TEXT NOT NULL,
            COMPANY_ID INTEGER NOT NULL REFERENCES COMPANIES(ID) ON DELETE CASCADE,
            LOCATION TEXT DEFAULT 'Remote',
            IS_REMOTE INTEGER DEFAULT 1,
            STIPEND_MIN REAL,
            STIPEND_MAX REAL,
            CURRENCY TEXT DEFAULT 'USD',
            APPLY_URL TEXT NOT NULL,
            SOURCE TEXT DEFAULT 'Direct',
            EXTERNAL_ID TEXT,
            POSTED_DATE DATE DEFAULT (DATE('now')),
            DEADLINE DATE,
            STATUS TEXT DEFAULT 'ACTIVE',
            CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(SOURCE, EXTERNAL_ID)
        );

        CREATE TABLE IF NOT EXISTS SKILLS (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            NAME TEXT NOT NULL UNIQUE,
            CATEGORY TEXT DEFAULT 'General'
        );

        CREATE TABLE IF NOT EXISTS INTERNSHIP_SKILLS (
            INTERNSHIP_ID INTEGER NOT NULL REFERENCES INTERNSHIPS(ID) ON DELETE CASCADE,
            SKILL_ID INTEGER NOT NULL REFERENCES SKILLS(ID) ON DELETE CASCADE,
            PRIMARY KEY (INTERNSHIP_ID, SKILL_ID)
        );

        CREATE TABLE IF NOT EXISTS APPLICATIONS (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            INTERNSHIP_ID INTEGER NOT NULL REFERENCES INTERNSHIPS(ID) ON DELETE CASCADE,
            USER_IDENTIFIER TEXT DEFAULT 'local_user',
            STATUS TEXT DEFAULT 'WISHLIST',
            APPLIED_DATE DATE,
            FOLLOW_UP_DATE DATE,
            NOTES TEXT,
            CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(USER_IDENTIFIER, INTERNSHIP_ID)
        );

        CREATE VIEW IF NOT EXISTS V_ACTIVE_INTERNSHIPS AS
        SELECT 
            i.ID AS INTERNSHIP_ID,
            i.TITLE,
            c.NAME AS COMPANY_NAME,
            c.TIER AS COMPANY_TIER,
            i.LOCATION,
            CASE WHEN i.IS_REMOTE = 1 THEN 'Yes' ELSE 'No' END AS IS_REMOTE,
            i.STIPEND_MIN,
            i.STIPEND_MAX,
            i.CURRENCY,
            i.DEADLINE,
            i.APPLY_URL,
            i.SOURCE,
            i.POSTED_DATE
        FROM INTERNSHIPS i
        JOIN COMPANIES c ON i.COMPANY_ID = c.ID
        WHERE i.STATUS = 'ACTIVE';

        CREATE VIEW IF NOT EXISTS V_APPLICATION_FUNNEL AS
        SELECT 
            a.STATUS AS STAGE,
            COUNT(a.ID) AS TOTAL_COUNT,
            MIN(a.APPLIED_DATE) AS EARLIEST_APPLICATION,
            MAX(a.APPLIED_DATE) AS LATEST_APPLICATION
        FROM APPLICATIONS a
        GROUP BY a.STATUS;
        """)
        self.conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        # Clean parameter markers if needed (Db2 uses ? which SQLite also accepts)
        cur.execute(sql, params)
        rows = cur.fetchall()
        results = []
        for r in rows:
            results.append({k.upper(): r[k] for k in r.keys()})
        return results

    def execute_non_query(self, sql: str, params: tuple = ()) -> int:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur.rowcount

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


_CURRENT_CONNECTION = None

def get_db_connection(force_new: bool = False):
    """
    Factory function to retrieve or create the active database connection.
    Attempts live IBM Db2 connection first; falls back smoothly if unavailable.
    """
    global _CURRENT_CONNECTION

    if _CURRENT_CONNECTION is not None and not force_new:
        return _CURRENT_CONNECTION

    # 1. If user explicitly configured 'simulated'
    if DB_BACKEND == "simulated":
        _CURRENT_CONNECTION = SimulatedDb2Connection("internscrap_dev.sqlite3")
        return _CURRENT_CONNECTION

    # 2. Try native IBM Db2
    if IBM_DB_AVAILABLE:
        conn_str = get_db2_connection_string()
        try:
            native_conn = ibm_db.connect(conn_str, "", "")
            _CURRENT_CONNECTION = Db2ConnectionWrapper(native_conn)
            return _CURRENT_CONNECTION
        except Exception as e:
            # Fall back to simulated mode with diagnostic notice
            print(f"[Notice] Could not connect to IBM Db2 at {DB2_HOST}:{DB2_PORT} ({e}).")
            print("[Notice] Using simulated Db2 fallback mode (internscrap_dev.sqlite3).")
            _CURRENT_CONNECTION = SimulatedDb2Connection("internscrap_dev.sqlite3")
            return _CURRENT_CONNECTION
    else:
        print("[Notice] `ibm_db` driver not installed in current environment.")
        print("[Notice] Running in simulated Db2 fallback mode (internscrap_dev.sqlite3).")
        _CURRENT_CONNECTION = SimulatedDb2Connection("internscrap_dev.sqlite3")
        return _CURRENT_CONNECTION
