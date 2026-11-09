"""Inspect SYSCAT.COLUMNS for all 8 PACT tables in Db2."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.apply_schema import load_env
import ibm_db


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

    conn = ibm_db.connect(dsn, "", "")
    stmt = ibm_db.exec_immediate(
        conn,
        "SELECT TABNAME, COLNAME, TYPENAME, LENGTH, SCALE, NULLS "
        "FROM SYSCAT.COLUMNS "
        "WHERE TABSCHEMA = CURRENT USER "
        "ORDER BY TABNAME, COLNO"
    )

    current_tab = None
    row = ibm_db.fetch_tuple(stmt)
    while row:
        tab, col, typ, length, scale, nulls = row[0].strip(), row[1].strip(), row[2].strip(), row[3], row[4], row[5]
        if tab != current_tab:
            current_tab = tab
            print(f"\n--- {tab} ---")
        precision_str = f"({length},{scale})" if scale > 0 else f"({length})" if typ in ("VARCHAR", "DECIMAL") else ""
        print(f"  {col}: {typ}{precision_str} | NULLABLE: {nulls}")
        row = ibm_db.fetch_tuple(stmt)

    ibm_db.close(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
