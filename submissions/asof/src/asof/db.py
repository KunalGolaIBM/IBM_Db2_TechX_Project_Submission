"""Db2 connections and query helpers.

Rules this module enforces:
- One connection role per purpose: `admin` (setup only), `app` (runtime), `editor` (policy changes),
  `analyst` (read-only audit views, ledger text masked).
- Credentials are passed to the driver as separate arguments, never spliced into a DSN string.
- SQL text is a string literal in the source; every value goes through a `?` parameter marker.
  Runtime SQL uses unqualified names, and `use_schema` points the connection at a schema with
  `SET CURRENT SCHEMA = ?` and `SET CURRENT PATH = SYSTEM PATH, ?`, so even the schema is bound.
- Db2 cannot bind identifiers in DDL or GRANT. Setup code that must name an object or a user
  builds that name only through `ident`, which accepts a plain upper-case identifier and nothing
  else. `CREATE EXTERNAL MODEL` takes its URL and key only as literals; those go through
  `string_literal`, which rejects quotes and spaces. `tests/test_sql_safety.py` fails the build
  on any other string-built SQL.
- Driver errors are re-raised as DatabaseError with the SQLSTATE kept and nothing else leaked.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Literal

import ibm_db
import ibm_db_dbi

from .config import Settings

Role = Literal["admin", "app", "editor", "analyst"]
SCHEMA = "ASOF"

IDENT_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
SCHEMA_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")

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
    if role == "analyst":
        settings.require("asof_analyst_password")
        return settings.asof_analyst_user, settings.asof_analyst_password.get_secret_value()  # type: ignore[union-attr]
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
        except Exception:  # noqa: BLE001, S110 - closing a broken connection must not mask the real error
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


def validate_schema(schema: str) -> str:
    """A schema name AsOf may use: upper case, starting with a letter, at most 30 characters."""
    if not isinstance(schema, str) or not SCHEMA_RE.match(schema):
        raise ValueError(f"invalid schema name {schema!r}")
    return schema


def ident(name: str) -> str:
    """A Db2 identifier for DDL and GRANT, where Db2 accepts no parameter markers.

    Only plain upper-case identifiers pass (letters, digits, underscore). Anything else,
    including quotes, spaces, dots or semicolons, raises. Lower-case user names such as
    `asofapp` are upper-cased first, which is how Db2 stores unquoted authorization IDs.
    """
    if not isinstance(name, str):
        raise ValueError(f"invalid identifier {name!r}")
    upper = name.strip().upper()
    if not IDENT_RE.match(upper):
        raise ValueError(f"invalid identifier {name!r}")
    return upper


LITERAL_RE = re.compile(r"^[A-Za-z0-9_\-.:/]{1,500}$")


def string_literal(value: str) -> str:
    """A quoted SQL string constant, for the few DDL clauses that accept no parameter marker.

    CREATE EXTERNAL MODEL takes its model ID, URL and API key only as string literals. This
    accepts letters, digits and `_ - . : /` and nothing else (no quote, space, semicolon or
    comment marker can pass), so the value can never end the literal. The caller is
    responsible for never logging the statement when it carries a key.
    """
    if not isinstance(value, str) or not LITERAL_RE.match(value):
        raise ValueError("value is not safe as an SQL string literal")
    return "'" + value + "'"


_bound_schema: weakref.WeakKeyDictionary[ibm_db_dbi.Connection, str] = weakref.WeakKeyDictionary()


def use_schema(conn: ibm_db_dbi.Connection, schema: str = SCHEMA) -> None:
    """Make unqualified table, view and routine names on `conn` resolve to `schema`.

    Both registers are set through parameter markers. Special registers are not undone by a
    ROLLBACK, so this is done once per connection and schema, and repeated only on a change.
    """
    validate_schema(schema)
    try:
        if _bound_schema.get(conn) == schema:
            return
    except TypeError:  # a connection type that cannot be weakly referenced: always set
        pass
    execute(conn, "SET CURRENT SCHEMA = ?", (schema,))
    execute(conn, "SET CURRENT PATH = SYSTEM PATH, ?", (schema,))
    try:
        _bound_schema[conn] = schema
    except TypeError:
        pass
