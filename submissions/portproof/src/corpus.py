"""The migration corpus, the shared fixture, and the adversarial data variants.

Three things live here:

* :data:`CORPUS` -- realistic PostgreSQL and MySQL statements to migrate. It
  extends the 32-statement set used in the feasibility study, which measured
  IBM's ``db2-sqlglot-dialect`` reporting success on 32/32 while 20 of its
  outputs failed on a real Db2. The additions are joins, a column-by-column
  division and a ``NOT IN`` over a NULL-bearing subquery: the original set was
  entirely single-table, so nothing in it could expose a join or a NULL
  three-valued-logic difference at all.
* :data:`FIXTURE_DDL` / :data:`FIXTURE_ROWS` -- a tiny schema created identically
  in Db2 and in the source engine so results can be compared.
* :data:`VARIANTS` -- adversarial datasets, each built to make the source engine
  and Db2 disagree on a specific documented semantic difference.

The corpus covers four source dialects. PostgreSQL and MySQL were the original
two; SQL Server (``tsql``) and SQLite were added so that the claim "the prover
is not tied to one engine pair" is something the run measures rather than
something the README says. Each dialect is judged only by its own real engine.

A :class:`Variant` may also carry its own DDL. The hand-built ones below share
the four-table fixture; datasets produced by :mod:`src.datasets` for a schema
discovered on a source engine bring the schema with them.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Statement:
    dialect: str
    name: str
    sql: str
    #: Which source schema the statement reads. "" is the built-in fixture; any
    #: other value names a schema discovered on the source engine, whose
    #: datasets come from the dataset agent rather than from :data:`VARIANTS`.
    schema: str = ""

    @property
    def case_name(self) -> str:
        return f"{self.dialect}/{self.name}"


CORPUS: list[Statement] = [
    Statement("postgres", "limit_offset", "SELECT id, name FROM customers ORDER BY name LIMIT 10 OFFSET 2"),
    Statement("postgres", "ilike", "SELECT id FROM customers WHERE name ILIKE '%smith%' ORDER BY id"),
    Statement("postgres", "cast_colon", "SELECT created_at::date AS d, amount::numeric(10,2) AS a FROM orders ORDER BY id"),
    Statement("postgres", "string_agg", "SELECT customer_id, string_agg(sku, ', ' ORDER BY sku) AS skus FROM order_items GROUP BY customer_id ORDER BY customer_id"),
    Statement("postgres", "distinct_on", "SELECT DISTINCT ON (customer_id) customer_id, id FROM orders ORDER BY customer_id, created_at DESC"),
    Statement("postgres", "date_trunc", "SELECT date_trunc('month', created_at) AS m, sum(amount) AS s FROM orders GROUP BY 1 ORDER BY 1"),
    Statement("postgres", "filter_agg", "SELECT count(*) FILTER (WHERE status = 'PAID') AS paid, count(*) AS total FROM orders"),
    Statement("postgres", "boolean_col", "SELECT id FROM customers WHERE is_active = true AND NOT is_deleted ORDER BY id"),
    Statement("postgres", "coalesce_nullif", "SELECT id, coalesce(nullif(email, ''), 'n/a') AS e FROM customers ORDER BY id"),
    Statement("postgres", "jsonb_arrow", "SELECT id, payload->>'city' AS city FROM events ORDER BY id"),
    Statement("postgres", "array_agg", "SELECT customer_id, array_agg(id) AS ids FROM orders GROUP BY customer_id ORDER BY customer_id"),
    Statement("postgres", "extract_epoch", "SELECT id, extract(epoch FROM created_at) AS ep FROM orders ORDER BY id"),
    Statement("postgres", "window_lag", "SELECT id, amount - lag(amount) OVER (PARTITION BY customer_id ORDER BY created_at) AS delta FROM orders ORDER BY id"),
    Statement("postgres", "recursive_cte", "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 5) SELECT n FROM r ORDER BY n"),
    Statement("postgres", "regex_match", "SELECT id FROM customers WHERE email ~* '^[a-z]+@example[.]com$' ORDER BY id"),
    Statement("postgres", "concat_op", "SELECT first_name || ' ' || last_name AS full_name FROM customers ORDER BY id"),
    Statement("postgres", "to_char", "SELECT id, to_char(created_at, 'YYYY-MM') AS m FROM orders ORDER BY id"),
    Statement("postgres", "percentile", "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY amount) AS median FROM orders"),
    Statement("postgres", "int_division", "SELECT 7 / 2 AS q FROM customers WHERE id = 1"),
    Statement("postgres", "null_ordering", "SELECT id, email FROM customers ORDER BY email, id"),
    Statement("postgres", "empty_string_null", "SELECT id FROM customers WHERE email = '' ORDER BY id"),
    Statement("postgres", "case_compare", "SELECT id FROM customers WHERE name = 'ASHA SMITH' ORDER BY id"),
    Statement("postgres", "join_aggregate", "SELECT c.id, c.name, count(o.id) AS orders, coalesce(sum(o.amount), 0) AS spend FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name ORDER BY c.id"),
    Statement("postgres", "join_three_tables", "SELECT c.name, i.sku, o.amount FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items i ON i.customer_id = c.id WHERE o.status = 'PAID' ORDER BY c.name, i.sku, o.amount"),
    Statement("postgres", "column_division", "SELECT id, amount / quantity AS unit_price FROM orders WHERE quantity <> 0 ORDER BY id"),
    Statement("postgres", "not_in_null", "SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM orders) ORDER BY id"),
    Statement("mysql", "limit_comma", "SELECT id, name FROM customers ORDER BY id LIMIT 1, 3"),
    Statement("mysql", "join_group_concat", "SELECT c.id, GROUP_CONCAT(i.sku ORDER BY i.sku SEPARATOR ',') AS skus FROM customers c LEFT JOIN order_items i ON i.customer_id = c.id GROUP BY c.id ORDER BY c.id"),
    Statement("mysql", "column_division", "SELECT id, amount / quantity AS unit_price FROM orders WHERE quantity <> 0 ORDER BY id"),
    Statement("mysql", "backticks_ifnull", "SELECT `id`, IFNULL(`email`, 'n/a') AS e FROM `customers` ORDER BY `id`"),
    Statement("mysql", "date_format", "SELECT DATE_FORMAT(created_at, '%Y-%m') AS m, COUNT(*) AS n FROM orders GROUP BY m ORDER BY m"),
    Statement("mysql", "group_concat", "SELECT customer_id, GROUP_CONCAT(sku SEPARATOR ',') AS skus FROM order_items GROUP BY customer_id ORDER BY customer_id"),
    Statement("mysql", "date_sub", "SELECT id FROM orders WHERE created_at > DATE_SUB('2026-03-01', INTERVAL 7 DAY) ORDER BY id"),
    Statement("mysql", "if_func", "SELECT id, IF(amount > 100, 'big', 'small') AS size FROM orders ORDER BY id"),
    Statement("mysql", "case_insensitive_eq", "SELECT id FROM customers WHERE name = 'asha smith' ORDER BY id"),
    Statement("mysql", "concat_func", "SELECT CONCAT(first_name, ' ', last_name) AS full_name FROM customers ORDER BY id"),
    Statement("mysql", "int_division", "SELECT 7 DIV 2 AS q FROM customers WHERE id = 1"),
    Statement("mysql", "limit_only", "SELECT id FROM orders ORDER BY id LIMIT 3"),
    # -- SQL Server. Its default collation is case-insensitive, '+' is its
    # string concatenation, LEN ignores trailing blanks and '/' on two integers
    # truncates: four places where a clean translation changes the answer.
    Statement("tsql", "top_n", "SELECT TOP 3 id, name FROM customers ORDER BY id"),
    Statement("tsql", "isnull", "SELECT id, ISNULL(email, 'n/a') AS e FROM customers ORDER BY id"),
    Statement("tsql", "plus_concat", "SELECT id, first_name + ' ' + last_name AS full_name FROM customers ORDER BY id"),
    Statement("tsql", "len_trailing", "SELECT id, LEN(name) AS n FROM customers ORDER BY id"),
    Statement("tsql", "case_insensitive_eq", "SELECT id FROM customers WHERE name = 'asha smith' ORDER BY id"),
    Statement("tsql", "int_division", "SELECT id, quantity / 2 AS half FROM orders WHERE quantity IS NOT NULL ORDER BY id"),
    Statement("tsql", "column_division", "SELECT id, amount / quantity AS unit_price FROM orders WHERE quantity <> 0 ORDER BY id"),
    Statement("tsql", "datediff", "SELECT id, DATEDIFF(day, created_at, '2026-03-01') AS age FROM orders ORDER BY id"),
    Statement("tsql", "iif", "SELECT id, IIF(amount > 100, 'big', 'small') AS size FROM orders ORDER BY id"),
    Statement("tsql", "string_agg", "SELECT customer_id, STRING_AGG(sku, ',') WITHIN GROUP (ORDER BY sku) AS skus FROM order_items GROUP BY customer_id ORDER BY customer_id"),
    Statement("tsql", "offset_fetch", "SELECT id FROM orders ORDER BY id OFFSET 1 ROWS FETCH NEXT 2 ROWS ONLY"),
    Statement("tsql", "convert_month", "SELECT id, CONVERT(varchar(7), created_at, 126) AS m FROM orders ORDER BY id"),
    Statement("tsql", "null_ordering", "SELECT id, email FROM customers ORDER BY email, id"),
    Statement("tsql", "charindex", "SELECT id, CHARINDEX(' ', name) AS p FROM customers ORDER BY id"),
    Statement("tsql", "join_aggregate", "SELECT c.id, COUNT(o.id) AS orders, COALESCE(SUM(o.amount), 0) AS spend FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id ORDER BY c.id"),
    # -- SQLite. Dynamic typing is the trap: a DECIMAL column holding 7.00
    # stores the integer 7, so amount / quantity is integer division there and
    # decimal division on Db2. LIKE is case-insensitive, and NULLs sort first.
    Statement("sqlite", "limit_offset", "SELECT id, name FROM customers ORDER BY id LIMIT 2 OFFSET 1"),
    Statement("sqlite", "ifnull", "SELECT id, ifnull(email, 'n/a') AS e FROM customers ORDER BY id"),
    Statement("sqlite", "concat_op", "SELECT id, first_name || ' ' || last_name AS full_name FROM customers ORDER BY id"),
    Statement("sqlite", "column_division", "SELECT id, amount / quantity AS unit_price FROM orders WHERE quantity <> 0 ORDER BY id"),
    Statement("sqlite", "int_division", "SELECT id, quantity / 2 AS half FROM orders WHERE quantity IS NOT NULL ORDER BY id"),
    Statement("sqlite", "strftime_month", "SELECT strftime('%Y-%m', created_at) AS m, count(*) AS n FROM orders WHERE created_at IS NOT NULL GROUP BY strftime('%Y-%m', created_at) ORDER BY m"),
    Statement("sqlite", "group_concat", "SELECT customer_id, group_concat(sku, ',') AS skus FROM order_items GROUP BY customer_id ORDER BY customer_id"),
    Statement("sqlite", "like_case", "SELECT id FROM customers WHERE name LIKE '%SMITH%' ORDER BY id"),
    Statement("sqlite", "null_ordering", "SELECT id, email FROM customers ORDER BY email, id"),
    Statement("sqlite", "substr_instr", "SELECT id, substr(name, 1, 4) AS s, instr(name, ' ') AS p FROM customers ORDER BY id"),
    Statement("sqlite", "case_compare", "SELECT id FROM customers WHERE name = 'ASHA SMITH' ORDER BY id"),
    Statement("sqlite", "join_aggregate", "SELECT c.id, count(o.id) AS orders, coalesce(sum(o.amount), 0) AS spend FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id ORDER BY c.id"),
]

#: Every source dialect the corpus speaks, in report order.
DIALECTS: tuple[str, ...] = ("postgres", "mysql", "tsql", "sqlite")

#: Portable DDL: valid on Db2 and on the source engine without change.
FIXTURE_DDL: list[str] = [
    """CREATE TABLE customers (
         id INTEGER NOT NULL PRIMARY KEY,
         name VARCHAR(60),
         email VARCHAR(80),
         first_name VARCHAR(30),
         last_name VARCHAR(30),
         is_active BOOLEAN,
         is_deleted BOOLEAN
       )""",
    """CREATE TABLE orders (
         id INTEGER NOT NULL PRIMARY KEY,
         customer_id INTEGER,
         amount DECIMAL(10,2),
         status VARCHAR(10),
         created_at TIMESTAMP,
         quantity INTEGER
       )""",
    """CREATE TABLE order_items (
         customer_id INTEGER,
         sku VARCHAR(10)
       )""",
    """CREATE TABLE events (
         id INTEGER NOT NULL PRIMARY KEY,
         payload VARCHAR(400)
       )""",
]

FIXTURE_TABLES = ("customers", "orders", "order_items", "events")


@dataclass(frozen=True)
class Variant:
    """One adversarial dataset, aimed at a specific semantic difference."""

    name: str
    targets: str
    rows: dict[str, list[tuple]] = field(default_factory=dict)
    #: Portable ``CREATE TABLE`` statements for a schema other than the fixture.
    #: Empty means the four fixture tables.
    ddl: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    #: Where the dataset came from: BUILTIN (written by hand, below), GENERATED
    #: (a deterministic strategy in :mod:`src.datasets`) or LLM (proposed by a
    #: model and kept only because both engines loaded it).
    origin: str = "BUILTIN"
    strategy: str = ""

    @property
    def schema_ddl(self) -> tuple[str, ...]:
        return self.ddl or tuple(FIXTURE_DDL)

    @property
    def schema_tables(self) -> tuple[str, ...]:
        return self.tables or FIXTURE_TABLES

    @property
    def fingerprint(self) -> str:
        """Content hash: the same rows under the same DDL are the same dataset.

        Engines use it to load a dataset once and switch back to it, and the
        Db2 dataset cache uses it as the key, so a dataset that has already
        earned evidence is found again instead of being generated again.
        """
        import hashlib

        body = repr((self.schema_ddl, sorted((t, r) for t, r in self.rows.items())))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def shuffled(self) -> "Variant":
        """The same data, inserted in the opposite order.

        Logically identical: a table is a set, and no correct query can tell the
        difference. That is exactly what makes it a test. A statement whose
        ``ORDER BY`` has ties is not *determined* by its SQL, and reversing the
        insertion order is enough to make a real engine admit it by returning
        different rows for the same input -- see the stability probe in
        :func:`src.counterexample.prove_semantics`.
        """
        return Variant(
            name=f"{self.name}:reinserted",
            targets=f"{self.targets} (same rows, opposite insertion order)",
            rows={table: list(reversed(rows)) for table, rows in self.rows.items()},
            ddl=self.ddl,
            tables=self.tables,
            origin=self.origin,
            strategy=self.strategy,
        )


def _c(id_, name, email, first, last, active=True, deleted=False):
    return (id_, name, email, first, last, active, deleted)


def _o(id_, cust, amount, status, ts, quantity=2):
    return (id_, cust, amount, status, ts, quantity)


#: The baseline dataset: ordinary, unremarkable values.
BASE = Variant(
    name="base",
    targets="ordinary values; catches outright translation errors",
    rows={
        "customers": [
            _c(1, "Asha Smith", "asha@example.com", "Asha", "Smith"),
            _c(2, "Bob Stone", "bob@example.com", "Bob", "Stone"),
            _c(3, "Cy Smithers", "cy@example.com", "Cy", "Smithers", False, True),
            _c(4, "Dev Rao", "dev@example.com", "Dev", "Rao"),
        ],
        "orders": [
            _o(10, 1, "50.00", "PAID", "2026-01-05 10:00:00", 2),
            _o(11, 1, "150.00", "NEW", "2026-02-07 11:00:00", 3),
            _o(12, 2, "99.50", "PAID", "2026-02-20 09:30:00", 1),
            _o(13, 3, "10.00", "PAID", "2026-03-01 08:00:00", 4),
        ],
        "order_items": [(1, "B2"), (1, "A1"), (2, "C3")],
        "events": [
            (1, '{"type":"click","city":"Pune"}'),
            (2, '{"type":"view","city":"Agra"}'),
        ],
    },
)

# Every variant below overrides *all four* tables.
#
# They used to be written as ``{**BASE.rows, "customers": [...]}``, which looks
# like six datasets and is not. ``order_items`` and ``events`` were the same
# three and two rows in five of the six, so a statement over those tables was
# one test reported as five; and because the dict values were the *same list
# objects* as BASE's, there was nothing stopping one variant's data from being
# mistaken for another's. SemanticVerdict.distinct_inputs now measures this
# rather than trusting it, and the data below gives it something to measure.
VARIANTS: list[Variant] = [
    BASE,
    Variant(
        name="mixed_case",
        targets="case-sensitive comparison: MySQL's default collation matches "
                "'Asha' to 'ASHA'; Db2 and PostgreSQL do not",
        rows={
            "customers": [
                _c(1, "ASHA SMITH", "ASHA@EXAMPLE.COM", "Asha", "Smith"),
                _c(2, "asha smith", "bob@example.com", "Bob", "Stone"),
                _c(3, "Asha Smith", "cy@Example.com", "Cy", "Smithers"),
            ],
            "orders": [
                _o(20, 1, "11.00", "paid", "2026-01-06 10:00:00", 2),
                _o(21, 2, "22.00", "PAID", "2026-01-07 10:00:00", 4),
                _o(22, 3, "33.00", "Paid", "2026-01-08 10:00:00", 3),
            ],
            "order_items": [(1, "a1"), (1, "A1"), (2, "b2"), (3, "B2")],
            "events": [
                (1, '{"type":"Click","city":"PUNE"}'),
                (2, '{"type":"click","city":"pune"}'),
            ],
        },
    ),
    Variant(
        name="nulls_and_empties",
        targets="NULL ordering and empty-string handling: NULLs sort first in "
                "MySQL, last in Db2/PostgreSQL; aggregates skip NULLs; and "
                "NOT IN over a NULL-bearing subquery returns no rows at all",
        rows={
            "customers": [
                _c(1, "Asha Smith", None, "Asha", None),
                _c(2, "Bob Stone", "", "Bob", "Stone"),
                _c(3, "Cy Smithers", "cy@example.com", None, "Smithers"),
                _c(4, None, "dev@example.com", "Dev", "Rao", None, None),
            ],
            "orders": [
                # A NULL customer_id is what makes NOT IN collapse, and a NULL
                # amount is what separates COUNT(*) from COUNT(amount).
                _o(30, None, "40.00", "PAID", "2026-01-09 10:00:00", 2),
                _o(31, 1, None, "NEW", None, None),
                _o(32, 2, "0.00", None, "2026-02-01 00:00:00", 0),
            ],
            "order_items": [(1, None), (None, "A1"), (2, "")],
            "events": [
                (1, '{"type":"click"}'),
                (2, None),
                (3, '{"type":"view","city":null}'),
            ],
        },
    ),
    Variant(
        name="ties_and_duplicates",
        targets="unstable ordering: equal sort keys make DISTINCT ON and "
                "window functions non-deterministic unless fully ordered",
        rows={
            "customers": [
                _c(1, "Tie One", "t1@example.com", "Tie", "One"),
                _c(2, "Tie One", "t2@example.com", "Tie", "One"),
                _c(3, "Tie One", "t3@example.com", "Tie", "One"),
            ],
            "orders": [
                _o(40, 1, "50.00", "PAID", "2026-01-05 10:00:00", 2),
                _o(41, 1, "50.00", "PAID", "2026-01-05 10:00:00", 2),
                _o(42, 1, "50.00", "NEW", "2026-01-05 10:00:00", 2),
                _o(43, 2, "10.00", "PAID", "2026-03-01 08:00:00", 2),
            ],
            "order_items": [(1, "A1"), (1, "A1"), (1, "A1"), (2, "A1")],
            "events": [
                (1, '{"type":"click","city":"Agra"}'),
                (2, '{"type":"click","city":"Agra"}'),
            ],
        },
    ),
    Variant(
        name="division_and_rounding",
        targets="integer division and decimal scale: 7/2 is 3 on Db2 and "
                "PostgreSQL but 3.5 in MySQL, and DECIMAL/INTEGER scale rules "
                "differ, so amount/quantity rounds differently per engine",
        rows={
            "customers": [
                _c(1, "Asha Smith", "asha@example.com", "Asha", "Smith"),
                _c(2, "Bob Stone", "bob@example.com", "Bob", "Stone"),
            ],
            "orders": [
                # Chosen so amount/quantity is non-terminating, exactly .5, and
                # at the edge of DECIMAL(10,2) -- the three cases where the
                # engines' scale and rounding rules visibly part company.
                _o(50, 1, "7.00", "PAID", "2026-01-05 10:00:00", 2),
                _o(51, 1, "10.00", "PAID", "2026-02-07 11:00:00", 3),
                _o(52, 2, "0.01", "PAID", "2026-02-20 09:30:00", 7),
                _o(53, 2, "99999.99", "PAID", "2026-03-01 08:00:00", 1),
                _o(54, 2, "5.00", "NEW", "2026-03-02 08:00:00", 0),
            ],
            "order_items": [(1, "D4"), (2, "D4"), (2, "E5")],
            "events": [(1, '{"type":"sum","city":"Delhi"}')],
        },
    ),
    Variant(
        name="empty_groups",
        targets="aggregates over no rows: COUNT returns 0 but SUM/AVG return "
                "NULL, and a filtered aggregate may produce no group at all",
        rows={
            "customers": [_c(1, "Asha Smith", "asha@example.com", "Asha", "Smith")],
            "orders": [],
            "order_items": [],
            "events": [],
        },
    ),
    # -- the second six. The first six were chosen from the differences
    # between MySQL, PostgreSQL and Db2. These cover what those did not reach,
    # and what SQL Server and SQLite added when they joined the corpus.
    Variant(
        name="trailing_spaces",
        targets="blank padding: SQL Server's '=' and LEN ignore trailing "
                "blanks, Db2's VARCHAR comparison and LENGTH do not",
        rows={
            "customers": [
                _c(1, "Asha Smith ", "asha@example.com ", "Asha ", "Smith"),
                _c(2, "Asha Smith", "asha@example.com", "Asha", "Smith "),
                _c(3, " Bob Stone", "bob@example.com", " Bob", "Stone"),
                _c(4, "Cy  Smithers", "cy@example.com", "Cy", "Smithers  "),
            ],
            "orders": [
                _o(60, 1, "12.50", "PAID ", "2026-01-10 10:00:00", 2),
                _o(61, 2, "12.50", "PAID", "2026-01-11 10:00:00", 5),
                _o(62, 3, "7.25", " NEW", "2026-01-12 10:00:00", 3),
            ],
            "order_items": [(1, "A1 "), (1, "A1"), (2, " B2"), (3, "C3")],
            "events": [(1, '{"type":"click ","city":"Pune "}')],
        },
    ),
    Variant(
        name="accents_and_unicode",
        targets="accent and width sensitivity: MySQL's default collation is "
                "accent-insensitive ('Jose' = 'José'); Db2, PostgreSQL and "
                "SQL Server's default compare them as different strings",
        rows={
            "customers": [
                _c(1, "José Núñez", "jose@example.com", "José", "Núñez"),
                _c(2, "Jose Nunez", "jose2@example.com", "Jose", "Nunez"),
                _c(3, "Zoë Smith", "zoe@example.com", "Zoë", "Smith"),
                _c(4, "Zoe Smith", "zoe2@example.com", "Zoe", "Smith"),
                _c(5, "Asha Smith", "asha@example.com", "Asha", "Smith"),
            ],
            "orders": [
                _o(70, 1, "20.00", "PAID", "2026-01-15 10:00:00", 2),
                _o(71, 2, "30.00", "PAID", "2026-01-16 10:00:00", 3),
                _o(72, 3, "40.00", "NEW", "2026-01-17 10:00:00", 4),
            ],
            "order_items": [(1, "É1"), (2, "E1"), (3, "e1"), (3, "Z9")],
            "events": [(1, '{"type":"click","city":"Kraków"}')],
        },
    ),
    Variant(
        name="date_boundaries",
        targets="calendar edges: a leap day, the last second of a year and the "
                "first second of the next, where truncation, formatting and "
                "date arithmetic are most likely to round the wrong way",
        rows={
            "customers": [
                _c(1, "Asha Smith", "asha@example.com", "Asha", "Smith"),
                _c(2, "Bob Stone", "bob@example.com", "Bob", "Stone"),
            ],
            "orders": [
                _o(80, 1, "10.00", "PAID", "2024-02-29 00:00:00", 2),
                _o(81, 1, "20.00", "PAID", "2025-12-31 23:59:59", 3),
                _o(82, 2, "30.00", "PAID", "2026-01-01 00:00:00", 1),
                _o(83, 2, "40.00", "NEW", "2026-02-28 23:59:59", 4),
                _o(84, 2, "50.00", "NEW", "2026-03-01 00:00:00", 5),
            ],
            "order_items": [(1, "L1"), (2, "L2")],
            "events": [(1, '{"type":"rollover","city":"Pune"}')],
        },
    ),
    Variant(
        name="negatives_and_halves",
        targets="sign and rounding: -7/2 truncates toward zero, .5 rounds "
                "differently for DECIMAL and DOUBLE, and a negative quantity "
                "flips a comparison",
        rows={
            "customers": [
                _c(1, "Asha Smith", "asha@example.com", "Asha", "Smith"),
                _c(2, "Bob Stone", "bob@example.com", "Bob", "Stone"),
            ],
            "orders": [
                _o(90, 1, "-7.00", "PAID", "2026-01-05 10:00:00", 2),
                _o(91, 1, "7.00", "PAID", "2026-01-06 10:00:00", -2),
                _o(92, 2, "2.50", "PAID", "2026-01-07 10:00:00", 5),
                _o(93, 2, "0.05", "NEW", "2026-01-08 10:00:00", 2),
                _o(94, 2, "-0.01", "NEW", "2026-01-09 10:00:00", 3),
                _o(95, 2, "100.00", "PAID", "2026-01-10 10:00:00", 7),
                _o(96, 1, "100.01", "PAID", "2026-01-11 10:00:00", -7),
            ],
            "order_items": [(1, "N1"), (2, "N2"), (2, "N3")],
            "events": [(1, '{"type":"refund","city":"Agra"}')],
        },
    ),
    Variant(
        name="like_wildcards",
        targets="pattern matching: LIKE is case-insensitive on SQLite, MySQL "
                "and SQL Server and case-sensitive on Db2 and PostgreSQL, and "
                "literal % and _ in the data are where escaping goes wrong",
        rows={
            "customers": [
                _c(1, "Asha SMITH", "asha@example.com", "Asha", "SMITH"),
                _c(2, "bob smith", "bob@EXAMPLE.com", "bob", "smith"),
                _c(3, "Cy Smithers", "cy@example.com", "Cy", "Smithers"),
                _c(4, "100% Smith_Co", "pct@example.com", "100%", "Smith_Co"),
                _c(5, "Dev Rao", "dev@other.org", "Dev", "Rao"),
            ],
            "orders": [
                _o(100, 1, "150.00", "PAID", "2026-02-01 10:00:00", 3),
                _o(101, 2, "100.00", "paid", "2026-02-02 10:00:00", 2),
                _o(102, 4, "99.99", "NEW", "2026-02-03 10:00:00", 1),
            ],
            "order_items": [(1, "sm_1"), (2, "SM%1"), (4, "Sm11")],
            "events": [(1, '{"type":"search","city":"Smithfield"}')],
        },
    ),
    Variant(
        name="extreme_values",
        targets="range limits: the largest DECIMAL(10,2), a zero, a value "
                "filling its VARCHAR to the last character, and aggregates "
                "whose sum needs more digits than any one row",
        rows={
            "customers": [
                _c(1, "X" * 60, "a@b.co", "F" * 30, "L" * 30),
                _c(2, "y", "", "f", "l"),
                _c(3, "Asha Smith", "asha@example.com", "Asha", "Smith"),
            ],
            "orders": [
                _o(110, 1, "99999999.99", "PAID", "2026-01-05 10:00:00", 1),
                _o(111, 1, "99999999.99", "PAID", "2026-01-06 10:00:00", 2147483647),
                _o(112, 2, "0.00", "PAID", "2026-01-07 10:00:00", 1),
                _o(113, 3, "0.01", "NEW", "2026-01-08 10:00:00", 3),
            ],
            "order_items": [(1, "Z" * 10), (2, "0"), (3, "A1")],
            "events": [(1, '{"type":"bulk","city":"' + "Q" * 40 + '"}')],
        },
    ),
]

#: The six datasets the project shipped with, kept addressable so a run can be
#: compared before and after the set of datasets was doubled.
ORIGINAL_VARIANTS: list[Variant] = VARIANTS[:6]


def statements_for(dialect: str | None = None) -> list[Statement]:
    if dialect in (None, "", "all"):
        return list(CORPUS)
    return [s for s in CORPUS if s.dialect == dialect]
