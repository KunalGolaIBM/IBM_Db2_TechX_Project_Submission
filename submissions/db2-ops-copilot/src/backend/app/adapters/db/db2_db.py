"""REAL IBM Db2 database adapter (M2 — ``ibm_db`` / ``ibm_db_dbi``).

Contract (layering, see docs/DB2_INTEGRATION.md):
- This adapter is the EXECUTION layer. Callers MUST pass SQL that already
  passed the sqlglot validation gate (``app.services.sql_execution_service``
  enforces that order). The adapter does not re-parse SQL; it enforces the
  transport-level defenses: row cap (``fetchmany(max_rows + 1)``), query
  timeout (``SET CURRENT QUERY TIMEOUT`` on the same session), read-only
  account, and parameter binding (qmark markers only).
- Every failure is mapped to an actionable ``AdapterUnavailableError`` with
  an SQLSTATE classification — connectivity vs. permission vs. syntax are
  distinguishable, and credential material is stripped (``dsn.sanitize``).
- Connections are short-lived (one per operation, closed in ``finally``).
  This favors auditability and crash-isolation over pooled throughput, which
  is the right trade-off for a copilot serving low QPS; a ``transaction()``
  context manager groups multi-statement writes when needed.

NEVER executed against a live database on the development machine (no Db2
installation per the project constraint). Offline unit tests exercise the
code with a fake ``ibm_db_dbi`` module (backend/tests/test_db2_unit.py).
"""

from __future__ import annotations

import logging
import re
import socket
import time
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from app.adapters.base import (
    AdminResult,
    DbaToolResult,
    ExecutionRecord,
    ExplainObject,
    ExplainOperator,
    ExplainResult,
    ProbeResult,
    QueryResult,
    SchemaColumn,
    SchemaSnapshot,
    SchemaTable,
)
from app.core.config import Settings
from app.core.errors import (
    AdapterUnavailableError,
    AppError,
    DbError,
    DbObjectNotFoundError,
    DbPermissionError,
    DbSqlError,
    UpstreamTimeoutError,
)
from app.database.dsn import admin_connect_args, connect_args, sanitize

logger = logging.getLogger(__name__)

# SYSCAT.TABLES exposes the object kind in column TYPE ('T' table, 'V' view).
# (An earlier revision filtered on a non-existent TABTYPE column.)
_READ_TABLES_SQL = (
    "SELECT DISTINCT TABNAME FROM SYSCAT.TABLES "
    "WHERE TABSCHEMA = ? AND TYPE IN ('T', 'V') ORDER BY TABNAME"
)

_READ_COLUMNS_SQL = (
    "SELECT TABNAME, COLNAME, TYPENAME, NULLS FROM SYSCAT.COLUMNS "
    "WHERE TABSCHEMA = ? ORDER BY TABNAME, COLNO"
)

# SQLSTATE classes mapped to operator-actionable categories.
_SQLSTATE_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("08", "connectivity", "connection ended unexpectedly — is the database active?"),
    ("28", "authentication", "invalid credentials — check DB2_RO_USER / DB2_RO_PASSWORD"),
    ("425", "authorization", "user lacks the required privilege — check GRANTs (migrations 003/005)"),
    ("426", "syntax", "the statement is syntactically invalid for Db2"),
    ("427", "schema", "object does not exist — run database/migrations (see database/README.md)"),
    ("428", "sql-semantics", "the statement is not valid for this schema (type/column mismatch)"),
    ("570", "resource", "operation cancelled by the system (time/lock limit)"),
    ("571", "resource", "a SCAN lock escalation occurred — retry or reduce concurrency"),
    ("911", "transaction", "current transaction rolled back — retry the operation"),
)

# Well-known CLI message ids → SQLSTATE, for drivers that print only the
# message id (e.g. "SQL0204N ... is an undefined name").
_MESSAGE_ID_TO_SQLSTATE: dict[str, str] = {
    "0204": "42704",  # object name undefined
    "1013": "42704",  # cannot resolve qualified name
    "0206": "42703",  # column name invalid
    "0104": "42601",  # syntax error at token
    "0180": "42601",  # syntax error in use of tokens
    "0551": "42501",  # not authorized to object
    "0552": "42501",  # not authorized to object
    "0911": "911",    # lock timeout / rolled back
}

