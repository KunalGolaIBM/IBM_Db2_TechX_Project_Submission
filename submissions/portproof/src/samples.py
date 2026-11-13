"""Two source schemas PortProof was not written for.

Everything in :mod:`src.corpus` runs against one four-table fixture that the
hand-built datasets were designed around. That leaves a fair question open: does
any of this work on a schema nobody prepared datasets for?

These are the answer's test subjects. ``seed`` plays the part of the customer:
it creates an HR schema and a banking schema, with ordinary rows, in the source
engine's own database. From there PortProof is on its own. It reads the tables
back out of the engine's catalogue (:func:`src.datasets.introspect`), profiles
them with aggregate queries, and the dataset agent builds the adversarial
datasets for each query. Nothing here is consulted after seeding.

The workload is written once, in SQL that all four source engines accept
unchanged. The engines still disagree about what several of the queries mean,
which is the point.
"""
from __future__ import annotations

from typing import Any

from .corpus import DIALECTS, Statement, Variant
from .datasets import DatasetAgent, Profile, SourceSchema, introspect, profile

HR_DDL = (
    """CREATE TABLE departments (
         id INTEGER NOT NULL PRIMARY KEY,
         name VARCHAR(40),
         budget DECIMAL(12,2)
       )""",
    """CREATE TABLE employees (
         id INTEGER NOT NULL PRIMARY KEY,
         department_id INTEGER,
         full_name VARCHAR(60),
         email VARCHAR(80),
         grade VARCHAR(4),
         salary DECIMAL(10,2),
         bonus_pct INTEGER,
         hired_on DATE
       )""",
)

HR_ROWS = {
    "departments": [
        (1, "Engineering", "900000.00"),
        (2, "Finance", "250000.00"),
        (3, "Legal", "120000.00"),
    ],
    "employees": [
        (1, 1, "Priya Nair", "priya@corp.example", "E5", "128000.00", 12, "2019-04-01"),
        (2, 1, "Tom Becker", "tom@corp.example", "E3", "91000.00", 8, "2021-09-15"),
        (3, 2, "Lena Ortiz", "lena@corp.example", "F2", "74000.00", 5, "2022-01-10"),
        (4, 2, "Sam Okafor", "sam@corp.example", "F4", "99500.00", 10, "2018-06-30"),
        (5, 1, "Mei Tanaka", "mei@corp.example", "E4", "110000.00", None, "2020-11-02"),
    ],
}

BANK_DDL = (
    """CREATE TABLE accounts (
         id INTEGER NOT NULL PRIMARY KEY,
         owner_name VARCHAR(60),
         status VARCHAR(10),
         credit_limit DECIMAL(12,2),
         opened_at TIMESTAMP
       )""",
    """CREATE TABLE transactions (
         id INTEGER NOT NULL PRIMARY KEY,
         account_id INTEGER,
         amount DECIMAL(12,2),
         currency VARCHAR(3),
         memo VARCHAR(80),
         booked_at TIMESTAMP
       )""",
)

BANK_ROWS = {
    "accounts": [
        (1, "Priya Nair", "ACTIVE", "5000.00", "2020-01-15 09:00:00"),
        (2, "Tom Becker", "ACTIVE", "12000.00", "2021-03-02 14:30:00"),
        (3, "Lena Ortiz", "FROZEN", "3000.00", "2019-07-21 11:15:00"),
        (4, "Sam Okafor", "CLOSED", "0.00", "2018-11-05 16:45:00"),
    ],
    "transactions": [
        (1, 1, "1250.00", "EUR", "rent march", "2026-03-01 08:00:00"),
        (2, 1, "-89.90", "EUR", "groceries", "2026-03-02 18:20:00"),
        (3, 2, "15000.00", "USD", "invoice 4471", "2026-03-03 10:05:00"),
        (4, 2, "-420.00", "USD", "rent office", "2026-03-04 09:00:00"),
        (5, 3, "60.00", "EUR", "refund", "2026-03-05 12:00:00"),
    ],
}

#: ``schema name -> (ddl, rows)``: what ``seed`` puts in the source engine.
SAMPLES: dict[str, tuple[tuple[str, ...], dict[str, list[tuple]]]] = {
    "hr": (HR_DDL, HR_ROWS),
    "bank": (BANK_DDL, BANK_ROWS),
}

