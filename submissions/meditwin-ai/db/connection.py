"""
MediTwin AI — IBM Db2 Connection Manager
Handles connection lifecycle, schema initialization, and health checks.
"""

import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Try to import ibm_db; graceful fallback if not available
try:
    import ibm_db
    IBM_DB_AVAILABLE = True
except ImportError:
    IBM_DB_AVAILABLE = False
    logger.warning("ibm_db not installed. Db2 operations will not be available.")


class Db2Connection:
    """Manages IBM Db2 database connections."""

    def __init__(self, connection_string: str, schema: str = "MEDITWIN"):
        self.connection_string = connection_string
        self.schema = schema
        self._conn = None
        self._connected = False

    def connect(self) -> bool:
        """Establish connection to Db2."""
        if not IBM_DB_AVAILABLE:
            logger.error("ibm_db package is not installed.")
            return False
        try:
            self._conn = ibm_db.connect(self.connection_string, "", "")
            if self._conn:
                self._connected = True
                # Set schema
                stmt = ibm_db.exec_immediate(
                    self._conn, f"SET CURRENT SCHEMA = '{self.schema}'"
                )
                logger.info("Connected to IBM Db2 successfully.")
                return True
            return False
        except Exception as e:
            logger.error(f"Db2 connection failed: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Close the Db2 connection."""
        if self._conn and self._connected:
            try:
                ibm_db.close(self._conn)
                self._connected = False
                logger.info("Disconnected from Db2.")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        if not self._conn or not self._connected:
            return False
        try:
            ibm_db.exec_immediate(self._conn, "VALUES 1")
            return True
        except Exception:
            self._connected = False
            return False

    @property
    def conn(self):
        """Get the raw connection object."""
        return self._conn

    def get_server_info(self) -> dict:
        """Get Db2 server version and info."""
        if not self.is_connected:
            return {"status": "disconnected"}
        try:
            info = ibm_db.server_info(self._conn)
            return {
                "status": "connected",
                "dbms_name": info.DBMS_NAME if info else "Unknown",
                "dbms_ver": info.DBMS_VER if info else "Unknown",
                "db_name": info.DB_NAME if info else "Unknown",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def execute_sql(self, sql: str, params: tuple = None) -> Optional[object]:
        """Execute a parameterized SQL statement."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Db2.")
        try:
            stmt = ibm_db.prepare(self._conn, sql)
            if params:
                for i, param in enumerate(params, 1):
                    ibm_db.bind_param(stmt, i, param)
            ibm_db.execute(stmt)
            return stmt
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            raise

    def execute_immediate(self, sql: str) -> Optional[object]:
        """Execute SQL without parameters (for DDL)."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Db2.")
        return ibm_db.exec_immediate(self._conn, sql)

    def fetch_all(self, stmt) -> list:
        """Fetch all rows from a statement result."""
        rows = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            rows.append(dict(row))
            row = ibm_db.fetch_assoc(stmt)
        return rows

    def commit(self):
        """Commit the current transaction."""
        if self._conn:
            ibm_db.commit(self._conn)

    def rollback(self):
        """Rollback the current transaction."""
        if self._conn:
            ibm_db.rollback(self._conn)

    @contextmanager
    def transaction(self):
        """Context manager for transactions with auto-rollback on error."""
        try:
            # Turn off autocommit
            if self._conn:
                ibm_db.autocommit(self._conn, ibm_db.SQL_AUTOCOMMIT_OFF)
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise
        finally:
            if self._conn:
                ibm_db.autocommit(self._conn, ibm_db.SQL_AUTOCOMMIT_ON)

    def initialize_schema(self, schema_path: str) -> bool:
        """Execute the schema SQL file to create tables."""
        if not self.is_connected:
            return False
        try:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()

            # Split by semicolons, filter comments and empty
            statements = []
            for stmt in schema_sql.split(';'):
                cleaned = stmt.strip()
                # Skip pure comments and empty
                lines = [l for l in cleaned.split('\n')
                         if l.strip() and not l.strip().startswith('--')]
                if lines:
                    statements.append(cleaned)

            for stmt in statements:
                try:
                    ibm_db.exec_immediate(self._conn, stmt)
                    logger.info(f"Executed: {stmt[:60]}...")
                except Exception as e:
                    error_msg = str(e)
                    # Ignore "already exists" errors
                    if "SQL0601N" in error_msg or "SQLSTATE=42710" in error_msg:
                        logger.info(f"Table/index already exists, skipping.")
                    else:
                        logger.warning(f"Schema statement warning: {e}")

            logger.info("Schema initialization complete.")
            return True
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            return False


# Global connection instance (lazily initialized)
_db2_conn: Optional[Db2Connection] = None


def get_db2_connection() -> Db2Connection:
    """Get or create the global Db2 connection."""
    global _db2_conn
    if _db2_conn is None:
        from config.settings import db2_settings
        _db2_conn = Db2Connection(
            connection_string=db2_settings.connection_string,
            schema=db2_settings.schema_name
        )
    return _db2_conn


def test_connection() -> dict:
    """Test the Db2 connection and return status info."""
    conn = get_db2_connection()
    if not conn.is_connected:
        success = conn.connect()
        if not success:
            return {
                "status": "failed",
                "message": "Could not connect to IBM Db2. Check credentials and server status."
            }
    return conn.get_server_info()

