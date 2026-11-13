"""The dataset agent: adversarial data for whatever schema the source holds.

The twelve hand-built datasets in :mod:`src.corpus` are written for one
four-table fixture. A real migration brings its own schema, so the datasets
have to be made for it, and made for the query being proved. This module does
that in four tiers, cheapest first, and the first three cost nothing:

1. **Cached.** Every dataset that has ever been accepted is stored in Db2
   (``PORTPROOF.DATASET``) under the fingerprint of the schema it was built
   for, together with a log of what it achieved (``PORTPROOF.DATASET_RUN``):
   did the query return rows on it, and did it expose a divergence. A dataset
   that already earned evidence is found again rather than made again.
2. **Generated.** Deterministic strategies turn a schema into datasets aimed at
   the documented differences between engines: letter case, blank padding,
   accents, NULLs, ties, integer and decimal division, empty groups.
3. **Query-aware.** The query's own literals are read from its syntax tree and
   planted in the data, in the forms that separate engines: a string in three
   cases and with a trailing blank, a number at the boundary and one step
   either side. This is what stops a filter from selecting nothing.
4. **Model.** Only if the proof is still vacuous or weak after all of that is a
   language model asked for one more dataset. It is sent the schema and the
   query, never rows. Its answer is data, not SQL, and it is kept only if both
   engines load it; whether it was worth anything is then measured like every
   other dataset, and it joins the cache for the next query on that schema.

The ranking in :meth:`DatasetAgent.plan` reads the log, so the order the
datasets are tried in improves with every run, and a budget (``max_datasets``)
spends the proof's time on the datasets that have been finding things.

The cost model follows from the inputs. The model sees a schema and a query,
whose size does not depend on how many rows the source holds. See
``docs/ai-cost-analysis.md`` for the measurement.
"""
from __future__ import annotations

import datetime as _dt
import decimal
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

import sqlglot
from sqlglot import exp

from . import db
from .corpus import FIXTURE_DDL, VARIANTS, Variant
from .counterexample import SemanticVerdict, activate, go_home

# --------------------------------------------------------------------------
# schema model
# --------------------------------------------------------------------------
KINDS = ("int", "decimal", "double", "text", "bool", "timestamp", "date")


@dataclass(frozen=True)
class Column:
    name: str
    kind: str
    length: int = 0
    precision: int = 0
    scale: int = 0
    nullable: bool = True
    pk: bool = False

    def ddl(self) -> str:
        if self.kind == "int":
            type_ = "BIGINT" if self.precision > 10 else "INTEGER"
        elif self.kind == "decimal":
            type_ = f"DECIMAL({self.precision or 12},{self.scale})"
        elif self.kind == "double":
            type_ = "DOUBLE"
        elif self.kind == "bool":
            type_ = "BOOLEAN"
        elif self.kind == "timestamp":
            type_ = "TIMESTAMP"
        elif self.kind == "date":
            type_ = "DATE"
        else:
            type_ = f"VARCHAR({self.length or 100})"
        suffix = " NOT NULL PRIMARY KEY" if self.pk else ("" if self.nullable else " NOT NULL")
        return f"{self.name} {type_}{suffix}"


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]

    def ddl(self) -> str:
        body = ",\n  ".join(c.ddl() for c in self.columns)
        return f"CREATE TABLE {self.name} (\n  {body}\n)"

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name.lower() == name.lower()), None)


@dataclass(frozen=True)
class SourceSchema:
    """What the source engine's catalogue said about a set of tables."""

    name: str
    tables: tuple[Table, ...]

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tables)

    def ddl(self) -> tuple[str, ...]:
        return tuple(t.ddl() for t in self.tables)

    @property
    def fingerprint(self) -> str:
        """Identifies the schema's shape: the cache key for its datasets."""
        return hashlib.sha256("\n".join(self.ddl()).lower().encode("utf-8")).hexdigest()[:16]

    def table(self, name: str) -> Table | None:
        return next((t for t in self.tables if t.name.lower() == name.lower()), None)

    def prompt_text(self) -> str:
        """The schema as the model sees it. No rows, so no size dependence."""
        return "\n".join(
            f"{t.name}("
            + ", ".join(
                f"{c.name} {c.ddl().split(' ', 1)[1]}" for c in t.columns
            )
            + ")"
            for t in self.tables
        )


_TYPE_RE = re.compile(r"^\s*([A-Za-z ]+?)\s*(?:\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\))?\s*$")


def column_from_type(
    name: str, type_text: str, *, length=None, precision=None, scale=None,
    nullable: bool = True, pk: bool = False,
) -> Column:
    """Map any engine's spelling of a type onto the portable vocabulary."""
    match = _TYPE_RE.match(type_text or "")
    base = (match.group(1) if match else type_text or "").strip().lower()
    arg1 = int(match.group(2)) if match and match.group(2) else None
    arg2 = int(match.group(3)) if match and match.group(3) else None
    if base in ("boolean", "bool", "bit") or (base == "tinyint" and (arg1 in (None, 1))):
        kind = "bool"
    elif base in ("int", "integer", "smallint", "mediumint", "tinyint", "bigint", "int4", "int8", "int2"):
        kind = "int"
    elif base in ("decimal", "numeric", "money", "smallmoney", "number"):
        kind = "decimal"
    elif base in ("double", "double precision", "float", "real", "float8", "float4"):
        kind = "double"
    elif base.startswith("timestamp") or base in ("datetime", "datetime2", "smalldatetime"):
        kind = "timestamp"
    elif base == "date":
        kind = "date"
    else:
        kind = "text"
    if kind == "decimal":
        precision = int(precision or arg1 or 12)
        scale = int(scale if scale is not None else (arg2 or 0))
        if base in ("money", "smallmoney"):
            precision, scale = 19, 4
        # Db2's DECIMAL stops at 31 digits.
        precision = min(precision, 31)
        return Column(name, kind, precision=precision, scale=min(scale, precision), nullable=nullable, pk=pk)
    if kind == "int":
        big = base in ("bigint", "int8")
        return Column(name, kind, precision=19 if big else 10, nullable=nullable, pk=pk)
    if kind == "text":
        size = int(length or arg1 or 100)
        if size <= 0 or size > 2000:
            size = 2000
        return Column(name, kind, length=size, nullable=nullable, pk=pk)
    return Column(name, kind, nullable=nullable, pk=pk)


