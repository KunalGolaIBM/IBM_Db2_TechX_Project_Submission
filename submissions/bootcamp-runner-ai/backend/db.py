from __future__ import annotations

from collections.abc import Sequence
import logging
import re
from typing import Any

try:
    import ibm_db
except ImportError:  # pragma: no cover - exercised in environments without Db2
    ibm_db = None


logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised when a Db2 operation fails."""

    def __init__(
        self, message: str, *, sqlstate: str = "", sqlcode: str = "",
        diagnostic: str = "",
    ) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate
        self.sqlcode = sqlcode
        self.diagnostic = diagnostic


class DatabaseUnavailable(DatabaseError):
    """Raised when Db2 cannot be used; callers must expose offline behavior."""


class Db2Client:
    def __init__(self, dsn: str | None) -> None:
        self.dsn = dsn
        self.connection: Any = None

    def connect(self) -> None:
        if not self.dsn or ibm_db is None:
            raise DatabaseUnavailable("Db2 is not configured or ibm_db is unavailable")
        try:
            options: dict[int, int | str] = {
                ibm_db.SQL_ATTR_AUTOCOMMIT: ibm_db.SQL_AUTOCOMMIT_OFF
            }
            self.connection = ibm_db.connect(self.dsn, "", "", options)
        except Exception as exc:
            sqlstate, sqlcode, diagnostic = self._connection_diagnostics()
            logger.error(
                "Db2 connection failed sqlstate=%s sqlcode=%s message=%s",
                sqlstate or "unknown", sqlcode or "unknown", diagnostic or "unknown",
            )
            raise DatabaseUnavailable(
                "Db2 connection failed",
                sqlstate=sqlstate,
                sqlcode=sqlcode,
                diagnostic=diagnostic,
            ) from exc

    def close(self) -> None:
        if self.connection is not None and ibm_db is not None:
            connection = self.connection
            try:
                try:
                    ibm_db.rollback(connection)
                finally:
                    ibm_db.close(connection)
            finally:
                self.connection = None

    def _close_connection(self, connection: Any) -> None:
        try:
            ibm_db.close(connection)
        finally:
            if self.connection is connection:
                self.connection = None

    @staticmethod
    def _sanitize_diagnostic(message: str) -> str:
        return re.sub(
            r"(?i)\b(password|passwd|pwd|token|api[_-]?key|secret|dsn)\b\s*=\s*[^;\s]+",
            r"\1=[REDACTED]",
            message,
        )

    def _diagnostics(self, statement: Any = None) -> tuple[str, str, str]:
        if ibm_db is None:
            return "", "", ""
        state = ""
        code = ""
        message = ""
        try:
            error = getattr(ibm_db, "stmt_error", None)
            if error is not None:
                state = str(error(statement) or "")
        except Exception:
            pass
        try:
            get_sqlcode = getattr(ibm_db, "get_sqlcode", None)
            if get_sqlcode is not None:
                code = str(get_sqlcode() or "")
        except Exception:
            pass
        try:
            error_message = getattr(ibm_db, "stmt_errormsg", None)
            if error_message is not None:
                message = self._sanitize_diagnostic(
                    str(error_message(statement) or "")
                )
        except Exception:
            pass
        return state, code, message

    def _connection_diagnostics(self) -> tuple[str, str, str]:
        if ibm_db is None:
            return "", "", ""
        state = ""
        message = ""
        try:
            error = getattr(ibm_db, "conn_error", None)
            if error is not None:
                state = str(error() or "")
        except Exception:
            pass
        try:
            error_message = getattr(ibm_db, "conn_errormsg", None)
            if error_message is not None:
                message = self._sanitize_diagnostic(str(error_message() or ""))
        except Exception:
            pass
        try:
            get_sqlcode = getattr(ibm_db, "get_sqlcode", None)
            code = str(get_sqlcode() or "") if get_sqlcode is not None else ""
        except Exception:
            code = ""
        return state, code, message

    def _statement_sqlstate(self, statement: Any = None) -> str:
        return self._diagnostics(statement)[0]

    def _is_connection_failure(self, sqlstate: str) -> bool:
        return sqlstate.startswith("08")

    def _rollback_after_failure(self, connection: Any) -> None:
        try:
            if not ibm_db.rollback(connection):
                raise RuntimeError("Db2 rollback failed")
        except Exception as exc:
            try:
                self._close_connection(connection)
            except Exception as close_exc:
                raise RuntimeError("Db2 rollback and close failed") from close_exc
            raise RuntimeError("Db2 rollback failed") from exc

    def _prepare_and_bind(self, sql: str, params: Sequence[Any]) -> Any:
        statement = ibm_db.prepare(self.connection, sql)
        for index, value in enumerate(params, start=1):
            if not ibm_db.bind_param(statement, index, value):
                raise RuntimeError("Db2 parameter binding failed")
        return statement

    def execute(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        if self.connection is None or ibm_db is None:
            raise DatabaseUnavailable("Db2 is offline")
        connection = self.connection
        try:
            statement = self._prepare_and_bind(sql, params)
            if not ibm_db.execute(statement):
                raise RuntimeError("Db2 statement execution failed")
            rows: list[dict[str, Any]] = []
            field_count = ibm_db.num_fields(statement)
            if not isinstance(field_count, int) or isinstance(field_count, bool):
                raise RuntimeError("Db2 returned an invalid result column count")
            if field_count > 0:
                result = ibm_db.fetch_assoc(statement)
                while result:
                    rows.append(dict(result))
                    result = ibm_db.fetch_assoc(statement)
            if not ibm_db.commit(connection):
                raise RuntimeError("Db2 commit failed")
            return rows
        except Exception as exc:
            statement = locals().get("statement")
            sqlstate, sqlcode, diagnostic = self._diagnostics(statement)
            diagnostic = diagnostic or self._sanitize_diagnostic(str(exc))
            connection_failure = self._is_connection_failure(sqlstate)
            logger.error(
                "Db2 statement failed sqlstate=%s sqlcode=%s message=%s",
                sqlstate or "unknown", sqlcode or "unknown", diagnostic or "unknown",
            )
            try:
                self._rollback_after_failure(connection)
            except Exception as rollback_exc:
                logger.error("Db2 rollback failed after statement error")
                raise DatabaseUnavailable(
                    "Db2 query rollback failed",
                    sqlstate=sqlstate,
                    sqlcode=sqlcode,
                    diagnostic=diagnostic,
                ) from rollback_exc
            if connection_failure and self.connection is connection:
                self._close_connection(connection)
            error_type = DatabaseUnavailable if connection_failure else DatabaseError
            raise error_type(
                "Db2 query failed",
                sqlstate=sqlstate,
                sqlcode=sqlcode,
                diagnostic=diagnostic,
            ) from exc

    def execute_insert_and_get_identity(
        self, sql: str, params: Sequence[Any] = ()
    ) -> int:
        if self.connection is None or ibm_db is None:
            raise DatabaseUnavailable("Db2 is offline")
        connection = self.connection
        try:
            insert_statement = self._prepare_and_bind(sql, params)
            if not ibm_db.execute(insert_statement):
                raise RuntimeError("Db2 statement execution failed")

            identity_statement = self._prepare_and_bind(
                "SELECT IDENTITY_VAL_LOCAL() AS generated_id FROM SYSIBM.SYSDUMMY1",
                (),
            )
            if not ibm_db.execute(identity_statement):
                raise RuntimeError("Db2 identity query failed")
            row = ibm_db.fetch_assoc(identity_statement)
            if not row:
                raise RuntimeError("Db2 did not return the generated identity")
            identity = row.get("generated_id", row.get("GENERATED_ID"))
            if identity is None:
                raise RuntimeError("Db2 returned no generated identity value")
            if not ibm_db.commit(connection):
                raise RuntimeError("Db2 commit failed")
            return int(identity)
        except Exception as exc:
            statement = locals().get("identity_statement", locals().get("insert_statement"))
            sqlstate, sqlcode, diagnostic = self._diagnostics(statement)
            diagnostic = diagnostic or self._sanitize_diagnostic(str(exc))
            connection_failure = self._is_connection_failure(sqlstate)
            logger.error(
                "Db2 transaction failed sqlstate=%s sqlcode=%s message=%s",
                sqlstate or "unknown", sqlcode or "unknown", diagnostic or "unknown",
            )
            try:
                self._rollback_after_failure(connection)
            except Exception as rollback_exc:
                logger.error("Db2 rollback failed after transaction error")
                raise DatabaseUnavailable(
                    "Db2 transaction rollback failed",
                    sqlstate=sqlstate,
                    sqlcode=sqlcode,
                    diagnostic=diagnostic,
                ) from rollback_exc
            if connection_failure and self.connection is connection:
                self._close_connection(connection)
            error_type = DatabaseUnavailable if connection_failure else DatabaseError
            raise error_type(
                "Db2 transaction failed",
                sqlstate=sqlstate,
                sqlcode=sqlcode,
                diagnostic=diagnostic,
            ) from exc