_SQLSTATE_RE = re.compile(r"SQLSTATE[=:\s]+([0-9A-Z]{5})", re.IGNORECASE)
_MESSAGE_ID_RE = re.compile(r"\bSQL(\d{4})N\b")


def _as_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


_OBJECT_KINDS = {"TA": "TABLE", "IX": "INDEX", "VW": "VIEW", "NK": "NICKNAME"}


def _object_kind(value: Any) -> str:
    code = str(value).strip().upper()
    return _OBJECT_KINDS.get(code, code or "UNKNOWN")


@dataclass(slots=True)
class SqlErrorInfo:
    """Sanitized classification of a driver error."""

    sqlstate: str
    category: str
    hint: str


def classify_db_error(exc: BaseException) -> SqlErrorInfo:
    """Map a driver exception to a sanitized, actionable classification.

    ibm_db raises ``DatabaseError`` whose text embeds both a CLI message id
    (``SQL0204N``) and a SQLSTATE (``42704``). We surface neither raw driver
    text nor connection details — only the SQLSTATE plus a curated hint.
    """
    text = str(exc)
    sqlstate = "unknown"
    match = _SQLSTATE_RE.search(text)
    if match:
        sqlstate = match.group(1).upper()
    else:
        message_id = _MESSAGE_ID_RE.search(text)
        if message_id:
            sqlstate = _MESSAGE_ID_TO_SQLSTATE.get(
                message_id.group(1), "unknown"
            )
    if sqlstate == "42703":  # undefined column: the statement is wrong (422), not a missing object
        return SqlErrorInfo(
            sqlstate=sqlstate,
            category="sql-semantics",
            hint="a referenced column does not exist — check the column names",
        )
    for class_prefix, category, hint in _SQLSTATE_CATEGORIES:
        if sqlstate != "unknown" and sqlstate.startswith(class_prefix):
            if sqlstate == "57014":
                category, hint = (
                    "timeout",
                    "statement cancelled by the query timeout — simplify the "
                    "query or raise SQL_QUERY_TIMEOUT_MS",
                )
            return SqlErrorInfo(sqlstate=sqlstate, category=category, hint=hint)
    return SqlErrorInfo(
        sqlstate=sqlstate, category="unknown", hint="see the Db2 message catalog"
    )


def map_db_error(
    exc: BaseException, settings: Settings, *, action: str, **extra: Any
) -> AppError:
    """Translate a driver exception into the API error taxonomy.

    SQLSTATE category -> HTTP status:

    =================  ===========================  ======
    category           error                        status
    =================  ===========================  ======
    timeout (57014)    ``UpstreamTimeoutError``     504
    authorization      ``DbPermissionError``        403
    schema (427xx)     ``DbObjectNotFoundError``    404
    syntax/semantics   ``DbSqlError``               422
    connectivity/auth  ``AdapterUnavailableError``  503
    resource/txn       ``AdapterUnavailableError``  503 (retryable)
    anything else      ``DbError``                  502
    =================  ===========================  ======

    The message carries only the SQLSTATE, category and credential-stripped
    driver text (``dsn.sanitize``).
    """
    info = classify_db_error(exc)
    detail: dict[str, Any] = {
        "sqlstate": info.sqlstate,
        "category": info.category,
        "hint": info.hint,
        "error_type": type(exc).__name__,
        **extra,
    }
    message = (
        f"{action} failed [{info.category}, SQLSTATE {info.sqlstate}]: "
        f"{sanitize(str(exc), settings)}"
    )
    if info.category == "timeout":
        return UpstreamTimeoutError(
            f"{action} exceeded the configured timeout [SQLSTATE {info.sqlstate}].",
            detail=detail,
        )
    if info.category == "authorization":
        return DbPermissionError(message, detail=detail)
    if info.category == "schema":
        return DbObjectNotFoundError(message, detail=detail)
    if info.category in {"syntax", "sql-semantics"}:
        return DbSqlError(message, detail=detail)
    if info.category in {"connectivity", "authentication", "resource", "transaction"}:
        return AdapterUnavailableError(message, detail=detail)
    return DbError(message, detail=detail)


