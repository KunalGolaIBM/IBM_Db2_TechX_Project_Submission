"""IBM Db2 connection management using ibm_db driver."""

import logging
import os
import sys
from typing import Optional

# On Windows Python >= 3.8, explicitly add clidriver/bin to the DLL search directory
if sys.platform == "win32":
    potential_paths = [
        os.path.join(sys.prefix, "Lib", "site-packages", "clidriver", "bin"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".venv", "Lib", "site-packages", "clidriver", "bin"),
    ]
    for p in potential_paths:
        abs_p = os.path.abspath(p)
        if os.path.isdir(abs_p):
            try:
                os.add_dll_directory(abs_p)
                os.environ["PATH"] = abs_p + os.pathsep + os.environ.get("PATH", "")
            except Exception:
                pass

try:
    import ibm_db  # type: ignore
except ImportError:
    ibm_db = None  # type: ignore

try:
    from config import settings
except ImportError:
    from backend.config import settings

logger = logging.getLogger(__name__)

_connection = None


def get_connection():
    """Get or create a Db2 connection."""
    global _connection
    if ibm_db is None:
        raise ConnectionError("ibm_db driver is not installed")

    if _connection is not None:
        try:
            # Test if connection is still alive
            ibm_db.active(_connection)
            return _connection
        except Exception:
            _connection = None

    try:
        conn = ibm_db.connect(settings.db2_connection_string, "", "")
        if conn:
            _connection = conn
            # Set schema
            ibm_db.exec_immediate(conn, f"SET SCHEMA {settings.db2_schema}")
            logger.info("Connected to IBM Db2 at %s:%s/%s", settings.db2_host, settings.db2_port, settings.db2_database)
            return conn
        raise ConnectionError("ibm_db.connect returned falsy value")
    except Exception as exc:
        logger.error("Failed to connect to IBM Db2: %s", exc)
        raise ConnectionError(f"Cannot connect to IBM Db2: {exc}") from exc


def close_connection():
    """Close the active Db2 connection."""
    global _connection
    if _connection is not None:
        try:
            if ibm_db is not None:
                ibm_db.close(_connection)
            logger.info("Db2 connection closed.")
        except Exception as exc:
            logger.warning("Error closing Db2 connection: %s", exc)
        finally:
            _connection = None


def health_check() -> dict:
    """Check Db2 connectivity by running a simple query."""
    if ibm_db is None:
        return {"status": "disconnected", "message": "ibm_db driver is not installed"}

    try:
        conn = get_connection()
        stmt = ibm_db.exec_immediate(conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
        row = ibm_db.fetch_tuple(stmt)
        if row and row[0] == 1:
            return {"status": "connected", "host": settings.db2_host, "database": settings.db2_database}
        return {"status": "error", "message": "Unexpected health check result"}
    except Exception as exc:
        return {"status": "disconnected", "message": str(exc)}


def execute_sql(sql: str, params: Optional[tuple] = None) -> Optional[object]:
    """Execute a SQL statement with optional parameters using prepared statements."""
    conn = get_connection()
    if params:
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, params)
        return stmt
    else:
        return ibm_db.exec_immediate(conn, sql)


def fetch_one(sql: str, params: Optional[tuple] = None) -> Optional[dict]:
    """Execute SQL and fetch a single row as a dictionary."""
    stmt = execute_sql(sql, params)
    if stmt:
        return ibm_db.fetch_assoc(stmt)
    return None


def fetch_all(sql: str, params: Optional[tuple] = None) -> list[dict]:
    """Execute SQL and fetch all rows as a list of dictionaries."""
    stmt = execute_sql(sql, params)
    results = []
    if stmt:
        row = ibm_db.fetch_assoc(stmt)
        while row:
            results.append(row)
            row = ibm_db.fetch_assoc(stmt)
    return results


def commit():
    """Commit the current transaction."""
    conn = get_connection()
    ibm_db.commit(conn)


def rollback():
    """Rollback the current transaction."""
    conn = get_connection()
    ibm_db.rollback(conn)
