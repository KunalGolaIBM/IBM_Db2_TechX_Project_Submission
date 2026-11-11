"""Thin, safe wrapper around the official ``ibm_db`` driver.

* Parameterized statements only (``?`` markers).
* Statement handles are always freed.
* The driver is imported lazily so unit tests and tooling work without it installed.
* Errors are parsed (SQLCODE / SQLSTATE) and classified into LockLens exception types.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol, Sequence

from ..config import Settings
from ..errors import Db2ConnectionError, Db2Error, Db2PermissionError, Db2QueryError

log = logging.getLogger(__name__)

_SQLCODE_RE = re.compile(r"\bSQL(\d{4,5})([NWC])\b")
_SQLSTATE_RE = re.compile(r"SQLSTATE\s*=\s*(\w{5})")

# SQL0551N: no privilege for the operation, SQL0552N: lacks the required authority.
_PERMISSION_CODES = {551, 552}


class Executor(Protocol):
    """The tiny surface the monitoring and incident layers depend on (easy to fake in tests)."""

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]: ...

    def query_with_columns(self, sql: str, params: Sequence[Any] = ()
                           ) -> tuple[list[str], list[dict[str, Any]]]: ...

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int: ...


def parse_db2_error(message: str) -> tuple[int | None, str | None]:
    code = _SQLCODE_RE.search(message or "")
    state = _SQLSTATE_RE.search(message or "")
    return (int(code.group(1)) if code else None, state.group(1) if state else None)


def _scrub(message: str) -> str:
    """Remove anything that looks like a credential from an error message."""
    return re.sub(r"(?i)\b(PWD|PASSWORD)\s*=\s*(\{[^}]*\}|[^;\s]+)", r"\1=***", message).strip()


def classify_connection_error(exc: BaseException) -> Db2ConnectionError:
    """Translate a driver exception into a Db2ConnectionError with a stable ``kind``."""
    message = str(exc)
    sqlcode, sqlstate = parse_db2_error(message)
    lowered = message.lower()
    if sqlcode == 30082 or "username and/or password invalid" in lowered:
        kind, hint = "invalid_credentials", "Db2 rejected the user name or password."
    elif sqlcode in (1013, 1031):
        kind, hint = "database_not_found", "The database name was not found on the server."
    elif "timed out" in lowered or "timeout" in lowered:
        kind, hint = "timeout", "The connection attempt timed out."
    elif sqlcode == 30081 or "communication" in lowered or "refused" in lowered:
        kind, hint = "unreachable", "Could not reach Db2 at that host and port."
    else:
        kind, hint = "unknown", "Db2 connection failed."
    return Db2ConnectionError(f"{hint} ({_scrub(message)})", kind, sqlcode, sqlstate)


def _quote_cli_value(value: str) -> str:
    if any(c in value for c in ";={}"):
        return "{" + value.replace("}", "}}") + "}"
    return value


def build_connection_string(settings: Settings) -> str:
    """Build the CLI connection string. Never log the return value: it contains the password."""
    parts = [
        f"DATABASE={_quote_cli_value(settings.db_name)}",
        f"HOSTNAME={_quote_cli_value(settings.db_host)}",
        f"PORT={settings.db_port}",
        "PROTOCOL=TCPIP",
        f"UID={_quote_cli_value(settings.db_user)}",
        f"PWD={_quote_cli_value(settings.db_password)}",
        f"CONNECTTIMEOUT={settings.connect_timeout}",
    ]
    if settings.db_ssl:
        parts.append("SECURITY=SSL")
    return ";".join(parts) + ";"


def _load_driver() -> Any:
    try:
        import ibm_db  # type: ignore
    except ImportError as exc:
        raise Db2ConnectionError(
            "The ibm_db driver is not installed. Run: pip install -r requirements.txt",
            "driver_missing") from exc
    return ibm_db


class Db2Connection:
    """One long-lived autocommit connection used for monitoring and incident storage.

    Autocommit is deliberately ON so LockLens never holds locks of its own.
    """

    def __init__(self, settings: Settings, driver: Any | None = None):
        self._settings = settings
        self._driver = driver
        self._conn: Any | None = None

    # -- lifecycle ---------------------------------------------------------------------
    def connect(self) -> None:
        if self.is_alive():
            return
        driver = self._driver or _load_driver()
        self._driver = driver
        log.info("Connecting to Db2 as %s", self._settings.fingerprint())
        try:
            self._conn = driver.connect(build_connection_string(self._settings), "", "")
        except Db2Error:
            raise
        except Exception as exc:  # ibm_db raises plain Exception
            self._conn = None
            raise classify_connection_error(exc) from None
        try:
            driver.autocommit(self._conn, driver.SQL_AUTOCOMMIT_ON)
        except Exception:  # connection default is already autocommit
            log.debug("Could not set autocommit explicitly")

    def close(self) -> None:
        if self._conn is not None and self._driver is not None:
            try:
                self._driver.close(self._conn)
            except Exception:
                log.debug("Error while closing connection", exc_info=True)
        self._conn = None

    def is_alive(self) -> bool:
        if self._conn is None or self._driver is None:
            return False
        try:
            return bool(self._driver.active(self._conn))
        except Exception:
            return False

    def ping(self) -> bool:
        """Cheap server round trip proving the connection really works."""
        try:
            self.query("SELECT 1 AS OK FROM SYSIBM.SYSDUMMY1")
            return True
        except Db2Error:
            return False

    def __enter__(self) -> "Db2Connection":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- statements --------------------------------------------------------------------
    def _run(self, sql: str, params: Sequence[Any]) -> tuple[Any, Any]:
        if not self.is_alive():
            self.connect()
        driver = self._driver
        stmt = None
        try:
            stmt = driver.prepare(self._conn, sql)
            if params:
                driver.execute(stmt, tuple(params))
            else:
                driver.execute(stmt)
            return driver, stmt
        except Exception as exc:
            if stmt is not None:
                self._free(driver, stmt)
            raise self._query_error(exc) from None

    @staticmethod
    def _free(driver: Any, stmt: Any) -> None:
        try:
            driver.free_stmt(stmt)
        except Exception:
            log.debug("free_stmt failed", exc_info=True)

    @staticmethod
    def _query_error(exc: BaseException) -> Db2QueryError:
        message = _scrub(str(exc))
        sqlcode, sqlstate = parse_db2_error(message)
        cls = Db2PermissionError if sqlcode in _PERMISSION_CODES else Db2QueryError
        return cls(message, sqlcode, sqlstate)

    def query_with_columns(self, sql: str, params: Sequence[Any] = ()
                           ) -> tuple[list[str], list[dict[str, Any]]]:
        driver, stmt = self._run(sql, params)
        try:
            count = driver.num_fields(stmt)
            columns = [str(driver.field_name(stmt, i)).upper() for i in range(count)]
            rows: list[dict[str, Any]] = []
            while True:
                row = driver.fetch_assoc(stmt)
                if not row:
                    break
                rows.append({str(k).upper(): v for k, v in row.items()})
            return columns, rows
        except Db2Error:
            raise
        except Exception as exc:
            raise self._query_error(exc) from None
        finally:
            self._free(driver, stmt)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        return self.query_with_columns(sql, params)[1]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        driver, stmt = self._run(sql, params)
        try:
            try:
                return int(driver.num_rows(stmt))
            except Exception:
                return 0
        finally:
            self._free(driver, stmt)
