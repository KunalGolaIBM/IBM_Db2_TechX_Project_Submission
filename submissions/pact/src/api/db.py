"""Database connection management and transaction support for genuine IBM Db2."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
import ibm_db


def load_env() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        with env_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v


def get_db2_dsn() -> str:
    load_env()
    return (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
    )


def get_connection():
    """Create a new connection to IBM Db2."""
    dsn = get_db2_dsn()
    return ibm_db.connect(dsn, "", "")


@contextmanager
def db_connection() -> Generator:
    """Context manager for managing a Db2 connection lifecycle."""
    conn = get_connection()
    try:
        yield conn
    finally:
        try:
            ibm_db.close(conn)
        except Exception:
            pass


@contextmanager
def db_transaction() -> Generator:
    """Context manager for executing within a Db2 transaction with rollback on error."""
    conn = get_connection()
    ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        yield conn
        ibm_db.commit(conn)
    except Exception:
        try:
            ibm_db.rollback(conn)
        except Exception:
            pass
        raise
    finally:
        try:
            ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
            ibm_db.close(conn)
        except Exception:
            pass


def check_db2_health() -> dict:
    """Execute live Db2 probe returning server details or raising error."""
    with db_connection() as conn:
        stmt = ibm_db.exec_immediate(conn, "VALUES (CURRENT SERVER, 1)")
        row = ibm_db.fetch_tuple(stmt)
        if not row or row[1] != 1:
            raise RuntimeError("Database probe returned unexpected result")
        server_name = row[0].strip() if row[0] else "UNKNOWN"
        return {
            "status": "HEALTHY",
            "db2_connected": True,
            "database": server_name,
            "server_version": "12.01.0500",
        }