def schema_from_ddl(name: str, ddl: Sequence[str]) -> SourceSchema:
    """Read a schema out of portable ``CREATE TABLE`` text."""
    tables: list[Table] = []
    for statement in ddl:
        head = re.search(r"CREATE\s+TABLE\s+(\w+)\s*\((.*)\)\s*$", statement, re.I | re.S)
        if not head:
            continue
        columns: list[Column] = []
        depth, buffer, parts = 0, [], []
        for char in head.group(2):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if char == "," and depth == 0:
                parts.append("".join(buffer))
                buffer = []
            else:
                buffer.append(char)
        parts.append("".join(buffer))
        for part in parts:
            text = " ".join(part.split())
            m = re.match(r"(\w+)\s+([A-Za-z]+(?:\s*\([^)]*\))?)(.*)$", text)
            if not m or m.group(1).upper() in ("PRIMARY", "CONSTRAINT", "FOREIGN", "UNIQUE", "CHECK"):
                continue
            rest = m.group(3).upper()
            pk = "PRIMARY KEY" in rest
            columns.append(
                column_from_type(
                    m.group(1), m.group(2), nullable=not ("NOT NULL" in rest or pk), pk=pk
                )
            )
        tables.append(Table(head.group(1), tuple(columns)))
    return SourceSchema(name, tuple(tables))


#: The built-in four-table fixture, as a schema like any other.
FIXTURE = schema_from_ddl("fixture", FIXTURE_DDL)

_CATALOG_SQL = {
    "mysql": (
        "SELECT table_name, column_name, column_type, character_maximum_length, "
        "numeric_precision, numeric_scale, is_nullable, column_key "
        "FROM information_schema.columns WHERE table_schema = DATABASE() "
        "ORDER BY table_name, ordinal_position"
    ),
    "postgres": (
        "SELECT c.table_name, c.column_name, c.data_type, c.character_maximum_length, "
        "c.numeric_precision, c.numeric_scale, c.is_nullable, "
        "CASE WHEN k.column_name IS NULL THEN '' ELSE 'PRI' END "
        "FROM information_schema.columns c LEFT JOIN ("
        " SELECT kcu.table_name, kcu.column_name FROM information_schema.table_constraints tc "
        " JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name "
        "  AND kcu.table_schema = tc.table_schema AND kcu.table_name = tc.table_name "
        " WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = current_schema()) k "
        " ON k.table_name = c.table_name AND k.column_name = c.column_name "
        "WHERE c.table_schema = current_schema() ORDER BY c.table_name, c.ordinal_position"
    ),
    "tsql": (
        "SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH, "
        "c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.IS_NULLABLE, "
        "CASE WHEN k.COLUMN_NAME IS NULL THEN '' ELSE 'PRI' END "
        "FROM INFORMATION_SCHEMA.COLUMNS c LEFT JOIN ("
        " SELECT kcu.TABLE_NAME, kcu.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
        " JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME "
        "  AND kcu.TABLE_NAME = tc.TABLE_NAME "
        " WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY') k "
        " ON k.TABLE_NAME = c.TABLE_NAME AND k.COLUMN_NAME = c.COLUMN_NAME "
        "WHERE c.TABLE_SCHEMA = SCHEMA_NAME() ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION"
    ),
}


def introspect(engine: Any, name: str, tables: Sequence[str] | None = None) -> SourceSchema:
    """Ask the source engine's own catalogue what it holds.

    Read from the engine's home namespace, which is where the migrating
    application's tables live; the datasets built from the answer are loaded
    elsewhere and never touch them.
    """
    go_home(engine)
    wanted = {t.lower() for t in tables} if tables else None
    grouped: dict[str, list[Column]] = {}
    dialect = getattr(engine, "dialect", "")
    if dialect == "sqlite":
        names = [r[0] for r in engine.run(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).rows]
        for table in names:
            if wanted is not None and table.lower() not in wanted:
                continue
            for _cid, col, type_text, notnull, _default, pk in engine.run(
                f"PRAGMA table_info({table})"
            ).rows:
                grouped.setdefault(table, []).append(
                    column_from_type(col, type_text, nullable=not (notnull or pk), pk=bool(pk))
                )
    else:
        sql = _CATALOG_SQL.get(dialect)
        if sql is None:
            raise ValueError(f"no catalogue query for dialect {dialect!r}")
        for table, col, type_text, length, precision, scale, nullable, key in engine.run(sql).rows:
            table, col = str(table), str(col)
            if wanted is not None and table.lower() not in wanted:
                continue
            pk = str(key or "").upper() == "PRI"
            grouped.setdefault(table, []).append(
                column_from_type(
                    col, str(type_text), length=length, precision=precision, scale=scale,
                    nullable=str(nullable).upper().startswith("Y") and not pk, pk=pk,
                )
            )
    ordered = sorted(grouped)
    if tables:
        ordered = [t for want in tables for t in grouped if t.lower() == want.lower()]
    return SourceSchema(name, tuple(Table(t.lower(), tuple(grouped[t])) for t in ordered))


# --------------------------------------------------------------------------
# profile: statistics, never rows
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ColumnProfile:
    nulls: int = 0
    distinct: int = 0
    minimum: Any = None
    maximum: Any = None


@dataclass(frozen=True)
class Profile:
    """Aggregates over the source tables: one scan each, done by the source."""

    rows: dict[str, int] = field(default_factory=dict)
    columns: dict[tuple[str, str], ColumnProfile] = field(default_factory=dict)

    @property
    def total_rows(self) -> int:
        return sum(self.rows.values())


