"""Low-level IBM Db2 connection management.

`ibm_db` opens a native connection per call. AEGIS deliberately uses short-lived
connections managed by context managers so transactions and resource cleanup are
explicit, which is the safest pattern for a small modular monolith.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from typing import Iterator

import ibm_db

from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError, DatabaseOperationError, DatabaseUnavailableError

logger = logging.getLogger(__name__)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


def validate_identifier(value: str) -> str:
    if not _IDENTIFIER.match(value):
        raise ConfigurationError("Invalid database schema identifier.")
    return value.upper()


def _connection_error_message(exc: Exception) -> str:
    # Native Db2 errors can include connection strings. Only SQLSTATE / SQLCODE
    # are logged; credentials are never included.
    sqlstate = getattr(exc, "sqlstate", None)
    sqlcode = getattr(exc, "sqlcode", None)
    parts = []
    if sqlcode is not None:
        parts.append(f"SQLCODE={sqlcode}")
    if sqlstate:
        parts.append(f"SQLSTATE={sqlstate}")
    return " ".join(parts) or "no diagnostic code"


def _connect(settings: Settings):
    if not settings.db2_password:
        raise ConfigurationError(
            "DB2_PASSWORD is not configured. Set it in the environment or .env file."
        )
    try:
        connection = ibm_db.connect(settings.db2_dsn, "", "")
    except Exception as exc:  # ibm_db raises bare Exception subclasses
        logger.error("Db2 connection failed (%s)", _connection_error_message(exc))
        raise DatabaseUnavailableError(
            "IBM Db2 is unreachable. Check the database host, port, and credentials."
        ) from exc
    if not connection:
        raise DatabaseUnavailableError("IBM Db2 returned no connection handle.")
    schema = validate_identifier(settings.db2_schema)
    try:
        ibm_db.exec_immediate(connection, f'SET CURRENT SCHEMA "{schema}"')
        ibm_db.autocommit(connection, ibm_db.SQL_AUTOCOMMIT_OFF)
    except Exception as exc:
        ibm_db.close(connection)
        logger.error("Db2 session setup failed (%s)", _connection_error_message(exc))
        raise DatabaseUnavailableError("IBM Db2 session could not be initialized.") from exc
    return connection


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[object]:
    """Yield a Db2 connection that is always closed."""
    settings = settings or get_settings()
    connection = _connect(settings)
    try:
        yield connection
    finally:
        try:
            ibm_db.close(connection)
        except Exception:  # pragma: no cover - defensive cleanup
            logger.warning("Failed to close Db2 connection cleanly")


@contextmanager
def transaction(settings: Settings | None = None) -> Iterator[object]:
    """Yield a connection wrapped in an explicit commit/rollback transaction."""
    with get_connection(settings) as connection:
        try:
            yield connection
            ibm_db.commit(connection)
        except DatabaseUnavailableError:
            raise
        except Exception:
            try:
                ibm_db.rollback(connection)
            except Exception:  # pragma: no cover - defensive cleanup
                logger.warning("Db2 rollback failed")
            raise


def _prepared_statement(connection, sql: str, params: tuple | list | None = None):
    """Prepare, bind, and execute a statement.

    `ibm_db.exec_immediate(conn, sql, params)` segfaults with parameter markers
    on some macOS/arm64 builds of ibm_db 3.3.0. The prepared-statement API is
    equivalent, safe, and supports typed NULL binding.
    """
    statement = ibm_db.prepare(connection, sql)
    for index, value in enumerate(params or (), start=1):
        ibm_db.bind_param(statement, index, value)
    ibm_db.execute(statement)
    return statement


def query_all(connection, sql: str, params: tuple | list | None = None) -> list[dict]:
    statement = None
    try:
        statement = _prepared_statement(connection, sql, params)
        rows: list[dict] = []
        row = ibm_db.fetch_assoc(statement)
        while row:
            rows.append({key.lower(): value for key, value in row.items()})
            row = ibm_db.fetch_assoc(statement)
        return rows
    except Exception as exc:
        logger.error("Db2 query failed (%s)", _connection_error_message(exc))
        raise DatabaseOperationError("A database query failed.") from exc
    finally:
        if statement is not None:
            try:
                ibm_db.free_stmt(statement)
            except Exception:  # pragma: no cover - defensive cleanup
                logger.warning("Failed to free a Db2 statement")


def execute(connection, sql: str, params: tuple | list | None = None):
    statement = None
    try:
        statement = _prepared_statement(connection, sql, params)
        return statement
    except Exception as exc:
        logger.error("Db2 execute failed (%s)", _connection_error_message(exc))
        raise DatabaseOperationError("A database operation failed.") from exc
    finally:
        if statement is not None:
            try:
                ibm_db.free_stmt(statement)
            except Exception:  # pragma: no cover - defensive cleanup
                logger.warning("Failed to free a Db2 statement")


def insert_returning_id(connection, sql: str, params: tuple | list | None = None) -> int:
    execute(connection, sql, params)
    rows = query_all(connection, "SELECT IDENTITY_VAL_LOCAL() AS id FROM SYSIBM.SYSDUMMY1")
    if not rows or rows[0]["id"] is None:
        raise DatabaseOperationError("Could not determine the inserted row identifier.")
    return int(rows[0]["id"])
