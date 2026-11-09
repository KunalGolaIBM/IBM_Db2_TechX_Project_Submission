import logging
from typing import Optional, Any, List, Dict
from backend.app.core.config import settings

logger = logging.getLogger("cloud_loop.db2")

class Db2ConnectionManager:
    """
    Manages connections and transactions to IBM Db2 Enterprise.
    Gracefully handles environments where native C-extension drivers
    are blocked by operating system execution policies.
    """
    def __init__(self):
        self._driver = None
        self._driver_loaded = False
        self._driver_error: Optional[str] = None
        self._is_connected = False

    def load_driver(self):
        if self._driver_loaded:
            return self._driver
        try:
            import ibm_db
            self._driver = ibm_db
            self._driver_loaded = True
            logger.info("IBM Db2 native driver (ibm_db) loaded successfully.")
        except Exception as e:
            self._driver_loaded = True
            self._driver_error = str(e)
            logger.warning(
                f"IBM Db2 driver load skipped or blocked by system policy: {e}. "
                "Backend will operate via unified repository fallback."
            )
        return self._driver

    @property
    def status(self) -> Dict[str, Any]:
        driver = self.load_driver()
        return {
            "driver_available": driver is not None,
            "driver_error": self._driver_error,
            "configured": settings.is_db2_configured,
            "database": settings.DB2_DATABASE,
            "hostname": settings.DB2_HOSTNAME or "not_configured",
            "connected": self._is_connected,
        }

    def execute_query(self, sql: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a parameterized SQL query against IBM Db2.
        Protects against SQL injection via native prepared statements.
        """
        driver = self.load_driver()
        if not driver or not settings.is_db2_configured:
            raise RuntimeError(f"Db2 unavailable: {self._driver_error or 'Credentials unconfigured'}")

        dsn = settings.db2_dsn
        conn = None
        try:
            conn = driver.connect(dsn, "", "")
            stmt = driver.prepare(conn, sql)
            if params:
                for idx, param in enumerate(params, start=1):
                    driver.bind_param(stmt, idx, param)
            driver.execute(stmt)

            results = []
            row = driver.fetch_assoc(stmt)
            while row:
                results.append(dict(row))
                row = driver.fetch_assoc(stmt)
            return results
        except Exception as e:
            logger.error(f"Db2 query execution failed: {e}")
            raise
        finally:
            if conn and driver:
                try:
                    driver.close(conn)
                except Exception:
                    pass

    def execute_non_query(self, sql: str, params: List[Any] = None) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query in a transactional scope.
        """
        driver = self.load_driver()
        if not driver or not settings.is_db2_configured:
            raise RuntimeError(f"Db2 unavailable: {self._driver_error or 'Credentials unconfigured'}")

        dsn = settings.db2_dsn
        conn = None
        try:
            conn = driver.connect(dsn, "", "")
            stmt = driver.prepare(conn, sql)
            if params:
                for idx, param in enumerate(params, start=1):
                    driver.bind_param(stmt, idx, param)
            driver.execute(stmt)
            return driver.num_rows(stmt)
        except Exception as e:
            logger.error(f"Db2 non-query execution failed: {e}")
            raise
        finally:
            if conn and driver:
                try:
                    driver.close(conn)
                except Exception:
                    pass

db2_manager = Db2ConnectionManager()

