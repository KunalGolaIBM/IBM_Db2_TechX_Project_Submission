"""Small, explicit ibm_db connection and query helpers."""
from contextlib import contextmanager
from typing import Any, Iterator

from src.config import Settings, get_settings


class DatabaseUnavailable(RuntimeError):
    """Raised when the configured IBM Db2 server cannot be reached."""


def connect(settings: Settings | None = None):
    settings = settings or get_settings()
    try:
        import ibm_db
    except ModuleNotFoundError as exc:
        if exc.name != "ibm_db":
            raise DatabaseUnavailable("The IBM Db2 driver is present, but one of its dependencies could not be loaded.") from exc
        raise DatabaseUnavailable("The ibm_db driver is not installed. Install requirements.txt.") from exc
    except ImportError as exc:
        raise DatabaseUnavailable("The ibm_db native driver could not be loaded. Check the Python/driver compatibility and device application-control policy.") from exc
    connection = None
    try:
        connection = ibm_db.connect(settings.connection_string(), "", "")
        if not connection:
            raise DatabaseUnavailable("IBM Db2 rejected the connection. Check the host, database, user and password.")
        schema = settings.db2_schema
        if not schema.replace("_", "").isalnum():
            raise DatabaseUnavailable("DB2_SCHEMA must be a simple SQL identifier.")
        ibm_db.exec_immediate(connection, f'SET CURRENT SCHEMA = "{schema.upper()}"')
        return connection
    except DatabaseUnavailable:
        if connection is not None:
            try: ibm_db.close(connection)
            except Exception: pass
        raise
    except Exception as exc:
        if connection is not None:
            try: ibm_db.close(connection)
            except Exception: pass
        # Driver diagnostics can include connection details; expose only a generic actionable message.
        raise DatabaseUnavailable("Could not connect to IBM Db2. Check that the server is running and the .env settings are correct.") from exc


@contextmanager
def connection(settings: Settings | None = None) -> Iterator[Any]:
    conn = connect(settings)
    try:
        yield conn
    finally:
        try:
            import ibm_db
            ibm_db.close(conn)
        except Exception:
            pass


def test_connection(settings: Settings | None = None) -> dict[str, Any]:
    with connection(settings) as conn:
        import ibm_db
        stmt = ibm_db.exec_immediate(conn, "SELECT 1 AS CONNECTED FROM SYSIBM.SYSDUMMY1")
        row = ibm_db.fetch_assoc(stmt)
        return {"connected": bool(row), "database": (settings or get_settings()).db2_database}


def query_dataframe(sql: str, params: tuple[Any, ...] = (), settings: Settings | None = None):
    """Execute an already validated read query and return a DataFrame plus elapsed ms."""
    import time

    start = time.perf_counter()
    with connection(settings) as conn:
        import ibm_db
        import pandas as pd
        stmt = ibm_db.prepare(conn, sql)
        if params:
            ibm_db.execute(stmt, params)
        else:
            ibm_db.execute(stmt)
        columns = [ibm_db.field_name(stmt, i) for i in range(ibm_db.num_fields(stmt))]
        rows = []
        limit = (settings or get_settings()).db2_max_rows
        while len(rows) < limit:
            row = ibm_db.fetch_tuple(stmt)
            if row is False:
                break
            rows.append(row)
        return pd.DataFrame(rows, columns=columns), round((time.perf_counter() - start) * 1000, 1)
