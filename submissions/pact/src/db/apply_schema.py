"""Execute and verify Db2 DDL schema for PACT procurement tables."""

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

    schema_file = Path(__file__).resolve().parent / "001_initial_schema.sql"
    if not schema_file.is_file():
        print(f"Schema file not found: {schema_file}", file=sys.stderr)
        return 2

    sql_content = schema_file.read_text(encoding="utf-8")
    # Split statements by semicolon
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    conn = None
    try:
        conn = ibm_db.connect(dsn, "", "")
        print("Connected to IBM Db2.")

        # Execute DDL statements
        for idx, stmt in enumerate(statements, 1):
            first_line = stmt.split("\n")[0][:60]
            print(f"Executing [{idx}/{len(statements)}]: {first_line}...")
            try:
                ibm_db.exec_immediate(conn, stmt)
            except Exception as e:
                err_msg = ibm_db.stmt_errormsg() or str(e)
                sqlstate = ibm_db.stmt_error()
                print(f"DDL FAILED on statement {idx}: {err_msg} (SQLSTATE: {sqlstate})", file=sys.stderr)
                return 1

        print("\nAll DDL statements executed successfully.")

        # Catalog Verification
        expected_tables = [
            "BUYERS", "SUPPLIERS", "ITEMS", "REQUISITIONS",
            "PURCHASE_ORDERS", "PO_LINES", "GOODS_RECEIPTS", "SUPPLIER_INVOICES"
        ]

        # 1. Verify tables in SYSCAT.TABLES
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

        missing_tables = [t for t in expected_tables if t not in found_tables]
        if missing_tables:
            print(f"Missing expected tables in catalog: {missing_tables}", file=sys.stderr)
            return 1

        # 2. Verify Primary and Foreign Key Constraints in SYSCAT.TABCONST
        print("\n=== SYSCAT.TABCONST (CONSTRAINTS) VERIFICATION ===")
        const_stmt = ibm_db.exec_immediate(
            conn,
            "SELECT TABNAME, CONSTNAME, TYPE FROM SYSCAT.TABCONST "
            "WHERE TABSCHEMA = CURRENT USER ORDER BY TABNAME, TYPE, CONSTNAME"
        )
        constraints = {}
        row = ibm_db.fetch_tuple(const_stmt)
        while row:
            tname, cname, ctype = row[0].strip(), row[1].strip(), row[2].strip()
            constraints.setdefault(tname, []).append((cname, ctype))
            type_desc = {"P": "PRIMARY KEY", "F": "FOREIGN KEY", "U": "UNIQUE"}.get(ctype, ctype)
            print(f"  {tname} -> {cname} [{type_desc}]")
            row = ibm_db.fetch_tuple(const_stmt)

        # 3. Verify Indexes in SYSCAT.INDEXES
        print("\n=== SYSCAT.INDEXES VERIFICATION ===")
        idx_stmt = ibm_db.exec_immediate(
            conn,
            "SELECT TABNAME, INDNAME, UNIQUERULE, COLNAMES FROM SYSCAT.INDEXES "
            "WHERE INDSCHEMA = CURRENT USER ORDER BY TABNAME, INDNAME"
        )
        row = ibm_db.fetch_tuple(idx_stmt)
        while row:
            tname, iname, urule, cols = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
            unique_desc = "UNIQUE" if urule in ("U", "P") else "NON-UNIQUE"
            print(f"  {tname} -> Index: {iname} ({unique_desc}) on columns: {cols}")
            row = ibm_db.fetch_tuple(idx_stmt)

        print("\nSCHEMA_VERIFICATION=PASS")
        return 0

    except Exception as e:
        print(f"Verification error: {e}", file=sys.stderr)
        return 1
    finally:
        if conn:
            try:
                ibm_db.close(conn)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

