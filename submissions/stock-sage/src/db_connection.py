"""Database connection manager for IBM Db2.

Supports native IBM Db2 connections via the official `ibm_db` driver,
with an offline fallback simulator for local testing and CI verification.
"""

import logging
import sqlite3
from typing import Any, Dict, List, Optional
from src.config import (
    DB2_DATABASE,
    DB2_HOST,
    DB2_PASSWORD,
    DB2_PORT,
    DB2_SECURITY,
    DB2_USER,
    USE_MOCK_DB,
)

logger = logging.getLogger("StockSage.DB")
logging.basicConfig(level=logging.INFO)

try:
    import ibm_db
    IBM_DB_AVAILABLE = True
except ImportError:
    IBM_DB_AVAILABLE = False
    logger.warning("ibm_db module is not available in the current environment.")


class Db2ConnectionManager:
    """Manages connections and query execution against IBM Db2."""

    def __init__(self):
        self._conn = None
        self._mock_conn: Optional[sqlite3.Connection] = None
        self._is_mock = USE_MOCK_DB

    def get_connection_string(self) -> str:
        """Build the official IBM Db2 connection string."""
        conn_str = (
            f"DATABASE={DB2_DATABASE};"
            f"HOSTNAME={DB2_HOST};"
            f"PORT={DB2_PORT};"
            f"PROTOCOL=TCPIP;"
            f"UID={DB2_USER};"
            f"PWD={DB2_PASSWORD};"
        )
        if DB2_SECURITY.lower() in ("ssl", "true"):
            conn_str += "SECURITY=SSL;"
        return conn_str

    def connect(self):
        """Establish connection to IBM Db2 or fallback simulator."""
        if self._is_mock:
            self._ensure_mock_db()
            return self._mock_conn

        if not IBM_DB_AVAILABLE:
            logger.warning("ibm_db driver missing. Falling back to simulation mode.")
            self._is_mock = True
            self._ensure_mock_db()
            return self._mock_conn

        try:
            conn_str = self.get_connection_string()
            logger.info("Connecting to IBM Db2 at %s:%s...", DB2_HOST, DB2_PORT)
            self._conn = ibm_db.connect(conn_str, "", "")
            logger.info("Successfully connected to IBM Db2 database: %s", DB2_DATABASE)
            return self._conn
        except Exception as e:
            logger.warning("Could not connect to live Db2 (%s). Using fallback mode for resilience.", e)
            self._is_mock = True
            self._ensure_mock_db()
            return self._mock_conn

    def _ensure_mock_db(self):
        """Initialize in-memory fallback store for offline tests and simulation."""
        if self._mock_conn is None:
            self._mock_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mock_conn.row_factory = sqlite3.Row
            from src.database_setup import initialize_database
            initialize_database(self, force_recreate=True)

    @property
    def is_mock(self) -> bool:
        """Returns True if running in fallback simulation mode."""
        return self._is_mock

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return a list of dictionaries."""
        if self._conn is None and not self._is_mock:
            self.connect()

        if self._is_mock:
            self._ensure_mock_db()
            cursor = self._mock_conn.cursor()
            # Convert Db2 CURRENT DATE / DATE formatting if needed for SQLite
            sql_clean = sql.replace("CURRENT DATE", "DATE('now')")
            sql_clean = sql_clean.replace("DAYS", "days")
            if params:
                cursor.execute(sql_clean, params)
            else:
                cursor.execute(sql_clean)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        # IBM Db2 execution path
        stmt = ibm_db.prepare(self._conn, sql)
        if params:
            for i, p in enumerate(params, start=1):
                ibm_db.bind_param(stmt, i, p)

        ibm_db.execute(stmt)
        results = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            # Normalize keys to lowercase for consistent downstream consumption
            results.append({k.lower(): v for k, v in row.items()})
            row = ibm_db.fetch_assoc(stmt)
        return results

    def execute_non_query(self, sql: str, params: Optional[tuple] = None) -> int:
        """Execute DDL, INSERT, UPDATE, or DELETE statements."""
        if self._conn is None and not self._is_mock:
            self.connect()

        if self._is_mock:
            self._ensure_mock_db()
            cursor = self._mock_conn.cursor()
            sql_clean = sql.replace("CURRENT DATE", "DATE('now')")
            if params:
                cursor.execute(sql_clean, params)
            else:
                cursor.execute(sql_clean)
            self._mock_conn.commit()
            return cursor.rowcount

        # IBM Db2 execution path
        stmt = ibm_db.prepare(self._conn, sql)
        if params:
            for i, p in enumerate(params, start=1):
                ibm_db.bind_param(stmt, i, p)

        ibm_db.execute(stmt)
        return ibm_db.num_rows(stmt)

    def close(self):
        """Close active database connections."""
        if self._conn:
            try:
                ibm_db.close(self._conn)
            except Exception:
                pass
            self._conn = None
        if self._mock_conn:
            try:
                self._mock_conn.close()
            except Exception:
                pass
            self._mock_conn = None


# Global singleton instance
db_manager = Db2ConnectionManager()
