import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("db2sentinel.connector")

class Db2Connector:
    """
    Direct Python connector to IBM Db2 using the official ibm_db driver.
    Supports parameterized SQL execution, secure SSL connections,
    health inspection, and transaction management.
    """
    def __init__(self, host: str, port: int, database: str, username: str, password: str, security: str = "NONE", ssl_cert: str = ""):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.security = security
        self.ssl_cert = ssl_cert
        self._conn = None
        self._is_connected = False

    def build_connection_string(self) -> str:
        """Constructs an IBM Db2 CLI connection string."""
        conn_str = (
            f"DATABASE={self.database};"
            f"HOSTNAME={self.host};"
            f"PORT={self.port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.username};"
            f"PWD={self.password};"
        )
        if self.security.upper() == "SSL":
            conn_str += "SECURITY=SSL;"
            if self.ssl_cert:
                conn_str += f"SSLServerCertificate={self.ssl_cert};"
        return conn_str

    def connect(self) -> bool:
        """Attempts connection to the IBM Db2 database."""
        try:
            import ibm_db
            conn_str = self.build_connection_string()
            logger.info(f"Connecting to IBM Db2 at {self.host}:{self.port}/{self.database}...")
            self._conn = ibm_db.connect(conn_str, "", "")
            self._is_connected = True
            logger.info("Successfully established connection to IBM Db2.")
            return True
        except ImportError:
            logger.warning("ibm_db module is not installed or native C runtime failed to load.")
            self._is_connected = False
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to IBM Db2: {e}")
            self._is_connected = False
            return False

    def check_connection(self) -> Dict[str, Any]:
        """Runs a diagnostic query against IBM Db2 to verify live connectivity."""
        if not self._is_connected or not self._conn:
            return {"connected": False, "message": "Db2 connection not initialized", "engine": "IBM Db2"}
        try:
            import ibm_db
            stmt = ibm_db.exec_immediate(self._conn, "SELECT CURRENT TIMESTAMP AS SERVER_TIME, CURRENT SERVER AS DB_NAME FROM SYSIBM.SYSDUMMY1")
            row = ibm_db.fetch_assoc(stmt)
            if row:
                return {
                    "connected": True,
                    "engine": "IBM Db2",
                    "server_time": str(row.get("SERVER_TIME")),
                    "database_name": str(row.get("DB_NAME", self.database)),
                    "host": self.host,
                    "port": self.port,
                    "security": self.security
                }
            return {"connected": True, "engine": "IBM Db2", "message": "Query executed but no metadata returned"}
        except Exception as e:
            self._is_connected = False
            return {"connected": False, "engine": "IBM Db2", "error": str(e)}

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Executes a parameterized SELECT query against IBM Db2."""
        if not self._is_connected or not self._conn:
            raise ConnectionError("IBM Db2 is not connected.")
        import ibm_db
        try:
            stmt = ibm_db.prepare(self._conn, sql)
            if params:
                ibm_db.execute(stmt, params)
            else:
                ibm_db.execute(stmt)
            results = []
            row = ibm_db.fetch_assoc(stmt)
            while row:
                # Normalize column keys to lowercase
                results.append({k.lower(): v for k, v in row.items()})
                row = ibm_db.fetch_assoc(stmt)
            return results
        except Exception as e:
            logger.error(f"Error executing Db2 query [{sql}]: {e}")
            raise

    def execute_statement(self, sql: str, params: Optional[tuple] = None) -> int:
        """Executes a parameterized INSERT/UPDATE/DELETE statement against IBM Db2."""
        if not self._is_connected or not self._conn:
            raise ConnectionError("IBM Db2 is not connected.")
        import ibm_db
        try:
            stmt = ibm_db.prepare(self._conn, sql)
            if params:
                ibm_db.execute(stmt, params)
            else:
                ibm_db.execute(stmt)
            return ibm_db.num_rows(stmt)
        except Exception as e:
            logger.error(f"Error executing Db2 statement [{sql}]: {e}")
            raise

    def close(self):
        """Closes the active IBM Db2 connection."""
        if self._conn:
            try:
                import ibm_db
                ibm_db.close(self._conn)
            except Exception:
                pass
            self._conn = None
            self._is_connected = False
            logger.info("Closed IBM Db2 connection.")
