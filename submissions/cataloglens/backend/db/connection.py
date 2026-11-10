"""
IBM Db2 Database Connection Manager.
Handles real connection lifecycle, parameter assembly, test routines,
and safe parameterized query execution against IBM Db2 LUW.
"""
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("CatalogLens.Db2Connection")

# Attempt importing the official ibm_db driver
try:
    import ibm_db
    IBM_DB_AVAILABLE = True
except (ImportError, OSError, Exception):
    ibm_db = None
    IBM_DB_AVAILABLE = False


class Db2ConnectionManager:
    """
    Manages connections to IBM Db2 LUW databases.
    Implements safe query execution, credential masking, and connection testing.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50000,
        database: str = "SAMPLE",
        username: str = "db2inst1",
        password: str = "",
        security: str = "",
        timeout: int = 15,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.security = security
        self.timeout = timeout
        self._conn = None

    @staticmethod
    def is_driver_available() -> bool:
        """Returns True if the native ibm_db driver is installed."""
        return IBM_DB_AVAILABLE

    def build_connection_string(self, mask_password: bool = False) -> str:
        """
        Builds the standard Db2 connection string.
        Optionally masks credentials for safe logging.
        """
        pwd = "********" if mask_password else self.password
        conn_str = (
            f"DATABASE={self.database};"
            f"HOSTNAME={self.host};"
            f"PORT={self.port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.username};"
            f"PWD={pwd};"
        )
        if self.security:
            conn_str += f"SECURITY={self.security};"
        return conn_str

    def connect(self) -> Any:
        """
        Establishes a live connection using ibm_db.connect().
        Raises RuntimeError if the driver is missing or if connection fails.
        """
        if not IBM_DB_AVAILABLE:
            raise RuntimeError(
                "The 'ibm_db' Python driver is not installed on this system. "
                "Install it using 'pip install ibm_db' with appropriate C runtime libraries."
            )

        conn_str = self.build_connection_string(mask_password=False)
        try:
            conn = ibm_db.connect(conn_str, "", "")
            self._conn = conn
            logger.info("Successfully established connection to IBM Db2 at %s:%s/%s", self.host, self.port, self.database)
            return conn
        except Exception as e:
            safe_str = self.build_connection_string(mask_password=True)
            err_msg = str(e)
            try:
                db2_err = ibm_db.conn_errormsg()
                if db2_err:
                    err_msg += f" (Db2 Error: {db2_err})"
            except Exception:
                pass
            logger.error("Failed to connect to Db2 [%s]: %s", safe_str, err_msg)
            raise ConnectionError(f"Could not connect to Db2 at {self.host}:{self.port}/{self.database}: {err_msg}")

    def test_connection(self) -> Dict[str, Any]:
        """
        Performs a verifiable connection test against IBM Db2.
        Executes 'SELECT 1 FROM SYSIBM.SYSDUMMY1' to verify operational readiness.
        Does NOT report success unless a query genuinely executes.
        """
        if not IBM_DB_AVAILABLE:
            return {
                "success": False,
                "driver_installed": False,
                "message": (
                    "The official 'ibm_db' driver is not installed in the Python environment. "
                    "For local evaluation without a live Db2 instance, CatalogLens provides "
                    "a fully functional built-in Enterprise Demonstration Database."
                ),
                "host": self.host,
                "database": self.database,
            }

        try:
            conn = self.connect()
            # Test query execution
            stmt = ibm_db.exec_immediate(conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
            row = ibm_db.fetch_tuple(stmt)
            ibm_db.close(conn)
            self._conn = None
            return {
                "success": True,
                "driver_installed": True,
                "message": f"Successfully connected to IBM Db2 database '{self.database}' at {self.host}:{self.port}.",
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "username": self.username,
            }
        except Exception as e:
            return {
                "success": False,
                "driver_installed": True,
                "message": f"Db2 Connection failed: {str(e)}",
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "username": self.username,
            }

    def execute_query(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
        """
        Safely executes a parameterized SQL query against Db2.
        Returns a list of dictionaries with column names as keys.
        """
        if not self._conn:
            self.connect()

        try:
            stmt = ibm_db.prepare(self._conn, sql)
            if params:
                ibm_db.execute(stmt, params)
            else:
                ibm_db.execute(stmt)

            results: List[Dict[str, Any]] = []
            row = ibm_db.fetch_assoc(stmt)
            while row:
                # Clean up whitespace from Db2 CHAR types
                cleaned_row = {
                    k.upper(): (v.strip() if isinstance(v, str) else v)
                    for k, v in row.items()
                }
                results.append(cleaned_row)
                row = ibm_db.fetch_assoc(stmt)

            return results
        except Exception as e:
            logger.error("Query execution error on SQL [%s]: %s", sql[:80], str(e))
            raise

    def close(self):
        """Closes any active connection."""
        if self._conn and IBM_DB_AVAILABLE:
            try:
                ibm_db.close(self._conn)
            except Exception:
                pass
            self._conn = None
