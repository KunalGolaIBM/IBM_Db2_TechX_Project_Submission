import logging
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings

logger = logging.getLogger("neighbourhood_safety.db2")

class Db2Adapter:
    """
    IBM Db2 Database Adapter implementing parameterized queries,
    transaction management, SSL security handling, and health testing via ibm_db.
    """

    def __init__(self):
        self.host = settings.DB2_HOST
        self.port = settings.DB2_PORT
        self.database = settings.DB2_DATABASE
        self.user = settings.DB2_USER
        self.password = settings.DB2_PASSWORD
        self.security = settings.DB2_SECURITY

    def build_connection_string(self) -> str:
        conn_str = (
            f"DATABASE={self.database};"
            f"HOSTNAME={self.host};"
            f"PORT={self.port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.user};"
            f"PWD={self.password};"
        )
        if self.security and self.security.upper() == "SSL":
            conn_str += "SECURITY=SSL;"
        return conn_str

    def test_connection(self) -> Dict[str, Any]:
        """
        Verify connection to IBM Db2 by pinging SYSIBM.SYSDUMMY1.
        Returns a diagnostic dictionary.
        """
        if not self.host or not self.database:
            return {
                "connected": False,
                "error": "Db2 configuration incomplete (DB2_HOST or DB2_DATABASE missing).",
                "database": self.database or "unspecified",
                "host": self.host or "unspecified"
            }

        try:
            import ibm_db
        except ImportError:
            return {
                "connected": False,
                "error": "The 'ibm_db' Python driver is not installed in this environment. Run 'pip install ibm_db'.",
                "driver": "missing"
            }

        conn_str = self.build_connection_string()
        conn = None
        try:
            conn = ibm_db.connect(conn_str, "", "")
            sql = "SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1"
            stmt = ibm_db.exec_immediate(conn, sql)
            row = ibm_db.fetch_assoc(stmt)
            ibm_db.close(conn)
            return {
                "connected": True,
                "database": self.database,
                "host": self.host,
                "port": self.port,
                "server_time": str(row) if row else "OK",
                "status": "Verified connection to IBM Db2"
            }
        except Exception as e:
            err_msg = str(e)
            try:
                native_err = ibm_db.conn_errormsg()
                if native_err:
                    err_msg += f" [Db2 Native Error: {native_err}]"
            except Exception:
                pass
            logger.error(f"Db2 Connection Test Failed: {err_msg}")
            return {
                "connected": False,
                "error": err_msg,
                "database": self.database,
                "host": self.host
            }

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute parameterized query against IBM Db2 with SQL injection protection.
        """
        import ibm_db
        conn_str = self.build_connection_string()
        conn = ibm_db.connect(conn_str, "", "")
        try:
            stmt = ibm_db.prepare(conn, sql)
            if not stmt:
                raise RuntimeError(f"Db2 prepare error: {ibm_db.conn_errormsg(conn)}")

            if params:
                ibm_db.execute(stmt, params)
            else:
                ibm_db.execute(stmt)

            results = []
            row = ibm_db.fetch_assoc(stmt)
            while row:
                results.append(dict(row))
                row = ibm_db.fetch_assoc(stmt)
            return results
        finally:
            ibm_db.close(conn)

    def execute_non_query(self, sql: str, params: Optional[tuple] = None) -> int:
        """
        Execute parameterized insert/update/delete with transaction commit.
        """
        import ibm_db
        conn_str = self.build_connection_string()
        conn = ibm_db.connect(conn_str, "", "")
        try:
            ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
            stmt = ibm_db.prepare(conn, sql)
            if params:
                ibm_db.execute(stmt, params)
            else:
                ibm_db.execute(stmt)
            rows_affected = ibm_db.num_rows(stmt)
            ibm_db.commit(conn)
            return rows_affected
        except Exception as e:
            ibm_db.rollback(conn)
            raise e
        finally:
            ibm_db.close(conn)

    def get_session_factory(self):
        """
        Return a SQLAlchemy engine and session factory bound to IBM Db2 (via ibm_db_sa),
        creating all tables and seeding demo data on first run.
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.app.models.entities import Base
        
        # Build db2 connection uri
        ssl_str = "?security=SSL" if (self.security and self.security.upper() == "SSL") else ""
        db2_uri = f"db2+ibm_db://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}{ssl_str}"
        engine = create_engine(db2_uri, pool_pre_ping=True)
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Seed the same demo personas used in SQLite mode so Db2 mode is usable immediately.
        from backend.app.database.sqlite_adapter import seed_data
        session = SessionLocal()
        try:
            seed_data(session)
        finally:
            session.close()
        return engine, SessionLocal
