from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger("db2_connection")

try:
    import ibm_db
    import ibm_db_dbi
    IBM_DB_AVAILABLE = True
except ImportError:
    ibm_db = None
    ibm_db_dbi = None
    IBM_DB_AVAILABLE = False

try:
    from dotenv import find_dotenv, load_dotenv

    _env_path = find_dotenv(usecwd=True)
    if not _env_path:
        _sub_env = Path(__file__).resolve().parents[3] / ".env"
        if _sub_env.exists():
            _env_path = str(_sub_env)
    if _env_path:
        load_dotenv(_env_path, override=False)
    else:
        load_dotenv(override=False)
except ImportError:
    pass


class Db2ConnectionManager:
    """
    Manages connections to IBM Db2 Community Edition / Cloud via native ibm_db.
    Provides an explicit SQLite in-memory fallback for offline test suites,
    CI runners, and local development environments without a live Db2 instance.
    """

    def __init__(self, use_mock: bool | None = None) -> None:
        self.host = os.getenv("DB2_HOST", "").strip()
        self.port = os.getenv("DB2_PORT", "50000").strip()
        self.database = os.getenv("DB2_DATABASE", "testdb").strip()
        self.user = os.getenv("DB2_USER", "db2inst1").strip()
        self.password = os.getenv("DB2_PASSWORD", "").strip()
        self.protocol = os.getenv("DB2_PROTOCOL", "TCPIP").strip()
        self.security = os.getenv("DB2_SECURITY", "").strip()
        self.ssl_cert = os.getenv("DB2_SSL_SERVER_CERTIFICATE", "").strip()
        self.sqlite_path = os.getenv("DB2_SQLITE_PATH", ":memory:").strip()

        env_mock = os.getenv("DB2_USE_MOCK", "").lower() in ("true", "1", "yes")
        self.use_mock = env_mock if use_mock is None else use_mock

        self._active_mode = "uninitialized"
        self._last_error: str | None = None
        self._sqlite_conn: sqlite3.Connection | None = None

        self._initialize()

    @property
    def is_db2_active(self) -> bool:
        return self._active_mode == "ibm_db"

    @property
    def active_mode(self) -> str:
        return self._active_mode

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def build_conn_string(self) -> str:
        """Construct parameterized connection string for IBM Db2."""
        parts = [
            f"DATABASE={self.database}",
            f"HOSTNAME={self.host}",
            f"PORT={self.port}",
            f"PROTOCOL={self.protocol}",
            f"UID={self.user}",
            f"PWD={self.password}",
        ]
        if self.security.upper() == "SSL":
            parts.append("SECURITY=SSL")
            if self.ssl_cert:
                parts.append(f"SSLServerCertificate={self.ssl_cert}")
        return ";".join(parts) + ";"

    def _initialize(self) -> None:
        if self.use_mock or not self.host or self.host.lower() == "mock":
            logger.info("Initializing in SQLite mock mode.")
            self._init_sqlite()
            return

        if not IBM_DB_AVAILABLE:
            msg = "Native ibm_db module is not installed. Falling back to SQLite mock mode."
            logger.warning(msg)
            self._last_error = msg
            self._init_sqlite()
            return

        conn_str = self.build_conn_string()
        try:
            raw_conn = ibm_db.connect(conn_str, "", "")
            ibm_db.close(raw_conn)
            self._active_mode = "ibm_db"
            self._last_error = None
            logger.info("Successfully established connection to IBM Db2 instance at %s:%s", self.host, self.port)
        except Exception as exc:
            msg = f"Failed to connect to IBM Db2 at {self.host}:{self.port}: {exc}"
            logger.warning("%s. Falling back to SQLite mock engine.", msg)
            self._last_error = str(exc)
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        self._active_mode = "sqlite_mock"
        if self._sqlite_conn is None:
            self._sqlite_conn = sqlite3.connect(
                self.sqlite_path,
                check_same_thread=False,
            )
            self._sqlite_conn.row_factory = sqlite3.Row
            self._sqlite_conn.execute("PRAGMA foreign_keys = ON;")

    def check_health(self) -> dict[str, Any]:
        """Probes the active database connection with a standard dummy query."""
        if self._active_mode == "ibm_db":
            try:
                conn_str = self.build_conn_string()
                raw_conn = ibm_db.connect(conn_str, "", "")
                stmt = ibm_db.exec_immediate(raw_conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
                ibm_db.fetch_both(stmt)
                ibm_db.close(raw_conn)
                return {
                    "connected": True,
                    "mode": "ibm_db",
                    "host": f"{self.host}:{self.port}",
                    "database": self.database,
                    "simulated": False,
                    "error": None,
                }
            except Exception as e:
                return {
                    "connected": False,
                    "mode": "ibm_db",
                    "host": f"{self.host}:{self.port}",
                    "database": self.database,
                    "simulated": False,
                    "error": str(e),
                }
        else:
            try:
                if self._sqlite_conn is None:
                    self._init_sqlite()
                cur = self._sqlite_conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.close()
                return {
                    "connected": True,
                    "mode": "sqlite_mock",
                    "database": self.sqlite_path,
                    "simulated": True,
                    "error": self._last_error,
                }
            except Exception as e:
                return {
                    "connected": False,
                    "mode": "sqlite_mock",
                    "simulated": True,
                    "error": str(e),
                }

    @staticmethod
    def map_row(cursor: Any, row: Any) -> dict[str, Any] | None:
        """
        Safely maps a cursor fetch result to a standard dictionary with lowercase keys.
        Handles:
          - sqlite3.Row objects (supports row.keys())
          - ibm_db_dbi tuples (maps cursor.description column names)
          - Standard dictionaries
        """
        if row is None:
            return None
        if hasattr(row, "keys"):
            return {k.lower(): row[k] for k in row.keys()}
        if isinstance(row, dict):
            return {k.lower(): v for k, v in row.items()}
        if cursor and getattr(cursor, "description", None):
            col_names = [col[0].lower() for col in cursor.description]
            return dict(zip(col_names, row))
        raise ValueError(f"Cannot map row without column description: {row}")

    @contextmanager
    def get_cursor(self) -> Generator[Any, None, None]:
        """
        Context manager providing a transactional cursor.
        Ensures explicit commit on success, rollback on error, and proper resource cleanup.
        """
        if self._active_mode == "ibm_db":
            conn_str = self.build_conn_string()
            raw_conn = ibm_db.connect(conn_str, "", "")
            dbi_conn = ibm_db_dbi.Connection(raw_conn)
            cursor = dbi_conn.cursor()
            try:
                yield cursor
                dbi_conn.commit()
            except Exception:
                dbi_conn.rollback()
                raise
            finally:
                cursor.close()
                dbi_conn.close()
                try:
                    ibm_db.close(raw_conn)
                except Exception:
                    pass
        else:
            if self._sqlite_conn is None:
                self._init_sqlite()
            cursor = self._sqlite_conn.cursor()
            try:
                yield cursor
                self._sqlite_conn.commit()
            except Exception:
                self._sqlite_conn.rollback()
                raise
            finally:
                cursor.close()


db_manager = Db2ConnectionManager()