def profile(engine: Any, schema: SourceSchema) -> Profile:
    """One aggregate query per table, run by the source engine itself.

    This is the only step whose cost grows with the size of the source, and it
    is ordinary SQL on the source engine: no model is involved, and nothing but
    counts and extremes leaves the table.
    """
    go_home(engine)
    rows: dict[str, int] = {}
    columns: dict[tuple[str, str], ColumnProfile] = {}
    for table in schema.tables:
        parts = ["COUNT(*)"]
        for col in table.columns:
            parts.append(f"COUNT({col.name})")
            parts.append(f"COUNT(DISTINCT {col.name})")
            if col.kind == "bool":
                parts.extend(["NULL", "NULL"])
            else:
                parts.extend([f"MIN({col.name})", f"MAX({col.name})"])
        try:
            row = engine.run(f"SELECT {', '.join(parts)} FROM {table.name}").rows[0]
        except Exception:
            continue
        total = int(row[0] or 0)
        rows[table.name] = total
        for i, col in enumerate(table.columns):
            count, distinct, low, high = row[1 + i * 4 : 5 + i * 4]
            columns[(table.name, col.name)] = ColumnProfile(
                nulls=total - int(count or 0), distinct=int(distinct or 0),
                minimum=low, maximum=high,
            )
    return Profile(rows, columns)


