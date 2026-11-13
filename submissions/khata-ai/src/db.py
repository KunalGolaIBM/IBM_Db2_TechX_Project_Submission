"""Db2 helper functions for Khata AI.

All money maths (balances, ageing of udhaar) is done by SQL in Db2,
never by the AI model, so the numbers are always exact.
"""
import os
from datetime import date, timedelta

import ibm_db_dbi
from dotenv import load_dotenv

load_dotenv()

SCHEMA = [
    (
        "CUSTOMERS",
        """CREATE TABLE customers (
            id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
            name VARCHAR(60) NOT NULL,
            PRIMARY KEY (id)
        )""",
    ),
    (
        "ENTRIES",
        """CREATE TABLE entries (
            id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
            customer_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            entry_type VARCHAR(10) NOT NULL,
            note VARCHAR(200),
            entry_date DATE NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )""",
    ),
]


def get_connection():
    """Open a connection to Db2 using the values in the .env file."""
    missing = [k for k in ("DB2_DATABASE", "DB2_USER", "DB2_PASSWORD") if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Missing values in .env file: " + ", ".join(missing)
            + ". Copy .env.example to .env and fill it in."
        )
    dsn = (
        f"DATABASE={os.getenv('DB2_DATABASE')};"
        f"HOSTNAME={os.getenv('DB2_HOST', 'localhost')};"
        f"PORT={os.getenv('DB2_PORT', '50000')};"
        "PROTOCOL=TCPIP;"
        f"UID={os.getenv('DB2_USER')};"
        f"PWD={os.getenv('DB2_PASSWORD')};"
    )
    return ibm_db_dbi.connect(dsn, "", "")


def setup_schema():
    """Create the tables if they do not exist yet. Safe to call many times."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        for table_name, create_sql in SCHEMA:
            cur.execute(
                "SELECT COUNT(*) FROM SYSCAT.TABLES "
                "WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = ?",
                (table_name,),
            )
            if cur.fetchone()[0] == 0:
                cur.execute(create_sql)
        conn.commit()
    finally:
        conn.close()


def add_entry(name, amount, entry_type, note=None, entry_date=None):
    """Save one ledger entry. entry_type is 'UDHAAR' or 'PAYMENT'."""
    name = " ".join(name.split())
    entry_type = entry_type.upper()
    if entry_type not in ("UDHAAR", "PAYMENT"):
        raise ValueError("entry_type must be UDHAAR or PAYMENT")
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    entry_date = entry_date or date.today()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM customers WHERE UPPER(name) = ?", (name.upper(),))
        row = cur.fetchone()
        if row:
            customer_id = row[0]
        else:
            cur.execute("INSERT INTO customers (name) VALUES (?)", (name,))
            cur.execute("SELECT id FROM customers WHERE UPPER(name) = ?", (name.upper(),))
            customer_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO entries (customer_id, amount, entry_type, note, entry_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (customer_id, float(amount), entry_type, note, entry_date),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending():
    """Customers who still owe money: [(name, balance, days_old), ...], oldest first."""
    sql = """
        SELECT c.name,
               SUM(CASE WHEN e.entry_type = 'UDHAAR' THEN e.amount ELSE -e.amount END) AS balance,
               DAYS(CURRENT DATE) - DAYS(MIN(e.entry_date)) AS days_old
        FROM customers c
        JOIN entries e ON e.customer_id = c.id
        GROUP BY c.name
        HAVING SUM(CASE WHEN e.entry_type = 'UDHAAR' THEN e.amount ELSE -e.amount END) > 0
        ORDER BY days_old DESC, balance DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return [(r[0], float(r[1]), int(r[2])) for r in cur.fetchall()]
    finally:
        conn.close()


def get_history(name_part):
    """All entries of customers whose name contains name_part."""
    sql = """
        SELECT c.name, e.entry_date, e.entry_type, e.amount, e.note
        FROM entries e
        JOIN customers c ON c.id = e.customer_id
        WHERE UPPER(c.name) LIKE ?
        ORDER BY e.entry_date, e.id
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, ("%" + name_part.strip().upper() + "%",))
        return [(r[0], r[1], r[2], float(r[3]), r[4]) for r in cur.fetchall()]
    finally:
        conn.close()


def get_total_outstanding():
    return sum(balance for _, balance, _ in get_pending())


# (name, amount, type, note, days_ago)
DEMO_DATA = [
    ("Sharma ji", 200, "UDHAAR", "doodh aur bread", 45),
    ("Sharma ji", 100, "PAYMENT", "wapas diye", 30),
    ("Gupta aunty", 450, "UDHAAR", "mahine ka raashan", 20),
    ("Rahul bhaiya", 80, "UDHAAR", "cigarette aur chai", 7),
    ("Mehta ji", 1200, "UDHAAR", "shaadi ka saaman", 60),
    ("Mehta ji", 1200, "PAYMENT", "poora chuka diya", 10),
    ("Pooja didi", 150, "UDHAAR", "sabzi", 3),
]


def load_demo_data():
    """Insert sample entries so you can test the app quickly."""
    for name, amount, etype, note, days_ago in DEMO_DATA:
        add_entry(name, amount, etype, note, date.today() - timedelta(days=days_ago))
    return len(DEMO_DATA)


def reset_data():
    """Delete ALL entries and customers (use before the final demo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM entries")
        cur.execute("DELETE FROM customers")
        conn.commit()
    finally:
        conn.close()
