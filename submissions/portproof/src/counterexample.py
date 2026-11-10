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


# --------------------------------------------------------------------------
# engines
# --------------------------------------------------------------------------
class SourceEngine(Protocol):
    """The engine the SQL is migrating *from*."""

    name: str

    def load(self, variant: Variant) -> None: ...
    def run(self, sql: str) -> list[tuple]: ...
    def close(self) -> None: ...


class DuckDbSource:
    """PostgreSQL-compatible source engine, embedded so judges need no server.

    DuckDB implements PostgreSQL's dialect and semantics closely, which makes it
    a faithful stand-in for the Postgres cases and a reasonable one for MySQL
    *syntax*. Where MySQL's documented behaviour diverges from Postgres (notably
    case-insensitive collation and ``7/2`` returning 3.5), that divergence is
    encoded in the adversarial variants instead of being inferred from the
    engine, and the verdict text names the engine actually used.
    """

    name = "duckdb(postgres-compatible)"

    def __init__(self) -> None:
        import duckdb

        self._conn = duckdb.connect()

    def load(self, variant: Variant) -> None:
        for table in FIXTURE_TABLES:
            self._conn.execute(f"DROP TABLE IF EXISTS {table}")
        for ddl in FIXTURE_DDL:
            self._conn.execute(ddl)
        for table in FIXTURE_TABLES:
            for row in variant.rows.get(table, []):
                placeholders = ", ".join("?" for _ in row)
                self._conn.execute(f"INSERT INTO {table} VALUES ({placeholders})", list(row))

    def run(self, sql: str) -> list[tuple]:
        return [tuple(r) for r in self._conn.execute(sql).fetchall()]

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # pragma: no cover
            pass


class Db2Target:
    """The Db2 side of the comparison, in a throwaway fixture schema."""

    name = "Db2"

    def __init__(self, conn) -> None:
        self.conn = conn
        # Idempotent, and kept here as well so a target is self-sufficient even
        # if someone changed the schema in between.
        db.execute(conn, f"SET CURRENT SCHEMA {FIXTURE_SCHEMA}")

    def load(self, variant: Variant) -> None:
        for table in FIXTURE_TABLES:
            try:
                db.execute(self.conn, f"DROP TABLE {FIXTURE_SCHEMA}.{table}")
            except db.Db2Error:
                pass
        for ddl in FIXTURE_DDL:
            db.execute(self.conn, _qualify(ddl))
        for table in FIXTURE_TABLES:
            rows = variant.rows.get(table, [])
            if not rows:
                continue
            placeholders = ", ".join("?" for _ in rows[0])
            sql = f"INSERT INTO {FIXTURE_SCHEMA}.{table} VALUES ({placeholders})"
            for row in rows:
                db.execute(self.conn, sql, row)

    def run(self, sql: str) -> list[tuple]:
        return db.fetch_all(self.conn, sql)


def _qualify(ddl: str) -> str:
    """Point fixture DDL at the throwaway schema."""
    return re.sub(
        r"CREATE TABLE (\w+)", lambda m: f"CREATE TABLE {FIXTURE_SCHEMA}.{m.group(1)}", ddl, count=1
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

    @property
    def inconclusive(self) -> bool:
        return self.source_error is not None


@dataclass
class SemanticVerdict:
    outcome: str  # EQUIVALENT | DIFFERENT | INCONCLUSIVE
    instances_checked: int
    instances_agreed: int
    source_engine: str
    witness: InstanceResult | None = None
    notes: list[str] = field(default_factory=list)
    #: Every instance that was run, in order, so a reader can see the proof and
    #: not merely its conclusion. The ledger stores the witness; the UI shows
    #: all of them.
    instances: list[InstanceResult] = field(default_factory=list)

    @property
    def headline(self) -> str:
        if self.outcome == "EQUIVALENT":
            return (
                f"equivalent on {self.instances_agreed} adversarial instances "
                f"(vs {self.source_engine})"
            )
        if self.outcome == "DIFFERENT":
            variant = self.witness.variant if self.witness else "?"
            return f"PROVEN DIFFERENT on adversarial instance '{variant}'"
        return "inconclusive: the source engine could not run this statement"

    def witness_table(self, limit: int = 3) -> dict[str, list[tuple[str, ...]]]:
        if not self.witness:
            return {}
        return {
            "source": self.witness.source_rows[:limit],
            "db2": self.witness.db2_rows[:limit],
        }


def prove_semantics(
    *,
    source_sql: str,
    db2_sql: str,
    source: SourceEngine,
    target: Db2Target,
    variants: Sequence[Variant] | None = None,
) -> SemanticVerdict:
    """Run both statements over every adversarial dataset and compare."""
    variants = list(variants if variants is not None else VARIANTS)
    ordered = bool(_ORDER_BY_RE.search(source_sql))
    results: list[InstanceResult] = []
    notes: list[str] = []

    for variant in variants:
        source.load(variant)
        target.load(variant)

        try:
            source_rows = source.run(source_sql)
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

        try:
            db2_rows = target.run(db2_sql)
        except db.Db2Error as exc:
            results.append(
                InstanceResult(
                    variant=variant.name,
                    targets=variant.targets,
                    agreed=False,
                    db2_error=f"SQLCODE={exc.sqlcode} {exc.message[:140]}",
                    source_rows=canon_rows(source_rows, ordered=ordered),
                )
            )
            continue

        canon_source = canon_rows(source_rows, ordered=ordered)
        canon_db2 = canon_rows(db2_rows, ordered=ordered)
        results.append(
            InstanceResult(
                variant=variant.name,
                targets=variant.targets,
                agreed=canon_source == canon_db2,
                source_rows=canon_source,
                db2_rows=canon_db2,
            )
        )

    conclusive = [r for r in results if not r.inconclusive]
    disagreements = [r for r in conclusive if not r.agreed]

    if not conclusive:
        return SemanticVerdict(
            outcome="INCONCLUSIVE",
            instances_checked=len(results),
            instances_agreed=0,
            source_engine=source.name,
            notes=[r.source_error or "" for r in results if r.source_error][:3],
            instances=results,
        )

    if not ordered:
        notes.append(
            "no ORDER BY: rows compared as a multiset, so row order is not asserted"
        )

    if disagreements:
        return SemanticVerdict(
            outcome="DIFFERENT",
            instances_checked=len(conclusive),
            instances_agreed=len(conclusive) - len(disagreements),
            source_engine=source.name,
            witness=disagreements[0],
            notes=notes,
            instances=results,
        )

    return SemanticVerdict(
        outcome="EQUIVALENT",
        instances_checked=len(conclusive),
        instances_agreed=len(conclusive),
        source_engine=source.name,
        notes=notes,
        instances=results,
    )