class Db2DatabaseAdapter:
    """Read-only Db2 connectivity for generated SQL and schema introspection."""

    probe_name = "database"
    provider_id = "db2"
    mode = "real"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._closed = False

    # -- availability probes ---------------------------------------------
    def _tcp_reachable(self) -> tuple[bool, str]:
        timeout = max(self._settings.db2_connect_timeout_ms / 1000, 0.2)
        try:
            with socket.create_connection(
                (self._settings.db2_host, self._settings.db2_port), timeout=timeout
            ):
                return True, ""
        except OSError as exc:
            return False, str(exc.strerror or exc)

    def _import_driver(self) -> tuple[bool, str]:
        try:
            import ibm_db  # noqa: F401
            import ibm_db_dbi  # noqa: F401

            return True, ""
        except ImportError as exc:
            return False, str(exc)

    def ping(self) -> ProbeResult:
        if self._closed:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=0.0,
                detail="Db2 adapter closed",
            )
        start = time.perf_counter()
        target = f"{self._settings.db2_host}:{self._settings.db2_port}"
        reachable, sock_error = self._tcp_reachable()
        driver_ok, driver_error = self._import_driver()

        if not reachable:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=(time.perf_counter() - start) * 1000,
                detail=(
                    f"Db2 not reachable at {target} ({sock_error}). "
                    "Start the Db2 Community Edition container — see "
                    "docs/DB2_INTEGRATION.md."
                ),
            )
        if not driver_ok:
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=(time.perf_counter() - start) * 1000,
                detail=(
                    f"Db2 reachable at {target} but the ibm_db driver is missing "
                    f"({driver_error}). Install requirements-integration.txt."
                ),
            )

        # Driver present: attempt a real, short-lived login probe.
        try:
            import ibm_db_dbi

            dsn, user, password = connect_args(self._settings)
            conn = ibm_db_dbi.connect(dsn, user, password)
            conn.close()
            return ProbeResult(
                name=self.probe_name,
                status="ok",
                mode=self.mode,
                latency_ms=(time.perf_counter() - start) * 1000,
                detail=f"connected to Db2 at {target} as read-only user '{user}'",
            )
        except Exception as exc:  # driver raises many error classes
            info = classify_db_error(exc)
            return ProbeResult(
                name=self.probe_name,
                status="unavailable",
                mode=self.mode,
                latency_ms=(time.perf_counter() - start) * 1000,
                detail=(
                    f"Db2 login failed at {target} "
                    f"[{info.category}, SQLSTATE {info.sqlstate}]: "
                    f"{sanitize(str(exc), self._settings)}"
                ),
            )

    # -- connection / transaction lifecycle --------------------------------
    def _connect(self):
        try:
            import ibm_db_dbi
        except ImportError as exc:
            raise AdapterUnavailableError(
                "ibm_db driver is not installed. Install it with: "
                "pip install -r requirements-integration.txt (M2).",
                detail={"import_error": str(exc)},
            ) from exc

        dsn, user, password = connect_args(self._settings)
        try:
            return ibm_db_dbi.connect(dsn, user, password)
        except Exception as exc:
            info = classify_db_error(exc)
            raise AdapterUnavailableError(
                f"Cannot connect to Db2 at {self._settings.db2_host} "
                f"[{info.category}, SQLSTATE {info.sqlstate}]: "
                f"{sanitize(str(exc), self._settings)}",
                detail={
                    "host": self._settings.db2_host,
                    "port": self._settings.db2_port,
                    "sqlstate": info.sqlstate,
                    "hint": info.hint,
                },
            ) from exc

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Group writes in one connection with commit/rollback semantics.

        Usage::

            with adapter.transaction() as conn:
                cur = conn.cursor()
                cur.execute(insert_sql, params)
            # committed on success, rolled back on exception

        The read-only account limits what writes can actually do
        (APP_AUDIT / QUERY_EXECUTIONS INSERT only — see migration 003).
        """
        if self._closed:
            raise AdapterUnavailableError("Db2 adapter is closed.")
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 — rollback is best-effort
                logger.warning("rollback failed", exc_info=True)
            raise
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    @staticmethod
    def _apply_timeout(cursor: Any, timeout_ms: int) -> bool:
        """Set Db2's session query timeout; report whether it was applied."""
        timeout_s = max(int(timeout_ms / 1000), 1)
        try:
            cursor.execute(f"SET CURRENT QUERY TIMEOUT {timeout_s}")
            return True
        except Exception:  # noqa: BLE001 — not supported on every server/setup
            return False

    # -- queries -----------------------------------------------------------
    def execute_readonly(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        timeout_ms: int | None = None,
    ) -> QueryResult:
        """Execute an already-validated read-only statement with hard caps.

        Defenses applied here (independent of the validation gate):
        - row cap: fetches ``sql_max_rows + 1`` rows and marks truncation;
        - query timeout: ``SET CURRENT QUERY TIMEOUT`` on the same session
          (warning logged when unsupported — the Python-side fetch bound is
          still the last line of defense against unbounded fetches);
        - parameter binding: qmark markers only, never string interpolation;
        - the connection is read via the ``db2ro`` account whose GRANTs
          forbid DML/DDL (defense in depth).
        """
        if self._closed:
            raise AdapterUnavailableError("Db2 adapter is closed.")
        start = time.perf_counter()
        conn = self._connect()
        try:
            cursor = conn.cursor()
            timeout = timeout_ms or self._settings.sql_query_timeout_ms
            if not self._apply_timeout(cursor, timeout):
                logger.warning(
                    "SET CURRENT QUERY TIMEOUT not applied (unsupported on "
                    "this server/setup); relying on fetch cap + client timeout"
                )
            cursor.execute(sql, tuple(params) if params else None)
            max_rows = self._settings.sql_max_rows
            rows = cursor.fetchmany(max_rows + 1) or []
            columns = [d[0] for d in (cursor.description or [])]
            truncated = len(rows) > max_rows
            if truncated:
                rows = rows[:max_rows]
            return QueryResult(
                columns=columns,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                truncated=truncated,
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise map_db_error(
                exc, self._settings, action="Query execution"
            ) from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    # -- schema introspection ------------------------------------------------
    def fetch_schema(self) -> SchemaSnapshot:
        """Read tables/columns of the application schema from SYSCAT.

        Uses parameterized queries against SYSCAT (read-only catalog views
        granted to PUBLIC by Db2) — no DDL, no dynamic SQL. The schema read
        is ``DB2_APP_SCHEMA`` (default APP), NOT the login user's schema.
        """
        if self._closed:
            raise AdapterUnavailableError("Db2 adapter is closed.")
        start = time.perf_counter()
        schema = self._settings.app_schema
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(_READ_TABLES_SQL, (schema,))
            table_names = [row[0] for row in cursor.fetchall()]
            cursor.execute(_READ_COLUMNS_SQL, (schema,))
            columns_by_table: dict[str, list[SchemaColumn]] = {}
            for tabname, colname, typename, nulls in cursor.fetchall():
                columns_by_table.setdefault(tabname, []).append(
                    SchemaColumn(
                        name=colname,
                        data_type=typename,
                        nullable=str(nulls).upper() in {"Y", "YES", "1"},
                    )
                )
            tables = [
                SchemaTable(
                    name=name,
                    schema_name=schema,
                    columns=columns_by_table.get(name, []),
                )
                for name in table_names
            ]
            return SchemaSnapshot(
                tables=tables,
                source="SYSCAT",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise map_db_error(
                exc, self._settings, action="Schema introspection", schema=schema
            ) from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    # -- approved maintenance actions ------------------------------------------
    def execute_admin_statement(self, statement: str) -> AdminResult:
        """Execute ONE human-approved maintenance statement as the admin account.

        Preconditions enforced by the caller (approval service): the approval
        was explicitly granted, ``prepare_action`` re-rendered and re-validated
        the statement. Defense in depth here: refuses unless actions are
        enabled AND admin credentials are configured, and executes a single
        statement only. The read-only query path never uses this method.
        """
        if self._closed:
            raise AdapterUnavailableError("Db2 adapter is closed.")
        s = self._settings
        if not s.agent_actions_enabled:
            raise AdapterUnavailableError(
                "Executing approved actions is disabled (AGENT_ACTIONS_ENABLED=false).",
                detail={"code": "ACTIONS_DISABLED"},
            )
        if not s.db2_admin_user or not s.db2_admin_password.get_secret_value():
            raise AdapterUnavailableError(
                "No maintenance account configured (DB2_ADMIN_USER / DB2_ADMIN_PASSWORD).",
                detail={"code": "ADMIN_NOT_CONFIGURED"},
            )
        if ";" in statement or not statement.strip():
            raise DbSqlError("Exactly one statement may be executed.")
        try:
            import ibm_db_dbi
        except ImportError as exc:
            raise AdapterUnavailableError(
                "ibm_db driver is not installed (requirements-integration.txt)."
            ) from exc

        start = time.perf_counter()
        dsn, user, password = admin_connect_args(s)
        try:
            conn = ibm_db_dbi.connect(dsn, user, password)
        except Exception as exc:
            raise map_db_error(exc, s, action="Maintenance connection") from exc
        try:
            cursor = conn.cursor()
            cursor.execute(statement)
            conn.commit()
            return AdminResult(
                status="EXECUTED",
                simulated=False,
                detail="Statement executed by the maintenance account.",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise map_db_error(exc, s, action="Maintenance action") from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    # -- DBA tools (catalog + monitoring) -------------------------------------
    def run_dba_tool(
        self,
        tool_id: str,
        sql: str,
        params: Sequence[Any],
        limit: int,
    ) -> DbaToolResult:
        """Run one FIXED tool template (``app.dba.specs``) with bound params.

        ``sql`` must come from a ``ToolSpec`` — never from a user or a model.
        User-controlled values travel only in ``params`` (qmark binding); the
        row bound is enforced both in the template and by ``fetchmany``.
        """
        if self._closed:
            raise AdapterUnavailableError("Db2 adapter is closed.")
        start = time.perf_counter()
        conn = self._connect()
        try:
            cursor = conn.cursor()
            self._apply_timeout(cursor, self._settings.sql_query_timeout_ms)
            cursor.execute(sql, tuple(params) if params else None)
            rows = cursor.fetchmany(limit + 1) or []
            columns = [d[0] for d in (cursor.description or [])]
            truncated = len(rows) > limit
            return DbaToolResult(
                tool_id=tool_id,
                source="db2",
                columns=columns,
                rows=[list(r) for r in rows[:limit]],
                truncated=truncated,
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            raise map_db_error(
                exc, self._settings, action=f"DBA tool {tool_id}", tool=tool_id
            ) from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    # -- EXPLAIN ---------------------------------------------------------------
    # Explain-table access is by fixed templates: ``{es}`` is a validated plain
    # identifier (Settings), the QUERYTAG is bound, and the statement text is
    # the only interpolated value in ``EXPLAIN PLAN ... FOR`` (guarded below).
    _EXPLAIN_KEYS = (
        "S.EXPLAIN_REQUESTER = {a}.EXPLAIN_REQUESTER AND "
        "S.EXPLAIN_TIME = {a}.EXPLAIN_TIME AND "
        "S.SOURCE_NAME = {a}.SOURCE_NAME AND "
        "S.SOURCE_SCHEMA = {a}.SOURCE_SCHEMA AND "
        "S.SOURCE_VERSION = {a}.SOURCE_VERSION AND "
        "S.EXPLAIN_LEVEL = {a}.EXPLAIN_LEVEL AND "
        "S.STMTNO = {a}.STMTNO AND S.SECTNO = {a}.SECTNO"
    )
    _EXPLAIN_STMT_SQL = (
        "SELECT S.TOTAL_COST FROM {es}.EXPLAIN_STATEMENT S "
        "WHERE S.QUERYTAG = ? AND S.EXPLAIN_LEVEL = 'P'"
    )
    _EXPLAIN_OPERATORS_SQL = (
        "SELECT O.OPERATOR_ID, O.OPERATOR_TYPE, O.TOTAL_COST, O.IO_COST, "
        "O.CPU_COST FROM {es}.EXPLAIN_OPERATOR O "
        "JOIN {es}.EXPLAIN_STATEMENT S ON " + _EXPLAIN_KEYS.format(a="O") + " "
        "WHERE S.QUERYTAG = ? AND S.EXPLAIN_LEVEL = 'P' ORDER BY O.OPERATOR_ID"
    )
    _EXPLAIN_OBJECTS_SQL = (
        "SELECT DISTINCT B.OBJECT_SCHEMA, B.OBJECT_NAME, B.OBJECT_TYPE "
        "FROM {es}.EXPLAIN_OBJECT B "
        "JOIN {es}.EXPLAIN_STATEMENT S ON " + _EXPLAIN_KEYS.format(a="B") + " "
        "WHERE S.QUERYTAG = ? AND S.EXPLAIN_LEVEL = 'P' "
        "ORDER BY B.OBJECT_SCHEMA, B.OBJECT_NAME"
    )
    # Deleting the EXPLAIN_INSTANCE row cascades to the other explain tables.
    _EXPLAIN_CLEANUP_SQL = (
        "DELETE FROM {es}.EXPLAIN_INSTANCE WHERE EXPLAIN_REQUESTER = SESSION_USER "
        "AND EXPLAIN_TIME IN (SELECT S.EXPLAIN_TIME FROM {es}.EXPLAIN_STATEMENT S "
        "WHERE S.QUERYTAG = ?)"
    )
    _EXPLAIN_SETUP_HINT = (
        "Create the EXPLAIN tables once with: CALL SYSPROC.SYSINSTALLOBJECTS("
        "'EXPLAIN', 'C', CAST(NULL AS VARCHAR(128)), CAST(NULL AS VARCHAR(128))) "
        "and grant the account access (database/migrations/005_dba_tools.sql)."
    )

    def explain_plan(self, sql: str, timeout_ms: int | None = None) -> ExplainResult:
        """Run ``EXPLAIN PLAN`` and read the access plan back (never raises).

        Flow: ``EXPLAIN PLAN SET QUERYTAG = '<uuid>' FOR <validated SELECT>``
        populates the EXPLAIN_* tables; the plan is read back by that tag
        (statement cost, operators, objects) and the rows are then deleted.

        Graceful fallback (status, not exception): no driver/connection,
        missing EXPLAIN tables (SQL0219N), missing privilege, or a timeout
        yield ``UNAVAILABLE`` with an actionable hint; a statement Db2
        itself rejects yields ``FAILED``.
        """
        start = time.perf_counter()

        def result(**fields: Any) -> ExplainResult:
            return ExplainResult(
                latency_ms=(time.perf_counter() - start) * 1000, **fields
            )

        if self._closed:
            return result(status="UNAVAILABLE", source="none", hint="Db2 adapter closed.")
        statement = sql.strip()
        if (
            not statement
            or ";" in statement
            or not statement.upper().startswith(("SELECT", "WITH"))
        ):
            return result(
                status="FAILED",
                source="none",
                hint="Only a single validated SELECT can be explained.",
            )

        try:
            conn = self._connect()
        except AdapterUnavailableError as exc:
            return result(
                status="UNAVAILABLE",
                source="none",
                sqlstate=(exc.detail or {}).get("sqlstate") if isinstance(exc.detail, dict) else None,
                hint="Db2 is not reachable or the ibm_db driver is missing; "
                "EXPLAIN needs a live connection.",
                detail=exc.message[:300],
            )

        es = self._settings.explain_schema
        tag = uuid.uuid4().hex
        try:
            cursor = conn.cursor()
            self._apply_timeout(
                cursor, timeout_ms or self._settings.sql_query_timeout_ms
            )
            cursor.execute(f"EXPLAIN PLAN SET QUERYTAG = '{tag}' FOR {statement}")

            cursor.execute(self._EXPLAIN_STMT_SQL.format(es=es), (tag,))
            stmt_rows = cursor.fetchall()
            if not stmt_rows:
                conn.rollback()
                return result(
                    status="UNAVAILABLE",
                    source="none",
                    hint="EXPLAIN ran but the plan could not be read back. "
                    + self._EXPLAIN_SETUP_HINT,
                )
            total_cost = _as_float(stmt_rows[0][0])
            cursor.execute(self._EXPLAIN_OPERATORS_SQL.format(es=es), (tag,))
            operators = [
                ExplainOperator(
                    operator_id=int(r[0]),
                    operator_type=str(r[1]).strip(),
                    total_cost=_as_float(r[2]),
                    io_cost=_as_float(r[3]),
                    cpu_cost=_as_float(r[4]),
                )
                for r in cursor.fetchall()
            ]
            cursor.execute(self._EXPLAIN_OBJECTS_SQL.format(es=es), (tag,))
            objects = [
                ExplainObject(
                    schema_name=str(r[0]).strip(),
                    name=str(r[1]).strip(),
                    object_type=_object_kind(r[2]),
                )
                for r in cursor.fetchall()
            ]
            warnings: list[str] = []
            try:
                cursor.execute(self._EXPLAIN_CLEANUP_SQL.format(es=es), (tag,))
            except Exception as cleanup_exc:  # noqa: BLE001 — cleanup is best-effort
                warnings.append(
                    "Plan rows were left in the EXPLAIN tables (cleanup not permitted)."
                )
                logger.info("EXPLAIN cleanup skipped: %s", type(cleanup_exc).__name__)
            conn.commit()
            return result(
                status="OK",
                source="db2",
                total_cost=total_cost,
                operators=operators,
                objects=objects,
                warnings=warnings,
            )
        except Exception as exc:  # noqa: BLE001 — EXPLAIN never raises
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return self._explain_failure(exc, result)
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    def _explain_failure(self, exc: BaseException, result: Any) -> ExplainResult:
        """Map a driver error during EXPLAIN to UNAVAILABLE vs FAILED."""
        info = classify_db_error(exc)
        text = str(exc)
        detail = sanitize(text, self._settings)[:300]
        tables_missing = "SQL0219N" in text or "explain table" in text.lower()
        if tables_missing or info.category in {
            "authorization",
            "connectivity",
            "authentication",
            "timeout",
            "resource",
            "transaction",
        }:
            hint = (
                self._EXPLAIN_SETUP_HINT
                if tables_missing or info.category == "authorization"
                else info.hint
            )
            logger.info(
                "EXPLAIN unavailable (SQLSTATE %s, %s) — continuing without a plan",
                info.sqlstate,
                info.category,
            )
            return result(
                status="UNAVAILABLE",
                source="none",
                sqlstate=info.sqlstate,
                hint=hint,
                detail=detail,
            )
        return result(
            status="FAILED",
            source="none",
            sqlstate=info.sqlstate,
            hint=info.hint,
            detail=detail,
        )

    def explain(self, sql: str, timeout_ms: int | None = None) -> bool:
        """Advisory dry-run used by the execution path: True only for a real plan."""
        return self.explain_plan(sql, timeout_ms).status == "OK"

    # -- execution history (APP.QUERY_EXECUTIONS) ---------------------------

    _INSERT_EXECUTION_SQL = (
        "INSERT INTO {schema}.QUERY_EXECUTIONS ("
        "CLIENT_REQ_ID, SQL_TEXT, VALIDATION_STATUS, EXPLAIN_STATUS, "
        "EXECUTION_STATUS, ROW_COUNT, TRUNCATED, LATENCY_MS, SQLSTATE_CODE, "
        "METADATA) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    _SELECT_EXECUTIONS_SQL = (
        "SELECT EXECUTION_ID, REQ_TS, CLIENT_REQ_ID, SQL_TEXT, "
        "VALIDATION_STATUS, EXPLAIN_STATUS, EXECUTION_STATUS, ROW_COUNT, "
        "TRUNCATED, LATENCY_MS, SQLSTATE_CODE, METADATA "
        "FROM {schema}.QUERY_EXECUTIONS ORDER BY EXECUTION_ID DESC "
        "FETCH FIRST {limit} ROWS ONLY"
    )

    def record_execution(self, record: ExecutionRecord) -> int:
        """Append one row to APP.QUERY_EXECUTIONS (best-effort by contract).

        The read-only account has GRANT SELECT, INSERT on this table
        (migration 003). METADATA passes through the sanitizer first.
        """
        if self._closed:
            raise AdapterUnavailableError("Db2 adapter is closed.")
        from app.security.sanitize import sanitize_metadata

        sql = self._INSERT_EXECUTION_SQL.format(schema=self._settings.app_schema)
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (
                    record.request_id,
                    record.sql,
                    record.validation_status,
                    record.explain_status,
                    record.execution_status,
                    record.row_count,
                    "Y" if record.truncated else "N",
                    int(record.latency_ms),
                    record.sqlstate,
                    sanitize_metadata(record.detail),
                ),
            )
            conn.commit()
            new_id = getattr(cursor, "lastrowid", None)
            execution_id = int(new_id) if isinstance(new_id, int) else 0
            logger.debug(
                "execution row written id=%d status=%s rows=%s request_id=%s",
                execution_id,
                record.execution_status,
                record.row_count,
                record.request_id or "-",
            )
            return execution_id
        except Exception as exc:
            info = classify_db_error(exc)
            raise AdapterUnavailableError(
                f"Execution-history write failed [{info.category}, "
                f"SQLSTATE {info.sqlstate}]",
                detail={"hint": info.hint, "table": "QUERY_EXECUTIONS"},
            ) from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    def list_executions(self, limit: int = 20) -> list[ExecutionRecord]:
        """Read the most recent execution-history rows (newest first)."""
        if self._closed:
            raise AdapterUnavailableError("Db2 adapter is closed.")
        sql = self._SELECT_EXECUTIONS_SQL.format(
            schema=self._settings.app_schema,
            limit=max(1, min(int(limit), 500)),  # Db2 forbids markers in FETCH FIRST
        )
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            records: list[ExecutionRecord] = []
            for (
                execution_id,
                req_ts,
                client_req_id,
                sql_text,
                validation_status,
                explain_status,
                execution_status,
                row_count,
                truncated,
                latency_ms,
                sqlstate_code,
                metadata,
            ) in cursor.fetchall():
                ts = (
                    req_ts.isoformat()
                    if hasattr(req_ts, "isoformat")
                    else str(req_ts or "")
                )
                records.append(
                    ExecutionRecord(
                        id=int(execution_id),
                        timestamp=ts,
                        request_id=str(client_req_id) if client_req_id else None,
                        sql=str(sql_text or ""),
                        validation_status=str(validation_status or ""),
                        explain_status=str(explain_status) if explain_status else None,
                        execution_status=str(execution_status or ""),
                        row_count=int(row_count) if row_count is not None else None,
                        truncated=str(truncated or "N").upper() == "Y",
                        latency_ms=int(latency_ms or 0),
                        sqlstate=str(sqlstate_code) if sqlstate_code else None,
                        detail=str(metadata) if metadata else None,
                    )
                )
            return records
        except AdapterUnavailableError:
            raise
        except Exception as exc:
            info = classify_db_error(exc)
            raise AdapterUnavailableError(
                f"Execution-history read failed [{info.category}, "
                f"SQLSTATE {info.sqlstate}]",
                detail={"hint": info.hint, "table": "QUERY_EXECUTIONS"},
            ) from exc
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — close is best-effort
                pass

    def close(self) -> None:
        self._closed = True
