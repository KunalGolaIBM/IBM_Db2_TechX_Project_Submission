"""Load the 8 original procurement CSV files into genuine IBM Db2 with full transaction safety."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.apply_schema import load_env
import ibm_db

TABLE_SPECS = [
    (
        "buyers.csv",
        "BUYERS",
        ["id", "first_name", "last_name", "email", "team"],
        [int, str, str, str, str],
    ),
    (
        "suppliers.csv",
        "SUPPLIERS",
        ["id", "supplier_name", "country", "payment_terms"],
        [int, str, str, str],
    ),
    (
        "items.csv",
        "ITEMS",
        ["id", "sku", "catalogue", "item_label", "unit", "list_price"],
        [int, str, str, str, str, str],
    ),
    (
        "requisitions.csv",
        "REQUISITIONS",
        ["id", "requester_dept", "item_id", "quantity_requested", "list_price", "requested_on"],
        [int, str, int, int, str, str],
    ),
    (
        "purchase_orders.csv",
        "PURCHASE_ORDERS",
        ["id", "po_number", "supplier_id", "buyer_id", "ordered_on", "payment_terms"],
        [int, str, int, int, str, str],
    ),
    (
        "po_lines.csv",
        "PO_LINES",
        ["id", "purchase_order_id", "requisition_id", "item_id", "quantity", "ordered_on", "negotiated_factor", "unit_price"],
        [int, int, int, int, int, str, str, str],
    ),
    (
        "goods_receipts.csv",
        "GOODS_RECEIPTS",
        ["id", "po_line_id", "received_on", "received_share", "received_qty", "condition"],
        [int, int, str, str, int, str],
    ),
    (
        "supplier_invoices.csv",
        "SUPPLIER_INVOICES",
        ["id", "po_line_id", "invoice_no", "invoice_date", "qty_ratio", "invoiced_qty", "billing_drift", "billed_unit_price", "status", "paid_on"],
        [int, int, str, str, str, int, str, str, str, lambda v: v if v else None],
    ),
]


def convert_field(val: str, conv):
    val = val.strip()
    if callable(conv):
        return conv(val)
    if conv is int:
        return int(val)
    return val


def main() -> int:
    load_env()
    required = ("DB2_DATABASE", "DB2_HOST", "DB2_PORT", "DB2_USER", "DB2_PASSWORD")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

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

    conn = None
    try:
        conn = ibm_db.connect(dsn, "", "")
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        print("Connected to IBM Db2 (autocommit=OFF).")

        # Step 1: Idempotency safety - clear existing records in reverse dependency order
        print("\n--- Phase 1: Preparing clean target tables (Reverse Dependency) ---")
        for _, tname, _, _ in reversed(TABLE_SPECS):
            del_stmt = f"DELETE FROM {tname}"
            ibm_db.exec_immediate(conn, del_stmt)
            print(f"  Target table cleared: {tname}")

        # Step 2: Parameterized insert in forward dependency order
        print("\n--- Phase 2: Loading dataset records ---")
        total_loaded = 0
        for fname, tname, cols, converters in TABLE_SPECS:
            fpath = csv_dir / fname
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            placeholders = ", ".join(["?"] * len(cols))
            col_list = ", ".join(cols)
            sql = f"INSERT INTO {tname} ({col_list}) VALUES ({placeholders})"
            prep_stmt = ibm_db.prepare(conn, sql)

            loaded_count = 0
            for r in rows:
                params = tuple(convert_field(r[c], converters[i]) for i, c in enumerate(cols))
                res = ibm_db.execute(prep_stmt, params)
                if not res:
                    err = ibm_db.stmt_errormsg(prep_stmt)
                    raise RuntimeError(f"Failed to insert into {tname} with data {r}: {err}")
                loaded_count += 1

            total_loaded += loaded_count
            print(f"  {tname}: Successfully loaded {loaded_count}/{len(rows)} records from {fname}")

        # Commit transaction
        ibm_db.commit(conn)
        print(f"\nTransaction committed. Total rows loaded: {total_loaded}")
        return 0

    except Exception as e:
        if conn:
            ibm_db.rollback(conn)
            print("Transaction rolled back due to error.", file=sys.stderr)
        print(f"Dataset load failure: {e}", file=sys.stderr)
        return 1
    finally:
        if conn:
            try:
                ibm_db.close(conn)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