#: The workload, valid unchanged on PostgreSQL, MySQL, SQL Server and SQLite.
WORKLOAD: list[tuple[str, str, str]] = [
    ("hr", "headcount_by_department",
     "SELECT d.name, COUNT(e.id) AS headcount, COALESCE(SUM(e.salary), 0) AS payroll "
     "FROM departments d LEFT JOIN employees e ON e.department_id = d.id "
     "GROUP BY d.name ORDER BY d.name"),
    ("hr", "find_by_name",
     "SELECT id, email FROM employees WHERE full_name = 'priya nair' ORDER BY id"),
    ("hr", "bonus_amount",
     "SELECT id, salary * bonus_pct / 100 AS bonus FROM employees WHERE bonus_pct IS NOT NULL ORDER BY id"),
    ("hr", "half_bonus_pct",
     "SELECT id, bonus_pct / 2 AS half_pct FROM employees WHERE bonus_pct IS NOT NULL ORDER BY id"),
    ("hr", "senior_staff",
     "SELECT id, full_name FROM employees WHERE salary >= 90000 AND grade <> 'E3' ORDER BY id"),
    ("hr", "name_search",
     "SELECT id FROM employees WHERE full_name LIKE '%NAIR%' ORDER BY id"),
    ("hr", "grades_in_order",
     "SELECT id, grade FROM employees ORDER BY grade, id"),
    ("hr", "hired_since",
     "SELECT id FROM employees WHERE hired_on >= '2021-01-01' ORDER BY id"),
    ("bank", "balance_per_account",
     "SELECT a.id, COALESCE(SUM(t.amount), 0) AS balance FROM accounts a "
     "LEFT JOIN transactions t ON t.account_id = a.id GROUP BY a.id ORDER BY a.id"),
    ("bank", "large_euro_transactions",
     "SELECT id, amount FROM transactions WHERE amount > 10000 AND currency = 'eur' ORDER BY id"),
    ("bank", "third_of_limit",
     "SELECT id, credit_limit / 3 AS third FROM accounts ORDER BY id"),
    ("bank", "dormant_accounts",
     "SELECT id FROM accounts WHERE id NOT IN (SELECT account_id FROM transactions) ORDER BY id"),
    ("bank", "rent_payments",
     "SELECT id FROM transactions WHERE memo LIKE 'rent%' ORDER BY id"),
    ("bank", "accounts_by_status",
     "SELECT status, COUNT(*) AS n FROM accounts GROUP BY status ORDER BY status"),
    ("bank", "frozen_or_closed",
     "SELECT id, owner_name FROM accounts WHERE status IN ('frozen', 'closed') ORDER BY id"),
]


def statements(dialects: tuple[str, ...] = DIALECTS) -> list[Statement]:
    return [
        Statement(dialect, f"{schema}.{name}", sql, schema=schema)
        for dialect in dialects
        for schema, name, sql in WORKLOAD
    ]


def seed(engine: Any) -> None:
    """Create the sample schemas in the source engine's own database."""
    for name, (ddl, rows) in SAMPLES.items():
        engine.load(
            Variant(name=f"{name}:seed", targets="the application's own rows",
                    rows=rows, ddl=ddl, tables=tuple(rows))
        )


def discover(
    sources: dict[str, Any], agent: DatasetAgent, *, with_seed: bool = True
) -> dict[tuple[str, str], tuple[SourceSchema, Profile]]:
    """Read each sample schema back out of each source engine and register it.

    The schema handed to the agent is the one the engine's catalogue reports,
    not the DDL above. That is deliberate: the engines do not describe the same
    table the same way (SQLite has no DECIMAL, SQL Server calls a boolean a
    BIT), and discovery has to cope with what is actually there.
    """
    found: dict[tuple[str, str], tuple[SourceSchema, Profile]] = {}
    for dialect, engine in sources.items():
        if with_seed:
            seed(engine)
        for name, (_ddl, rows) in SAMPLES.items():
            schema = introspect(engine, name, tables=tuple(rows))
            prof = profile(engine, schema)
            agent.register(name, dialect, schema, prof)
            found[(name, dialect)] = (schema, prof)
    return found
