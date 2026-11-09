"""
Db2-Sentinel Database Seeder & Health Initializer
Executes zero-config initialization against IBM Db2 Community Edition on port 50000.
Creates tables and seeds intentional ledger/invoice anomalies for Db2Hack 2026.
"""

import sys
import os
from typing import List

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import db2_settings

DDL_STATEMENTS: List[str] = [
    # 1. Accounts Ledger Master
    """
    CREATE TABLE ACCOUNTS_LEDGER (
        ACCOUNT_ID VARCHAR(20) NOT NULL PRIMARY KEY,
        ACCOUNT_NAME VARCHAR(100) NOT NULL,
        CATEGORY VARCHAR(50) NOT NULL,
        CURRENT_BALANCE DECIMAL(15,2) NOT NULL,
        LAST_UPDATED TIMESTAMP NOT NULL
    )
    """,
    # 2. Invoices Master Table
    """
    CREATE TABLE INVOICES (
        INVOICE_ID VARCHAR(30) NOT NULL PRIMARY KEY,
        CUSTOMER_ID VARCHAR(20) NOT NULL,
        INVOICE_DATE DATE NOT NULL,
        REPORTED_TOTAL DECIMAL(15,2) NOT NULL,
        STATUS VARCHAR(20) NOT NULL
    )
    """,
    # 3. Invoice Line Items Table
    """
    CREATE TABLE INVOICE_ITEMS (
        ITEM_ID VARCHAR(30) NOT NULL PRIMARY KEY,
        INVOICE_ID VARCHAR(30) NOT NULL,
        DESCRIPTION VARCHAR(150),
        QUANTITY INT NOT NULL,
        UNIT_PRICE DECIMAL(10,2) NOT NULL,
        LINE_TOTAL DECIMAL(15,2) NOT NULL,
        CONSTRAINT FK_INV_ITEMS FOREIGN KEY (INVOICE_ID) REFERENCES INVOICES(INVOICE_ID)
    )
    """,
    # 4. Immutable Agent Audit Trail Table
    """
    CREATE TABLE AUDIT_RECONCILIATION_LOG (
        AUDIT_ID VARCHAR(64) NOT NULL PRIMARY KEY,
        TIMESTAMP TIMESTAMP NOT NULL,
        TRIGGER_EVENT VARCHAR(100) NOT NULL,
        ANOMALY_DETECTED VARCHAR(500),
        PROPOSED_PATCH CLOB,
        STATUS VARCHAR(30) NOT NULL,
        EXECUTED_BY VARCHAR(50) NOT NULL
    )
    """
]

SEED_DATA_STATEMENTS: List[str] = [
    # Seed Accounts Ledger
    "INSERT INTO ACCOUNTS_LEDGER VALUES ('ACC-101', 'Accounts Receivable', 'ASSET', 45000.00, CURRENT TIMESTAMP)",
    "INSERT INTO ACCOUNTS_LEDGER VALUES ('ACC-102', 'Revenue', 'EQUITY', 120000.00, CURRENT TIMESTAMP)",
    
    # Seed Invoices & Lines with Intentional Anomaly:
    # INV-2026-001 has REPORTED_TOTAL = 1500.00, but sum of line items is 1200.00
    "INSERT INTO INVOICES VALUES ('INV-2026-001', 'CUST-88', '2026-11-01', 1500.00, 'UNRECONCILED')",
    "INSERT INTO INVOICE_ITEMS VALUES ('ITM-01', 'INV-2026-001', 'Enterprise Cloud Tier', 1, 1000.00, 1000.00)",
    "INSERT INTO INVOICE_ITEMS VALUES ('ITM-02', 'INV-2026-001', 'Storage Addon', 2, 100.00, 200.00)",
    
    # INV-2026-002 is balanced
    "INSERT INTO INVOICES VALUES ('INV-2026-002', 'CUST-92', '2026-11-02', 800.00, 'PAID')",
    "INSERT INTO INVOICE_ITEMS VALUES ('ITM-03', 'INV-2026-002', 'Consulting Services', 8, 100.00, 800.00)"
]


def seed_database():
    print(f"Connecting to IBM Db2 Community Edition ({db2_settings.host}:{db2_settings.port}/{db2_settings.database})...")
    
    try:
        import ibm_db_dbi as dbi
    except ImportError:
        print("[!] ibm_db is not installed on this host environment.")
        print("    Run: pip install -r requirements.txt")
        return False

    try:
        conn = dbi.connect(db2_settings.connection_string, "", "")
        cursor = conn.cursor()
        print("[+] Successfully connected to IBM Db2.")
        
        # Check existing tables in SYSCAT.TABLES using uppercase identifiers
        cursor.execute(
            f"SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = '{db2_settings.schema.upper()}'"
        )
        existing_tables = [row[0].strip() for row in cursor.fetchall()]
        print(f"[*] Existing tables in schema {db2_settings.schema}: {existing_tables}")

        # Create missing tables
        target_tables = ["ACCOUNTS_LEDGER", "INVOICES", "INVOICE_ITEMS", "AUDIT_RECONCILIATION_LOG"]
        for stmt in DDL_STATEMENTS:
            for t in target_tables:
                if f"CREATE TABLE {t}" in stmt:
                    if t not in existing_tables:
                        print(f"[*] Creating table: {t}...")
                        cursor.execute(stmt)
                        conn.commit()
                        print(f"[+] Created table: {t}")
                    else:
                        print(f"[-] Table {t} already exists. Skipping DDL.")

        # Seed initial data if INVOICES is empty
        cursor.execute("SELECT COUNT(*) FROM INVOICES")
        count = cursor.fetchone()[0]
        if count == 0:
            print("[*] Seeding intentional audit anomaly dataset into Db2...")
            for seed_stmt in SEED_DATA_STATEMENTS:
                cursor.execute(seed_stmt)
            conn.commit()
            print("[+] Seed records populated successfully!")
        else:
            print(f"[-] Database already contains {count} invoice records. Skipping seed.")

        conn.close()
        print("\n=== Db2-Sentinel Database Ready for Db2Hack 2026 ===")
        return True
    except Exception as exc:
        print(f"[!] Db2 initialization failed: {str(exc)}")
        return False


if __name__ == "__main__":
    seed_database()

