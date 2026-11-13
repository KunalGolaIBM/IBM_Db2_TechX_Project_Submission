"""Stage 3: prove meaning, not just syntax.

A statement that compiles on Db2 can still be *wrong*: it runs, returns rows,
and the rows differ from what the source engine returned. Those are the
migration bugs that reach production silently.

PortProof attacks that by construction. For each statement it loads a series of
**adversarial datasets** -- each one built to expose a specific documented
difference between the engines (case-sensitive collation, NULL ordering, integer
division, unstable ties, empty groups) -- runs the original SQL on the source
engine and the translated SQL on Db2, and compares the results.

The verdict is deliberately modest. Proving two SQL programs equivalent is
undecidable in general, so PortProof never claims "equivalent". It reports
**equivalent on N adversarial instances**, or **proven different** with the
witness rows that disagree. A counterexample is a proof; an absence of one is
evidence.
"""
from __future__ import annotations

import datetime as _dt
import decimal
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from . import db
from .corpus import FIXTURE_DDL, FIXTURE_TABLES, VARIANTS, Variant

#: Dedicated Db2 schema for throwaway adversarial fixtures.
FIXTURE_SCHEMA = "PPTEST"

_ORDER_BY_RE = re.compile(r"\border\s+by\b", re.IGNORECASE)
#: A string that is entirely a decimal number, e.g. '50.00', '-3', '1.5E+2'.
_DECIMAL_LITERAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


# --------------------------------------------------------------------------
# value canonicalisation
# --------------------------------------------------------------------------
def canon_value(value: Any) -> str:
    """Render a value so two engines' spellings of the same datum match.

    Engines differ in surface form, not meaning: ``Decimal('50.00')`` and
    ``50.0``, ``True`` and ``1``, a padded ``CHAR`` and a ``VARCHAR``. Those are
    not semantic differences and must not be reported as ones.
    """
    if value is None:
        return "<null>"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, decimal.Decimal)):
        try:
            number = decimal.Decimal(str(value))
        except decimal.InvalidOperation:  # pragma: no cover
            return str(value)
        # Always format in positional notation. ``normalize()`` alone returns
        # exponent form for trailing-zero values ("5E+1" for 50.00), and
        # stripping zeros from an integer string would turn 100 into 1 -- both
        # would be reported as semantic differences when they are not.
        if number == number.to_integral_value():
            return format(number.to_integral_value(), "f")
        return format(number.normalize(), "f")
    if isinstance(value, _dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, _dt.date):  # date.isoformat takes no arguments
        return value.isoformat()
    if isinstance(value, _dt.timedelta):  # pragma: no cover
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, (list, tuple)):
        # An array column. psycopg hands back a Python list, whose repr is
        # Python's ("[10, 11]"), not SQL's. Render it the way the engine itself
        # renders an array cast to text, so that a Db2 rewrite producing that
        # text can be compared with it rather than against Python syntax.
        return "{" + ",".join(canon_value(v) for v in value) + "}"
    text = str(value).rstrip()
    # The drivers disagree about *type*, not meaning: ibm_db hands back a
    # DECIMAL column as the string '50.00' while DuckDB returns Decimal('50.00').
    # Canonicalising numeric-looking strings the same way as numbers keeps that
    # driver artefact out of the verdict.
    #
    # Trade-off, accepted deliberately: a VARCHAR literally containing '50.00'
    # now compares equal to the number 50. That is far rarer than the driver
    # mismatch, and reporting the mismatch as a semantic difference would make
    # every verdict untrustworthy.
    if _DECIMAL_LITERAL_RE.match(text):
        return canon_value(decimal.Decimal(text))
    return text


def canon_rows(rows: Sequence[Sequence[Any]], *, ordered: bool) -> list[tuple[str, ...]]:
    canon = [tuple(canon_value(v) for v in row) for row in rows]
    return canon if ordered else sorted(canon)


def canon_columns(names: Sequence[str]) -> tuple[str, ...]:
    """Normalise result column names for comparison.

    Case and padding differ between engines by convention, not by meaning: Db2
    folds unquoted identifiers to upper case, DuckDB keeps them lower. Anything
    beyond that -- a different name, or a different number of columns -- is a
    real difference in what the statement produces.
    """
    return tuple(str(n).strip().upper() for n in names)


#: Engines generate names like "1" or "EXPR" for unaliased expressions, and they
#: do not agree on the spelling. Comparing those would be noise, not signal.
_GENERATED_COLUMN_RE = re.compile(r"^(?:\d+|\?+|EXPR\d*|COL\d+|_?C\d+|CASE|UNNAMED.*)$")


def comparable_columns(names: Sequence[str]) -> tuple[str, ...]:
    """The subset of column names worth comparing across engines."""
    canon = canon_columns(names)
    if any(_GENERATED_COLUMN_RE.match(n) for n in canon):
        return ()
    return canon


