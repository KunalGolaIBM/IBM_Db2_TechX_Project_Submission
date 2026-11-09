"""Import 492 procurement records into genuine IBM Db2 database."""

from __future__ import annotations

import csv
import os
import sys
from decimal import Decimal
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.apply_schema import load_env
import ibm_db

EXPECTED_COUNTS = {
    "BUYERS": 5,
    "SUPPLIERS": 14,
    "ITEMS": 20,
    "REQUISITIONS": 150,
    "PURCHASE_ORDERS": 36,
    "PO_LINES": 91,
    "GOODS_RECEIPTS": 89,
    "SUPPLIER_INVOICES": 87,
}

IMPORT_ORDER = [
    ("buyers.csv", "BUYERS", ["id", "first_name", "last_name", "email", "team"], [int, str, str, str, str]),
    ("suppliers.csv", "SUPPLIERS", ["id", "supplier_name", "country", "payment_terms"], [int, str, str, str]),
    ("items.csv", "ITEMS", ["id", "sku", "catalogue", "item_label", "unit", "list_price"], [int, str, str, str, str, str]),
    ("requisitions.csv", "REQUISITIONS", ["id", "requester_dept", "item_id", "quantity_requested", "list_price", "requested_on"], [int, str, int, int, str, str]),
    ("purchase_orders.csv", "PURCHASE_ORDERS", ["id", "po_number", "supplier_id", "buyer_id", "ordered_on", "payment_terms"], [int, str, int, int, str, str]),
    ("po_lines.csv", "PO_LINES", ["id", "purchase_order_id", "requisition_id", "item_id", "quantity", "ordered_on", "negotiated_factor", "unit_price"], [int, int, int, int, int, str, str, str]),
    ("goods_receipts.csv", "GOODS_RECEIPTS", ["id", "po_line_id", "received_on", "received_share", "received_qty", "condition"], [int, int, str, str, int, str]),
    ("supplier_invoices.csv", "SUPPLIER_INVOICES", ["id", "po_line_id", "invoice_no", "invoice_date", "qty_ratio", "invoiced_qty", "billing_drift", "billed_unit_price", "status", "paid_on"], [int, int, str, str, str, int, str, str, str, lambda v: v if v else None]),
]


def convert_val(val: str, type_fn):
    val = val.strip()
    if type_fn is str:
        return val
    if callable(type_fn):
        return type_fn(val)
    if type_fn is int:
        return int(val)
    return val


def main() -> int:
    load_env()
    dsn = (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
    )

    csv_dir = Path(__file__).resolve().parent.parent / "data" / "source_csv"
    if not csv_dir.is_dir():
        print(f"Dataset directory not found: {csv_dir}", file=sys.stderr)
        return 2

    conn = ibm_db.connect(dsn, "", "")
    ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    print("Connected to IBM Db2 with autocommit OFF.")

    try:
        # Step 1: Idempotency - Clean tables in reverse dependency order
        print("\n=== Idempotent Clean (Reverse Dependency) ===")
        reverse_tables = [t[1] for t in reversed(IMPORT_ORDER)]
        for tname in reverse_tables:
            stmt = ibm_db.exec_immediate(conn, f"DELETE FROM {tname}")
            print(f"  Cleared {tname}")

        # Step 2: Insert records in forward dependency order
        print("\n=== Relational Data Import ===")
        for fname, tname, cols, types in IMPORT_ORDER:
            fpath = csv_dir / fname
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            sql = f"INSERT INTO {tname} ({col_names}) VALUES ({placeholders})"
            prep_stmt = ibm_db.prepare(conn, sql)

            inserted = 0
            for r in rows:
                params = tuple(convert_val(r[c], types[i]) for i, c in enumerate(cols))
                res = ibm_db.execute(prep_stmt, params)
                if not res:
                    err = ibm_db.stmt_errormsg(prep_stmt)
                    raise RuntimeError(f"Insert failed on {tname} row {r}: {err}")
                inserted += 1

            print(f"  {tname}: Inserted {inserted}/{len(rows)} records from {fname}")

        # Commit transaction
        ibm_db.commit(conn)
        print("\nTransaction committed successfully.")

        # Step 3: SQL Count Verification from Db2
        print("\n=== Db2 SQL Row Count Verification ===")
        total_rows = 0
        all_passed = True
        for tname, expected in EXPECTED_COUNTS.items():
            count_stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {tname}")
            count_res = ibm_db.fetch_tuple(count_stmt)
            actual = count_res[0] if count_res else 0
            total_rows += actual
            status = "PASS" if actual == expected else "FAIL"
            if actual != expected:
                all_passed = False
            print(f"  {tname}: {actual}/{expected} rows [{status}]")

        print(f"\nTotal Db2 Rows: {total_rows}/492 [{'PASS' if total_rows == 492 else 'FAIL'}]")

        # Step 4: Sample Verification Query (3-way join sanity check)
        print("\n=== Relational Verification Query (Sample 3-way join) ===")
        sample_sql = """
            SELECT p.po_number, l.id AS po_line_id, l.quantity, 
                   COUNT(DISTINCT r.id) AS receipt_count, 
                   COUNT(DISTINCT i.id) AS invoice_count
            FROM purchase_orders p
            JOIN po_lines l ON l.purchase_order_id = p.id
            LEFT JOIN goods_receipts r ON r.po_line_id = l.id
            LEFT JOIN supplier_invoices i ON i.po_line_id = l.id
            WHERE p.id = 1
            GROUP BY p.po_number, l.id, l.quantity
            ORDER BY l.id
        """
        sample_stmt = ibm_db.exec_immediate(conn, sample_sql)
        row = ibm_db.fetch_tuple(sample_stmt)
        while row:
            print(f"  PO: {row[0]} | Line: {row[1]} | Qty: {row[2]} | Receipts: {row[3]} | Invoices: {row[4]}")
            row = ibm_db.fetch_tuple(sample_stmt)

        if all_passed and total_rows == 492:
            print("\nDATASET_IMPORT=PASS (Gate G1 VERIFIED)")
            return 0
        else:
            print("\nDATASET_IMPORT=FAIL", file=sys.stderr)
            return 1

    except Exception as e:
        ibm_db.rollback(conn)
        print(f"Import error (rolled back): {e}", file=sys.stderr)
        return 1
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    raise SystemExit(main())