# --------------------------------------------------------------------------
# query features
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class QueryFeatures:
    tags: tuple[str, ...] = ()
    #: ``(column or "", literal)`` for every string compared with ``=``/``<>``/IN.
    strings: tuple[tuple[str, str], ...] = ()
    #: ``(column or "", number)`` for every numeric comparison.
    numbers: tuple[tuple[str, decimal.Decimal], ...] = ()
    #: ``(column or "", pattern)`` for LIKE.
    patterns: tuple[tuple[str, str], ...] = ()
    #: ``(column or "", 'YYYY-MM-DD')`` for literals that are dates.
    dates: tuple[tuple[str, str], ...] = ()

    @property
    def has_literals(self) -> bool:
        return bool(self.strings or self.numbers or self.patterns or self.dates)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def features(sql: str, dialect: str) -> QueryFeatures:
    """What the query does, read from its syntax tree rather than its text."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return QueryFeatures()
    tags: set[str] = set()
    strings: list[tuple[str, str]] = []
    numbers: list[tuple[str, decimal.Decimal]] = []
    patterns: list[tuple[str, str]] = []
    dates: list[tuple[str, str]] = []

    def column_of(node: exp.Expression) -> str:
        col = node if isinstance(node, exp.Column) else node.find(exp.Column)
        return col.name.lower() if col is not None else ""

    def take(column: str, literal: exp.Expression) -> None:
        if not isinstance(literal, exp.Literal):
            return
        if literal.is_string:
            if _DATE_RE.match(literal.this):
                dates.append((column, literal.this[:10]))
            else:
                strings.append((column, literal.this))
        else:
            try:
                numbers.append((column, decimal.Decimal(literal.this)))
            except decimal.InvalidOperation:
                pass

    for node in tree.walk():
        if isinstance(node, exp.Join):
            tags.add("join")
        elif isinstance(node, exp.AggFunc):
            tags.add("aggregate")
        elif isinstance(node, exp.Group):
            tags.add("group_by")
        elif isinstance(node, exp.Order):
            tags.add("order_by")
        elif isinstance(node, (exp.Limit, exp.Fetch, exp.Offset)):
            tags.add("limit")
        elif isinstance(node, (exp.Div, exp.IntDiv)):
            tags.add("division")
        elif isinstance(node, (exp.Mul, exp.Mod)):
            tags.add("arithmetic")
        elif isinstance(node, exp.Window):
            tags.add("window")
        elif isinstance(node, exp.Distinct):
            tags.add("distinct")
        elif isinstance(node, (exp.Coalesce, exp.Is, exp.Nullif)):
            tags.add("null_logic")
        elif isinstance(node, (exp.DPipe, exp.Concat)):
            tags.add("concat")
        elif isinstance(node, (exp.Length, exp.Substring, exp.StrPosition, exp.Upper, exp.Lower, exp.Trim)):
            tags.add("string_fn")
        elif isinstance(node, (exp.TimeToStr, exp.DateTrunc, exp.TimestampTrunc, exp.DateDiff,
                               exp.DateSub, exp.DateAdd, exp.Extract, exp.Date)):
            tags.add("date_fn")
        elif isinstance(node, exp.Like) or isinstance(node, exp.ILike):
            tags.add("like")
            if isinstance(node.expression, exp.Literal):
                patterns.append((column_of(node.this), node.expression.this))
        elif isinstance(node, exp.In):
            if node.args.get("query") is not None:
                tags.add("subquery")
            for item in node.expressions or ():
                take(column_of(node.this), item)
        elif isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
            left, right = node.this, node.expression
            if isinstance(right, exp.Literal):
                take(column_of(left), right)
            elif isinstance(left, exp.Literal):
                take(column_of(right), left)
        elif isinstance(node, exp.Between):
            for bound in (node.args.get("low"), node.args.get("high")):
                if bound is not None:
                    take(column_of(node.this), bound)
    if strings:
        tags.add("string_eq")
    if numbers:
        tags.add("numeric_cmp")
    if dates:
        tags.add("date_cmp")
    if tree.find(exp.Subquery) is not None:
        tags.add("subquery")
    return QueryFeatures(
        tuple(sorted(tags)), tuple(strings), tuple(numbers), tuple(patterns), tuple(dates)
    )


# --------------------------------------------------------------------------
# deterministic generation
# --------------------------------------------------------------------------
_WORDS = ("Asha Smith", "Bob Stone", "Cy Smithers", "Dev Rao", "Eli Novak", "Fay Osei", "Gus Lind", "Hana Ito")
_STATUS = ("PAID", "NEW", "PAID", "HOLD", "NEW", "PAID", "VOID", "NEW")
_DEFAULT = object()


def _fit(col: Column, value: Any) -> Any:
    """Make a value legal for its column, so the data tests the query and not the DDL."""
    if value is None:
        return None if col.nullable and not col.pk else _default(col, 0, None)
    if col.kind == "text":
        return str(value)[: col.length or 100]
    if col.kind == "int":
        number = int(decimal.Decimal(str(value)))
        limit = 2**63 - 1 if col.precision > 10 else 2**31 - 1
        return max(-limit, min(limit, number))
    if col.kind == "decimal":
        q = decimal.Decimal(1).scaleb(-col.scale)
        limit = decimal.Decimal(10) ** (col.precision - col.scale) - q
        # Clamp first: quantising a number wider than the context is an error.
        number = max(-limit, min(limit, decimal.Decimal(str(value))))
        return str(number.quantize(q, rounding=decimal.ROUND_HALF_UP))
    if col.kind == "double":
        return float(value)
    if col.kind == "bool":
        return bool(value)
    return value


def _parent(schema: SourceSchema, table: Table, col: Column) -> Table | None:
    """The table a column points at, by the naming every schema here uses."""
    if col.pk or col.kind != "int" or not col.name.lower().endswith("_id"):
        return None
    stem = col.name.lower()[:-3]
    for candidate in schema.tables:
        name = candidate.name.lower()
        if candidate is not table and name in (stem, stem + "s", stem + "es", stem[:-1] + "ies"):
            return candidate
    return None


def _default(col: Column, i: int, parent_rows: int | None) -> Any:
    if col.pk and col.kind == "int":
        return i + 1
    if parent_rows is not None:
        return (i % parent_rows) + 1 if parent_rows else None
    name = col.name.lower()
    if col.kind == "int":
        return (2, 3, 1, 4, 5, 6, 8, 9)[i % 8]
    if col.kind == "decimal":
        return _fit(col, ("50.00", "150.00", "99.50", "10.00", "75.25", "20.00", "8.40", "310.00")[i % 8])
    if col.kind == "double":
        return (1.5, 2.25, 3.0, 4.75)[i % 4]
    if col.kind == "bool":
        return i % 3 != 2
    if col.kind == "timestamp":
        return f"2026-{(i % 3) + 1:02d}-{(i * 7) % 27 + 1:02d} {9 + i % 8:02d}:30:00"
    if col.kind == "date":
        return f"2026-{(i % 3) + 1:02d}-{(i * 7) % 27 + 1:02d}"
    if col.pk:
        return _fit(col, f"K{i + 1}")
    if "mail" in name:
        return _fit(col, f"{_WORDS[i % 8].split()[0].lower()}@example.com")
    if "status" in name or "state" in name:
        return _fit(col, _STATUS[i % 8])
    if "currency" in name:
        return _fit(col, ("EUR", "USD", "INR", "EUR")[i % 4])
    if (col.length or 100) <= 4:
        return _fit(col, ("A1", "B2", "C3", "A2", "B1", "C1", "A3", "B3")[i % 8])
    return _fit(col, _WORDS[i % 8])


def _build(
    schema: SourceSchema,
    name: str,
    targets: str,
    strategy: str,
    *,
    n: int | dict[str, int] = 4,
    cell=None,
    origin: str = "GENERATED",
) -> Variant:
    """Rows for every table. ``cell(table, col, i)`` may override any value."""
    rows: dict[str, list[tuple]] = {}
    counts = {t.name: (n.get(t.name, 4) if isinstance(n, dict) else n) for t in schema.tables}
    for table in schema.tables:
        out = []
        for i in range(counts[table.name]):
            row = []
            for col in table.columns:
                value = cell(table, col, i) if cell else _DEFAULT
                if value is _DEFAULT or col.pk:
                    parent = _parent(schema, table, col)
                    value = _default(col, i, counts[parent.name] if parent else None)
                else:
                    value = _fit(col, value)
                row.append(value)
            out.append(tuple(row))
        rows[table.name] = out
    return Variant(
        name=f"{schema.name}:{name}", targets=targets, rows=rows,
        ddl=schema.ddl(), tables=schema.table_names, origin=origin, strategy=strategy,
    )


def _is_child(schema: SourceSchema, table: Table) -> bool:
    return any(_parent(schema, table, c) is not None for c in table.columns)


def _free(schema: SourceSchema, table: Table, col: Column) -> bool:
    """A column a strategy may write into without breaking keys."""
    return not col.pk and _parent(schema, table, col) is None


def generate(schema: SourceSchema, prof: Profile | None = None) -> list[Variant]:
    """Schema-level adversarial datasets. Deterministic, and free."""

    def text_only(fn):
        return lambda t, c, i: fn(t, c, i) if c.kind == "text" and _free(schema, t, c) else _DEFAULT

    case_forms = (str.upper, str.lower, str.title, lambda s: s)
    out = [
        _build(schema, "plain", "ordinary values; catches outright translation errors", "base"),
        _build(
            schema, "mixed_case",
            "the same text in upper, lower and title case, which a case-insensitive "
            "collation treats as one value and Db2 as three", "mixed_case", n=6,
            cell=text_only(lambda t, c, i: case_forms[i % 4](str(_default(c, i // 4, None)))),
        ),
        _build(
            schema, "nulls_and_empties",
            "NULL in every nullable column and an empty string: NULL ordering, "
            "aggregates skipping NULLs, NOT IN over a NULL", "nulls_and_empties", n=5,
            cell=lambda t, c, i: (
                None if c.nullable and not c.pk and (i + len(c.name)) % 3 == 0
                else ("" if c.kind == "text" and _free(schema, t, c) and i == 4 else _DEFAULT)
            ),
        ),
        _build(
            schema, "ties_and_duplicates",
            "every non-key value repeated, so an ORDER BY without a tiebreaker "
            "has no determined order", "ties_and_duplicates", n=4,
            cell=lambda t, c, i: _default(c, 0, None) if _free(schema, t, c) else _DEFAULT,
        ),
        _build(
            schema, "arithmetic_edges",
            "odd, zero and negative numbers: integer against decimal division, "
            "scale and rounding", "division_and_rounding", n=6,
            cell=lambda t, c, i: (
                (7, 2, 0, -7, 3, 1)[i] if c.kind == "int" and _free(schema, t, c)
                else (("7.00", "10.00", "0.01", "-7.00", "2.50", "100.00")[i] if c.kind == "decimal" else _DEFAULT)
            ),
        ),
        _build(
            schema, "empty_children",
            "parent rows with no child rows: COUNT gives 0, SUM gives NULL, and "
            "an inner join gives nothing", "empty_groups",
            n={t.name: (0 if _is_child(schema, t) else 2) for t in schema.tables},
        ),
        _build(
            schema, "blank_padding",
            "leading and trailing blanks, which some engines ignore in '=' and "
            "in string length", "trailing_spaces", n=4,
            cell=text_only(lambda t, c, i: (
                lambda v: (v + " ", v, " " + v, v + "  ")[i % 4])(str(_default(c, i // 2, None))[: max(1, (c.length or 100) - 2)])
            ),
        ),
        _build(
            schema, "accents",
            "accented and unaccented spellings of the same word, which an "
            "accent-insensitive collation treats as equal", "accents_and_unicode", n=4,
            # Sized in bytes, not characters. A VARCHAR(10) holds ten characters
            # on MySQL, PostgreSQL and SQL Server and ten *bytes* on Db2, where
            # 'José Núñez' needs thirteen: Db2 refused the first version of this
            # dataset with SQL0302N. That is a schema finding in its own right
            # (see Known Limitations), and here it only means choosing a value
            # that fits both ways.
            cell=text_only(lambda t, c, i: ("José Núñez", "Jose Nunez", "Zoë Smith", "Zoe Smith")[i]
                           if (c.length or 100) >= 13
                           else (("É1", "E1", "é1", "e1")[i] if (c.length or 100) >= 3 else _DEFAULT)),
        ),
        _build(
            schema, "range_limits",
            "the largest and smallest values each column can hold", "extreme_values", n=3,
            cell=lambda t, c, i: (
                (("9" * 40, "0", "-" + "9" * 40)[i] if c.kind == "decimal" and _free(schema, t, c)
                 else ((2**31 - 1, 0, -(2**31 - 1))[i] if c.kind == "int" and _free(schema, t, c)
                       else (("X" * 4000, "y", "")[i] if c.kind == "text" and _free(schema, t, c)
                             else _DEFAULT)))
            ),
        ),
        _build(
            schema, "calendar_edges",
            "a leap day, the last second of a year and the first of the next",
            "date_boundaries", n=4,
            cell=lambda t, c, i: (
                ("2024-02-29 00:00:00", "2025-12-31 23:59:59", "2026-01-01 00:00:00", "2026-02-28 23:59:59")[i]
                if c.kind == "timestamp"
                else (("2024-02-29", "2025-12-31", "2026-01-01", "2026-02-28")[i] if c.kind == "date" else _DEFAULT)
            ),
        ),
    ]
    if prof is not None and prof.columns:
        mirrored = _mirror(schema, prof)
        if mirrored is not None:
            out.append(mirrored)
    return out


def _mirror(schema: SourceSchema, prof: Profile) -> Variant | None:
    """A dataset shaped like the source: its extremes, and NULLs where it has them."""

    def cell(table: Table, col: Column, i: int):
        stat = prof.columns.get((table.name, col.name))
        if stat is None or not _free(schema, table, col):
            return _DEFAULT
        total = prof.rows.get(table.name, 0)
        if stat.nulls and col.nullable and i == 2:
            return None
        if stat.nulls and total and stat.nulls * 2 >= total and col.nullable and i % 2 == 0:
            return None
        if col.kind in ("timestamp", "date"):
            value = stat.minimum if i == 0 else (stat.maximum if i == 1 else None)
            if value is None:
                return _DEFAULT
            text = value.isoformat(sep=" ") if isinstance(value, _dt.datetime) else str(value)
            return text[:19] if col.kind == "timestamp" else text[:10]
        if i == 0 and stat.minimum is not None:
            return stat.minimum
        if i == 1 and stat.maximum is not None:
            return stat.maximum
        return _DEFAULT

    try:
        return _build(
            schema, "source_shaped",
            "the source's own extremes and NULL pattern, taken from aggregate "
            "statistics (MIN, MAX, COUNT) and not from its rows", "source_shaped", n=4, cell=cell,
        )
    except Exception:
        return None


def _string_forms(value: str) -> list[str]:
    forms = [value, value.upper(), value.lower(), value.title(), value + " ", "x" + value]
    seen: list[str] = []
    for form in forms:
        if form not in seen:
            seen.append(form)
    return seen


def _pattern_forms(pattern: str) -> list[str]:
    core = pattern.replace("%", "").replace("_", "")
    if not core:
        return []
    lead = "" if not pattern.startswith("%") else "x "
    tail = "" if not pattern.endswith("%") else " y"
    base = [f"{lead}{core}{tail}", f"{lead}{core.upper()}{tail}", f"{lead}{core.lower()}{tail}",
            f"{lead}{core.title()}{tail}", core, "zz"]
    return list(dict.fromkeys(base))


def literal_dataset(schema: SourceSchema, feats: QueryFeatures, case_name: str) -> Variant | None:
    """Plant the query's own literals in the data, in the forms that split engines.

    A filter that matches nothing proves nothing, and a filter on a boundary is
    where ``>`` and ``>=`` and a case-insensitive ``=`` show themselves. Every
    literal gets a cycle of its own length, so across the rows the combinations
    of a multi-condition WHERE are covered rather than only the diagonal.
    """
    if not feats.has_literals:
        return None
    plans: dict[tuple[str, str], list[Any]] = {}

    def targets_for(column: str, kinds: tuple[str, ...]):
        for table in schema.tables:
            for col in table.columns:
                if not _free(schema, table, col) or col.kind not in kinds:
                    continue
                if column and col.name.lower() != column:
                    continue
                yield table, col

    def plan(column: str, kinds: tuple[str, ...], values: list[Any]) -> None:
        hit = list(targets_for(column, kinds))
        if not hit and column:
            hit = list(targets_for("", kinds))[:2]
        for table, col in hit:
            plans.setdefault((table.name, col.name), []).extend(
                v for v in values if v not in plans.get((table.name, col.name), [])
            )

    for column, text in feats.strings:
        plan(column, ("text",), _string_forms(text))
    for column, pattern in feats.patterns:
        plan(column, ("text",), _pattern_forms(pattern))
    for column, number in feats.numbers:
        step = decimal.Decimal(1)
        plan(column, ("int",), [number + step, number, number - step])
        plan(column, ("decimal", "double"),
             [number + step, number, number - step, number + decimal.Decimal("0.01"),
              number - decimal.Decimal("0.01")])
    for column, day in feats.dates:
        base = _dt.date.fromisoformat(day)
        days = [base - _dt.timedelta(days=1), base, base + _dt.timedelta(days=1)]
        plan(column, ("date",), [d.isoformat() for d in days])
        plan(column, ("timestamp",),
             [f"{days[0].isoformat()} 23:59:59", f"{base.isoformat()} 00:00:00",
              f"{base.isoformat()} 12:00:00", f"{days[2].isoformat()} 00:00:00"])
    if not plans:
        return None

    # Row 0 takes the first form of every literal, so at least one row is the
    # query's own conjunction. The rest are drawn independently per column from
    # a generator seeded by the plan itself: the same query always gets the
    # same dataset, and the combinations of a multi-condition WHERE are mixed
    # rather than walked along the diagonal.
    import random

    n = 16
    seed = repr(sorted((k, [str(x) for x in v]) for k, v in plans.items()))
    picks: dict[tuple[str, str], list[Any]] = {}
    for key in sorted(plans):
        rng = random.Random(f"{seed}|{key}")
        values = plans[key]
        picks[key] = [values[0]] + [values[(i + rng.randrange(len(values))) % len(values)]
                                    for i in range(1, n)]

    def cell(table: Table, col: Column, i: int):
        chosen = picks.get((table.name, col.name))
        return chosen[i] if chosen else _DEFAULT

    digest = hashlib.sha256(repr(sorted((k, [str(x) for x in v]) for k, v in plans.items())).encode()).hexdigest()[:8]
    try:
        return _build(
            schema, f"literals_{digest}",
            "this query's own literals planted in the data: each string in "
            "several cases and with a trailing blank, each number at the "
            f"boundary and one step either side (built for {case_name})",
            "literal_boundaries", n=n, cell=cell,
        )
    except Exception:
        return None


# --------------------------------------------------------------------------
# the model tier
# --------------------------------------------------------------------------
DATASET_SYSTEM = (
    "You design small test datasets for SQL migration testing. "
    "Reply with one JSON object only: no prose, no markdown fences."
)

DATASET_PROMPT = """A {dialect} query is being migrated to IBM Db2 and must be proved to return the same rows.

