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

import logging
import re
import threading
import weakref
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Literal

import ibm_db
import ibm_db_dbi

from .config import ConfigError, Settings

log = logging.getLogger(__name__)

Role = Literal["admin", "app", "editor", "analyst", "mart"]
SCHEMA = "ASOF"

IDENT_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
SCHEMA_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")

_SQLSTATE = re.compile(r"SQLSTATE=([0-9A-Z]{5})")
_SQLCODE = re.compile(r"SQLCODE=(-?[0-9]+)")
_SQLMSG = re.compile(r"(SQL[0-9]{4,5}[NWC][^\n]*?)(?:\s+SQLSTATE=|$)")


SQL_LOCK_TIMEOUT = "SET CURRENT LOCK TIMEOUT = ?"
SQL_PING = "SELECT 1 FROM SYSIBM.SYSDUMMY1"


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
    if role == "mart":
        settings.require("asof_mart_password")
        return settings.asof_mart_user, settings.asof_mart_password.get_secret_value()  # type: ignore[union-attr]
    raise ValueError(f"unknown role {role!r}")


def dsn(settings: Settings) -> str:
    """Connection string without credentials. Values come from validated settings.

    With DB2_SSL=true the driver speaks TLS (SECURITY=SSL), and DB2_SSL_SERVER_CERT pins the server's
    certificate (SSLServerCertificate). The certificate path is checked here: it must exist, and it must not
    carry a ';' or '=' that could add a keyword to the connection string."""
    out = (
        f"DATABASE={settings.db2_database};HOSTNAME={settings.db2_host};PORT={settings.db2_port};"
        f"PROTOCOL=TCPIP;CONNECTTIMEOUT={settings.db2_connect_timeout_s};"
    )
    if settings.db2_ssl:
        out += "SECURITY=SSL;"
        cert = settings.db2_ssl_cert_path
        if cert is not None:
            if any(ch in str(cert) for ch in ";={}"):
                raise ConfigError(f"DB2_SSL_SERVER_CERT: the path {cert} contains a character the driver cannot take")
            if not cert.is_file():
                raise ConfigError(f"DB2_SSL_SERVER_CERT: no certificate file at {cert}")
            out += f"SSLServerCertificate={cert};"
    return out


_warned_plain_tcp = False


def connect(settings: Settings, role: Role = "app", autocommit: bool = False) -> ibm_db_dbi.Connection:
    global _warned_plain_tcp
    if not settings.db2_ssl and not settings.db2_is_local and not _warned_plain_tcp:
        _warned_plain_tcp = True
        log.warning("connecting to Db2 at %s over plain TCP: set DB2_SSL=true for a remote database",
                    settings.db2_host)
    user, password = _credentials(settings, role)
    try:
        conn = ibm_db_dbi.connect(dsn(settings), user, password)
    except Exception as exc:  # noqa: BLE001 - ibm_db raises plain Exception subclasses
        raise wrap_error(
            exc, f"Cannot connect to Db2 {settings.db2_host}:{settings.db2_port}/{settings.db2_database} as {user}"
        ) from None
    conn.set_autocommit(autocommit)
    if role != "admin":  # setup (the owner) may wait on its own DDL; the runtime users must not wait forever
        try:
            execute(conn, SQL_LOCK_TIMEOUT, (settings.db2_lock_timeout_s,))
        except DatabaseError:
            conn.close()
            raise
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


def _close_quietly(conn: ibm_db_dbi.Connection) -> None:
    try:
        conn.close()
    except Exception:  # noqa: BLE001, S110 - a broken connection is being thrown away anyway
        pass


class PooledConnection:
    """A checked-out pooled connection. Use it like the ibm_db_dbi connection it wraps;
    close() hands it back to the pool instead of closing it."""

    def __init__(self, pool: ConnectionPool, raw: ibm_db_dbi.Connection):
        self._pool, self.raw = pool, raw

    def __getattr__(self, name: str) -> Any:
        if self.raw is None:
            raise DatabaseError("this pooled connection was already returned")
        return getattr(self.raw, name)

    def close(self) -> None:
        if self.raw is not None:
            raw, self.raw = self.raw, None
            self._pool._release(raw)


