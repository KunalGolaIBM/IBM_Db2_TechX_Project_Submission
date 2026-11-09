import time
import logging
from typing import List, Dict, Any, Tuple, Optional
from app.config import settings

logger = logging.getLogger("finsight.db")

class Db2Manager:
    def __init__(self):
        self._conn = None
        self._conn_str = (
            f"DATABASE={settings.db2_database};"
            f"HOSTNAME={settings.db2_host};"
            f"PORT={settings.db2_port};"
            f"PROTOCOL=TCPIP;"
            f"UID={settings.db2_user};"
            f"PWD={settings.db2_password};"
        )

    def get_connection(self):
        """Returns active connection or establishes a new one."""
        import ibm_db
        if self._conn is not None:
            try:
                # Test connection is alive
                if ibm_db.active(self._conn):
                    return self._conn
            except Exception:
                self._conn = None

        try:
            self._conn = ibm_db.connect(self._conn_str, "", "")
            return self._conn
        except Exception as e:
            logger.error("Failed to connect to IBM Db2 FINDB: %s", e)
            raise ConnectionError(f"IBM Db2 Connection Failed: {e}")

    def execute_query(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
        """Executes a parameterized SELECT query and returns rows as dictionaries."""
        import ibm_db
        conn = self.get_connection()
        stmt = ibm_db.prepare(conn, sql)
        if not stmt:
            raise RuntimeError(f"Db2 prepare failed: {ibm_db.stmt_errormsg()}")

        if params:
            res = ibm_db.execute(stmt, params)
        else:
            res = ibm_db.execute(stmt)

        if not res:
            raise RuntimeError(f"Db2 query execution failed: {ibm_db.stmt_errormsg()}")

        rows = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            # Normalize keys to lowercase for consistent access
            normalized_row = {k.lower(): v for k, v in row.items()}
            rows.append(normalized_row)
            row = ibm_db.fetch_assoc(stmt)

        ibm_db.free_result(stmt)
        return rows

    def execute_statement(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> int:
        """Executes a parameterized statement (INSERT/UPDATE/DELETE) and returns affected rows."""
        import ibm_db
        conn = self.get_connection()
        stmt = ibm_db.prepare(conn, sql)
        if not stmt:
            raise RuntimeError(f"Db2 prepare failed: {ibm_db.stmt_errormsg()}")

        if params:
            res = ibm_db.execute(stmt, params)
        else:
            res = ibm_db.execute(stmt)

        if not res:
            raise RuntimeError(f"Db2 statement execution failed: {ibm_db.stmt_errormsg()}")

        affected = ibm_db.num_rows(stmt)
        ibm_db.free_result(stmt)
        return affected

    def execute_transaction_batch(self, operations: List[Tuple[str, Tuple[Any, ...]]]) -> int:
        """Executes a list of (sql, params) statements inside a single transaction."""
        import ibm_db
        conn = self.get_connection()
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        total_affected = 0
        try:
            for sql, params in operations:
                stmt = ibm_db.prepare(conn, sql)
                if not stmt:
                    raise RuntimeError(f"Db2 prepare failed: {ibm_db.stmt_errormsg()}")
                res = ibm_db.execute(stmt, params) if params else ibm_db.execute(stmt)
                if not res:
                    raise RuntimeError(f"Db2 batch statement execution failed: {ibm_db.stmt_errormsg()}")
                total_affected += ibm_db.num_rows(stmt)
                ibm_db.free_result(stmt)
            ibm_db.commit(conn)
            return total_affected
        except Exception as e:
            try:
                ibm_db.rollback(conn)
            except Exception as rb_err:
                logger.error("Failed to rollback Db2 transaction: %s", rb_err)
            raise e
        finally:
            try:
                ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
            except Exception:
                pass

    def health_check(self) -> Dict[str, Any]:
        """Runs a health check against Db2 and returns status, latency, and server details."""
        import ibm_db
        t0 = time.time()
        conn = self.get_connection()
        server_info = ibm_db.server_info(conn)
        
        # Count transactions
        stmt = ibm_db.exec_immediate(conn, "SELECT count(*) FROM FINSIGHT.TRANSACTIONS")
        row = ibm_db.fetch_tuple(stmt)
        tx_count = row[0] if row else 0
        ibm_db.free_result(stmt)

        latency = (time.time() - t0) * 1000.0
        return {
            "status": "UP",
            "database": settings.db2_database,
            "server_version": f"{server_info.DBMS_NAME} {server_info.DBMS_VER}",
            "latency_ms": round(latency, 2),
            "total_transactions": tx_count
        }

db_manager = Db2Manager()
