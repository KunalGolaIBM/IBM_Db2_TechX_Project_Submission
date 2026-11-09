"""Apply and verify Db2 schema migration 002 for PACT case management tables."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def load_env() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        with env_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v


def main() -> int:
    load_env()
    required = ("DB2_DATABASE", "DB2_HOST", "DB2_PORT", "DB2_USER", "DB2_PASSWORD")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

    import ibm_db

    dsn = (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
    )

    schema_file = Path(__file__).resolve().parent / "002_case_schema.sql"
    if not schema_file.is_file():
        print(f"Schema file not found: {schema_file}", file=sys.stderr)
        return 2

    sql_content = schema_file.read_text(encoding="utf-8")
    raw_statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    # Filter out pure comment blocks
    statements = []
    for s in raw_statements:
        lines = [line for line in s.splitlines() if not line.strip().startswith("--")]
        cleaned = "\n".join(lines).strip()
        if cleaned:
            statements.append(cleaned)

    conn = None
    try:
        conn = ibm_db.connect(dsn, "", "")
        print("Connected to IBM Db2 PACTDB.")

        # Check existing source tables and row counts before migration
        source_tables = [
            "BUYERS", "SUPPLIERS", "ITEMS", "REQUISITIONS",
            "PURCHASE_ORDERS", "PO_LINES", "GOODS_RECEIPTS", "SUPPLIER_INVOICES"
        ]
        print("\n=== PRE-MIGRATION SOURCE TABLE CHECK ===")
        pre_counts = {}
        for tbl in source_tables:
            stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {tbl}")
            count = ibm_db.fetch_tuple(stmt)[0]
            pre_counts[tbl] = count
            print(f"  {tbl}: {count} rows")

        total_source_rows = sum(pre_counts.values())
        if total_source_rows != 492:
            print(f"ERROR: Expected 492 source rows before migration, found {total_source_rows}", file=sys.stderr)
            return 1

        # Execute Migration Statements
        print(f"\n=== EXECUTING MIGRATION 002 ({len(statements)} STATEMENTS) ===")
        for idx, stmt in enumerate(statements, 1):
            first_line = stmt.split("\n")[0][:70]
            print(f"Executing [{idx}/{len(statements)}]: {first_line}...")
            try:
                ibm_db.exec_immediate(conn, stmt)
            except Exception as e:
                err_msg = ibm_db.stmt_errormsg() or str(e)
                sqlstate = ibm_db.stmt_error()
                print(f"DDL FAILED on statement {idx}: {err_msg} (SQLSTATE: {sqlstate})", file=sys.stderr)
                return 1

        print("\nAll Migration 002 statements executed successfully.")

        # Catalog Verification
        expected_app_tables = [
            "INVESTIGATION_CASES", "CASE_FINDINGS", "SCENARIO_RUNS",
            "REVIEW_DECISIONS", "AUDIT_EVENTS"
        ]

        print("\n=== SYSCAT.TABLES VERIFICATION ===")
        table_stmt = ibm_db.exec_immediate(
            conn,
            "SELECT TABSCHEMA, TABNAME, TYPE, COLCOUNT FROM SYSCAT.TABLES "
            "WHERE TABSCHEMA = CURRENT USER AND TYPE = 'T' ORDER BY TABNAME"
        )
        found_tables = {}
        row = ibm_db.fetch_tuple(table_stmt)
        while row:
            schema, name, t_type, colcount = row[0].strip(), row[1].strip(), row[2].strip(), row[3]
            found_tables[name] = colcount
            print(f"  Table: {schema}.{name} | Type: {t_type} | Columns: {colcount}")
            row = ibm_db.fetch_tuple(table_stmt)

        all_expected = source_tables + expected_app_tables
        missing = [t for t in all_expected if t not in found_tables]
        if missing:
            print(f"ERROR: Missing tables in catalog: {missing}", file=sys.stderr)
            return 1

        # Verify Constraints
        print("\n=== SYSCAT.TABCONST CONSTRAINTS VERIFICATION ===")
        const_stmt = ibm_db.exec_immediate(
            conn,
            "SELECT TABNAME, CONSTNAME, TYPE FROM SYSCAT.TABCONST "
            "WHERE TABSCHEMA = CURRENT USER ORDER BY TABNAME, CONSTNAME"
        )
        constraints_found = []
        row = ibm_db.fetch_tuple(const_stmt)
        while row:
            tname, cname, ctype = row[0].strip(), row[1].strip(), row[2].strip()
            constraints_found.append((tname, cname, ctype))
            if tname in expected_app_tables:
                print(f"  Constraint on {tname}: {cname} (Type: {ctype})")
            row = ibm_db.fetch_tuple(const_stmt)

        # Check Post-Migration Source Table Counts to ensure zero impact
        print("\n=== POST-MIGRATION SOURCE TABLE INTEGRITY CHECK ===")
        post_counts = {}
        for tbl in source_tables:
            stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {tbl}")
            count = ibm_db.fetch_tuple(stmt)[0]
            post_counts[tbl] = count
            if count != pre_counts[tbl]:
                print(f"ERROR: Row count altered on {tbl}: was {pre_counts[tbl]}, now {count}", file=sys.stderr)
                return 1
            print(f"  {tbl}: {count} rows (Verified unchanged)")

        print("\n=== MIGRATION 002 COMPLETE AND FULLY VERIFIED ===")
        return 0

    except Exception as e:
        err = ibm_db.conn_errormsg() if conn else str(e)
        print(f"Database error: {err}", file=sys.stderr)
        return 1
    finally:
        if conn:
            ibm_db.close(conn)


if __name__ == "__main__":
    sys.exit(main())