#: Comments and quoted literals, stripped before any structural scan of SQL so
#: that the word "order by" inside a string or a comment cannot be mistaken for
#: a clause.
_NOISE_RE = re.compile(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", re.S)


def has_outer_order_by(sql: str) -> bool:
    """True only if the statement's *own* result order is specified.

    Row order is asserted only when the outermost query orders its rows. An
    ``ORDER BY`` inside ``OVER (...)``, inside a subquery, or inside a CTE says
    nothing about the order the rows come back in -- so matching the bare words
    made PortProof compare a window function's output positionally and report
    engine-dependent tie order as a semantic difference.

    Nesting is tracked by parenthesis depth, which is why comments and string
    literals are removed first: an unbalanced ``'('`` in a literal would shift
    the depth of everything after it.
    """
    clean = _NOISE_RE.sub(" ", sql)
    depth = 0
    for match in re.finditer(r"\(|\)|\border\s+by\b", clean, re.IGNORECASE):
        token = match.group(0)
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            return True
    return False


# --------------------------------------------------------------------------
# engines
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultSet:
    """Rows plus the column names that produced them."""

    rows: list[tuple]
    columns: tuple[str, ...] = ()

    def __len__(self) -> int:  # convenience for `len(result)`
        return len(self.rows)


class SourceEngine(Protocol):
    """The engine the SQL is migrating *from*."""

    name: str
    #: The source dialect this engine faithfully implements. The prover refuses
    #: to certify a statement whose dialect this engine does not speak.
    dialect: str

    def load(self, variant: Variant) -> None: ...
    def run(self, sql: str) -> ResultSet: ...
    def close(self) -> None: ...


class Namespaced:
    """Load each dataset once, into a namespace of its own, and switch to it.

    ``load`` drops, creates and fills the tables in the engine's home
    namespace, every time it is called. That is the right contract for a
    single proof and the wrong cost for a run: 38 statements over six datasets
    was 228 full reloads of each engine, all of them reloading rows the engine
    had held a moment earlier.

    ``use`` is the same promise -- "after this call the engine holds exactly
    this dataset" -- kept by switching to a namespace named after the dataset's
    content hash, and loading it only the first time it is asked for. The
    namespaces belong to the process and are dropped by ``close``.

    A second reason matters more than speed. A dataset generated for a schema
    discovered on a customer's source engine must never be loaded over the
    customer's own tables, and a namespace is how it is kept away from them.
    """

    #: More than this and the least recently created namespace is dropped.
    MAX_NAMESPACES = 96

    def _spaces(self) -> dict[str, str]:
        return self.__dict__.setdefault("_ns", {})

    def use(self, variant: Variant) -> None:
        spaces = self._spaces()
        key = variant.fingerprint
        namespace = spaces.get(key)
        if namespace is not None:
            self._ns_switch(namespace)
            return
        if len(spaces) >= self.MAX_NAMESPACES:
            oldest = next(iter(spaces))
            self._ns_switch(None)
            self._ns_drop(spaces.pop(oldest))
        namespace = f"ppv_{key[:12]}"
        self._ns_create(namespace)
        self._ns_switch(namespace)
        try:
            self._load_here(variant)
        except Exception:
            # A dataset the engine refuses must not leave half a namespace
            # behind: nothing would ever know to drop it.
            try:
                self._ns_switch(None)
                self._ns_drop(namespace)
            except Exception:  # pragma: no cover - cleanup only
                pass
            raise
        spaces[key] = namespace

    def home(self) -> None:
        """Back to the namespace the engine was opened on."""
        self._ns_switch(None)

    def drop_namespaces(self) -> None:
        spaces = self._spaces()
        try:
            self._ns_switch(None)
        except Exception:  # pragma: no cover - connection already gone
            return
        for namespace in list(spaces.values()):
            try:
                self._ns_drop(namespace)
            except Exception:  # pragma: no cover - cleanup must never raise
                pass
        spaces.clear()

    @property
    def loads(self) -> int:
        """How many datasets this engine has actually had to load."""
        return self.__dict__.get("_loads", 0)

    def _count_load(self) -> None:
        self.__dict__["_loads"] = self.loads + 1


def activate(engine: Any, variant: Variant) -> None:
    """Make ``engine`` hold ``variant``, as cheaply as the engine allows."""
    use = getattr(engine, "use", None)
    if callable(use):
        use(variant)
    else:
        engine.load(variant)


def go_home(engine: Any) -> None:
    home = getattr(engine, "home", None)
    if callable(home):
        try:
            home()
        except Exception:  # pragma: no cover - never mask the verdict
            pass


def portable_ddl(ddl: str, dialect: str) -> str:
    """Adapt the shared DDL vocabulary to one engine's spelling of it.

    The fixture and every generated schema are written in one small portable
    vocabulary (INTEGER, BIGINT, DECIMAL, DOUBLE, VARCHAR, BOOLEAN, DATE,
    TIMESTAMP). Each engine needs at most a type renamed.
    """
    if dialect == "mysql":
        return _mysql_ddl(ddl)
    if dialect == "tsql":
        ddl = re.sub(r"\bBOOLEAN\b", "BIT", ddl, flags=re.IGNORECASE)
        ddl = re.sub(r"\bTIMESTAMP\b", "DATETIME2(0)", ddl, flags=re.IGNORECASE)
        ddl = re.sub(r"\bDOUBLE\b", "FLOAT", ddl, flags=re.IGNORECASE)
        # NVARCHAR, so the accent datasets are stored as written rather than
        # squeezed through the server's single-byte code page.
        return re.sub(r"\bVARCHAR\b", "NVARCHAR", ddl, flags=re.IGNORECASE)
    return ddl


def unfaithful(source: Any, sql: str) -> str:
    """Why ``source`` cannot be trusted about ``sql``, or "" if it can.

    An engine standing in for another one is entitled -- required -- to say so.
    A stand-in that answers confidently where it is known to differ from the
    engine it represents does not produce a weaker verdict; it produces a wrong
    one, attributed to the engine it is impersonating.
    """
    declare = getattr(source, "declared_divergences", None)
    return declare(sql) if callable(declare) else ""


class DuckDbSource(Namespaced):
    """Embedded PostgreSQL stand-in, so judges need no server.

    DuckDB implements PostgreSQL's dialect closely and is the zero-setup default.
    It is a *stand-in*, and this class says where the stand-in ends:

    * ``/`` on two integers. Measured: DuckDB returns 3.5 for ``7 / 2``;
      PostgreSQL and Db2 both return 3. Judging that statement here reported
      PROVEN DIFFERENT against Db2 when PostgreSQL and Db2 actually agree -- a
      false accusation, and the mirror image of the false EQUIVALENT below.
    * decimal division generally. DuckDB returns a 64-bit float
      (``0.0014285714285714286``); PostgreSQL returns an exact ``numeric`` and
      Db2 a wider DECIMAL, so the three disagree in three different ways and
      only two of them are a migration finding.
    * ``array_agg``, whose text rendering is DuckDB's, not PostgreSQL's.

    It is emphatically not a stand-in for MySQL, and PortProof used to pretend
    otherwise. MySQL's divergences -- case-insensitive default collation, ``7/2``
    returning 3.5 -- are properties of the engine, not of the data, so no
    fixture can recover them. Judging a MySQL statement here produced a *false*
    verdict: ``mysql/case_insensitive_eq`` returns rows on real MySQL and none
    on Db2, but DuckDB also returned none, so two empty results matched and
    PortProof certified EQUIVALENT.

    Both failures have the same cause and the same cure: run the real engine
    (:class:`PostgresSource`, :class:`MySqlSource`), and where you cannot, say
    so instead of guessing.
    """

    name = "duckdb(postgresql stand-in)"
    dialect = "postgres"

    #: Constructs on which this engine is known to differ from the PostgreSQL it
    #: stands in for. Each was measured, not assumed.
    DIVERGENCES: tuple[tuple[str, str], ...] = (
        (
            r"/",
            "DuckDB's '/' is floating-point division (7/2 = 3.5); PostgreSQL's "
            "integer '/' truncates (7/2 = 3) and its numeric '/' is exact, so "
            "DuckDB cannot adjudicate division against Db2",
        ),
        (
            r"\barray_agg\b",
            "DuckDB renders array_agg as '[10, 11]'; PostgreSQL renders it "
            "'{10,11}', so the text comparison would measure DuckDB's "
            "formatting rather than the migration",
        ),
    )

    def __init__(self) -> None:
        import duckdb

        self._conn = duckdb.connect()

    def declared_divergences(self, sql: str) -> str:
        stripped = _NOISE_RE.sub(" ", sql)
        for pattern, reason in self.DIVERGENCES:
            if re.search(pattern, stripped, re.IGNORECASE):
                return reason
        return ""

    def load(self, variant: Variant) -> None:
        self.home()
        self._load_here(variant)

    def _load_here(self, variant: Variant) -> None:
        self._count_load()
        for table in variant.schema_tables:
            self._conn.execute(f"DROP TABLE IF EXISTS {table}")
        for ddl in variant.schema_ddl:
            self._conn.execute(ddl)
        for table in variant.schema_tables:
            for row in variant.rows.get(table, []):
                placeholders = ", ".join("?" for _ in row)
                self._conn.execute(f"INSERT INTO {table} VALUES ({placeholders})", list(row))

    def _ns_create(self, namespace: str) -> None:
        self._conn.execute(f"DROP SCHEMA IF EXISTS {namespace} CASCADE")
        self._conn.execute(f"CREATE SCHEMA {namespace}")

    def _ns_switch(self, namespace: str | None) -> None:
        self._conn.execute(f"USE memory.{namespace or 'main'}")

    def _ns_drop(self, namespace: str) -> None:
        self._conn.execute(f"DROP SCHEMA IF EXISTS {namespace} CASCADE")

    def run(self, sql: str) -> ResultSet:
        cur = self._conn.execute(sql)
        rows = [tuple(r) for r in cur.fetchall()]
        columns = tuple(d[0] for d in (cur.description or ()))
        return ResultSet(rows=rows, columns=columns)

    def close(self) -> None:
        self.drop_namespaces()
        try:
            self._conn.close()
        except Exception:  # pragma: no cover
            pass


class PostgresSource(Namespaced):
    """A real PostgreSQL, when one is reachable.

    Preferred over :class:`DuckDbSource` for exactly the reasons that class
    documents: integer division, decimal division and ``array_agg`` rendering
    are PostgreSQL's, so the comparison against Db2 measures the migration
    rather than the stand-in.

    Connection settings come from the environment; see ``.env.example``.
    """

    name = "postgresql"
    dialect = "postgres"

    def __init__(self) -> None:
        import psycopg

        from .config import postgres_config

        cfg = postgres_config()
        self._conn = psycopg.connect(
            host=cfg.host,
            port=cfg.port,
            dbname=cfg.database,
            user=cfg.user,
            password=cfg.password,
            autocommit=True,
            connect_timeout=5,
        )

    def load(self, variant: Variant) -> None:
        self.home()
        self._load_here(variant)

    def _load_here(self, variant: Variant) -> None:
        self._count_load()
        with self._conn.cursor() as cur:
            for table in variant.schema_tables:
                cur.execute(f"DROP TABLE IF EXISTS {table}")
            for ddl in variant.schema_ddl:
                cur.execute(ddl)
            for table in variant.schema_tables:
                rows = variant.rows.get(table, [])
                if not rows:
                    continue
                placeholders = ", ".join(["%s"] * len(rows[0]))
                cur.executemany(
                    f"INSERT INTO {table} VALUES ({placeholders})", [list(r) for r in rows]
                )

    def _ns_create(self, namespace: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {namespace} CASCADE")
            cur.execute(f"CREATE SCHEMA {namespace}")

    def _ns_switch(self, namespace: str | None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"SET search_path TO {namespace or 'public'}")

    def _ns_drop(self, namespace: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {namespace} CASCADE")

    def run(self, sql: str) -> ResultSet:
        with self._conn.cursor() as cur:
            cur.execute(sql)
            rows = [tuple(r) for r in (cur.fetchall() or ())]
            columns = tuple(d.name for d in (cur.description or ()))
        return ResultSet(rows=rows, columns=columns)

    def close(self) -> None:
        self.drop_namespaces()
        try:
            self._conn.close()
        except Exception:  # pragma: no cover
            pass


class MySqlSource(Namespaced):
    """A real MySQL, because MySQL semantics live in the engine.

    The two divergences the corpus cares about cannot be emulated by a
    PostgreSQL-compatible engine, because they are not expressible in data:

    * the default collation (``utf8mb4_0900_ai_ci``) makes ``=`` on strings
      case-insensitive, so ``name = 'asha smith'`` matches ``'Asha Smith'``;
    * ``7 / 2`` is ``3.5`` (``/`` is decimal division; ``DIV`` is the integer one).

    Db2 disagrees with both. Those are exactly the migration bugs PortProof
    exists to catch, and with DuckDB standing in for MySQL it certified the
    first one as EQUIVALENT.

    Connection settings are read from the environment; see ``.env.example``.
    """

    name = "mysql"
    dialect = "mysql"

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        import pymysql

        from .config import mysql_config

        cfg = mysql_config()
        self._pymysql = pymysql
        self._home = database or cfg.database
        self._conn = pymysql.connect(
            host=host or cfg.host,
            port=int(port or cfg.port),
            user=user or cfg.user,
            password=password if password is not None else cfg.password,
            database=database or cfg.database,
            autocommit=True,
            charset="utf8mb4",
        )

    def load(self, variant: Variant) -> None:
        self.home()
        self._load_here(variant)

    def _load_here(self, variant: Variant) -> None:
        self._count_load()
        with self._conn.cursor() as cur:
            for table in variant.schema_tables:
                cur.execute(f"DROP TABLE IF EXISTS {table}")
            for ddl in variant.schema_ddl:
                cur.execute(_mysql_ddl(ddl))
            for table in variant.schema_tables:
                rows = variant.rows.get(table, [])
                if not rows:
                    continue
                placeholders = ", ".join(["%s"] * len(rows[0]))
                cur.executemany(
                    f"INSERT INTO {table} VALUES ({placeholders})", [list(r) for r in rows]
                )

    def _ns_create(self, namespace: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {namespace}")
            cur.execute(f"CREATE DATABASE {namespace}")

    def _ns_switch(self, namespace: str | None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"USE {namespace or self._home}")

    def _ns_drop(self, namespace: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {namespace}")

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


def available_sources(
    *, mysql: bool = True, real_postgres: bool = True, sqlserver: bool = True, sqlite: bool = True
) -> dict[str, SourceEngine]:
    """The best source engine reachable for each dialect.

    A real server is preferred over a stand-in, and an engine that cannot be
    started is simply absent. Both halves are deliberate:

    * PostgreSQL falls back to the embedded DuckDB, which declares the
      constructs it cannot adjudicate rather than answering for them.
    * MySQL has no fallback at all. A missing MySQL makes the MySQL statements
      *inconclusive*; it never promotes a substitute, because a substitute's
      agreement with Db2 is not evidence about MySQL.
    """
    sources: dict[str, SourceEngine] = {}
    if real_postgres:
        try:
            sources["postgres"] = PostgresSource()
        except Exception:
            pass
    if "postgres" not in sources:
        try:
            sources["postgres"] = DuckDbSource()
        except Exception:  # pragma: no cover - duckdb is a hard dependency
            pass
    if mysql:
        try:
            sources["mysql"] = MySqlSource()
        except Exception:
            pass
    # Imported here because src.engines imports this module for the protocol.
    from .engines import SqliteSource, SqlServerSource

    if sqlserver:
        # Like MySQL, no fallback: nothing else has SQL Server's collation,
        # its '+' or its LEN, so a missing server means INCONCLUSIVE.
        try:
            sources["tsql"] = SqlServerSource()
        except Exception:
            pass
    if sqlite:
        # The real engine, in process. It needs no server and no stand-in.
        try:
            sources["sqlite"] = SqliteSource()
        except Exception:  # pragma: no cover - sqlite3 ships with Python
            pass
    return sources


def _mysql_ddl(ddl: str) -> str:
    """Make the shared fixture DDL acceptable to MySQL.

    MySQL has no ``BOOLEAN`` type of its own -- it is a synonym for
    ``TINYINT(1)`` -- which is fine, but ``TIMESTAMP`` columns are implicitly
    ``NOT NULL`` with an automatic default, so they are declared ``DATETIME``
    here to keep NULL handling identical across the three engines.
    """
    return re.sub(r"\bTIMESTAMP\b", "DATETIME", ddl, flags=re.IGNORECASE)


class Db2Target(Namespaced):
    """The Db2 side of the comparison, in throwaway fixture schemas.

    ``PPTEST`` is home. Each dataset loaded through ``use`` gets a schema of
    its own (``PPV_<hash>``), reached with ``SET CURRENT SCHEMA``, which is
    also what makes unqualified application SQL resolve against it.
    """

    name = "Db2"

    def __init__(self, conn) -> None:
        self.conn = conn
        # Idempotent, and kept here as well so a target is self-sufficient even
        # if someone changed the schema in between.
        db.execute(conn, f"SET CURRENT SCHEMA {FIXTURE_SCHEMA}")

    def load(self, variant: Variant) -> None:
        self.home()
        self._load_into(FIXTURE_SCHEMA, variant)

    def _load_here(self, variant: Variant) -> None:
        self._load_into(self.__dict__["_current"], variant)

    def _load_into(self, schema: str, variant: Variant) -> None:
        self._count_load()
        for table in variant.schema_tables:
            try:
                db.execute(self.conn, f"DROP TABLE {schema}.{table}")
            except db.Db2Error:
                pass
        for ddl in variant.schema_ddl:
            db.execute(self.conn, _qualify(ddl, schema))
        for table in variant.schema_tables:
            rows = variant.rows.get(table, [])
            if not rows:
                continue
            placeholders = ", ".join("?" for _ in rows[0])
            sql = f"INSERT INTO {schema}.{table} VALUES ({placeholders})"
            for row in rows:
                db.execute(self.conn, sql, row)

    def _ns_create(self, namespace: str) -> None:
        # IMPLICIT_SCHEMA creates the schema with its first table, so there is
        # nothing to create here; what may exist is a leftover from a run that
        # was killed before it could clean up.
        self._ns_drop(namespace)

    def _ns_switch(self, namespace: str | None) -> None:
        schema = (namespace or FIXTURE_SCHEMA).upper()
        self.__dict__["_current"] = schema
        db.execute(self.conn, f"SET CURRENT SCHEMA {schema}")

    def _ns_drop(self, namespace: str) -> None:
        schema = namespace.upper()
        for (table,) in db.fetch_all(
            self.conn,
            "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T'",
            (schema,),
        ):
            try:
                db.execute(self.conn, f'DROP TABLE {schema}."{str(table).strip()}"')
            except db.Db2Error:  # pragma: no cover - cleanup only
                pass

    def run(self, sql: str) -> ResultSet:
        rows, columns = db.fetch_described(self.conn, sql)
        return ResultSet(rows=rows, columns=columns)

    def close(self) -> None:
        self.drop_namespaces()


def _qualify(ddl: str, schema: str = FIXTURE_SCHEMA) -> str:
    """Point fixture DDL at a throwaway schema."""
    return re.sub(
        r"CREATE TABLE (\w+)", lambda m: f"CREATE TABLE {schema}.{m.group(1)}", ddl, count=1
    )


def ensure_fixture_schema(conn) -> None:
    """Make the throwaway fixture schema exist *and* be the resolution context.

    Both halves matter. The corpus is written the way real application SQL is
    written -- ``FROM orders``, unqualified -- so whether ``PREPARE`` succeeds
    depends on what ``CURRENT SCHEMA`` is when the compile oracle runs. Setting
    it here, in the same call that guarantees the tables, keeps the oracle's
    name-resolution context tied to the tables it resolves against.

    It used to be set as a side effect of ``Db2Target.__init__`` instead. Any
    caller that compiled before constructing a target therefore got SQLCODE
    -204 on perfectly good SQL -- a false "silent failure", which is the one
    kind of mistake this project cannot afford to make.

    An explicit ``CREATE SCHEMA`` needs DBADM, which the owner deliberately does
    not have. With IMPLICIT_SCHEMA the schema is created by the first table, so
    "already exists" (-601) and "not authorised" (-552) are both fine here.
    """
    try:
        db.execute(conn, f"CREATE SCHEMA {FIXTURE_SCHEMA}")
    except db.Db2Error as exc:
        if exc.sqlcode not in (-601, -552):
            raise
    db.execute(conn, f"SET CURRENT SCHEMA {FIXTURE_SCHEMA}")


# --------------------------------------------------------------------------
# the proof
# --------------------------------------------------------------------------
@dataclass
class InstanceResult:
    variant: str
    targets: str
    agreed: bool
    source_error: str | None = None
    db2_error: str | None = None
    source_rows: list[tuple[str, ...]] = field(default_factory=list)
    db2_rows: list[tuple[str, ...]] = field(default_factory=list)
    source_columns: tuple[str, ...] = ()
    db2_columns: tuple[str, ...] = ()
    #: Why the two sides differ, when they do: 'rows' or 'columns'.
    difference: str = ""
    #: Which dataset produced this instance, so its yield can be logged.
    origin: str = "BUILTIN"
    strategy: str = ""
    fingerprint: str = ""

    @property
    def inconclusive(self) -> bool:
        return self.source_error is not None

    @property
    def rows_compared(self) -> int:
        """How much evidence this instance actually produced."""
        return max(len(self.source_rows), len(self.db2_rows))

    @property
    def vacuous(self) -> bool:
        """Agreement that proves nothing: both engines returned no rows.

        ``[] == []`` is true for every pair of statements that happen to select
        nothing, including two that mean entirely different things. Counting it
        as supporting evidence is how a proof engine fools itself.
        """
        return self.agreed and self.rows_compared == 0


#: Fewer conclusive instances than this and PortProof will not certify anything.
MIN_CONCLUSIVE_INSTANCES = 2


@dataclass
class SemanticVerdict:
    #: EQUIVALENT | DIFFERENT | UNSTABLE | VACUOUS | INCONCLUSIVE
    outcome: str
    instances_checked: int
    instances_agreed: int
    source_engine: str
    witness: InstanceResult | None = None
    #: True when the source engine gave a different answer for the same rows
    #: inserted in another order -- so its ORDER BY has ties and Db2's
    #: disagreement is not a migration bug. Recorded rather than acted on here;
    #: see :meth:`src.pipeline.Pipeline.run_statement`.
    order_unstable: bool = False
    notes: list[str] = field(default_factory=list)
    #: Every instance that was run, in order, so a reader can see the proof and
    #: not merely its conclusion. The ledger stores the witness; the UI shows
    #: all of them.
    instances: list[InstanceResult] = field(default_factory=list)

    # -- evidence, not just conclusion -----------------------------------
    @property
    def conclusive(self) -> list[InstanceResult]:
        return [r for r in self.instances if not r.inconclusive]

    @property
    def rows_compared(self) -> int:
        """Total rows that actually took part in the comparison."""
        return sum(r.rows_compared for r in self.conclusive)

    @property
    def vacuous_instances(self) -> int:
        return sum(1 for r in self.conclusive if r.vacuous)

    @property
    def substantive_instances(self) -> int:
        """Instances that agreed on at least one row -- the real evidence."""
        return sum(1 for r in self.conclusive if r.agreed and not r.vacuous)

    @property
    def distinct_inputs(self) -> int:
        """How many *different* results the datasets actually produced.

        Six datasets that all yield the same rows are one test run six times.
        This is the number the strength score cares about.
        """
        seen = {
            (tuple(r.source_rows), r.source_columns)
            for r in self.conclusive
            if not r.inconclusive
        }
        return len(seen)

    @property
    def strength(self) -> str:
        """How much the verdict is actually worth: NONE | WEAK | MODERATE | STRONG."""
        if self.outcome in ("INCONCLUSIVE", "VACUOUS", "UNSTABLE"):
            return "NONE"
        if self.outcome == "DIFFERENT":
            # A single counterexample is a proof; more datasets do not add to it.
            return "STRONG"
        if self.substantive_instances == 0:
            return "NONE"
        if self.substantive_instances < 2 or self.distinct_inputs < 2:
            return "WEAK"
        if self.distinct_inputs >= 3 and self.rows_compared >= 6:
            return "STRONG"
        return "MODERATE"

    @property
    def headline(self) -> str:
        if self.outcome == "EQUIVALENT":
            return (
                f"equivalent on {self.substantive_instances} of "
                f"{self.instances_checked} instances that returned rows "
                f"({self.rows_compared} rows, {self.distinct_inputs} distinct "
                f"inputs, evidence {self.strength}) vs {self.source_engine}"
            )
        if self.outcome == "DIFFERENT":
            variant = self.witness.variant if self.witness else "?"
            if self.witness and self.witness.db2_error:
                return (
                    f"PROVEN DIFFERENT on '{variant}': the source returned "
                    f"{len(self.witness.source_rows)} rows where Db2 raised "
                    f"{self.witness.db2_error[:60]}"
                )
            if self.witness and self.witness.difference == "columns":
                return f"PROVEN DIFFERENT on '{variant}': the result columns differ"
            return f"PROVEN DIFFERENT on adversarial instance '{variant}'"
        if self.outcome == "UNSTABLE":
            variant = self.witness.variant if self.witness else "?"
            return (
                f"ORDER NOT DETERMINED on '{variant}': {self.source_engine} "
                "returns different rows for the same data in a different "
                "insertion order, so no engine owes you this order -- add a "
                "tiebreaker to ORDER BY"
            )
        if self.outcome == "VACUOUS":
            return (
                f"VACUOUS: both engines returned no rows on all "
                f"{self.instances_checked} instances, so nothing was compared"
            )
        return "inconclusive: the source engine could not run this statement"

    def witness_table(self, limit: int = 3) -> dict[str, list[tuple[str, ...]]]:
        if not self.witness:
            return {}
        return {
            "source": self.witness.source_rows[:limit],
            "db2": self.witness.db2_rows[:limit],
        }

    def evidence(self) -> dict[str, Any]:
        """What the verdict rests on, for the ledger and the certificate.

        An EQUIVALENT verdict used to persist nothing but two integers, so a
        vacuous proof and a substantive one produced byte-identical ledger
        detail -- and the Db2-computed certificate therefore attested to a
        conclusion rather than to evidence. This is that evidence.
        """
        return {
            "instances_checked": self.instances_checked,
            "instances_agreed": self.instances_agreed,
            "substantive_instances": self.substantive_instances,
            "vacuous_instances": self.vacuous_instances,
            "rows_compared": self.rows_compared,
            "distinct_inputs": self.distinct_inputs,
            "strength": self.strength,
            "per_instance": [
                {
                    "variant": r.variant,
                    "agreed": r.agreed,
                    "rows": r.rows_compared,
                    "vacuous": r.vacuous,
                }
                for r in self.conclusive
            ],
        }


def _is_order_unstable(
    source: SourceEngine,
    source_sql: str,
    witness: InstanceResult,
    variants: Sequence[Variant],
    *,
    ordered: bool,
) -> bool:
    """Ask the source engine whether its own answer was even determined.

    Before reporting PROVEN DIFFERENT on an ordered statement, the same
    statement is re-run on the same engine against the same rows inserted in the
    opposite order. A table is a set; no correct query can notice. If the engine
    returns something else, the ``ORDER BY`` has ties and the result is the
    engine's arbitrary choice -- so Db2 "disagreeing" is not a migration bug and
    reporting one would be a false accusation that costs a reviewer real time.

    This distinction cannot be made by inspecting the SQL. ``ORDER BY name`` is
    unstable or not depending entirely on the data, which is why the engine is
    asked instead of the parser.
    """
    original = next((v for v in variants if v.name == witness.variant), None)
    if original is None:  # pragma: no cover - witness always comes from variants
        return False
    try:
        activate(source, original.shuffled())
        again = canon_rows(source.run(source_sql).rows, ordered=ordered)
    except Exception:  # pragma: no cover - probe must never mask the verdict
        return False
    return again != witness.source_rows


def prove_semantics(
    *,
    source_sql: str,
    db2_sql: str,
    source: SourceEngine,
    target: Db2Target,
    variants: Sequence[Variant] | None = None,
    dialect: str | None = None,
) -> SemanticVerdict:
    """Run both statements over every adversarial dataset and compare.

    The verdict is deliberately hard to earn. It is EQUIVALENT only if the two
    engines agreed, on enough instances, having actually compared some rows.
    Agreement on nothing is reported as VACUOUS, not as equivalence.
    """
    variants = list(variants if variants is not None else VARIANTS)
    ordered = has_outer_order_by(source_sql)
    results: list[InstanceResult] = []
    notes: list[str] = []

    # A source engine may only judge the dialect it actually implements.
    # Letting a PostgreSQL engine rule on MySQL SQL is how PortProof certified
    # `mysql/case_insensitive_eq` as EQUIVALENT when MySQL and Db2 genuinely
    # disagree -- both non-MySQL engines returned nothing, and nothing matched
    # nothing.
    engine_dialect = getattr(source, "dialect", None)
    if dialect and engine_dialect and dialect != engine_dialect:
        return SemanticVerdict(
            outcome="INCONCLUSIVE",
            instances_checked=0,
            instances_agreed=0,
            source_engine=source.name,
            notes=[
                f"refused to judge {dialect} SQL with a {engine_dialect} engine "
                f"({source.name}): engine-level semantics such as collation and "
                "division cannot be recovered from fixture data"
            ],
        )

    # ...and a stand-in engine may decline on its own known divergences. The
    # alternative is a verdict about DuckDB reported as a verdict about
    # PostgreSQL, in whichever direction the divergence happens to point.
    declined = unfaithful(source, source_sql)
    if declined:
        return SemanticVerdict(
            outcome="INCONCLUSIVE",
            instances_checked=0,
            instances_agreed=0,
            source_engine=source.name,
            notes=[
                f"{source.name} declined to adjudicate this statement: {declined}",
                "run a real PostgreSQL (see .env.example) to get a verdict here",
            ],
        )

    for variant in variants:
        activate(source, variant)
        activate(target, variant)

        try:
            source_result = source.run(source_sql)
        except Exception as exc:
            results.append(
                InstanceResult(
                    variant=variant.name,
                    targets=variant.targets,
                    agreed=False,
                    source_error=f"{type(exc).__name__}: {str(exc)[:160]}",
                )
            )
            continue

        canon_source = canon_rows(source_result.rows, ordered=ordered)
        try:
            db2_result = target.run(db2_sql)
        except db.Db2Error as exc:
            results.append(
                InstanceResult(
                    variant=variant.name,
                    targets=variant.targets,
                    agreed=False,
                    db2_error=f"SQLCODE={exc.sqlcode} {exc.message[:140]}",
                    source_rows=canon_source,
                    source_columns=canon_columns(source_result.columns),
                    difference="db2_error",
                )
            )
            continue

        canon_db2 = canon_rows(db2_result.rows, ordered=ordered)
        source_cols = canon_columns(source_result.columns)
        db2_cols = canon_columns(db2_result.columns)

        # Arity is part of the answer, and it is the only thing that survives
        # when both sides are empty: without it, a 2-column result and a
        # 7-column result are "equal" whenever both return no rows.
        if len(source_cols) != len(db2_cols):
            difference = "columns"
            agreed = False
        else:
            named_source = comparable_columns(source_result.columns)
            named_db2 = comparable_columns(db2_result.columns)
            if named_source and named_db2 and named_source != named_db2:
                difference, agreed = "columns", False
            elif canon_source != canon_db2:
                difference, agreed = "rows", False
            else:
                difference, agreed = "", True

        results.append(
            InstanceResult(
                variant=variant.name,
                targets=variant.targets,
                agreed=agreed,
                source_rows=canon_source,
                db2_rows=canon_db2,
                source_columns=source_cols,
                db2_columns=db2_cols,
                difference=difference,
            )
        )

    for result, variant in zip(results, variants):
        result.origin = variant.origin
        result.strategy = variant.strategy or variant.name
        result.fingerprint = variant.fingerprint

    conclusive = [r for r in results if not r.inconclusive]
    disagreements = [r for r in conclusive if not r.agreed]

    def _verdict(outcome: str, **kw: Any) -> SemanticVerdict:
        return SemanticVerdict(
            outcome=outcome,
            source_engine=source.name,
            instances=results,
            notes=notes,
            **kw,
        )

    if not conclusive:
        notes.extend([r.source_error or "" for r in results if r.source_error][:3])
        return _verdict("INCONCLUSIVE", instances_checked=len(results), instances_agreed=0)

    if not ordered:
        notes.append(
            "no ORDER BY: rows compared as a multiset, so row order is not asserted"
        )

    # A counterexample stands on its own, so disagreement is decided first and
    # is not subject to the evidence thresholds below.
    if disagreements:
        witness = disagreements[0]
        unstable = (
            ordered
            and witness.db2_error is None
            and _is_order_unstable(source, source_sql, witness, variants, ordered=ordered)
        )
        if unstable:
            notes.append(
                f"{source.name} returned different rows for the same data "
                "inserted in the opposite order, so this statement's own "
                "ORDER BY does not determine its result"
            )
        # Reported as DIFFERENT even when unstable: the instability is recorded
        # on the verdict, and the caller decides. Settling it here would rank a
        # diagnosis above a repair -- `postgres/array_agg` is both unstable
        # *and* fixable, and a verdict of UNSTABLE suppressed the fix.
        return _verdict(
            "DIFFERENT",
            instances_checked=len(conclusive),
            instances_agreed=len(conclusive) - len(disagreements),
            witness=witness,
            order_unstable=unstable,
        )

    agreed_with_rows = [r for r in conclusive if not r.vacuous]
    empty = len(conclusive) - len(agreed_with_rows)
    if empty:
        notes.append(
            f"{empty} of {len(conclusive)} instances returned no rows on either "
            "engine and prove nothing"
        )

    if not agreed_with_rows:
        return _verdict(
            "VACUOUS", instances_checked=len(conclusive), instances_agreed=len(conclusive)
        )

    if len(conclusive) < MIN_CONCLUSIVE_INSTANCES:
        notes.append(
            f"only {len(conclusive)} instance(s) could be run, below the "
            f"minimum of {MIN_CONCLUSIVE_INSTANCES} needed to certify"
        )
        return _verdict(
            "INCONCLUSIVE",
            instances_checked=len(conclusive),
            instances_agreed=len(conclusive),
        )

    return _verdict(
        "EQUIVALENT",
        instances_checked=len(conclusive),
        instances_agreed=len(conclusive),
    )
