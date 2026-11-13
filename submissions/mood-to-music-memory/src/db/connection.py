"""
src/db/connection.py
--------------------
Shared Db2 connection factory.
Call get_connection() to obtain a live ibm_db connection.
Always call ibm_db.close(conn) when done, or use it as a context manager
via the ConnectionManager helper below.
"""

import os
import ibm_db
from dotenv import load_dotenv

load_dotenv()

SCHEMA = "MOODMUSIC"


def _required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _dsn() -> str:
    return (
        f"DATABASE={_required('DB2_DATABASE')};"
        f"HOSTNAME={_required('DB2_HOST')};"
        f"PORT={_required('DB2_PORT')};"
        "PROTOCOL=TCPIP;"
        f"UID={_required('DB2_USER')};"
        f"PWD={_required('DB2_PASSWORD')};"
    )


def get_connection():
    """Return a live ibm_db connection. Caller is responsible for closing it."""
    conn = ibm_db.connect(_dsn(), "", "")
    ibm_db.exec_immediate(conn, f"SET CURRENT SCHEMA {SCHEMA}")
    return conn


class ConnectionManager:
    """Context manager wrapper around ibm_db connection."""

    def __enter__(self):
        self._conn = get_connection()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            ibm_db.close(self._conn)
        except Exception:
            pass
        return False  # do not suppress exceptions