class ConnectionPool:
    """A few open connections for one role, reused across requests.

    Opening a Db2 connection costs about 180 ms on the dev machine (authentication plus the session
    setup in connect()), a query on an open one about 0.5 ms, and one check opens two to six. A
    checked-out connection belongs to one caller until it is closed. A returned one is rolled back,
    and an idle one is pinged before it is handed out again, so a connection broken by a Db2 restart
    is dropped and replaced instead of failing a check. At most `size` idle connections are kept and
    at most `max_open` are checked out at once; a caller that cannot get one within `wait_s` gets a
    DatabaseError, so a burst of requests fails closed instead of opening connections without limit.
    """

    def __init__(self, settings: Settings, role: Role = "app", size: int = 8, max_open: int = 16,
                 wait_s: float | None = None):
        self._settings, self._role, self._size = settings, role, size
        self._idle: list[ibm_db_dbi.Connection] = []
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(max_open)
        self._wait_s = settings.db2_connect_timeout_s if wait_s is None else wait_s
        self._closed = False
        self.opened = 0  # connections opened over the pool's life (tests and the benchmark read it)

    def connect(self) -> PooledConnection:
        if not self._slots.acquire(timeout=self._wait_s):
            raise DatabaseError("every pooled Db2 connection is busy", sqlstate="57030")
        try:
            while True:
                with self._lock:
                    if self._closed:
                        raise DatabaseError("the connection pool is closed")
                    raw = self._idle.pop() if self._idle else None
                if raw is None:
                    conn = connect(self._settings, self._role)
                    with self._lock:
                        self.opened += 1
                    return PooledConnection(self, conn)
                try:
                    query(raw, SQL_PING)
                    return PooledConnection(self, raw)
                except Exception:  # noqa: BLE001 - however it failed, it is not handed out
                    _close_quietly(raw)
        except BaseException:
            self._slots.release()
            raise

    def _release(self, raw: ibm_db_dbi.Connection) -> None:
        try:
            try:
                raw.rollback()  # nothing a caller left uncommitted carries over to the next one
            except Exception:  # noqa: BLE001
                _close_quietly(raw)
                return
            with self._lock:
                if not self._closed and len(self._idle) < self._size:
                    self._idle.append(raw)
                    return
            _close_quietly(raw)  # pool full or closed: a connection returned late is closed, not kept
        finally:
            self._slots.release()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            idle, self._idle = self._idle, []
        for raw in idle:
            _close_quietly(raw)


def query(conn: ibm_db_dbi.Connection, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
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
        return int(cur.rowcount)
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


# ? = & are for a URL's query string (watsonx.ai needs ?version=...): inside a quoted literal they are plain
# characters, and none of them can end the literal or start a comment.
LITERAL_RE = re.compile(r"^[A-Za-z0-9_\-.:/?=&]{1,500}$")


def string_literal(value: str) -> str:
    """A quoted SQL string constant, for the few DDL clauses that accept no parameter marker.

    CREATE EXTERNAL MODEL takes its model ID, URL and API key only as string literals. This
    accepts letters, digits and `_ - . : / ? = &` and nothing else (no quote, space, semicolon or
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
    key = getattr(conn, "raw", None) or conn  # a pooled connection keeps its registers between checkouts
    try:
        if _bound_schema.get(key) == schema:
            return
    except TypeError:  # a connection type that cannot be weakly referenced: always set
        pass
    execute(conn, "SET CURRENT SCHEMA = ?", (schema,))
    execute(conn, "SET CURRENT PATH = SYSTEM PATH, ?", (schema,))
    try:
        _bound_schema[key] = schema
    except TypeError:
        pass
