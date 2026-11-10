import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("sentinel.database")

# Attempt importing ibm_db if available
ibm_db = None
try:
    import ibm_db
except Exception as e:
    logger.info(f"ibm_db native module not loaded: {e}. Will use SQLite compatibility mode.")

class DatabaseConnector:
    def __init__(self):
        self.is_db2_active = False
        self.db2_conn = None
        self.sqlite_path = os.path.join(os.path.dirname(__file__), "..", "..", "sentinel.db")
        self._init_connection()

    def _init_connection(self):
        """Initialize connection to IBM Db2 or fallback to SQLite."""
        if ibm_db and settings.DB2_UID and settings.DB2_PWD:
            try:
                conn_str = (
                    f"DATABASE={settings.DB2_DATABASE};"
                    f"HOSTNAME={settings.DB2_HOSTNAME};"
                    f"PORT={settings.DB2_PORT};"
                    f"PROTOCOL={settings.DB2_PROTOCOL};"
                    f"UID={settings.DB2_UID};"
                    f"PWD={settings.DB2_PWD};"
                )
                if settings.DB2_SECURITY.upper() == "SSL":
                    conn_str += "SECURITY=SSL;"
                
                logger.info(f"Connecting to IBM Db2 at {settings.DB2_HOSTNAME}:{settings.DB2_PORT}...")
                self.db2_conn = ibm_db.connect(conn_str, "", "")
                self.is_db2_active = True
                logger.info("Successfully established connection to IBM Db2.")
                return
            except Exception as e:
                logger.warning(f"Could not connect to IBM Db2: {e}. Falling back to SQLite local store.")
                self.is_db2_active = False
        else:
            logger.info("IBM Db2 credentials not fully specified. Using local high-performance SQLite store.")
            self.is_db2_active = False

    def get_sqlite_conn(self):
        """Returns SQLite connection with dict row factory."""
        os.makedirs(os.path.dirname(os.path.abspath(self.sqlite_path)), exist_ok=True)
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return rows as list of dicts."""
        if self.is_db2_active and self.db2_conn:
            try:
                # Convert '?' placeholders for Db2 if needed (Db2 supports '?' with ibm_db.prepare)
                stmt = ibm_db.prepare(self.db2_conn, query)
                ibm_db.execute(stmt, params)
                results = []
                row = ibm_db.fetch_assoc(stmt)
                while row:
                    results.append({k.lower(): v for k, v in row.items()})
                    row = ibm_db.fetch_assoc(stmt)
                return results
            except Exception as e:
                logger.error(f"Db2 query error: {e}. Falling back to SQLite.")
                # Fallback to sqlite if Db2 drops
                return self._execute_sqlite_query(query, params)
        else:
            return self._execute_sqlite_query(query, params)

    def _execute_sqlite_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = self.get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute INSERT, UPDATE, DELETE query and return affected rows."""
        if self.is_db2_active and self.db2_conn:
            try:
                stmt = ibm_db.prepare(self.db2_conn, query)
                ibm_db.execute(stmt, params)
                return ibm_db.num_rows(stmt)
            except Exception as e:
                logger.error(f"Db2 update error: {e}. Falling back to SQLite.")
                return self._execute_sqlite_update(query, params)
        else:
            return self._execute_sqlite_update(query, params)

    def _execute_sqlite_update(self, query: str, params: tuple = ()) -> int:
        conn = self.get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_status(self) -> Dict[str, Any]:
        """Return connectivity status for dashboard display."""
        return {
            "is_db2_active": self.is_db2_active,
            "engine": "IBM Db2 Enterprise" if self.is_db2_active else "IBM Db2 Emulation (SQLite V2)",
            "host": settings.DB2_HOSTNAME if self.is_db2_active else "Local Storage Engine",
            "database": settings.DB2_DATABASE,
            "driver": "ibm_db 3.3.0" if ibm_db else "sqlite3 native driver",
            "status": "ONLINE"
        }

db_connector = DatabaseConnector()