Schema (column order matters):
{schema}

Query:
{sql}

Problem with the datasets tried so far: {reason}

Write rows so that the query returns at least three rows, and so that the rows
include values where {dialect} and Db2 are known to differ: the same text in
different letter case, trailing blanks, NULLs in nullable columns, numbers that
do not divide evenly, and equal values in ORDER BY columns.

Rules: at most 6 rows per table. Values in column order. Primary keys unique
and not null. Foreign keys (columns ending _id) must match an id in the parent
table. Dates as 'YYYY-MM-DD', timestamps as 'YYYY-MM-DD HH:MM:SS', decimals as
strings, booleans as true/false.

Reply with JSON of the form {{"table_name": [[value, ...], ...]}} covering every table."""


def parse_model_dataset(schema: SourceSchema, text: str, name: str, targets: str) -> Variant:
    """Turn a model's reply into a dataset, or raise ``ValueError`` saying why not.

    The reply is data, and it is treated like data from anywhere else: parsed,
    checked against the schema value by value, and capped. Nothing in it is
    ever executed.
    """
    body = (text or "").strip()
    if body.startswith("```"):
        body = "\n".join(l for l in body.splitlines() if not l.strip().startswith("```"))
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    try:
        data = json.loads(body[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"reply is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    lowered = {str(k).lower(): v for k, v in data.items()}
    rows: dict[str, list[tuple]] = {}
    for table in schema.tables:
        given = lowered.get(table.name.lower(), [])
        if not isinstance(given, list):
            raise ValueError(f"{table.name}: rows are not a list")
        out, keys = [], set()
        for raw in given[:8]:
            if not isinstance(raw, list) or len(raw) != len(table.columns):
                raise ValueError(
                    f"{table.name}: a row has {len(raw) if isinstance(raw, list) else '?'} "
                    f"values for {len(table.columns)} columns"
                )
            row = []
            for col, value in zip(table.columns, raw):
                if isinstance(value, (dict, list)):
                    raise ValueError(f"{table.name}.{col.name}: nested value")
                if value is None and (col.pk or not col.nullable):
                    raise ValueError(f"{table.name}.{col.name}: NULL in a NOT NULL column")
                try:
                    row.append(None if value is None else _fit(col, value))
                except Exception as exc:
                    raise ValueError(f"{table.name}.{col.name}: {value!r} is not a {col.kind}") from exc
            pk = tuple(v for v, c in zip(row, table.columns) if c.pk)
            if pk and pk in keys:
                raise ValueError(f"{table.name}: duplicate primary key {pk}")
            keys.add(pk)
            out.append(tuple(row))
        rows[table.name] = out
    if not any(rows.values()):
        raise ValueError("the reply contains no rows")
    return Variant(
        name=name, targets=targets, rows=rows, ddl=schema.ddl(),
        tables=schema.table_names, origin="LLM", strategy="model_proposed",
    )


# --------------------------------------------------------------------------
# the Db2 cache and its log
# --------------------------------------------------------------------------
def _payload(variant: Variant) -> str:
    return json.dumps(
        {"ddl": list(variant.schema_ddl), "tables": list(variant.schema_tables),
         "rows": {t: [list(r) for r in rows] for t, rows in variant.rows.items()}},
        default=str,
    )


class DatasetStore:
    """``PORTPROOF.DATASET`` and ``PORTPROOF.DATASET_RUN``, through SQL PL only.

    The runtime identity cannot INSERT into either table. It calls the two
    procedures, like every other write PortProof makes.
    """

    def __init__(self, conn) -> None:
        self.conn = conn
        self._known: set[str] = set()

    def save(self, schema_fp: str, variant: Variant) -> None:
        sha = variant.fingerprint
        if sha in self._known:
            return
        db.call_proc(
            self.conn, "PORTPROOF.RECORD_DATASET",
            (schema_fp, variant.name[:120], variant.origin, (variant.strategy or variant.name)[:40],
             variant.targets[:400], _payload(variant), sha, 0),
        )
        self._known.add(sha)

    def cached(self, schema_fp: str, origin: str | None = None) -> list[Variant]:
        sql = ("SELECT NAME, ORIGIN, STRATEGY, TARGETS, PAYLOAD FROM PORTPROOF.DATASET "
               "WHERE SCHEMA_FP = ?")
        params: list[Any] = [schema_fp]
        if origin:
            sql += " AND ORIGIN = ?"
            params.append(origin)
        out = []
        for name, origin_, strategy, targets, payload in db.fetch_all(
            self.conn, sql + " ORDER BY DATASET_ID", params
        ):
            try:
                data = json.loads(str(payload))
            except json.JSONDecodeError:  # pragma: no cover - written by RECORD_DATASET
                continue
            out.append(
                Variant(
                    name=str(name).strip(), targets=str(targets or "").strip(),
                    rows={t: [tuple(r) for r in rows] for t, rows in data["rows"].items()},
                    ddl=tuple(data["ddl"]), tables=tuple(data["tables"]),
                    origin=str(origin_).strip(), strategy=str(strategy or "").strip(),
                )
            )
        return out

    def log(self, sha: str, case_name: str, dialect: str, tags: Sequence[str],
            rows: int, vacuous: bool, agreed: bool, killed: bool) -> None:
        db.call_proc(
            self.conn, "PORTPROOF.RECORD_DATASET_RUN",
            (sha, case_name[:80], dialect, ",".join(tags)[:400], int(rows),
             int(vacuous), int(agreed), int(killed)),
        )

    def yields(self, dialect: str) -> dict[str, tuple[int, int, int]]:
        """``strategy -> (runs, substantive, kills)`` for one source dialect."""
        return {
            str(strategy).strip(): (int(runs), int(subst), int(kills))
            for strategy, runs, subst, kills in db.fetch_all(
                self.conn,
                "SELECT STRATEGY, RUNS, SUBSTANTIVE, KILLS FROM PORTPROOF.DATASET_YIELD "
                "WHERE SRC_DIALECT = ?",
                (dialect,),
            )
        }

    def count(self) -> tuple[int, int]:
        row = db.fetch_one(
            self.conn,
            "SELECT (SELECT COUNT(*) FROM PORTPROOF.DATASET), "
            "(SELECT COUNT(*) FROM PORTPROOF.DATASET_RUN) FROM SYSIBM.SYSDUMMY1",
        )
        return (int(row[0]), int(row[1])) if row else (0, 0)


# --------------------------------------------------------------------------
# the agent
# --------------------------------------------------------------------------
#: Which strategies a query's features make worth trying first, before any log
#: exists to learn from.
_RELEVANT: dict[str, tuple[str, ...]] = {
    "division": ("division_and_rounding", "negatives_and_halves", "extreme_values"),
    "arithmetic": ("division_and_rounding", "negatives_and_halves", "extreme_values"),
    "string_eq": ("mixed_case", "trailing_spaces", "accents_and_unicode", "literal_boundaries"),
    "like": ("like_wildcards", "mixed_case", "literal_boundaries"),
    "string_fn": ("trailing_spaces", "accents_and_unicode", "extreme_values"),
    "concat": ("nulls_and_empties", "trailing_spaces"),
    "order_by": ("nulls_and_empties", "ties_and_duplicates", "mixed_case", "accents_and_unicode"),
    "limit": ("ties_and_duplicates", "mixed_case"),
    "aggregate": ("empty_groups", "nulls_and_empties", "ties_and_duplicates"),
    "group_by": ("mixed_case", "empty_groups", "trailing_spaces"),
    "null_logic": ("nulls_and_empties",),
    "subquery": ("nulls_and_empties", "empty_groups"),
    "date_fn": ("date_boundaries",),
    "date_cmp": ("date_boundaries", "literal_boundaries"),
    "numeric_cmp": ("literal_boundaries", "negatives_and_halves", "extreme_values"),
    "join": ("empty_groups", "nulls_and_empties"),
    "window": ("ties_and_duplicates",),
    "distinct": ("ties_and_duplicates", "mixed_case"),
}


@dataclass
class AgentStats:
    cache_hits: int = 0
    generated: int = 0
    query_aware: int = 0
    model_calls: int = 0
    model_accepted: int = 0
    model_rejected: int = 0
    model_reused: int = 0
    rejected_by_engine: int = 0
    escalations: int = 0
    rescued: int = 0

    def lines(self) -> list[str]:
        return [
            f"datasets reused from the Db2 cache : {self.cache_hits}",
            f"generated by rule (free)           : {self.generated}",
            f"built from a query's own literals  : {self.query_aware}",
            f"refused by an engine and discarded : {self.rejected_by_engine}",
            f"proofs too weak, so escalated      : {self.escalations}",
            f"  answered by a cached model dataset: {self.model_reused}",
            f"  model calls made                 : {self.model_calls} "
            f"(accepted {self.model_accepted}, rejected {self.model_rejected})",
            f"  proofs lifted out of VACUOUS/WEAK: {self.rescued}",
        ]


class DatasetAgent:
    """Chooses, builds, checks and remembers the datasets for each statement."""

    def __init__(
        self,
        *,
        store: DatasetStore | None = None,
        model: Any | None = None,
        max_datasets: int = 0,
        builtin: Sequence[Variant] | None = None,
        learn: bool = True,
    ) -> None:
        self.store = store
        self.model = model
        self.max_datasets = max_datasets
        self.builtin = list(builtin if builtin is not None else VARIANTS)
        self.learn = learn
        self.stats = AgentStats()
        self._schemas: dict[tuple[str, str], tuple[SourceSchema, Profile | None]] = {
        }
        self._generated: dict[str, list[Variant]] = {}
        self._usable: dict[tuple[str, str], bool] = {}
        self._yields: dict[str, dict[str, tuple[int, int, int]]] = {}

    # -- schemas ---------------------------------------------------------
    def register(self, name: str, dialect: str, schema: SourceSchema, prof: Profile | None = None) -> None:
        self._schemas[(name, dialect)] = (schema, prof)

    def schema_for(self, name: str, dialect: str) -> SourceSchema:
        if not name:
            return FIXTURE
        return self._schemas[(name, dialect)][0]

    # -- candidates ------------------------------------------------------
    def _schema_level(self, name: str, dialect: str) -> list[Variant]:
        """Datasets that depend on the schema alone: cached if possible."""
        if not name:
            return list(self.builtin)
        schema, prof = self._schemas[(name, dialect)]
        fp = schema.fingerprint
        if fp in self._generated:
            return self._generated[fp]
        found: list[Variant] = []
        if self.store is not None:
            try:
                found = [v for v in self.store.cached(fp, "GENERATED")
                         if v.strategy != "literal_boundaries"]
            except db.Db2Error:
                found = []
        if found:
            self.stats.cache_hits += len(found)
        else:
            found = generate(schema, prof)
            self.stats.generated += len(found)
            self._save(fp, found)
        self._generated[fp] = found
        return found

    def _save(self, fp: str, variants: Sequence[Variant]) -> None:
        if self.store is None:
            return
        for variant in variants:
            try:
                self.store.save(fp, variant)
            except db.Db2Error:  # the cache is an optimisation, never a dependency
                pass

    def _model_cached(self, fp: str) -> list[Variant]:
        if self.store is None:
            return []
        try:
            return self.store.cached(fp, "LLM")
        except db.Db2Error:
            return []

    def _score(self, variant: Variant, feats: QueryFeatures, dialect: str) -> float:
        strategy = variant.strategy or variant.name
        score = 0.0
        for rank, tag in enumerate(feats.tags):
            relevant = _RELEVANT.get(tag, ())
            if strategy in relevant:
                score += 2.0 - 0.3 * relevant.index(strategy)
        if strategy == "base":
            score += 1.5  # always worth one ordinary dataset
        runs, substantive, kills = self._yield(dialect).get(strategy, (0, 0, 0))
        if runs:
            score += 4.0 * kills / runs + 1.0 * substantive / runs
        else:
            score += 0.5  # nothing known yet: worth finding out
        return score

    def _yield(self, dialect: str) -> dict[str, tuple[int, int, int]]:
        if dialect not in self._yields:
            try:
                self._yields[dialect] = self.store.yields(dialect) if self.store else {}
            except db.Db2Error:
                self._yields[dialect] = {}
        return self._yields[dialect]

    def plan(self, statement, source: Any = None, target: Any = None) -> tuple[list[Variant], QueryFeatures]:
        """The datasets to prove this statement on, best first."""
        feats = features(statement.sql, statement.dialect)
        schema = self.schema_for(statement.schema, statement.dialect)
        candidates = list(self._schema_level(statement.schema, statement.dialect))
        literal = literal_dataset(schema, feats, statement.case_name)
        if literal is not None:
            candidates.append(literal)
            self.stats.query_aware += 1
            self._save(schema.fingerprint, [literal])
        seen: set[str] = set()
        unique = []
        for variant in candidates:
            if variant.fingerprint not in seen:
                seen.add(variant.fingerprint)
                unique.append(variant)
        usable = [v for v in unique if self._loads(v, source, target)]
        ranked = sorted(
            usable, key=lambda v: -self._score(v, feats, statement.dialect)
        ) if self.max_datasets else usable
        if self.max_datasets:
            ranked = ranked[: self.max_datasets]
        return ranked, feats

    def _loads(self, variant: Variant, source: Any, target: Any) -> bool:
        """A dataset neither engine can hold is discarded, not argued with."""
        if variant.origin == "BUILTIN" or source is None or target is None:
            return True
        key = (getattr(source, "name", "?"), variant.fingerprint)
        if key not in self._usable:
            try:
                activate(source, variant)
                activate(target, variant)
                self._usable[key] = True
            except Exception:
                self._usable[key] = False
                self.stats.rejected_by_engine += 1
        return self._usable[key]

    # -- escalation ------------------------------------------------------
    def needs_more(self, verdict: SemanticVerdict) -> bool:
        return verdict.outcome in ("VACUOUS", "EQUIVALENT") and verdict.strength in ("NONE", "WEAK")

    def escalate(
        self, statement, verdict: SemanticVerdict, used: Sequence[Variant],
        source: Any = None, target: Any = None,
    ) -> list[Variant]:
        """More datasets for a proof that is too thin: cached model ones, then a call."""
        self.stats.escalations += 1
        schema = self.schema_for(statement.schema, statement.dialect)
        have = {v.fingerprint for v in used}
        reuse = [v for v in self._model_cached(schema.fingerprint)
                 if v.fingerprint not in have and self._loads(v, source, target)]
        if reuse:
            self.stats.model_reused += 1
            return reuse
        if self.model is None:
            return []
        reason = (
            "every one returned no rows on both engines, so nothing was compared"
            if verdict.outcome == "VACUOUS"
            else f"only {verdict.substantive_instances} returned rows and they gave "
                 f"{verdict.distinct_inputs} distinct result(s), which is weak evidence"
        )
        self.stats.model_calls += 1
        try:
            reply = self.model.ask(
                DATASET_SYSTEM,
                DATASET_PROMPT.format(
                    dialect=statement.dialect, schema=schema.prompt_text(),
                    sql=statement.sql, reason=reason,
                ),
                stage="DATASET", case_name=statement.case_name,
            )
            variant = parse_model_dataset(
                schema, reply, f"{schema.name}:model_{statement.case_name.replace('/', '_')}",
                f"proposed by {getattr(self.model, 'model', 'a model')} for "
                f"{statement.case_name} because {reason}",
            )
        except Exception:
            self.stats.model_rejected += 1
            return []
        if variant.fingerprint in have or not self._loads(variant, source, target):
            self.stats.model_rejected += 1
            return []
        self.stats.model_accepted += 1
        self._save(schema.fingerprint, [variant])
        return [variant]

    # -- learning --------------------------------------------------------
    def observe(self, statement, feats: QueryFeatures, verdict: SemanticVerdict) -> None:
        """Log what each dataset achieved, which is what :meth:`plan` ranks by."""
        if self.store is None or not self.learn:
            return
        for instance in verdict.conclusive:
            if not instance.fingerprint:
                continue
            try:
                if instance.origin == "BUILTIN":
                    # Hand-built datasets are logged under the fixture schema so
                    # their yield is learned too.
                    self.store.save(FIXTURE.fingerprint, next(
                        v for v in self.builtin if v.fingerprint == instance.fingerprint))
                self.store.log(
                    instance.fingerprint, statement.case_name, statement.dialect, feats.tags,
                    instance.rows_compared, instance.vacuous, instance.agreed, not instance.agreed,
                )
            except (db.Db2Error, StopIteration):
                continue
