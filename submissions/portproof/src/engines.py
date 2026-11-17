"""Two more source engines: SQL Server and SQLite.

PortProof started with PostgreSQL and MySQL. Adding an engine is deliberately
small: a class that can load a dataset and run a statement, registered under the
dialect name ``sqlglot`` reads. Nothing in the prover, the repair loops or the
ledger knows which engines exist.

Both of these are the real engine, for the reason :class:`MySqlSource` gives.
The differences that matter live in the engine, not in the data:

* **SQL Server**: the default collation is case-insensitive, ``+`` concatenates
  strings and returns NULL if either side is NULL, ``LEN`` does not count
  trailing blanks, ``=`` ignores them, and NULLs sort first.
* **SQLite**: typing is dynamic. A ``DECIMAL(10,2)`` column has NUMERIC
  affinity, so ``7.00`` is stored as the integer ``7`` and ``amount / quantity``
  becomes integer division. ``LIKE`` is case-insensitive for ASCII, and NULLs
  sort first.
"""
from __future__ import annotations

import sqlite3

from .corpus import Variant
from .counterexample import Namespaced, ResultSet, portable_ddl


class SqliteSource(Namespaced):
    """The real SQLite, in process. No server, and no stand-in."""

    name = "sqlite"
    dialect = "sqlite"

    def __init__(self, path: str = ":memory:") -> None:
        self._home_conn = sqlite3.connect(path)
        self._conn = self._home_conn
        self._ns_conns: dict[str, sqlite3.Connection] = {}

    def load(self, variant: Variant) -> None:
        self.home()
        self._load_here(variant)

    def _load_here(self, variant: Variant) -> None:
        self._count_load()
        cur = self._conn.cursor()
        for table in variant.schema_tables:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
        for ddl in variant.schema_ddl:
            cur.execute(ddl)
        for table in variant.schema_tables:
            rows = variant.rows.get(table, [])
            if not rows:
                continue
            placeholders = ", ".join("?" for _ in rows[0])
            cur.executemany(f"INSERT INTO {table} VALUES ({placeholders})", [list(r) for r in rows])
        self._conn.commit()

    # An in-memory SQLite database *is* a connection, so a namespace is one.
    def _ns_create(self, namespace: str) -> None:
        self._ns_drop(namespace)
        self._ns_conns[namespace] = sqlite3.connect(":memory:")

    def _ns_switch(self, namespace: str | None) -> None:
        self._conn = self._ns_conns[namespace] if namespace else self._home_conn

    def _ns_drop(self, namespace: str) -> None:
        conn = self._ns_conns.pop(namespace, None)
        if conn is not None:
            conn.close()

    def run(self, sql: str) -> ResultSet:
        cur = self._conn.execute(sql)
        rows = [tuple(r) for r in cur.fetchall()]
        columns = tuple(d[0] for d in (cur.description or ()))
        return ResultSet(rows=rows, columns=columns)

    def close(self) -> None:
        self.drop_namespaces()
        try:
            self._home_conn.close()
        except Exception:  # pragma: no cover
            pass


class SqlServerSource(Namespaced):
    """A real SQL Server.

    Connection settings come from the environment (``MSSQL_*``); see
    ``.env.example``. A namespace is a database, because unqualified names
    resolve against the login's default schema and ``USE`` is the one switch
    that needs no change to the SQL under test.
    """

    name = "sqlserver"
    dialect = "tsql"

    def __init__(self) -> None:
        import pymssql

        from .config import sqlserver_config

        cfg = sqlserver_config()
        if not cfg.password:
            raise RuntimeError("MSSQL_PASSWORD is not set")
        self._home = cfg.database
        self._conn = pymssql.connect(
            server=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database="master",
            autocommit=True,
            login_timeout=5,
            timeout=60,
        )
        with self._conn.cursor() as cur:
            cur.execute(f"IF DB_ID('{self._home}') IS NULL CREATE DATABASE {self._home}")
            cur.execute(f"USE {self._home}")

    def load(self, variant: Variant) -> None:
        self.home()
        self._load_here(variant)

    def _load_here(self, variant: Variant) -> None:
        self._count_load()
        with self._conn.cursor() as cur:
            for table in variant.schema_tables:
                cur.execute(f"DROP TABLE IF EXISTS {table}")
            for ddl in variant.schema_ddl:
                cur.execute(portable_ddl(ddl, "tsql"))
            for table in variant.schema_tables:
                rows = variant.rows.get(table, [])
                if not rows:
                    continue
                placeholders = ", ".join(["%s"] * len(rows[0]))
                cur.executemany(
                    f"INSERT INTO {table} VALUES ({placeholders})", [tuple(r) for r in rows]
                )

    def _ns_create(self, namespace: str) -> None:
        self._ns_drop(namespace)
        with self._conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE {namespace}")

    def _ns_switch(self, namespace: str | None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"USE {namespace or self._home}")

    def _ns_drop(self, namespace: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute("USE master")
            cur.execute(f"IF DB_ID('{namespace}') IS NOT NULL DROP DATABASE {namespace}")

    def run(self, sql: str) -> ResultSet:
        with self._conn.cursor() as cur:
            cur.execute(sql)
            rows = [tuple(r) for r in (cur.fetchall() or ())]
            columns = tuple(d[0] for d in (cur.description or ()))
        return ResultSet(rows=rows, columns=columns)

    def close(self) -> None:
        self.drop_namespaces()
        try:
            self._conn.close()
        except Exception:  # pragma: no cover
            pass
