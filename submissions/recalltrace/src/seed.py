"""Create RecallTrace tables and insert the fictional inventory once."""

import sys
from pathlib import Path

from db import Db2Error, connect, run

PRODUCTS = (
    ("PWB-10000", "Aster 10K Power Bank"),
    ("PWB-20000", "Aster 20K Power Bank"),
)

INVENTORY = (
    ("PWB-10000", "PB2410A", "Sydney DC", 24),
    ("PWB-10000", "PB2410A", "Melbourne Store", 6),
    ("PWB-10000", "PB2410B", "Brisbane DC", 14),
    ("PWB-10000", "PB2411C", "Sydney DC", 9),
    ("PWB-20000", "PB2410A", "Brisbane DC", 11),
)

PRODUCT_INSERT = """
    MERGE INTO recalltrace_products AS target
    USING (VALUES (CAST(? AS VARCHAR(40)), CAST(? AS VARCHAR(120))))
        AS sample (product_code, product_name)
    ON target.product_code = sample.product_code
    WHEN NOT MATCHED THEN INSERT (product_code, product_name)
        VALUES (sample.product_code, sample.product_name)
"""

INVENTORY_INSERT = """
    MERGE INTO recalltrace_inventory AS target
    USING (VALUES (CAST(? AS VARCHAR(40)), CAST(? AS VARCHAR(40)),
                   CAST(? AS VARCHAR(80)), CAST(? AS INTEGER)))
        AS sample (product_code, lot_code, site, quantity)
    ON target.product_code = sample.product_code
        AND target.lot_code = sample.lot_code AND target.site = sample.site
    WHEN NOT MATCHED THEN INSERT (product_code, lot_code, site, quantity)
        VALUES (sample.product_code, sample.lot_code, sample.site, sample.quantity)
"""


def seed():
    ddl = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with connect(transactional=True) as (driver, connection):
        for command in ddl.split(";"):
            if not command.strip():
                continue
            try:
                run("Could not create the RecallTrace tables", driver.exec_immediate, connection, command)
            except Db2Error as error:
                if error.state != "42710":  # The named table already exists.
                    raise

        for query, rows in ((PRODUCT_INSERT, PRODUCTS), (INVENTORY_INSERT, INVENTORY)):
            statement = run("Could not prepare the sample insert", driver.prepare, connection, query)
            for row in rows:
                run("Could not seed the sample inventory", driver.execute, statement, row)


if __name__ == "__main__":
    try:
        seed()
    except Db2Error as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    print("RecallTrace tables and sample inventory are ready.")
