"""IBM Db2 access: the native ibm_db driver for health checks and raw prepared statements,
and the ibm_db_sa SQLAlchemy dialect for the ORM."""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings

logger = logging.getLogger("neighbourhood_safety.db2")


class Db2Adapter:
    """Connection settings, health probing and parameterised SQL for IBM Db2."""

    def __init__(self):
        self.host = settings.DB2_HOST
        self.port = settings.DB2_PORT
        self.database = settings.DB2_DATABASE
        self.user = settings.DB2_USER
        self.password = settings.DB2_PASSWORD
        self.security = (settings.DB2_SECURITY or "").upper()
        # Schema holding the application tables. Set it when the app connects as a
        # least-privilege user whose own default schema is different (see db/least_privilege.sql).
        self.schema = (settings.DB2_SCHEMA or "").upper()

    # ---- native ibm_db -----------------------------------------------------------------------
    def build_connection_string(self) -> str:
        parts = [
            f"DATABASE={self.database}", f"HOSTNAME={self.host}", f"PORT={self.port}",
            "PROTOCOL=TCPIP", f"UID={self.user}", f"PWD={self.password}",
        ]
        if self.security == "SSL":
            parts.append("SECURITY=SSL")
        if self.schema:
            parts.append(f"CURRENTSCHEMA={self.schema}")
        return ";".join(parts) + ";"

    def test_connection(self) -> Dict[str, Any]:
        """Open a native ibm_db connection and read the server time and version from SYSIBM.SYSDUMMY1."""
        if not self.host or not self.database:
            return {"connected": False, "error": "Db2 configuration incomplete (DB2_HOST or DB2_DATABASE missing)."}
        try:
            import ibm_db
        except ImportError:
            return {"connected": False, "error": "The ibm_db driver is not installed. Run 'pip install ibm_db'."}

        conn = None
        try:
            conn = ibm_db.connect(self.build_connection_string(), "", "")
            stmt = ibm_db.exec_immediate(conn, "SELECT CURRENT TIMESTAMP, CURRENT SCHEMA FROM SYSIBM.SYSDUMMY1")
            row = ibm_db.fetch_tuple(stmt)
            server = ibm_db.server_info(conn)  # driver metadata: needs no database privilege
            return {
                "connected": True,
                "database": self.database,
                "host": self.host,
                "port": self.port,
                "server_time": str(row[0]) if row else None,
                "server_version": f"{server.DBMS_NAME} {server.DBMS_VER}" if server else None,
                "current_schema": row[1].strip() if row and row[1] else None,
                "status": "Verified connection to IBM Db2",
            }
        except Exception as e:
            err_msg = str(e)
            try:
                native = ibm_db.conn_errormsg()
                if native:
                    err_msg += f" [Db2: {native}]"
            except Exception:
                pass
            logger.error("Db2 connection test failed: %s", err_msg)
            return {"connected": False, "error": err_msg, "database": self.database, "host": self.host}
        finally:
            if conn is not None:
                ibm_db.close(conn)

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Run a parameterised SELECT with ibm_db.prepare/execute (no string-built SQL)."""
        import ibm_db
        conn = ibm_db.connect(self.build_connection_string(), "", "")
        try:
            stmt = ibm_db.prepare(conn, sql)
            if not stmt:
                raise RuntimeError(f"Db2 prepare error: {ibm_db.conn_errormsg(conn)}")
            ibm_db.execute(stmt, params) if params else ibm_db.execute(stmt)
            rows, row = [], ibm_db.fetch_assoc(stmt)
            while row:
                rows.append(dict(row))
                row = ibm_db.fetch_assoc(stmt)
            return rows
        finally:
            ibm_db.close(conn)

    def execute_non_query(self, sql: str, params: Optional[tuple] = None) -> int:
        """Run a parameterised INSERT/UPDATE/DELETE in an explicit transaction."""
        import ibm_db
        conn = ibm_db.connect(self.build_connection_string(), "", "")
        try:
            ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
            stmt = ibm_db.prepare(conn, sql)
            ibm_db.execute(stmt, params) if params else ibm_db.execute(stmt)
            affected = ibm_db.num_rows(stmt)
            ibm_db.commit(conn)
            return affected
        except Exception:
            ibm_db.rollback(conn)
            raise
        finally:
            ibm_db.close(conn)

    # ---- SQLAlchemy (ibm_db_sa) ---------------------------------------------------------------
    def sqlalchemy_url(self) -> URL:
        query: Dict[str, str] = {}
        if self.security == "SSL":
            query["Security"] = "SSL"
        if self.schema:
            query["CurrentSchema"] = self.schema
        # URL.create escapes credentials, so passwords containing @ : / ? are safe.
        return URL.create("db2+ibm_db", username=self.user, password=self.password, host=self.host,
                          port=self.port, database=self.database, query=query)

    @staticmethod
    def _missing_tables(engine, names: List[str]) -> set:
        """Check the Db2 catalog in CURRENT SCHEMA, so a least-privilege login (whose own schema
        differs from the table owner's) never attempts DDL it is not allowed to run."""
        from sqlalchemy import text
        with engine.connect() as conn:
            present = {r[0] for r in conn.execute(text(
                "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA AND TYPE = 'T'"))}
        return set(names) - present

    def get_session_factory(self):
        """Engine and session factory bound to Db2. Creates missing tables (a least-privilege
        user skips this, because the tables already exist) and seeds the demo data on first run."""
        from backend.app.database.sqlite_adapter import seed_data
        from backend.app.models.entities import Base

        engine = create_engine(self.sqlalchemy_url(), pool_pre_ping=True, pool_size=5, max_overflow=10)
        missing = self._missing_tables(engine, [t.name.upper() for t in Base.metadata.sorted_tables])
        if missing:
            logger.info("Creating Db2 tables: %s", ", ".join(sorted(missing)))
            Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        session = SessionLocal()
        try:
            seed_data(session)
        finally:
            session.close()
        return engine, SessionLocal
