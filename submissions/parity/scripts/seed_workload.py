"""Seed the sample shop workload.

Creates four tables in Postgres, fills them with fixed
data, then syncs schema and data to Db2. The same rows
land in both databases, so any result difference comes
from the databases and not from the data.

Runs inside a Linux container where ibm_db works.
"""

from __future__ import annotations

import os

SCHEMA_SQL = """
CREATE TABLE customers (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(150),
    country VARCHAR(2),
    signup_date DATE,
    credit_limit DECIMAL(10, 2),
    active BOOLEAN
);
CREATE TABLE products (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10, 2),
    stock INTEGER,
    discontinued BOOLEAN
);
CREATE TABLE orders (
    id INTEGER NOT NULL PRIMARY KEY,
    customer_id INTEGER,
    order_date DATE,
    status VARCHAR(20),
    total DECIMAL(12, 2),
    shipped BOOLEAN
);
CREATE TABLE order_items (
    id INTEGER NOT NULL PRIMARY KEY,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    unit_price DECIMAL(10, 2),
    discount DECIMAL(5, 2)
);
"""

CUSTOMERS = [
    (1, "alice", "alice@example.com", "US", "2023-01-15", 1000.00, True),
    (2, "bob", "bob@example.com", "GB", "2023-02-20", 500.50, True),
    (3, "Carol", "carol@example.com", "DE", "2023-03-25", 2500.00, False),
    (4, None, None, None, None, None, None),
    (5, "dave", "dave@example.com", "US", "2023-05-01", 75.25, True),
    (6, "erin", "erin@example.com", "JP", "2023-06-11", 300.00, True),
    (7, "frank", "frank@example.com", "FR", "2023-07-30", 0.00, False),
    (8, "grace", "grace@example.com", "US", "2023-09-09", 9999.99, True),
    (9, "heidi", "heidi@example.com", "CA", "2023-10-19", 450.75, True),
    (10, "ivan", "ivan@example.com", "IN", "2023-12-24", 1250.00, True),
]

PRODUCTS = [
    (1, "Widget", "tools", 19.99, 100, False),
    (2, "Gadget", "tools", 29.50, 50, False),
    (3, "Doohickey", "parts", 5.25, 500, False),
    (4, "Thingamajig", "parts", 149.00, 10, True),
    (5, "Gizmo", "tools", 89.95, 0, False),
    (6, "Sprocket", "parts", 3.75, 1000, False),
    (7, "Caf\u00e9 Blend", "coffee", 12.50, 75, False),
    (8, "Green Tea", "tea", 8.25, 120, False),
    (9, "Espresso Beans", "coffee", 15.00, 40, False),
    (10, "Herbal Tea", "tea", 9.00, 0, True),
]

ORDERS = [
    (1, 1, "2023-01-20", "shipped", 49.49, True),
    (2, 1, "2023-02-14", "shipped", 19.99, True),
    (3, 2, "2023-03-01", "pending", 29.50, False),
    (4, 3, "2023-04-11", "cancelled", 149.00, False),
    (5, 3, "2023-06-02", "shipped", 5.25, True),
    (6, 5, "2023-07-19", "pending", 12.50, False),
    (7, 5, "2023-08-08", "shipped", 89.95, True),
    (8, 6, "2023-09-23", "shipped", 20.75, True),
    (9, 8, "2023-10-30", "pending", 15.00, False),
    (10, 9, "2023-11-15", "shipped", 8.25, True),
    (11, 10, "2023-12-05", "pending", 19.99, False),
    (12, 10, "2024-01-08", "shipped", 3.75, True),
    (13, 2, "2024-02-22", "shipped", 74.25, True),
    (14, 8, "2024-03-14", "cancelled", 22.00, False),
    (15, 1, "2024-04-01", "shipped", 44.50, True),
]

ORDER_ITEMS = [
    (1, 1, 1, 2, 19.99, 0.00),
    (2, 1, 3, 1, 5.25, 0.00),
    (3, 2, 1, 1, 19.99, 0.00),
    (4, 3, 2, 1, 29.50, 0.00),
    (5, 4, 4, 1, 149.00, 0.00),
    (6, 5, 3, 1, 5.25, 0.00),
    (7, 6, 7, 1, 12.50, 0.00),
    (8, 7, 5, 1, 89.95, 0.00),
    (9, 8, 3, 1, 5.25, 0.00),
    (10, 8, 1, 1, 15.50, 0.00),
    (11, 9, 9, 1, 15.00, 0.00),
    (12, 10, 8, 1, 8.25, 0.00),
    (13, 11, 1, 1, 19.99, 0.00),
    (14, 12, 6, 1, 3.75, 0.00),
    (15, 13, 2, 1, 29.50, 0.00),
    (16, 13, 7, 2, 12.50, 0.50),
    (17, 14, 1, 1, 19.99, 0.00),
    (18, 15, 3, 2, 5.25, 0.00),
    (19, 15, 7, 1, 12.50, 0.00),
    (20, 15, 8, 2, 8.25, 1.00),
]


def main() -> int:
    """Create and fill the schema in Postgres, then sync to Db2."""
    import psycopg

    from parity.config import load_settings
    from parity.sync.data import checksum_rows, copy_table, read_postgres_rows
    from parity.sync.db2_admin import Db2Admin
    from parity.sync.schema import build_create_table, introspect_postgres

    source, db2_settings = load_settings()
    conn = psycopg.connect(
        host=os.environ.get("PARITY_SOURCE_HOST", "localhost"),
        dbname=source.database,
        user=source.user,
        password=source.password,
        autocommit=True,
    )
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS order_items")
    cur.execute("DROP TABLE IF EXISTS orders")
    cur.execute("DROP TABLE IF EXISTS products")
    cur.execute("DROP TABLE IF EXISTS customers")
    cur.execute(SCHEMA_SQL)
    for row in CUSTOMERS:
        cur.execute(
            "INSERT INTO customers VALUES (%s, %s, %s, %s, %s, %s, %s)", row
        )
    for row in PRODUCTS:
        cur.execute(
            "INSERT INTO products VALUES (%s, %s, %s, %s, %s, %s)", row
        )
    for row in ORDERS:
        cur.execute(
            "INSERT INTO orders VALUES (%s, %s, %s, %s, %s, %s)", row
        )
    for row in ORDER_ITEMS:
        cur.execute(
            "INSERT INTO order_items VALUES (%s, %s, %s, %s, %s, %s)", row
        )
    conn.close()
    print("seeded postgres")

    tables = introspect_postgres(source)
    admin = Db2Admin(db2_settings)
    for table in tables:
        print("ddl:", build_create_table(table))
        admin.drop_tables((table,))
        admin.create_tables((table,))
    for table in tables:
        count, source_sum, _ = copy_table(source, admin, table)
        rows = read_postgres_rows(source, table)
        assert checksum_rows(rows) == source_sum
        print(f"copied {count} rows for {table.name}, checksum {source_sum[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
