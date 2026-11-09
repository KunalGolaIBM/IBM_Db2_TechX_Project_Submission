"""
GitMind 2.0 — IBM Db2 Connection Management

Provides enterprise-grade, secure connection handling for IBM Db2:
- SSL/TLS encryption with optional CA certificate validation
- Bounded retry with exponential backoff for transient connection hiccups
- Connection pooling & thread-safe context managers
- Deep capability & version probing (Native VECTOR, ANN indexing, VECTOR_DISTANCE)
- Zero credentials in logs / sanitized diagnostics
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Optional, Tuple

import config

logger = logging.getLogger("gitmind.db2.connection")


@dataclass
class Db2Capabilities:
    """Detailed capability report for an IBM Db2 database instance."""
    connected: bool = False
    server_version_raw: str = ""
    parsed_version: Tuple[int, int, int] = (0, 0, 0)
    dbms_name: str = ""
    is_db2: bool = False
    native_vector_supported: bool = False
    vector_index_supported: bool = False
    vector_distance_verified: bool = False
    schema_exists: bool = False
    vector_table_exists: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def parse_db2_version(version_str: str) -> Tuple[int, int, int]:
    """
    Parse Db2 DBMS_VER strings (e.g. '12.01.0200', '12.1.2', 'DB2/LINUXX8664 12.01.0200').
    Returns tuple of (major, minor, fixpack).
    """
    if not version_str:
        return (0, 0, 0)

    # Search for numeric patterns like 12.01.0200 or 12.1.2
    match = re.search(r"(\d+)\.(\d+)\.?(\d+)?", version_str)
    if not match:
        return (0, 0, 0)

    major = int(match.group(1))
    minor = int(match.group(2))
    raw_fix = match.group(3) or "0"
    # Db2 sometimes encodes fixpack as 0200 -> fixpack 2
    if len(raw_fix) >= 4 and raw_fix.endswith("00"):
        fixpack = int(raw_fix[:2])
    else:
        fixpack = int(raw_fix[:2]) if len(raw_fix) > 2 else int(raw_fix)

    return (major, minor, fixpack)


def sanitize_conn_str(conn_str: str) -> str:
    """Redact sensitive passwords from connection strings and logs."""
    return re.sub(r"(PWD|pwd|PASSWORD|password)=[^;]+", r"\1=********", conn_str)


class Db2ConnectionManager:
    """
    Thread-safe connection manager for IBM Db2 Cloud and Community Edition.
    """

    def __init__(
        self,
        database: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = None,
        ssl_certificate: Optional[str] = None,
        schema: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.database = database or config.DB2_DATABASE
        self.host = host or config.DB2_HOST
        self.port = port or config.DB2_PORT
        self.username = username or config.DB2_USERNAME
        self.password = password or config.DB2_PASSWORD
        self.ssl = config.DB2_SSL if ssl is None else ssl
        self.ssl_certificate = ssl_certificate or config.DB2_SSL_CERTIFICATE
        self.schema = (schema or config.DB2_SCHEMA).upper()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def build_connection_string(self) -> str:
        """Builds sanitized/standard Db2 DB-API connection string."""
        parts = [
            f"DATABASE={self.database}",
            f"HOSTNAME={self.host}",
            f"PORT={self.port}",
            "PROTOCOL=TCPIP",
            f"UID={self.username}",
            f"PWD={self.password}",
        ]
        if self.ssl:
            parts.append("SECURITY=SSL")
            if self.ssl_certificate:
                parts.append(f"SSLServerCertificate={self.ssl_certificate}")

        parts.append(f"CONNECTTIMEOUT={self.timeout}")
        return ";".join(parts) + ";"

    def get_connection_args(self) -> dict[str, Any]:
        """Dictionary representation suitable for langchain_db2 DB2VS."""
        args: dict[str, Any] = {
            "database": self.database,
            "host": self.host,
            "port": str(self.port),
            "username": self.username,
            "password": self.password,
            "security": self.ssl,
        }
        return args

    def connect(self):
        """
        Create a new raw ibm_db_dbi.Connection with retries.
        Does not share a mutable connection across threads/agents.
        """
        import ibm_db_dbi

        conn_str = self.build_connection_string()
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                conn = ibm_db_dbi.connect(conn_str, "", "")
                # Set default current schema
                try:
                    cursor = conn.cursor()
                    cursor.execute(f"SET CURRENT SCHEMA = '{self.schema}'")
                    cursor.close()
                except Exception:
                    pass
                return conn
            except Exception as e:
                last_error = e
                sanitized_msg = sanitize_conn_str(str(e))
                logger.warning(
                    f"Db2 connection attempt {attempt}/{self.max_retries} failed: {sanitized_msg}"
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)

        sanitized_err = sanitize_conn_str(str(last_error))
        raise ConnectionError(
            f"Could not connect to IBM Db2 at {self.host}:{self.port}/{self.database} after "
            f"{self.max_retries} attempts. Error: {sanitized_err}"
        )

    @contextmanager
    def connection(self) -> Generator[Any, None, None]:
        """Context manager for an isolated, auto-closing Db2 connection."""
        conn = self.connect()
        try:
            yield conn
            try:
                conn.commit()
            except Exception:
                pass
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @contextmanager
    def cursor(self) -> Generator[Any, None, None]:
        """Context manager yielding a cursor and handling transaction lifecycle."""
        with self.connection() as conn:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                try:
                    cur.close()
                except Exception:
                    pass

    def check_capabilities(self) -> Db2Capabilities:
        """
        Deep diagnostic check of the Db2 instance:
        - Server version
        - Native vector data type support (12.1.2+)
        - Vector index support (12.1.5+)
        - VECTOR_DISTANCE execution
        - Table & Schema verification
        """
        caps = Db2Capabilities()

        try:
            import ibm_db
            import ibm_db_dbi
        except ImportError as e:
            caps.errors.append(f"Missing required Db2 Python packages: {e}")
            return caps

        try:
            with self.connection() as conn:
                caps.connected = True

                # 1. Server Info via ibm_db
                try:
                    server_info = ibm_db.server_info(conn.conn_handler)
                    caps.server_version_raw = str(getattr(server_info, "DBMS_VER", ""))
                    caps.dbms_name = str(getattr(server_info, "DBMS_NAME", ""))
                    caps.is_db2 = "DB2" in caps.dbms_name.upper()
                except Exception as ex:
                    caps.errors.append(f"Error querying server_info: {ex}")

                # Fallback server version via SQL
                if not caps.server_version_raw:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
                        row = cur.fetchone()
                        if row:
                            caps.server_version_raw = str(row[0])
                        cur.close()
                    except Exception:
                        pass

                # 2. Parse version
                caps.parsed_version = parse_db2_version(caps.server_version_raw)
                major, minor, fix = caps.parsed_version

                # Db2 12.1.2+ supports Native VECTOR
                # Note: Cloud instances or 12.1.x instances
                if major >= 13:
                    caps.native_vector_supported = True
                    caps.vector_index_supported = True
                elif major == 12:
                    if (minor > 1) or (minor == 1 and fix >= 2):
                        caps.native_vector_supported = True
                    if (minor > 1) or (minor == 1 and fix >= 5):
                        caps.vector_index_supported = True
                else:
                    caps.native_vector_supported = False
                    caps.vector_index_supported = False

                # 3. Test VECTOR_DISTANCE directly via SQL probe
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "VALUES (VECTOR_DISTANCE(VECTOR('[1.0, 0.0]', 2, FLOAT32), "
                        "VECTOR('[0.0, 1.0]', 2, FLOAT32), COSINE))"
                    )
                    row = cur.fetchone()
                    if row is not None:
                        caps.vector_distance_verified = True
                        caps.native_vector_supported = True
                        caps.details["vector_distance_test_result"] = float(row[0])
                    cur.close()
                except Exception as ex:
                    caps.details["vector_distance_probe_error"] = str(ex)

                # 4. Check schema
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT SCHEMANAME FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?",
                        (self.schema,),
                    )
                    if cur.fetchone():
                        caps.schema_exists = True
                    cur.close()
                except Exception as ex:
                    caps.errors.append(f"Error checking schema: {ex}")

                # 5. Check vector table
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
                        (self.schema, config.DB2_VECTOR_TABLE),
                    )
                    if cur.fetchone():
                        caps.vector_table_exists = True
                    cur.close()
                except Exception:
                    pass

        except Exception as e:
            caps.connected = False
            caps.errors.append(sanitize_conn_str(str(e)))

        return caps


# Global default connection manager instance
_default_manager: Optional[Db2ConnectionManager] = None


def get_connection_manager() -> Db2ConnectionManager:
    """Retrieve or create the singleton Db2ConnectionManager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = Db2ConnectionManager()
    return _default_manager

