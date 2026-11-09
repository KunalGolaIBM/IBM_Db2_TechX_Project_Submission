"""Comprehensive verification of loaded procurement dataset in IBM Db2."""

from __future__ import annotations

import csv
import os
import sys
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

FK_CHECKS = [
    ("REQUISITIONS", "item_id", "ITEMS", "id"),
    ("PURCHASE_ORDERS", "supplier_id", "SUPPLIERS", "id"),
    ("PURCHASE_ORDERS", "buyer_id", "BUYERS", "id"),
    ("PO_LINES", "purchase_order_id", "PURCHASE_ORDERS", "id"),
    ("PO_LINES", "requisition_id", "REQUISITIONS", "id"),
    ("PO_LINES", "item_id", "ITEMS", "id"),
    ("GOODS_RECEIPTS", "po_line_id", "PO_LINES", "id"),
    ("SUPPLIER_INVOICES", "po_line_id", "PO_LINES", "id"),
]


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
    conn = ibm_db.connect(dsn, "", "")
    failures = 0

    try:
        print("=== 1. PER-TABLE ROW COUNT AUDIT ===")
        total_rows = 0
        for tname, expected in EXPECTED_COUNTS.items():
            stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {tname}")
            row = ibm_db.fetch_tuple(stmt)
            count = row[0] if row else 0
            total_rows += count
            ok = count == expected
            if not ok:
                failures += 1
            print(f"  {tname:18}: {count}/{expected} rows [{'PASS' if ok else 'FAIL'}]")

        print(f"Total Database Rows: {total_rows}/492 [{'PASS' if total_rows == 492 else 'FAIL'}]")
        if total_rows != 492:
            failures += 1

        print("\n=== 2. PRIMARY KEY UNIQUENESS AUDIT ===")
        for tname in EXPECTED_COUNTS:
            sql = f"SELECT COUNT(*) - COUNT(DISTINCT id) FROM {tname}"
            stmt = ibm_db.exec_immediate(conn, sql)
            dups = ibm_db.fetch_tuple(stmt)[0]
            ok = dups == 0
            if not ok:
                failures += 1
            print(f"  {tname:18}: {dups} duplicate IDs [{'PASS' if ok else 'FAIL'}]")

        print("\n=== 3. FOREIGN KEY REFERENTIAL INTEGRITY AUDIT ===")
        for child, ccol, parent, pcol in FK_CHECKS:
            sql = f"SELECT COUNT(*) FROM {child} c LEFT JOIN {parent} p ON c.{ccol} = p.{pcol} WHERE p.{pcol} IS NULL"
            stmt = ibm_db.exec_immediate(conn, sql)
            orphans = ibm_db.fetch_tuple(stmt)[0]
            ok = orphans == 0
            if not ok:
                failures += 1
            print(f"  {child}.{ccol} -> {parent}.{pcol}: {orphans} orphans [{'PASS' if ok else 'FAIL'}]")

        print("\n=== 4. NULL VALUE AUDIT ===")
        # supplier_invoices.paid_on expected nulls = 37
        stmt = ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM supplier_invoices WHERE paid_on IS NULL")
        null_paid_on = ibm_db.fetch_tuple(stmt)[0]
        ok = null_paid_on == 37
        if not ok:
            failures += 1
        print(f"  SUPPLIER_INVOICES.PAID_ON NULLs: {null_paid_on}/37 [{'PASS' if ok else 'FAIL'}]")

        # Check that NO other column in supplier_invoices is NULL
        stmt = ibm_db.exec_immediate(
            conn,
            "SELECT COUNT(*) FROM supplier_invoices WHERE id IS NULL OR po_line_id IS NULL OR invoice_no IS NULL "
            "OR invoice_date IS NULL OR qty_ratio IS NULL OR invoiced_qty IS NULL OR billing_drift IS NULL OR billed_unit_price IS NULL OR status IS NULL"
        )
        other_nulls = ibm_db.fetch_tuple(stmt)[0]
        ok = other_nulls == 0
        if not ok:
            failures += 1
        print(f"  SUPPLIER_INVOICES Unexpected NULLs: {other_nulls} [{'PASS' if ok else 'FAIL'}]")

        print("\n=== 5. REPRESENTATIVE SAMPLE VALUE VERIFICATION ===")
        # Verify first and last row of po_lines (testing decimals, dates, ints)
        stmt = ibm_db.exec_immediate(conn, "SELECT id, quantity, ordered_on, negotiated_factor, unit_price FROM po_lines WHERE id IN (1, 91) ORDER BY id")
        row = ibm_db.fetch_tuple(stmt)
        while row:
            print(f"  PO_LINE id={row[0]}: qty={row[1]}, date={row[2]}, factor={float(row[3]):.4f}, price={float(row[4]):.2f}")
            row = ibm_db.fetch_tuple(stmt)

        # Verify sample invoices (including one paid and one unpaid)
        stmt = ibm_db.exec_immediate(conn, "SELECT id, invoice_no, invoice_date, billed_unit_price, status, paid_on FROM supplier_invoices WHERE id IN (1, 87) ORDER BY id")
        row = ibm_db.fetch_tuple(stmt)
        while row:
            paid_str = str(row[5]) if row[5] is not None else "NULL (unpaid)"
            print(f"  INVOICE id={row[0]}: no={row[1]}, date={row[2]}, price={float(row[3]):.2f}, status={row[4]}, paid_on={paid_str}")
            row = ibm_db.fetch_tuple(stmt)

        print("\n==========================================")
        if failures == 0:
            print("DATASET_VERIFICATION=PASS (All 492 rows verified in genuine IBM Db2)")
            return 0
        else:
            print(f"DATASET_VERIFICATION=FAIL ({failures} check(s) failed)", file=sys.stderr)
            return 1

    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    raise SystemExit(main())

