"""IBM Db2 Database Connection Management.

Provides connection helpers for native ibm_db and SQLAlchemy,
with automatic Windows DLL resolution for IBM clidriver.
"""
import sys
import os
import site
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Any
import logging

logger = logging.getLogger("db2_connection")

# 1. Automatic IBM clidriver DLL registration on Windows
if sys.platform == "win32":
    # Locate clidriver/bin in virtual environment site-packages
    candidate_paths = []
    for sp in site.getsitepackages():
        candidate_paths.append(Path(sp) / "clidriver" / "bin")
    # Also check relative to Python executable
    candidate_paths.append(Path(sys.prefix) / "Lib" / "site-packages" / "clidriver" / "bin")
    candidate_paths.append(Path(sys.prefix) / "site-packages" / "clidriver" / "bin")

    for clidir in candidate_paths:
        if clidir.is_dir():
            try:
                os.add_dll_directory(str(clidir))
                current_path = os.environ.get("PATH", "")
                if str(clidir) not in current_path:
                    os.environ["PATH"] = f"{clidir};{current_path}"
                logger.info(f"Registered IBM clidriver DLL directory: {clidir}")
                break
            except Exception as e:
                logger.warning(f"Failed to register DLL directory {clidir}: {e}")

try:
    import ibm_db
    import ibm_db_dbi
    HAVE_IBM_DB = True
except ImportError as e:
    HAVE_IBM_DB = False
    logger.warning(f"ibm_db could not be imported: {e}")

from recipe_waste_optimizer.config import settings


class Db2ConnectionManager:
    """Manages active IBM Db2 connections and transactions."""

    def __init__(self, conn_str: str | None = None):
        self.conn_str = conn_str or settings.db2_connection_string

    def get_connection(self):
        """Establish and return an active native ibm_db connection."""
        if not HAVE_IBM_DB:
            raise RuntimeError(
                "ibm_db driver is not installed or failed to load. "
                "Ensure ibm_db and required clidriver DLLs are present."
            )
        try:
            conn = ibm_db.connect(self.conn_str, "", "")
            return conn
        except Exception as e:
            err_msg = ibm_db.conn_errormsg() if HAVE_IBM_DB else str(e)
            raise ConnectionError(f"Failed to connect to IBM Db2 ({settings.DB2_HOST}:{settings.DB2_PORT}/{settings.DB2_DATABASE}): {err_msg}") from e

    @contextmanager
    def cursor(self) -> Generator[Any, None, None]:
        """Context manager yielding a DB-API 2.0 cursor over IBM Db2 connection."""
        if not HAVE_IBM_DB:
            raise RuntimeError("ibm_db driver not available.")
        conn = self.get_connection()
        dbi_conn = ibm_db_dbi.Connection(conn)
        cur = dbi_conn.cursor()
        try:
            yield cur
            dbi_conn.commit()
        except Exception:
            dbi_conn.rollback()
            raise
        finally:
            cur.close()
            dbi_conn.close()

    def test_connection(self) -> dict:
        """Check Db2 connectivity and retrieve system metadata."""
        try:
            conn = self.get_connection()
            server_info = ibm_db.server_info(conn)
            client_info = ibm_db.client_info(conn)
            ibm_db.close(conn)
            return {
                "status": "connected",
                "dbms_name": server_info.DBMS_NAME if hasattr(server_info, "DBMS_NAME") else "IBM Db2",
                "dbms_version": server_info.DBMS_VER if hasattr(server_info, "DBMS_VER") else "Unknown",
                "database": settings.DB2_DATABASE,
                "host": settings.DB2_HOST,
                "port": settings.DB2_PORT
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "host": settings.DB2_HOST,
                "port": settings.DB2_PORT
            }


db_manager = Db2ConnectionManager()
