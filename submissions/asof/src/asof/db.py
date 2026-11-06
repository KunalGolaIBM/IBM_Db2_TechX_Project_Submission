"""Db2 connections and query helpers.

Rules this module enforces:
- One connection role per purpose: `admin` (setup only), `app` (runtime), `editor` (policy changes).
- Credentials are passed to the driver as separate arguments, never spliced into a DSN string.
- SQL text is always a constant; every value goes through a `?` parameter marker.
- Driver errors are re-raised as DatabaseError with the SQLSTATE kept and nothing else leaked.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Literal

import ibm_db
import ibm_db_dbi

from .config import Settings

Role = Literal["admin", "app", "editor"]
SCHEMA = "ASOF"

_SQLSTATE = re.compile(r"SQLSTATE=([0-9A-Z]{5})")
_SQLCODE = re.compile(r"SQLCODE=(-?[0-9]+)")
_SQLMSG = re.compile(r"(SQL[0-9]{4,5}[NWC][^\n]*?)(?:\s+SQLSTATE=|$)")


class DatabaseError(RuntimeError):
    """A Db2 error with its SQLSTATE, safe to log and show."""

    def __init__(self, message: str, sqlstate: str | None = None, sqlcode: int | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate
        self.sqlcode = sqlcode


def wrap_error(exc: BaseException, context: str) -> DatabaseError:
    text = str(exc)
    state = _SQLSTATE.search(text)
    code = _SQLCODE.search(text)
    msg = _SQLMSG.search(text)
    detail = msg.group(1).strip() if msg else type(exc).__name__
    return DatabaseError(
        f"{context}: {detail}",
        sqlstate=state.group(1) if state else None,
        sqlcode=int(code.group(1)) if code else None,
    )


def _credentials(settings: Settings, role: Role) -> tuple[str, str]:
    if role == "admin":
        settings.require("db2_admin_password")
        return settings.db2_admin_user, settings.db2_admin_password.get_secret_value()  # type: ignore[union-attr]
    if role == "app":
        settings.require("asof_app_password")
        return settings.asof_app_user, settings.asof_app_password.get_secret_value()  # type: ignore[union-attr]
    if role == "editor":
        settings.require("asof_editor_password")
        return settings.asof_editor_user, settings.asof_editor_password.get_secret_value()  # type: ignore[union-attr]
    raise ValueError(f"unknown role {role!r}")


def dsn(settings: Settings) -> str:
    """Connection string without credentials. Values come from validated settings."""
    return (
        f"DATABASE={settings.db2_database};HOSTNAME={settings.db2_host};PORT={settings.db2_port};"
        f"PROTOCOL=TCPIP;CONNECTTIMEOUT={settings.db2_connect_timeout_s};"
    )


def connect(settings: Settings, role: Role = "app", autocommit: bool = False) -> ibm_db_dbi.Connection:
    user, password = _credentials(settings, role)
    try:
        conn = ibm_db_dbi.connect(dsn(settings), user, password)
    except Exception as exc:  # noqa: BLE001 - ibm_db raises plain Exception subclasses
        raise wrap_error(
            exc, f"Cannot connect to Db2 {settings.db2_host}:{settings.db2_port}/{settings.db2_database} as {user}"
        ) from None
    conn.set_autocommit(autocommit)
    return conn


@contextmanager
def connection(settings: Settings, role: Role = "app", autocommit: bool = False) -> Iterator[ibm_db_dbi.Connection]:
    conn = connect(settings, role, autocommit)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - closing a broken connection must not mask the real error
            pass


def query(conn: ibm_db_dbi.Connection, sql: str, params: Sequence[Any] = ()) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        raise wrap_error(exc, "Query failed") from None
    finally:
        cur.close()


def execute(conn: ibm_db_dbi.Connection, sql: str, params: Sequence[Any] = ()) -> int:
    cur = conn.cursor()
    try:
        cur.execute(sql, tuple(params))
        return cur.rowcount
    except Exception as exc:  # noqa: BLE001
        raise wrap_error(exc, "Statement failed") from None
    finally:
        cur.close()


def server_version(conn: ibm_db_dbi.Connection) -> str:
    """Db2 server version string, read from the driver (no fenced routine needed)."""
    info = ibm_db.server_info(conn.conn_handler)
    return f"{info.DBMS_NAME} {info.DBMS_VER}"


def vector_literal(embedding: Sequence[float]) -> str:
    """Format an embedding for a `VECTOR(?, n, FLOAT32)` parameter, as langchain-db2 does."""
    return "[" + ",".join(f"{float(x):.8g}" for x in embedding) + "]"
