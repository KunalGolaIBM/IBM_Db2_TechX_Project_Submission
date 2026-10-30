"""
Database Connection Manager for IBM Db2
Uses official ibm_db and ibm_db_dbi drivers.
"""
import os
import sys
from contextlib import contextmanager

try:
    import ibm_db
    import ibm_db_dbi
except ImportError as e:
    raise ImportError(
        "Please install the IBM Db2 driver via 'pip install ibm-db' "
        "before running this application."
    ) from e

# Default connection settings (fallback to standard Db2 Community Edition or running IBMDB201)
DB2_HOST = os.getenv("DB2_HOST", "127.0.0.1")
DB2_PORT = os.getenv("DB2_PORT", "50000")
DB2_DATABASE = os.getenv("DB2_DATABASE", "IBMDB201")
DB2_USER = os.getenv("DB2_USER", "dbayush")
DB2_PASSWORD = os.getenv("DB2_PASSWORD", "8844")

def get_connection_string() -> str:
    """Build standard IBM Db2 TCPIP connection string."""
    return (
        f"DATABASE={DB2_DATABASE};"
        f"HOSTNAME={DB2_HOST};"
        f"PORT={DB2_PORT};"
        f"PROTOCOL=TCPIP;"
        f"UID={DB2_USER};"
        f"PWD={DB2_PASSWORD};"
    )

def get_raw_connection():
    """Returns a raw ibm_db connection."""
    conn_str = get_connection_string()
    return ibm_db.connect(conn_str, "", "")

def get_dbi_connection() -> ibm_db_dbi.Connection:
    """Returns an active Python DB-API 2.0 connection using ibm_db_dbi."""
    conn_str = get_connection_string()
    return ibm_db_dbi.connect(conn_str, "", "")

@contextmanager
def db_session():
    """Context manager for safe database cursor execution and automatic commit/rollback."""
    conn = get_dbi_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def execute_query(conn: ibm_db_dbi.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT query and return list of dictionaries with uppercase column keys."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        cols = [desc[0].upper() for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        cursor.close()

def execute_dml(conn: ibm_db_dbi.Connection, sql: str, params: tuple = ()) -> int:
    """Execute INSERT/UPDATE/DELETE statement and commit."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
