"""Db2 access layer.

Two rules hold everywhere in PortProof:

1. **Every value is bound.** SQL text is never built by string interpolation,
   so there is no SQL-injection surface even though the application handles
   untrusted SQL as *data*.
2. **Db2 is the authority.** :func:`compile_check` asks the engine whether a
   statement is valid Db2 and returns the engine's own SQLCODE. Nothing in
   PortProof decides that for itself.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Sequence

import ibm_db

from .config import APPL_NAME, Db2Config, runtime_config, setup_config

_SQLCODE_RE = re.compile(r"SQLCODE=(-?\d+)")
_SQLSTATE_RE = re.compile(r"SQLSTATE=(\w{5})")


class Db2Error(RuntimeError):
    """A Db2 operation failed. Carries the engine's own diagnostics."""

    def __init__(self, message: str, sqlcode: int | None = None, sqlstate: str | None = None):
        super().__init__(message)
        self.message = message
        self.sqlcode = sqlcode
        self.sqlstate = sqlstate


def _diagnostics(fallback: BaseException | None = None) -> tuple[str, int | None, str | None]:
    """Pull the message, SQLCODE and SQLSTATE out of Db2's last error."""
    text = ""
    try:
        text = ibm_db.stmt_errormsg() or ""
    except Exception:  # pragma: no cover - driver with no statement context
        text = ""
    if not text:
        try:
            text = ibm_db.conn_errormsg() or ""
        except Exception:  # pragma: no cover
            text = ""
    if not text and fallback is not None:
        text = str(fallback)
    code = _SQLCODE_RE.search(text)
    state = _SQLSTATE_RE.search(text)
    return (
        " ".join(text.split()),
        int(code.group(1)) if code else None,
        state.group(1) if state else None,
    )


def connect(cfg: Db2Config | None = None, *, role: str = "app"):
    """Open a connection and tag it so Db2 WLM can recognise PortProof."""
    if cfg is None:
        cfg = runtime_config() if role == "app" else setup_config()
    try:
        conn = ibm_db.connect(cfg.dsn(), "", "")
    except Exception as exc:
        message, code, state = _diagnostics(exc)
        raise Db2Error(f"Could not connect as {cfg.redacted()}: {message}", code, state) from exc

    ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
    # Best effort: lets `CREATE WORKLOAD ... CURRENT CLIENT_APPLNAME` match us.
    try:
        ibm_db.set_option(conn, {ibm_db.SQL_ATTR_INFO_PROGRAMNAME: APPL_NAME}, 1)
    except Exception:  # pragma: no cover - option unsupported on some drivers
        pass
    return conn


@contextmanager
def connection(cfg: Db2Config | None = None, *, role: str = "app") -> Iterator[Any]:
    conn = connect(cfg, role=role)
    try:
        yield conn
    finally:
        try:
            ibm_db.close(conn)
        except Exception:  # pragma: no cover
            pass


def execute(conn, sql: str, params: Sequence[Any] = ()) -> None:
    """Run a statement with bound parameters."""
    try:
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, tuple(params))
    except Exception as exc:
        message, code, state = _diagnostics(exc)
        raise Db2Error(message or str(exc), code, state) from exc


def fetch_all(conn, sql: str, params: Sequence[Any] = ()) -> list[tuple]:
    """Run a query with bound parameters and return every row."""
    try:
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, tuple(params))
    except Exception as exc:
        message, code, state = _diagnostics(exc)
        raise Db2Error(message or str(exc), code, state) from exc

    rows: list[tuple] = []
    row = ibm_db.fetch_tuple(stmt)
    while row is not False and row is not None:
        rows.append(tuple(row))
        row = ibm_db.fetch_tuple(stmt)
    return rows


def fetch_one(conn, sql: str, params: Sequence[Any] = ()) -> tuple | None:
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


def call_proc(conn, name: str, args: Sequence[Any]) -> tuple:
    """CALL a stored procedure and return its parameters with OUT values filled.

    ``name`` is a fixed identifier from PortProof's own code, never user input;
    every *value* is bound by the driver.
    """
    try:
        result = ibm_db.callproc(conn, name, tuple(args))
    except Exception as exc:
        message, code, state = _diagnostics(exc)
        raise Db2Error(message or str(exc), code, state) from exc
    if result is None:
        raise Db2Error(f"CALL {name} returned no parameter tuple")
    # callproc returns (stmt, *params) on some driver versions and just the
    # params on others; normalise to the parameter tuple.
    if isinstance(result, tuple) and len(result) == len(args) + 1:
        return tuple(result[1:])
    return tuple(result)


@dataclass(frozen=True)
class CompileResult:
    """What Db2 said about a candidate statement."""

    ok: bool
    sqlcode: int | None = None
    sqlstate: str | None = None
    message: str = ""

    @property
    def summary(self) -> str:
        return "compiles on Db2" if self.ok else f"SQLCODE={self.sqlcode} {self.message[:200]}"


def compile_check(conn, candidate_sql: str) -> CompileResult:
    """Ask Db2 whether ``candidate_sql`` is valid Db2 SQL.

    This is PortProof's compile oracle. ``PREPARE`` parses, resolves every name
    against the live catalog and type-checks, **without executing anything** --
    so an invalid or hostile statement never runs here.
    """
    try:
        ibm_db.prepare(conn, candidate_sql)
        return CompileResult(ok=True)
    except Exception as exc:
        message, code, state = _diagnostics(exc)
        return CompileResult(ok=False, sqlcode=code, sqlstate=state, message=message or str(exc))


def explain_cost(conn, candidate_sql: str) -> float | None:
    """Estimated total cost in timerons, from Db2's own optimiser.

    Returns ``None`` when the statement is not explainable (DDL, or no EXPLAIN
    tables in this database).
    """
    try:
        ibm_db.exec_immediate(conn, f"EXPLAIN PLAN FOR {candidate_sql}")
    except Exception:
        return None
    row = None
    try:
        row = fetch_one(
            conn,
            "SELECT TOTAL_COST FROM EXPLAIN_OPERATOR "
            "WHERE OPERATOR_TYPE = 'RETURN' ORDER BY EXPLAIN_TIME DESC "
            "FETCH FIRST 1 ROWS ONLY",
        )
    except Db2Error:
        return None
    return float(row[0]) if row and row[0] is not None else None


def server_version(conn) -> str:
    row = fetch_one(conn, "SELECT SERVICE_LEVEL FROM TABLE(SYSPROC.ENV_GET_INST_INFO())")
    return row[0].strip() if row else "unknown"


def current_identity(conn) -> tuple[str, str]:
    row = fetch_one(conn, "SELECT CURRENT USER, CURRENT SCHEMA FROM SYSIBM.SYSDUMMY1")
    return (row[0].strip(), row[1].strip()) if row else ("?", "?")


def split_script(text: str) -> Iterable[str]:
    """Split a .sql file on lines containing only ``--@``."""
    for chunk in re.split(r"(?m)^\s*--@\s*$", text):
        statement = chunk.strip()
        if statement and not all(
            line.strip().startswith("--") or not line.strip()
            for line in statement.splitlines()
        ):
            yield statement
